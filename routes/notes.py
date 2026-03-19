from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from database.models import Note, Subject
from datetime import datetime

notes_bp = Blueprint('notes', __name__, url_prefix='/notes')

@notes_bp.route('/')
@login_required
def index():
    q = request.args.get('q', '').strip()
    subject_id = request.args.get('subject_id', type=int)
    query = Note.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(Note.title.ilike(f'%{q}%') | Note.content.ilike(f'%{q}%'))
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    notes = query.order_by(Note.is_pinned.desc(), Note.updated_at.desc()).all()
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('notes/notes.html', notes=notes, subjects=subjects, q=q, subject_id=subject_id)

@notes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('Title is required.', 'warning')
            return redirect(url_for('notes.new'))
        note = Note(
            user_id=current_user.id,
            subject_id=request.form.get('subject_id') or None,
            title=title,
            content=request.form.get('content', ''),
            tags=request.form.get('tags', ''),
            color=request.form.get('color', '#ffffff'),
        )
        db.session.add(note)
        db.session.commit()
        flash('Note saved!', 'success')
        return redirect(url_for('notes.index'))
    return render_template('notes/note_edit.html', note=None, subjects=subjects)

@notes_bp.route('/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    if request.method == 'POST':
        note.title      = request.form.get('title', note.title).strip()
        note.content    = request.form.get('content', '')
        note.tags       = request.form.get('tags', '')
        note.color      = request.form.get('color', '#ffffff')
        note.subject_id = request.form.get('subject_id') or None
        note.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Note updated!', 'success')
        return redirect(url_for('notes.index'))
    return render_template('notes/note_edit.html', note=note, subjects=subjects)

@notes_bp.route('/<int:note_id>/delete', methods=['POST'])
@login_required
def delete(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return jsonify({'ok': True})

@notes_bp.route('/<int:note_id>/pin', methods=['POST'])
@login_required
def pin(note_id):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first_or_404()
    note.is_pinned = not note.is_pinned
    db.session.commit()
    return jsonify({'ok': True, 'pinned': note.is_pinned})
