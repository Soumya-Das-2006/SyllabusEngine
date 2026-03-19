from flask import Blueprint, render_template, jsonify, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from database.models import Notification

notif_bp = Blueprint('notif', __name__, url_prefix='/notifications')

@notif_bp.route('/')
@login_required
def index():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications/index.html', notifs=notifs)

@notif_bp.route('/api')
@login_required
def api_list():
    notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False)\
        .order_by(Notification.created_at.desc()).limit(10).all()
    return jsonify([{'id': n.id, 'title': n.title, 'message': n.message or '',
        'type': n.notif_type, 'link': n.link or '',
        'time': n.created_at.strftime('%b %d %H:%M'),
        'is_read': n.is_read} for n in notifs])

@notif_bp.route('/mark-read/<int:nid>', methods=['POST'])
@login_required
def mark_read(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    n.is_read = True; db.session.commit()
    return jsonify({'ok': True})

@notif_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})


@notif_bp.route('/read/<int:nid>')
@login_required
def read_and_redirect(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    if not n.is_read:
        n.is_read = True
        db.session.commit()
    target = n.link or url_for('notif.index')
    return redirect(target)
