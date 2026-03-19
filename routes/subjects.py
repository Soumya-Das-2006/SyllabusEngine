from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from database.models import Subject, db
from datetime import datetime

subjects_bp = Blueprint('subjects', __name__)

@subjects_bp.route('/subjects')
@login_required
def index():
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).order_by(Subject.created_at.desc()).all()
    return render_template('dashboard/subjects.html', subjects=subjects)

@subjects_bp.route('/subjects/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#6366f1')
    semester_length = int(request.form.get('semester_length', 15))
    start_date_str = request.form.get('start_date', '')

    if not name:
        flash('Subject name is required.', 'error')
        return redirect(url_for('subjects.index'))

    start_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    subject = Subject(
        user_id=current_user.id,
        name=name,
        color=color,
        semester_length=semester_length,
        start_date=start_date
    )
    db.session.add(subject)
    db.session.commit()
    flash(f'Subject "{name}" added! Now upload your syllabus.', 'success')
    return redirect(url_for('upload.upload_page', subject_id=subject.id))

@subjects_bp.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete(subject_id):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    subject.is_active = False
    db.session.commit()
    flash(f'Subject "{subject.name}" archived.', 'success')
    return redirect(url_for('subjects.index'))

@subjects_bp.route('/subjects/<int:subject_id>')
@login_required
def view(subject_id):
    subject = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    return redirect(url_for('study_plan.week_grid', subject_id=subject_id))
