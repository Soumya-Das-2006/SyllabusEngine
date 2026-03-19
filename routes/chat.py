from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from database.models import ChatRoom, ChatMessage, Subject
from datetime import datetime

chat_bp = Blueprint('chat', __name__, url_prefix='/groupchat')

@chat_bp.route('/')
@login_required
def index():
    rooms = ChatRoom.query.filter_by(is_public=True).order_by(ChatRoom.created_at).all()
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('chat/groupchat.html', rooms=rooms, subjects=subjects)

@chat_bp.route('/room/<int:room_id>')
@login_required
def room(room_id):
    chat_room = ChatRoom.query.get_or_404(room_id)
    messages = (ChatMessage.query.filter_by(room_id=room_id)
                .order_by(ChatMessage.created_at.desc()).limit(100).all())
    messages.reverse()
    rooms = ChatRoom.query.filter_by(is_public=True).order_by(ChatRoom.created_at).all()
    return render_template('chat/groupchat.html', rooms=rooms, current_room=chat_room, messages=messages)

@chat_bp.route('/room/create', methods=['POST'])
@login_required
def create_room():
    name = request.form.get('name', '').strip()
    subject_id = request.form.get('subject_id') or None
    if not name:
        return jsonify({'error': 'Name required'}), 400
    existing = ChatRoom.query.filter_by(name=name).first()
    if existing:
        return jsonify({'room_id': existing.id})
    room = ChatRoom(name=name, created_by=current_user.id, subject_id=subject_id, is_public=True)
    db.session.add(room)
    db.session.commit()
    return jsonify({'room_id': room.id})

@chat_bp.route('/room/<int:room_id>/messages')
@login_required
def get_messages(room_id):
    since_id = request.args.get('since', 0, type=int)
    messages = (ChatMessage.query.filter_by(room_id=room_id)
                .filter(ChatMessage.id > since_id)
                .order_by(ChatMessage.created_at).limit(50).all())
    return jsonify([m.to_dict() for m in messages])

@chat_bp.route('/room/<int:room_id>/send', methods=['POST'])
@login_required
def send_message(room_id):
    ChatRoom.query.get_or_404(room_id)
    data = request.get_json()
    text = (data.get('message') or '').strip()
    if not text or len(text) > 2000:
        return jsonify({'error': 'Invalid message'}), 400
    msg = ChatMessage(room_id=room_id, user_id=current_user.id, message=text)
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict())
