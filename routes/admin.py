from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response, current_app
from flask_login import login_required, current_user
from database.models import (User, Subject, Syllabus, StudyPlan, Quiz, Question,
                              UserQuizAttempt, ChatRoom, ChatMessage, Note,
                              ActivityLog, Notification, Certificate, News,
                              Testimonial, ContactMessage, db)
from functools import wraps
from datetime import datetime, date, timedelta
import threading, json, csv, io, os, secrets
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.home'))
        return f(*args, **kwargs)
    return decorated

def _log(action, detail=''):
    try:
        log = ActivityLog(user_id=current_user.id, action=action,
                          detail=str(detail)[:500], ip=request.remote_addr)
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _save_image(file, subfolder):
    if not file or file.filename == '':
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
        return None
    filename = secure_filename(file.filename)
    name = f"{secrets.token_hex(8)}.{ext}"
    rel_dir = os.path.join('uploads', subfolder)
    abs_dir = os.path.join(current_app.root_path, 'static', rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    file.save(os.path.join(abs_dir, name))
    return os.path.join(rel_dir, name).replace('\\', '/')

# ── Dashboard ─────────────────────────────────────────────────────────────────
@admin_bp.route('/')
@login_required
@admin_required
def index():
    from sqlalchemy import func
    today = date.today()
    total_users    = User.query.filter_by(role='student').count()
    total_syllabi  = Syllabus.query.count()
    failed_syllabi = Syllabus.query.filter_by(processing_status='failed').count()
    total_quizzes  = Quiz.query.count()
    total_attempts = UserQuizAttempt.query.count()
    active_today   = User.query.filter(
        User.last_seen >= datetime.combine(today, datetime.min.time())
    ).filter_by(role='student').count()
    recent_users   = User.query.filter_by(role='student').order_by(User.created_at.desc()).limit(8).all()
    recent_logs    = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(15).all()

    # Top performers
    top_students = (db.session.query(User,
                    func.avg(UserQuizAttempt.accuracy_pct).label('avg_score'),
                    func.count(UserQuizAttempt.id).label('quiz_count'))
        .join(UserQuizAttempt, User.id == UserQuizAttempt.user_id)
        .filter(User.role == 'student', UserQuizAttempt.status == 'completed')
        .group_by(User.id)
        .order_by(func.avg(UserQuizAttempt.accuracy_pct).desc())
        .limit(5).all())

    # Signups last 7 days
    signups_chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = User.query.filter(
            User.created_at >= datetime.combine(d, datetime.min.time()),
            User.created_at <  datetime.combine(d + timedelta(1), datetime.min.time())
        ).count()
        signups_chart.append({'date': d.strftime('%a %d'), 'count': count})

    # Quiz attempts last 7 days
    attempts_chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = UserQuizAttempt.query.filter(
            UserQuizAttempt.started_at >= datetime.combine(d, datetime.min.time()),
            UserQuizAttempt.started_at <  datetime.combine(d + timedelta(1), datetime.min.time())
        ).count()
        attempts_chart.append({'date': d.strftime('%a %d'), 'count': count})

    return render_template('admin/dashboard.html',
        total_users=total_users, total_syllabi=total_syllabi,
        failed_syllabi=failed_syllabi, total_quizzes=total_quizzes,
        total_attempts=total_attempts, active_today=active_today,
        recent_users=recent_users, recent_logs=recent_logs,
        top_students=top_students,
        signups_chart=json.dumps(signups_chart),
        attempts_chart=json.dumps(attempts_chart))

# ── Users ─────────────────────────────────────────────────────────────────────
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    q      = request.args.get('q', '').strip()
    status = request.args.get('status', 'all')
    query  = User.query.filter_by(role='student')
    if q:
        query = query.filter(User.name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%') |
                             User.college.ilike(f'%{q}%') | User.course.ilike(f'%{q}%'))
    if status == 'active':   query = query.filter_by(is_active=True)
    elif status == 'blocked': query = query.filter_by(is_active=False)
    users = query.order_by(User.created_at.desc()).all()
    failed_syllabi = Syllabus.query.filter_by(processing_status='failed').count()
    return render_template('admin/users.html', users=users, q=q, status=status, failed_syllabi=failed_syllabi)

@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    user     = User.query.get_or_404(user_id)
    attempts = UserQuizAttempt.query.filter_by(user_id=user_id).order_by(UserQuizAttempt.completed_at.desc()).limit(20).all()
    logs     = ActivityLog.query.filter_by(user_id=user_id).order_by(ActivityLog.created_at.desc()).limit(30).all()
    subjects = Subject.query.filter_by(user_id=user_id, is_active=True).all()
    certs    = Certificate.query.filter_by(user_id=user_id).all()
    avg_score = round(sum(a.accuracy_pct for a in attempts) / len(attempts), 1) if attempts else 0
    return render_template('admin/user_detail.html', user=user, attempts=attempts,
        logs=logs, subjects=subjects, certs=certs, avg_score=avg_score)

@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot suspend yourself'}), 400
    user.is_active = not user.is_active
    db.session.commit()
    _log('toggle_user', f'{user.email} → {"active" if user.is_active else "blocked"}')
    return jsonify({'ok': True, 'active': user.is_active})

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Soft-delete a user by deactivating access instead of removing records."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('admin.users'))
    email = user.email
    user.is_active = False
    user.role = 'archived'
    db.session.commit()
    _log('delete_user', email)
    flash(f'User {email} archived.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/export')
@login_required
@admin_required
def export_users():
    users = User.query.filter_by(role='student').all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Name','Email','College','Course','Year','Active','Joined'])
    for u in users:
        writer.writerow([u.id, u.name, u.email, u.college or '', u.course or '',
                         u.year or '', 'Yes' if u.is_active else 'No',
                         u.created_at.strftime('%Y-%m-%d')])
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv'
    resp.headers['Content-Disposition'] = 'attachment; filename=students.csv'
    return resp

# ── Quiz Management ────────────────────────────────────────────────────────────
@admin_bp.route('/quizzes')
@login_required
@admin_required
def quiz_list():
    quizzes = Quiz.query.order_by(Quiz.created_at.desc()).all()
    subjects = Subject.query.filter_by(is_active=True).all()
    return render_template('admin/quiz_list.html', quizzes=quizzes, subjects=subjects)

@admin_bp.route('/quizzes/create', methods=['GET', 'POST'])
@login_required
@admin_required
def quiz_create():
    subjects = Subject.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        from database.models import Quiz, Question
        title      = request.form.get('title', '').strip()
        subject_id = request.form.get('subject_id', type=int)
        duration   = request.form.get('duration', 30, type=int)
        pass_marks = request.form.get('pass_marks', 50, type=int)
        max_viol   = request.form.get('max_violations', 3, type=int)
        fullscreen = bool(request.form.get('fullscreen_req'))
        webcam     = bool(request.form.get('webcam_req'))
        shuffle    = bool(request.form.get('shuffle_q'))
        ai_gen     = request.form.get('ai_generate') == 'on'

        quiz = Quiz(user_id=current_user.id, subject_id=subject_id,
            title=title, duration_minutes=duration, pass_marks=pass_marks,
            max_violations=max_viol, total_marks=0,
            fullscreen_req=fullscreen, webcam_req=webcam, shuffle_q=shuffle,
            is_active=True)
        db.session.add(quiz); db.session.flush()
        q_count = 0

        if ai_gen:
            import os, re
            from groq import Groq
            topic = request.form.get('ai_topic', title)
            num_q = request.form.get('ai_num_q', 10, type=int)
            diff  = request.form.get('ai_difficulty', 'medium')
            subj  = Subject.query.get(subject_id)
            prompt = f"""Generate exactly {num_q} MCQ about "{topic}" (Subject: {subj.name if subj else ''}).
Difficulty: {diff}. Return ONLY JSON (no markdown):
{{"questions":[{{"question":"?","options":{{"A":"","B":"","C":"","D":""}},"correct_answer":"A","explanation":"","difficulty":"{diff}","topic_tag":""}}]}}"""
            try:
                client = Groq(api_key=os.environ.get('GROQ_API_KEY', ''))
                resp   = client.chat.completions.create(model='llama-3.3-70b-versatile',
                    messages=[{'role':'user','content':prompt}], max_tokens=3000, temperature=0.4)
                raw  = resp.choices[0].message.content.strip()
                raw  = re.sub(r'^```[a-z]*\n?', '', raw)
                raw  = re.sub(r'\n?```$', '', raw)
                data = json.loads(raw)
                for i, q in enumerate(data.get('questions', [])):
                    opts = q.get('options', {})
                    if all(k in opts for k in ('A','B','C','D')):
                        db.session.add(Question(quiz_id=quiz.id,
                            question_text=q.get('question',''), option_a=opts['A'],
                            option_b=opts['B'], option_c=opts['C'], option_d=opts['D'],
                            correct_answer=q.get('correct_answer','A').upper(),
                            explanation=q.get('explanation',''),
                            difficulty=q.get('difficulty', diff),
                            topic_tag=q.get('topic_tag', topic), order_index=i))
                        q_count += 1
            except Exception:
                current_app.logger.exception('AI question generation failed for quiz_id=%s', quiz.id)
                flash('AI question generation failed. Add questions manually.', 'warning')
        else:
            texts = request.form.getlist('q_text[]')
            a_opts = request.form.getlist('q_a[]')
            b_opts = request.form.getlist('q_b[]')
            c_opts = request.form.getlist('q_c[]')
            d_opts = request.form.getlist('q_d[]')
            corrects = request.form.getlist('q_correct[]')
            marks_list = request.form.getlist('q_marks[]')
            for i, text in enumerate(texts):
                if not text.strip(): continue
                db.session.add(Question(quiz_id=quiz.id, question_text=text,
                    option_a=a_opts[i], option_b=b_opts[i],
                    option_c=c_opts[i], option_d=d_opts[i],
                    correct_answer=corrects[i].upper(),
                    order_index=i))
                q_count += 1

        quiz.total_marks = q_count
        db.session.commit()

        # Notify all students in-app
        students = User.query.filter_by(role='student', is_active=True).all()
        for s in students:
            db.session.add(Notification(user_id=s.id,
                title=f'📝 New Quiz: {title}',
                message='A new quiz has been added. Take it now!',
                notif_type='quiz', link=url_for('quiz.quiz_home')))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Send email alerts (best-effort, does not block quiz creation)
        try:
            from integrations.email import send_quiz_created_email
            for s in students:
                send_quiz_created_email(s, quiz)
        except Exception as e:
            current_app.logger.warning('Failed to send quiz created emails: %s', e)
        _log('create_quiz', title)
        flash(f'Quiz "{title}" created with {q_count} questions!', 'success')
        return redirect(url_for('admin.quiz_list'))
    return render_template('admin/quiz_create.html', subjects=subjects)

@admin_bp.route('/quizzes/<int:qid>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_quiz(qid):
    q = Quiz.query.get_or_404(qid)
    q.is_active = not q.is_active; db.session.commit()
    return jsonify({'ok': True, 'active': q.is_active})

@admin_bp.route('/quizzes/<int:qid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_quiz(qid):
    """Soft-delete a quiz by deactivating it."""
    q = Quiz.query.get_or_404(qid)
    title = q.title
    q.is_active = False
    db.session.commit()
    _log('delete_quiz', title)
    flash(f'Quiz "{title}" archived.', 'success')
    return redirect(url_for('admin.quiz_list'))

@admin_bp.route('/quizzes/<int:qid>/attempts')
@login_required
@admin_required
def quiz_attempts(qid):
    quiz     = Quiz.query.get_or_404(qid)
    attempts = UserQuizAttempt.query.filter_by(quiz_id=qid).order_by(UserQuizAttempt.started_at.desc()).all()
    return render_template('admin/quiz_attempts.html', quiz=quiz, attempts=attempts)

# ── Global Search ─────────────────────────────────────────────────────────────
@admin_bp.route('/search')
@login_required
@admin_required
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return render_template('admin/search.html', q='', results=None)
    users    = User.query.filter_by(role='student').filter(
        User.name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%') |
        User.college.ilike(f'%{q}%')).limit(10).all()
    quizzes  = Quiz.query.filter(Quiz.title.ilike(f'%{q}%')).limit(10).all()
    notes    = Note.query.filter(Note.title.ilike(f'%{q}%') | Note.content.ilike(f'%{q}%')).limit(10).all()
    messages = ChatMessage.query.filter(ChatMessage.message.ilike(f'%{q}%')).limit(10).all()
    subjects = Subject.query.filter(Subject.name.ilike(f'%{q}%')).limit(10).all()
    return render_template('admin/search.html', q=q, users=users, quizzes=quizzes,
        notes=notes, messages=messages, subjects=subjects)

# ── Notifications broadcast ───────────────────────────────────────────────────
@admin_bp.route('/broadcast', methods=['POST'])
@login_required
@admin_required
def broadcast():
    title   = request.form.get('title', '').strip()
    message = request.form.get('message', '').strip()
    link    = request.form.get('link', '').strip() or None
    if not title:
        flash('Title is required.', 'warning')
        return redirect(url_for('admin.index'))
    students = User.query.filter_by(role='student', is_active=True).all()
    for s in students:
        db.session.add(Notification(user_id=s.id, title=title,
            message=message, notif_type='broadcast', link=link))
    try:
        db.session.commit()
        flash(f'Broadcast sent to {len(students)} students!', 'success')
    except Exception:
        db.session.rollback()
        flash('Error sending broadcast.', 'error')
    _log('broadcast', title)
    return redirect(url_for('admin.index'))

# ── Activity logs ─────────────────────────────────────────────────────────────
@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    page   = request.args.get('page', 1, type=int)
    action = request.args.get('action', '').strip()
    query  = ActivityLog.query.order_by(ActivityLog.created_at.desc())
    if action:
        query = query.filter(ActivityLog.action.ilike(f'%{action}%'))
    logs = query.paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/logs.html', logs=logs, action=action)

# ── Chat monitor ──────────────────────────────────────────────────────────────
@admin_bp.route('/chat')
@login_required
@admin_required
def chat_monitor():
    rooms    = ChatRoom.query.filter_by(is_deleted=False).order_by(ChatRoom.created_at.desc()).all()
    room_id  = request.args.get('room_id', type=int)
    messages = []
    current_room = None
    if room_id:
        current_room = ChatRoom.query.filter_by(id=room_id, is_deleted=False).first()
        messages = (ChatMessage.query.filter_by(room_id=room_id, is_deleted=False)
                    .order_by(ChatMessage.created_at.asc()).all())
    return render_template('admin/chat_monitor.html',
        rooms=rooms, messages=messages, current_room=current_room)

@admin_bp.route('/chat/delete-msg/<int:msg_id>', methods=['POST'])
@login_required
@admin_required
def delete_message(msg_id):
    """Soft-delete a chat message by redacting content."""
    msg = ChatMessage.query.filter_by(id=msg_id, is_deleted=False).first_or_404()
    msg.message = '[Archived by admin]'
    msg.is_deleted = True
    msg.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})

# ── Syllabi management (existing) ──────────────────────────────────────────────
@admin_bp.route('/syllabi')
@login_required
@admin_required
def syllabi():
    syllabi = Syllabus.query.order_by(Syllabus.uploaded_at.desc()).limit(50).all()
    failed_syllabi = Syllabus.query.filter_by(processing_status='failed').count()
    return render_template('admin/syllabi.html', syllabi=syllabi, failed_syllabi=failed_syllabi)

@admin_bp.route('/failed-parses')
@login_required
@admin_required
def failed_parses():
    failed = Syllabus.query.filter_by(processing_status='failed').order_by(Syllabus.uploaded_at.desc()).all()
    return render_template('admin/failed_parses.html', failed=failed)

@admin_bp.route('/syllabi/<int:syllabus_id>/reprocess', methods=['POST'])
@login_required
@admin_required
def reprocess(syllabus_id):
    from flask import current_app
    from routes.upload import process_syllabus_background
    syllabus = Syllabus.query.get_or_404(syllabus_id)
    syllabus.processing_status = 'processing'
    syllabus.error_message     = None
    db.session.commit()
    app = current_app._get_current_object()
    t   = threading.Thread(target=process_syllabus_background, args=(app, syllabus.id))
    t.daemon = True; t.start()
    flash(f'Reprocessing started for "{syllabus.original_filename}".', 'success')
    return redirect(url_for('admin.failed_parses'))


# ── News / Updates management ───────────────────────────────────────────────

@admin_bp.route('/news')
@login_required
@admin_required
def news_list():
    page = request.args.get('page', 1, type=int)
    pagination = News.query.filter_by(is_deleted=False).order_by(News.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/news_list.html', pagination=pagination, news_items=pagination.items)


@admin_bp.route('/news/add', methods=['GET', 'POST'])
@login_required
@admin_required
def news_add():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        summary = request.form.get('summary', '').strip()
        content = request.form.get('content', '').strip()
        image_file = request.files.get('image')

        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('admin.news_add'))

        image_url = _save_image(image_file, 'news') if image_file else None

        news = News(title=title, summary=summary or None, content=content, image_url=image_url)
        db.session.add(news)
        db.session.commit()

        # Create notifications for all active students
        students = User.query.filter_by(role='student', is_active=True).all()
        for s in students:
            db.session.add(Notification(
                user_id=s.id,
                title=f'New Update: {news.title}',
                message=(news.summary or (news.content[:140] + '...')),
                notif_type='broadcast',
                link=url_for('public.news_detail', news_id=news.id)
            ))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        _log('news_add', news.title)
        flash('News article created.', 'success')
        return redirect(url_for('admin.news_list'))

    return render_template('admin/add_news.html')


@admin_bp.route('/news/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def news_edit(news_id):
    news = News.query.filter_by(id=news_id, is_deleted=False).first_or_404()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        summary = request.form.get('summary', '').strip()
        content = request.form.get('content', '').strip()
        image_file = request.files.get('image')

        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('admin.news_edit', news_id=news.id))

        news.title = title
        news.summary = summary or None
        news.content = content
        if image_file and image_file.filename:
            image_url = _save_image(image_file, 'news')
            if image_url:
                news.image_url = image_url
        db.session.commit()
        _log('news_edit', news.title)
        flash('News article updated.', 'success')
        return redirect(url_for('admin.news_list'))

    return render_template('admin/edit_news.html', news=news)


@admin_bp.route('/news/delete/<int:news_id>', methods=['POST'])
@login_required
@admin_required
def news_delete(news_id):
    """Soft-delete a news item by archiving instead of removing the row."""
    news = News.query.filter_by(id=news_id, is_deleted=False).first_or_404()
    title = news.title
    if not news.title.startswith('[ARCHIVED] '):
        news.title = f'[ARCHIVED] {news.title}'
    news.summary = None
    news.content = '[Archived by admin]'
    news.image_url = None
    news.is_deleted = True
    news.deleted_at = datetime.utcnow()
    db.session.commit()
    _log('news_delete', title)
    flash('News article archived.', 'success')
    return redirect(url_for('admin.news_list'))


# ── Testimonials management ────────────────────────────────────────────────

@admin_bp.route('/testimonials')
@login_required
@admin_required
def testimonials_list():
    testimonials = Testimonial.query.filter_by(is_deleted=False).order_by(Testimonial.created_at.desc()).all()
    return render_template('admin/testimonials_list.html', testimonials=testimonials)


@admin_bp.route('/testimonials/add', methods=['GET', 'POST'])
@login_required
@admin_required
def testimonials_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        feedback = request.form.get('feedback', '').strip()
        photo_file = request.files.get('photo')

        if not name or not feedback:
            flash('Name and feedback are required.', 'error')
            return redirect(url_for('admin.testimonials_add'))

        photo_url = _save_image(photo_file, 'testimonials') if photo_file else None
        t = Testimonial(name=name, feedback=feedback, photo_url=photo_url)
        db.session.add(t)
        db.session.commit()
        _log('testimonial_add', name)
        flash('Testimonial added.', 'success')
        return redirect(url_for('admin.testimonials_list'))

    return render_template('admin/add_testimonial.html')


@admin_bp.route('/testimonials/delete/<int:testimonial_id>', methods=['POST'])
@login_required
@admin_required
def testimonials_delete(testimonial_id):
    """Soft-delete a testimonial by archiving visible content."""
    t = Testimonial.query.filter_by(id=testimonial_id, is_deleted=False).first_or_404()
    name = t.name
    if not t.name.startswith('[ARCHIVED] '):
        t.name = f'[ARCHIVED] {t.name}'
    t.feedback = '[Archived by admin]'
    t.photo_url = None
    t.is_deleted = True
    t.deleted_at = datetime.utcnow()
    db.session.commit()
    _log('testimonial_delete', name)
    flash('Testimonial archived.', 'success')
    return redirect(url_for('admin.testimonials_list'))


# ── Contact messages ───────────────────────────────────────────────────────

@admin_bp.route('/messages')
@login_required
@admin_required
def messages():
    msgs = ContactMessage.query.filter_by(is_deleted=False).order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=msgs)


@admin_bp.route('/messages/<int:message_id>/read', methods=['POST'])
@login_required
@admin_required
def messages_mark_read(message_id):
    m = ContactMessage.query.filter_by(id=message_id, is_deleted=False).first_or_404()
    m.is_read = True
    db.session.commit()
    _log('message_read', m.email)
    flash('Message marked as read.', 'success')
    return redirect(url_for('admin.messages'))
