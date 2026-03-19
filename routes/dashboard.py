from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from database.models import Subject, Assignment, Week, UserQuizAttempt, StudyAnalytics, Note, StudySchedule, Quiz, db
from datetime import date, datetime, timedelta
import json

dashboard_bp = Blueprint('dashboard', __name__)

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_student:
            flash('Student access required. Admins use Admin Panel.', 'error')
            return redirect(url_for('admin.index'))
        return f(*args, **kwargs)
    return decorated

@dashboard_bp.route('/dashboard')
@login_required
@student_required
def index():
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    today = date.today()

    # Upcoming deadlines
    upcoming_deadlines = (
        Assignment.query.join(Subject)
        .filter(Subject.user_id == current_user.id,
                Assignment.due_date >= today,
                Assignment.due_date <= today + timedelta(days=14),
                Assignment.is_completed == False)
        .order_by(Assignment.due_date).limit(8).all()
    )

    # Subject data with current week
    subject_data = []
    total_completed = 0
    total_topics = 0
    for s in subjects:
        plan = s.latest_plan
        current_week = None
        if plan and s.start_date:
            weeks_elapsed = (today - s.start_date).days // 7 + 1
            current_week = Week.query.filter_by(
                study_plan_id=plan.id,
                week_number=min(max(weeks_elapsed, 1), s.semester_length)
            ).first()
        if plan:
            for w in plan.weeks:
                t = json.loads(w.topics or '[]')
                total_topics += len(t)
                total_completed += min(len(t), w.completion_pct * len(t) // 100) if len(t) else 0
        subject_data.append({'subject': s, 'plan': plan, 'current_week': current_week, 'completion': s.completion_pct})

    # Quiz stats
    all_attempts = UserQuizAttempt.query.filter_by(user_id=current_user.id).all()
    avg_quiz_score = round(sum(a.accuracy_pct for a in all_attempts) / len(all_attempts), 1) if all_attempts else 0

    # Analytics
    analytics = StudyAnalytics.query.filter_by(user_id=current_user.id).all()
    weak_topics_all = []
    for a in analytics:
        weak_topics_all.extend(a.get_weak_topics())

    # Today's schedule
    todays_schedule = StudySchedule.query.filter_by(
        user_id=current_user.id, date=today, is_done=False
    ).order_by(StudySchedule.priority.desc()).limit(5).all()

    # Recent notes
    recent_notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.updated_at.desc()).limit(3).all()

    # Pending tasks count
    pending_tasks = Assignment.query.join(Subject).filter(
        Subject.user_id == current_user.id,
        Assignment.is_completed == False,
        Assignment.due_date != None
    ).count()

    # Admin-created quizzes assigned to this student (similar logic as quiz_home)
    subject_ids = [s.id for s in subjects]
    assigned_quizzes = []
    if subject_ids:
        assigned_quizzes = (Quiz.query
            .filter(Quiz.subject_id.in_(subject_ids))
            .filter(Quiz.is_active.is_(True))
            .filter(Quiz.cache_key.is_(None))
            .order_by(Quiz.created_at.desc())
            .limit(5)
            .all())

    return render_template('dashboard/home.html',
        subject_data=subject_data,
        upcoming_deadlines=upcoming_deadlines,
        today=today, now=datetime.now(),
        avg_quiz_score=avg_quiz_score,
        total_subjects=len(subjects),
        total_completed=total_completed,
        pending_tasks=pending_tasks,
        weak_topics=list(set(weak_topics_all))[:5],
        todays_schedule=todays_schedule,
        recent_notes=recent_notes,
        total_quizzes=len(all_attempts),
        assigned_quizzes=assigned_quizzes,
    )

@dashboard_bp.route('/api/progress/toggle', methods=['POST'])
@login_required
@student_required
def toggle_progress():
    data = request.get_json()
    if data.get('type') == 'assignment':
        from database.models import Assignment
        a = Assignment.query.get(data.get('id'))
        if a and a.subject.user_id == current_user.id:
            a.is_completed = not a.is_completed
            db.session.commit()
            return jsonify({'success': True, 'completed': a.is_completed})
    return jsonify({'success': False})

@dashboard_bp.route('/api/dashboard/chart-data')
@login_required
@student_required
def chart_data():
    """Feed Chart.js on the dashboard."""
    from database.models import UserQuizAttempt, Subject
    from datetime import timedelta
    today = date.today()
    # Score trend – last 30 days
    cutoff = datetime.utcnow() - timedelta(days=30)
    attempts = (UserQuizAttempt.query
                .filter(UserQuizAttempt.user_id == current_user.id,
                        UserQuizAttempt.completed_at >= cutoff)
                .order_by(UserQuizAttempt.completed_at).all())
    trend_labels = [a.completed_at.strftime('%b %d') for a in attempts]
    trend_scores = [round(a.accuracy_pct, 1) for a in attempts]

    # Subject completion
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    subj_labels = [s.name for s in subjects]
    subj_pcts   = [s.completion_pct for s in subjects]

    # Topic performance
    from database.models import TopicPerformance
    topics = (TopicPerformance.query.filter_by(user_id=current_user.id)
              .order_by(TopicPerformance.accuracy_pct).limit(8).all())
    topic_labels = [t.topic for t in topics]
    topic_scores = [round(t.accuracy_pct, 1) for t in topics]

    return jsonify({
        'trend': {'labels': trend_labels, 'scores': trend_scores},
        'subjects': {'labels': subj_labels, 'pcts': subj_pcts},
        'topics': {'labels': topic_labels, 'scores': topic_scores},
    })
