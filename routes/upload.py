import os
import uuid
import threading
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from database.models import Subject, Syllabus, StudyPlan, db
from werkzeug.utils import secure_filename

upload_bp = Blueprint('upload', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

@upload_bp.route('/upload')
@upload_bp.route('/upload/<int:subject_id>')
@login_required
def upload_page(subject_id=None):
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    selected = None
    if subject_id:
        selected = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first()
    return render_template('dashboard/upload.html', subjects=subjects, selected=selected)

@upload_bp.route('/upload/process', methods=['POST'])
@login_required
def process_upload():
    """Validate and queue a syllabus PDF for background processing."""
    subject_id = request.form.get('subject_id')
    try:
        subject_id_int = int(subject_id)
    except (TypeError, ValueError):
        flash('Please select a subject.', 'error')
        return redirect(url_for('upload.upload_page'))

    subject = Subject.query.filter_by(id=subject_id_int, user_id=current_user.id).first_or_404()

    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('upload.upload_page', subject_id=subject_id_int))

    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        flash('Please upload a valid PDF file.', 'error')
        return redirect(url_for('upload.upload_page', subject_id=subject_id_int))

    # Update start_date if provided
    start_date_str = request.form.get('start_date', '')
    semester_length_raw = request.form.get('semester_length', subject.semester_length)
    if start_date_str:
        from datetime import datetime
        try:
            subject.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            subject.semester_length = max(1, min(int(semester_length_raw), 52))
            db.session.commit()
        except ValueError:
            flash('Invalid date or semester length input. Kept previous subject settings.', 'warning')

    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    syllabus = Syllabus(
        subject_id=subject.id,
        file_path=file_path,
        original_filename=file.filename,
        processing_status='processing'
    )
    db.session.add(syllabus)
    db.session.commit()

    # Process in background thread
    app = current_app._get_current_object()
    thread = threading.Thread(target=process_syllabus_background, args=(app, syllabus.id))
    thread.daemon = True
    thread.start()

    return redirect(url_for('upload.processing_status', syllabus_id=syllabus.id))

@upload_bp.route('/upload/status/<int:syllabus_id>')
@login_required
def processing_status(syllabus_id):
    syllabus = Syllabus.query.get_or_404(syllabus_id)
    subject = Subject.query.filter_by(id=syllabus.subject_id, user_id=current_user.id).first_or_404()
    return render_template('dashboard/processing.html', syllabus=syllabus, subject=subject)

@upload_bp.route('/api/upload/status/<int:syllabus_id>')
@login_required
def api_status(syllabus_id):
    syllabus = Syllabus.query.get_or_404(syllabus_id)
    subject = Subject.query.filter_by(id=syllabus.subject_id, user_id=current_user.id).first_or_404()
    data = {
        'status': syllabus.processing_status,
        'ocr_used': syllabus.ocr_used,
        'confidence': syllabus.confidence_score
    }
    if syllabus.processing_status == 'awaiting_confirmation':
        data['redirect'] = url_for('upload.confirmation', syllabus_id=syllabus_id)
    elif syllabus.processing_status == 'failed':
        data['error'] = syllabus.error_message
    return jsonify(data)

@upload_bp.route('/upload/confirmation/<int:syllabus_id>')
@login_required
def confirmation(syllabus_id):
    syllabus = Syllabus.query.get_or_404(syllabus_id)
    subject = Subject.query.filter_by(id=syllabus.subject_id, user_id=current_user.id).first_or_404()

    import json
    if syllabus.processing_status != 'awaiting_confirmation':
        flash('Syllabus is not ready for confirmation. Please wait or check status.', 'error')
        return redirect(url_for('dashboard.home'))

    def safe_json_parse(data):
        try:
            return json.loads(data) if data else {}
        except:
            return {}

    raw = safe_json_parse(syllabus.raw_ai_output)
    assignments = raw.get('assignments', [])
    exams = raw.get('exams', [])
    weekly_plan = raw.get('weekly_plan', [])
    course_info = raw.get('course_information', {})

    return render_template('dashboard/confirmation.html',
        syllabus=syllabus, subject=subject,
        assignments=assignments, exams=exams,
        weekly_plan=weekly_plan, course_info=course_info,
        raw_json=syllabus.raw_ai_output
    )

