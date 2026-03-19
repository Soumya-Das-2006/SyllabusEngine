from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from database.models import Subject, Assignment, Exam, Quiz
import json

# This is the authoritative calendar blueprint.
# app.py imports: from routes.calendar import calendar_bp
# routes/assistant.py must NOT define its own calendar_bp — it imports this one.
calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/subjects/<int:subject_id>/calendar')
@login_required
def view(subject_id):
    subject     = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    assignments = Assignment.query.filter_by(subject_id=subject_id).all()
    exams       = []
    plan        = subject.latest_plan

    if plan:
        exams = Exam.query.filter_by(study_plan_id=plan.id).all()

    # Admin-created quizzes for this subject (shown as red events like exams)
    quizzes = Quiz.query.filter_by(subject_id=subject_id, is_active=True).all()

    events = []

    for a in assignments:
        if a.due_date:
            events.append({
                'title': f'📋 {a.title}',
                'start': a.due_date.isoformat(),
                'color': '#f97316',
                'type':  'assignment',
            })

    for e in exams:
        if e.exam_date:
            events.append({
                'title': f'📝 {e.name}',
                'start': e.exam_date.isoformat(),
                'color': '#ef4444',
                'type':  'exam',
            })

    for q in quizzes:
        # Use explicit start date if set, otherwise fall back to created_at
        dt = (q.starts_at or q.created_at)
        if dt:
            events.append({
                'title': f'🧪 {q.title}',
                'start': dt.date().isoformat(),
                'color': '#ef4444',
                'type':  'quiz',
            })

    return render_template('dashboard/calendar.html',
        subject=subject,
        events=json.dumps(events),
    )

@calendar_bp.route('/calendar')
@login_required
def calendar_view():
    """Top-level calendar — redirect to first subject or show picker."""
    first = Subject.query.filter_by(user_id=current_user.id, is_active=True).first()
    if first:
        return redirect(url_for('calendar.view', subject_id=first.id))
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('dashboard/calendar.html', subjects=subjects, events=[])

