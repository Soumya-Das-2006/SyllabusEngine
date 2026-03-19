from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from database.models import Subject, StudyPlan, Week, Assignment, Exam, Progress, db
from datetime import date

study_plan_bp = Blueprint('study_plan', __name__)


@study_plan_bp.route('/subjects/<int:subject_id>/plan')
@login_required
def week_grid(subject_id):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    plan = subject.latest_plan
    if not plan:
        return redirect(url_for('upload.upload_page', subject_id=subject_id))

    weeks = Week.query.filter_by(study_plan_id=plan.id).order_by(Week.week_number).all()
    today = date.today()

    current_week_num = 1
    if subject.start_date:
        elapsed = (today - subject.start_date).days // 7 + 1
        current_week_num = min(max(elapsed, 1), subject.semester_length)

    week_data = []
    for w in weeks:
        topics          = w.get_topics()
        num_assignments = Assignment.query.filter_by(week_id=w.id).count()
        intensity = 'light'
        if w.is_exam_week or num_assignments >= 2:
            intensity = 'heavy'
        elif num_assignments == 1 or len(topics) >= 3:
            intensity = 'medium'
        week_data.append({
            'week':            w,
            'intensity':       intensity,
            'is_current':      w.week_number == current_week_num,
            'num_assignments': num_assignments,
        })

    exams = Exam.query.filter_by(study_plan_id=plan.id).all()

    return render_template('dashboard/week_grid.html',
        subject=subject,
        plan=plan,
        week_data=week_data,
        exams=exams,
        current_week_num=current_week_num,
        today=today,             # ← needed by template for exam countdown
    )


@study_plan_bp.route('/subjects/<int:subject_id>/plan/week/<int:week_num>')
@login_required
def week_detail(subject_id, week_num):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    plan = subject.latest_plan
    if not plan:
        return redirect(url_for('upload.upload_page', subject_id=subject_id))

    week        = Week.query.filter_by(study_plan_id=plan.id, week_number=week_num).first_or_404()
    assignments = Assignment.query.filter_by(week_id=week.id).all()
    total_weeks = subject.semester_length
    today       = date.today()

    completed_keys = {
        p.item_key for p in Progress.query.filter_by(
            user_id=current_user.id,
            week_id=week.id,
            is_completed=True
        ).all()
    }

    return render_template('dashboard/week_detail.html',
        subject=subject,
        plan=plan,
        week=week,
        assignments=assignments,
        total_weeks=total_weeks,
        completed_keys=completed_keys,
        today=today,             # ← needed by template for due-date badges
        prev_week=week_num - 1 if week_num > 1 else None,
        next_week=week_num + 1 if week_num < total_weeks else None,
    )


@study_plan_bp.route('/api/progress/mark', methods=['POST'])
@login_required
def mark_progress():
    data      = request.get_json()
    week_id   = data.get('week_id')
    item_type = data.get('type')
    item_key  = data.get('key')
    completed = data.get('completed', True)

    week = Week.query.get(week_id)
    if not week:
        return jsonify({'success': False, 'error': 'Week not found'})

    subject = Subject.query.get(week.study_plan.subject_id)
    if not subject or subject.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'})

    existing = Progress.query.filter_by(
        user_id=current_user.id,
        week_id=week_id,
        item_key=item_key
    ).first()

    if existing:
        existing.is_completed = completed
    else:
        p = Progress(
            user_id=current_user.id,
            subject_id=subject.id,
            week_id=week_id,
            item_type=item_type,
            item_key=item_key,
            is_completed=completed
        )
        db.session.add(p)

    # Recalculate week completion percentage
    total_items = len(week.get_topics()) + len(week.get_revision_tasks())
    if total_items > 0:
        done = Progress.query.filter_by(
            user_id=current_user.id,
            week_id=week_id,
            is_completed=True
        ).count()
        week.completion_pct = min(100, int((done / total_items) * 100))

    db.session.commit()
    return jsonify({'success': True, 'completion_pct': week.completion_pct})


@study_plan_bp.route('/subjects/<int:subject_id>/progress')
@login_required
def progress(subject_id):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    plan    = subject.latest_plan
    weeks   = (
        Week.query.filter_by(study_plan_id=plan.id).order_by(Week.week_number).all()
        if plan else []
    )
    assignments           = Assignment.query.filter_by(subject_id=subject_id).all()
    total_assignments     = len(assignments)
    completed_assignments = sum(1 for a in assignments if a.is_completed)

    return render_template('dashboard/progress.html',
        subject=subject,
        plan=plan,
        weeks=weeks,
        total_assignments=total_assignments,
        completed_assignments=completed_assignments,
    )