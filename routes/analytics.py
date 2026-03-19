from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from database.models import StudyAnalytics, Subject, UserQuizAttempt, TopicPerformance, Progress, StudyPlan
from datetime import datetime, timedelta
import json

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

def _compute(user_id, subject_id=None):
    from database.models import StudyAnalytics, Week
    from extensions import db
    subjects = (Subject.query.filter_by(id=subject_id, user_id=user_id).all()
                if subject_id else Subject.query.filter_by(user_id=user_id, is_active=True).all())
    for subj in subjects:
        attempts = UserQuizAttempt.query.filter_by(user_id=user_id, subject_id=subj.id).all()
        avg_score = round(sum(a.accuracy_pct for a in attempts) / len(attempts), 2) if attempts else 0.0
        # completion
        plan = StudyPlan.query.filter_by(subject_id=subj.id).order_by(StudyPlan.generated_at.desc()).first()
        completion_rate = 0.0
        if plan:
            total_t, done_t = 0, 0
            for w in plan.weeks:
                t = json.loads(w.topics or '[]')
                total_t += len(t)
                done_t  += min(len(t), w.completion_pct * len(t) // 100) if len(t) else 0
            completion_rate = round(done_t / total_t * 100, 2) if total_t else 0.0
        # consistency
        if attempts:
            first = attempts[0].completed_at.date()
            total_days = max((datetime.utcnow().date() - first).days, 1)
            active = set(a.completed_at.date() for a in attempts)
            prog = Progress.query.filter_by(user_id=user_id, subject_id=subj.id, is_completed=True).all()
            active.update(p.marked_at.date() for p in prog)
            consistency_score = round(len(active) / total_days * 100, 2)
            active_days = len(active)
        else:
            consistency_score, active_days = 0.0, 0
        weak_topics = [t.topic for t in TopicPerformance.query.filter_by(
            user_id=user_id, subject_id=subj.id).filter(TopicPerformance.accuracy_pct < 60).all()]
        rec = StudyAnalytics.query.filter_by(user_id=user_id, subject_id=subj.id).first()
        if not rec:
            rec = StudyAnalytics(user_id=user_id, subject_id=subj.id)
            db.session.add(rec)
        rec.completion_rate   = completion_rate
        rec.consistency_score = consistency_score
        rec.avg_score         = avg_score
        rec.total_quiz_taken  = len(attempts)
        rec.weak_topics       = json.dumps(weak_topics)
        rec.active_days       = active_days
        rec.last_updated      = datetime.utcnow()
    from extensions import db as _db
    _db.session.commit()

@analytics_bp.route('/dashboard')
@login_required
def dashboard():
    try: _compute(current_user.id)
    except Exception: pass
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    analytics = StudyAnalytics.query.filter_by(user_id=current_user.id).all()
    all_attempts = UserQuizAttempt.query.filter_by(user_id=current_user.id).all()
    overall_avg = round(sum(a.accuracy_pct for a in all_attempts) / len(all_attempts), 1) if all_attempts else 0
    analytics_by_subj = {a.subject_id: a for a in analytics}
    all_weak = []
    for a in analytics:
        all_weak.extend(a.get_weak_topics())
    return render_template('analytics/analytics_dashboard.html',
        subjects=subjects, analytics_by_subj=analytics_by_subj,
        overall_avg=overall_avg, total_quizzes=len(all_attempts),
        all_weak=list(set(all_weak))[:8])

@analytics_bp.route('/data')
@login_required
def data():
    subject_id = request.args.get('subject_id', type=int)
    days = request.args.get('days', 30, type=int)
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = UserQuizAttempt.query.filter(
        UserQuizAttempt.user_id == current_user.id,
        UserQuizAttempt.completed_at >= cutoff)
    if subject_id: q = q.filter_by(subject_id=subject_id)
    attempts = q.order_by(UserQuizAttempt.completed_at).all()
    trend = [{'date': a.completed_at.strftime('%b %d'), 'score': round(a.accuracy_pct, 1)} for a in attempts]
    tq = TopicPerformance.query.filter_by(user_id=current_user.id)
    if subject_id: tq = tq.filter_by(subject_id=subject_id)
    breakdown = [{'topic': t.topic, 'accuracy': round(t.accuracy_pct, 1), 'attempts': t.attempts}
                 for t in tq.order_by(TopicPerformance.accuracy_pct).all()]
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    subj_data = []
    for s in subjects:
        a_list = UserQuizAttempt.query.filter_by(user_id=current_user.id, subject_id=s.id).all()
        avg = round(sum(x.accuracy_pct for x in a_list) / len(a_list), 1) if a_list else 0
        subj_data.append({'name': s.name, 'avg_score': avg, 'attempts': len(a_list),
                          'completion': s.completion_pct})
    return jsonify({'trend': trend, 'breakdown': breakdown, 'subjects': subj_data})
