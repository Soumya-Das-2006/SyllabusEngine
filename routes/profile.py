import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from database.models import ActivityLog

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

def _save_avatar(file):
    if not file or file.filename == '':
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
        return None
    import secrets
    folder   = os.path.join('static', 'uploads', 'profiles')
    os.makedirs(folder, exist_ok=True)
    filename = f"{secrets.token_hex(12)}.{ext}"
    file.save(os.path.join(folder, filename))
    return f'uploads/profiles/{filename}'

@profile_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        current_user.name    = request.form.get('name', current_user.name).strip()
        current_user.college = request.form.get('college', '').strip()
        current_user.course  = request.form.get('course', '').strip()
        current_user.year    = request.form.get('year', '').strip()
        current_user.phone   = request.form.get('phone', '').strip()
        current_user.bio     = request.form.get('bio', '').strip()
        if 'avatar' in request.files:
            path = _save_avatar(request.files['avatar'])
            if path:
                current_user.avatar = path
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile.index'))
    return render_template('profile/index.html')

@profile_bp.route('/toggle-dark', methods=['POST'])
@login_required
def toggle_dark():
    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()
    return jsonify({'dark': current_user.dark_mode})
