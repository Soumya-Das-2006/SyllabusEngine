from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from extensions import db
from database.models import User, UserQuizAttempt, Subject
from sqlalchemy import func

leaderboard_bp = Blueprint('leaderboard', __name__, url_prefix='/leaderboard')


@leaderboard_bp.route('/')
@login_required
def index():
    subject_id = request.args.get('subject_id', type=int)
    subjects   = Subject.query.filter_by(is_active=True).order_by(Subject.name).all()

    query = (db.session.query(
                User,
                func.avg(UserQuizAttempt.accuracy_pct).label('avg_score'),
                func.count(UserQuizAttempt.id).label('total_quizzes'),
                func.max(UserQuizAttempt.accuracy_pct).label('best_score'))
             .join(UserQuizAttempt, User.id == UserQuizAttempt.user_id)
             .filter(User.role == 'student',
                     UserQuizAttempt.status == 'completed'))

    if subject_id:
        from database.models import Quiz
        quiz_ids = [q.id for q in Quiz.query.filter_by(subject_id=subject_id).all()]
        if quiz_ids:
            query = query.filter(UserQuizAttempt.quiz_id.in_(quiz_ids))

    rankings = (query.group_by(User.id)
                .order_by(func.avg(UserQuizAttempt.accuracy_pct).desc())
                .limit(50).all())

    my_rank = None
    for idx, (user, avg, total, best) in enumerate(rankings, 1):
        if user.id == current_user.id:
            my_rank = idx
            break

    return render_template('leaderboard/index.html',
        rankings=rankings, subjects=subjects,
        subject_id=subject_id, my_rank=my_rank)
