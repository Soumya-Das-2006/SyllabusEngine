from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from database.models import AttendanceSession, AttendanceRecord, User, Subject
from functools import wraps
from datetime import date, datetime

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if not current_user.is_admin:
            return redirect(url_for('auth.login'))
        return f(*a, **kw)
    return d

# ── Student: my attendance ─────────────────────────────────────────────────
@attendance_bp.route('/me')
@login_required
def my_attendance():
    records = (AttendanceRecord.query.filter_by(user_id=current_user.id, is_deleted=False)
               .join(AttendanceSession)
               .filter(AttendanceSession.is_deleted.is_(False))
               .order_by(AttendanceSession.date.desc()).all())
    total   = len(records)
    present = sum(1 for r in records if r.status == 'present')
    late    = sum(1 for r in records if r.status == 'late')
    absent  = sum(1 for r in records if r.status == 'absent')
    pct     = round((present + late * 0.5) / total * 100, 1) if total else 0
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    subject_id = request.args.get('subject_id', type=int)
    if subject_id:
        records = [r for r in records if r.session.subject_id == subject_id]
    return render_template('attendance/my_attendance.html',
        records=records, total=total, present=present, late=late, absent=absent,
        pct=pct, subjects=subjects, subject_id=subject_id)

# ── Admin: manage attendance ───────────────────────────────────────────────
@attendance_bp.route('/admin')
@login_required
@admin_required
def admin_view():
    sessions  = AttendanceSession.query.filter_by(is_deleted=False).order_by(AttendanceSession.date.desc()).limit(30).all()
    subjects  = Subject.query.filter_by(is_active=True).all()
    students  = User.query.filter_by(role='student', is_active=True).order_by(User.name).all()
    return render_template('attendance/admin_attendance.html',
        sessions=sessions, subjects=subjects, students=students, today=date.today())

@attendance_bp.route('/admin/session/create', methods=['POST'])
@login_required
@admin_required
def create_session():
    """Create an attendance session and seed default records for active students."""
    subject_id = request.form.get('subject_id') or None
    if subject_id:
        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            flash('Invalid subject selected.', 'error')
            return redirect(url_for('attendance.admin_view'))
    title      = request.form.get('title', 'Class').strip()
    sess_date  = request.form.get('date') or str(date.today())
    try:
        parsed_date = date.fromisoformat(sess_date)
    except ValueError:
        flash('Invalid session date. Please use YYYY-MM-DD.', 'error')
        return redirect(url_for('attendance.admin_view'))

    if not title:
        flash('Session title is required.', 'error')
        return redirect(url_for('attendance.admin_view'))

    students   = User.query.filter_by(role='student', is_active=True).all()
    sess = AttendanceSession(
        subject_id=subject_id or None,
        title=title,
        date=parsed_date,
        created_by=current_user.id)
    db.session.add(sess)
    db.session.flush()
    # Create present records for everyone by default
    for s in students:
        db.session.add(AttendanceRecord(session_id=sess.id, user_id=s.id, status='present'))
    db.session.commit()
    flash(f'Session "{title}" created for {len(students)} students.', 'success')
    return redirect(url_for('attendance.session_detail', session_id=sess.id))

@attendance_bp.route('/admin/session/<int:session_id>')
@login_required
@admin_required
def session_detail(session_id):
    sess     = AttendanceSession.query.filter_by(id=session_id, is_deleted=False).first_or_404()
    records  = AttendanceRecord.query.filter_by(session_id=session_id, is_deleted=False).all()
    students = User.query.filter_by(role='student', is_active=True).order_by(User.name).all()
    rec_map  = {r.user_id: r for r in records}
    return render_template('attendance/session_detail.html',
        sess=sess, students=students, rec_map=rec_map)

@attendance_bp.route('/admin/session/<int:session_id>/mark', methods=['POST'])
@login_required
@admin_required
def mark(session_id):
    """Update a student's attendance status for a given session."""
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get('user_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid user id.'}), 400

    status = (data.get('status') or '').strip().lower()
    if status not in {'present', 'absent', 'late'}:
        return jsonify({'error': 'Invalid status value.'}), 400

    AttendanceSession.query.filter_by(id=session_id, is_deleted=False).first_or_404()
    user = User.query.filter_by(id=user_id, role='student').first()
    if not user:
        return jsonify({'error': 'Student not found.'}), 404

    rec = AttendanceRecord.query.filter_by(session_id=session_id, user_id=user_id, is_deleted=False).first()
    if not rec:
        rec = AttendanceRecord(session_id=session_id, user_id=user_id)
        db.session.add(rec)
    rec.status   = status
    rec.note     = data.get('note', '')
    rec.marked_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})

@attendance_bp.route('/admin/student/<int:user_id>')
@login_required
@admin_required
def student_attendance(user_id):
    """Admin view of a single student's full attendance history."""
    user    = User.query.get_or_404(user_id)
    records = (AttendanceRecord.query.filter_by(user_id=user_id, is_deleted=False)
               .join(AttendanceSession)
               .filter(AttendanceSession.is_deleted.is_(False))
               .order_by(AttendanceSession.date.desc()).all())
    total   = len(records)
    present = sum(1 for r in records if r.status == 'present')
    late    = sum(1 for r in records if r.status == 'late')
    absent  = sum(1 for r in records if r.status == 'absent')
    pct     = round((present + late * 0.5) / total * 100, 1) if total else 0
    return render_template('attendance/student_report.html',
        user=user, records=records, total=total,
        present=present, late=late, absent=absent, pct=pct)

@attendance_bp.route('/admin/overview')
@login_required
@admin_required
def overview():
    """All students with their attendance percentage."""
    students = User.query.filter_by(role='student', is_active=True).order_by(User.name).all()
    data = []
    for s in students:
        records = AttendanceRecord.query.filter_by(user_id=s.id, is_deleted=False).all()
        total   = len(records)
        present = sum(1 for r in records if r.status == 'present')
        late    = sum(1 for r in records if r.status == 'late')
        pct     = round((present + late * 0.5) / total * 100, 1) if total else 0
        data.append({'user': s, 'total': total, 'present': present, 'late': late,
                     'absent': total - present - late, 'pct': pct})
    data.sort(key=lambda x: x['pct'])
    return render_template('attendance/overview.html', data=data)