@upload_bp.route('/upload/confirm/<int:syllabus_id>', methods=['POST'])
@login_required
def confirm_plan(syllabus_id):
    """Persist a confirmed study plan after validating payload structure."""
    syllabus = Syllabus.query.get_or_404(syllabus_id)
    subject = Subject.query.filter_by(id=syllabus.subject_id, user_id=current_user.id).first_or_404()

    import json
    from datetime import datetime, date

    confirmed_data = request.get_json(silent=True)

    def safe_json_parse(data):
        try:
            return json.loads(data) if data else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    if not confirmed_data:
        if syllabus.processing_status != 'awaiting_confirmation':
            return jsonify({'error': 'Syllabus not confirmed yet'}), 400
        confirmed_data = safe_json_parse(syllabus.raw_ai_output)

    if not isinstance(confirmed_data, dict):
        return jsonify({'error': 'Invalid confirmation payload.'}), 400

    # Build study plan from confirmed data
    plan = StudyPlan(
        subject_id=subject.id,
        syllabus_id=syllabus.id,
        course_title=confirmed_data.get('course_information', {}).get('course_title', subject.name),
        instructor=confirmed_data.get('course_information', {}).get('instructor', ''),
        json_raw=json.dumps(confirmed_data),
        confirmed_at=datetime.utcnow()
    )
    db.session.add(plan)
    db.session.flush()

    from database.models import Week, Assignment, Exam
    weeks_data = confirmed_data.get('weekly_plan', [])
    for w in weeks_data:
        week_num = w.get('week_number', 1)
        date_start = None
        if subject.start_date:
            from datetime import timedelta
            date_start = subject.start_date + timedelta(weeks=week_num - 1)

        week = Week(
            study_plan_id=plan.id,
            week_number=week_num,
            date_start=date_start,
            date_end=(date_start + timedelta(days=6)) if date_start else None,
            topics=json.dumps(w.get('topics', [])),
            key_concepts=json.dumps(w.get('key_concepts', [])),
            difficulty=w.get('difficulty', 'medium'),
            recommended_hours=w.get('study_hours', 6),
            readings=json.dumps(w.get('readings', [])),
            revision_tasks=json.dumps(w.get('revision_tasks', [])),
            study_advice=w.get('study_advice', ''),
            is_exam_week=w.get('is_exam_week', False)
        )
        db.session.add(week)
        db.session.flush()

        for a in w.get('assignments', []):
            due = None
            if a.get('due_date'):
                try:
                    due = datetime.strptime(a['due_date'], '%Y-%m-%d').date()
                except Exception:
                    pass
            assignment = Assignment(
                week_id=week.id,
                subject_id=subject.id,
                title=a.get('title', 'Assignment'),
                due_date=due,
                estimated_hours=a.get('estimated_hours', 2),
                preparation_steps=json.dumps(a.get('preparation_steps', [])),
                confidence=a.get('confidence', 'high')
            )
            db.session.add(assignment)

    for e in confirmed_data.get('exams', []):
        exam_date = None
        if e.get('exam_date'):
            try:
                exam_date = datetime.strptime(e['exam_date'], '%Y-%m-%d').date()
            except Exception:
                pass
        exam = Exam(
            study_plan_id=plan.id,
            name=e.get('name', 'Exam'),
            exam_date=exam_date,
            coverage_weeks=json.dumps(e.get('coverage_weeks', [])),
            preparation_plan=e.get('preparation_plan', ''),
            confidence=e.get('confidence', 'high')
        )
        db.session.add(exam)

    syllabus.processing_status = 'completed'
    db.session.commit()

    return jsonify({'success': True, 'redirect': url_for('study_plan.week_grid', subject_id=subject.id)})


def process_syllabus_background(app, syllabus_id):
    """Background processing: extract text, call AI, store raw output."""
    with app.app_context():
        syllabus = Syllabus.query.get(syllabus_id)
        if not syllabus:
            return
        try:
            from pdf.extractor import extract_text
            from ai.groq_processor import analyze_syllabus
            from database.models import Subject

            subject = Subject.query.get(syllabus.subject_id)

            # Step 1: Extract text
            text, ocr_used = extract_text(syllabus.file_path)
            syllabus.extracted_text = text
            syllabus.ocr_used = ocr_used
            db.session.commit()

            if not text or len(text.strip()) < 100:
                syllabus.processing_status = 'failed'
                syllabus.error_message = 'Could not extract text from PDF. The file may be password-protected or corrupted.'
                db.session.commit()
                return

            # Step 2: AI analysis
            result = analyze_syllabus(text, subject.semester_length, subject.start_date)
            syllabus.raw_ai_output = result
            syllabus.confidence_score = 0.85
            syllabus.processing_status = 'awaiting_confirmation'
            db.session.commit()

        except Exception:
            syllabus.processing_status = 'failed'
            syllabus.error_message = 'Syllabus processing failed unexpectedly. Please upload again or contact support.'
            db.session.commit()
            app.logger.exception('Syllabus processing failed for syllabus_id=%s', syllabus_id)
