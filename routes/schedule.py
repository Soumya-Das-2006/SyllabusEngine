import json
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from database.models import StudySchedule, Subject, TopicPerformance, StudyPlan

schedule_bp = Blueprint('schedule', __name__, url_prefix='/schedule')

SLOTS = ['08:00','09:30','11:00','13:00','14:30','16:00','18:00','19:30']
DIFF_W = {'easy':0.3,'medium':0.6,'hard':1.0}

def _build(user_id, hours_per_day, start, days):
    subjects = Subject.query.filter_by(user_id=user_id, is_active=True).all()
    topics = []
    for subj in subjects:
        plan = StudyPlan.query.filter_by(subject_id=subj.id).order_by(StudyPlan.generated_at.desc()).first()
        if not plan: continue
        weak_map = {tp.topic: max(0.0, 1-tp.accuracy_pct/100)
            for tp in TopicPerformance.query.filter_by(user_id=user_id, subject_id=subj.id).all()}
        for week in plan.weeks:
            for t in json.loads(week.topics or '[]'):
                deadline = week.date_end or (date.today()+timedelta(days=14))
                days_left = max((deadline - date.today()).days, 0)
                urgency   = max(0.0, 1.0 - days_left/30)
                weakness  = weak_map.get(t, 0.0)
                diff      = week.difficulty or 'medium'
                priority  = round(urgency*0.5 + DIFF_W.get(diff,0.6)*0.3 + weakness*0.2, 4)
                topics.append({'topic':t,'subject_id':subj.id,'difficulty':diff,
                               'priority':priority,'weakness':weakness})
    topics.sort(key=lambda x: -x['priority'])
    max_min = int(hours_per_day * 60)
    day_used = {}
    slot_idx = 0
    entries  = []
    for t in topics:
        dur = 60 if t['difficulty']=='easy' else (90 if t['difficulty']=='medium' else 120)
        reps = 2 if t['weakness'] > 0.5 else 1
        for rep in range(reps):
            for d_off in range(days):
                day = start + timedelta(days=d_off)
                used = day_used.get(day, 0)
                if used + dur <= max_min:
                    day_used[day] = used + dur
                    slot = SLOTS[slot_idx % len(SLOTS)]
                    slot_idx += 1
                    sh, sm = int(slot.split(':')[0]), int(slot.split(':')[1])
                    em, es = divmod(sh*60+sm+dur, 60)
                    entries.append({'user_id':user_id,'subject_id':t['subject_id'],
                        'date':day,'topic':t['topic']+(' (Revision)'if rep else ''),
                        'duration':dur,'priority':t['priority'],'difficulty':t['difficulty'],
                        'time_slot':f"{slot} - {em:02d}:{es:02d}",'notes':''})
                    break
    return sorted(entries, key=lambda x: x['date'])

@schedule_bp.route('/')
@login_required
def schedule_home():
    schedules = StudySchedule.query.filter_by(user_id=current_user.id)\
        .filter(StudySchedule.date >= date.today())\
        .order_by(StudySchedule.date, StudySchedule.priority.desc()).limit(80).all()
    grouped = {}
    for s in schedules:
        grouped.setdefault(s.date, []).append(s)
    subjects = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('schedule/schedule.html', grouped=grouped, subjects=subjects)

@schedule_bp.route('/generate', methods=['POST','GET'])
@login_required
def generate():
    if request.method == 'GET':
        return redirect(url_for('schedule.schedule_home'))
    hours_per_day = float(request.form.get('hours_per_day', 2.0))
    days          = int(request.form.get('days', 14))
    ai_advice     = request.form.get('ai_advice') == 'on'
    hours_per_day = max(0.5, min(hours_per_day, 12))
    days          = max(1, min(days, 30))
    entries = _build(current_user.id, hours_per_day, date.today(), days)
    if not entries:
        flash('No topics found. Upload a syllabus and confirm your study plan first.','warning')
        return redirect(url_for('schedule.schedule_home'))
    StudySchedule.query.filter(StudySchedule.user_id==current_user.id,
        StudySchedule.date>=date.today(), StudySchedule.is_done==False).delete()
    db.session.commit()
    for e in entries:
        db.session.add(StudySchedule(user_id=current_user.id, subject_id=e['subject_id'],
            date=e['date'], topic=e['topic'], duration=e['duration'], priority=e['priority'],
            difficulty=e['difficulty'], time_slot=e['time_slot'], notes=e['notes']))
    db.session.commit()
    ai_tip = ''
    if ai_advice:
        try:
            import os; from groq import Groq
            compact = [{'date':str(e['date']),'topic':e['topic'],'duration':e['duration'],'difficulty':e['difficulty']} for e in entries[:20]]
            client = Groq(api_key=os.environ.get('GROQ_API_KEY',''))
            r = client.chat.completions.create(model="llama-3.3-70b-versatile",
                messages=[{'role':'user','content':f"You are Kai, a friendly study advisor. Briefly review this 2-week study schedule in 3 sentences: {json.dumps(compact)}. Mention the busiest day, one consistency tip, and one topic that looks heavy. Be encouraging."}],
                max_tokens=250, temperature=0.7)
            ai_tip = r.choices[0].message.content.strip()
        except Exception: ai_tip = "Your schedule looks great! Tackle the hardest topics first each day. Take short breaks every 90 minutes to stay sharp."
    flash('Schedule generated! 🎯','success')
    return render_template('schedule/schedule_generated.html', entries=entries[:60], ai_tip=ai_tip, days=days)

@schedule_bp.route('/mark-done/<int:entry_id>', methods=['POST'])
@login_required
def mark_done(entry_id):
    s = StudySchedule.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    s.is_done = True; db.session.commit()
    return jsonify({'ok': True})
