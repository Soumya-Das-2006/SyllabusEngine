import json, random, os, re
from datetime import datetime
from flask import (Blueprint, render_template, request, jsonify,
                   redirect, url_for, flash, session)
from flask_login import login_required, current_user
from extensions import db
from database.models import Quiz, Question, UserQuizAttempt, TopicPerformance, Subject

quiz_bp = Blueprint('quiz', __name__, url_prefix='/quiz')


# ── Helpers ───────────────────────────────────────────────────────────────────
def _adaptive_difficulty(user_id, subject_id=None):
    q = UserQuizAttempt.query.filter_by(user_id=user_id, status='completed')
    if subject_id:
        q = q.filter_by(subject_id=subject_id)
    last3 = q.order_by(UserQuizAttempt.submitted_at.desc()).limit(3).all()
    if not last3: return 'medium'
    avg = sum(a.accuracy_pct for a in last3) / len(last3)
    return 'hard' if avg >= 80 else ('easy' if avg < 50 else 'medium')


def _ai_generate(topic, subject_name, difficulty, num_q):
    """Generate questions via Groq. Returns list of dicts."""
    hint = {'easy': 'basic recall and definitions',
            'medium': 'conceptual understanding and application',
            'hard': 'analysis, synthesis and evaluation'}.get(difficulty, 'concepts')
    prompt = f"""Generate exactly {num_q} multiple-choice questions about "{topic}".
Subject context: {subject_name or topic}. Difficulty: {difficulty} — {hint}.
Return ONLY valid JSON, no markdown:
{{"questions":[{{"question":"?","options":{{"A":"","B":"","C":"","D":""}},"correct_answer":"A","explanation":"","difficulty":"{difficulty}","topic_tag":""}}]}}"""
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get('GROQ_API_KEY', ''))
        resp   = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=3000, temperature=0.4)
        raw  = resp.choices[0].message.content.strip()
        raw  = re.sub(r'^```[a-z]*\n?', '', raw)
        raw  = re.sub(r'\n?```$', '', raw)
        data = json.loads(raw)
        return [q for q in data.get('questions', [])
                if q.get('question') and isinstance(q.get('options'), dict)
                and all(k in q['options'] for k in 'ABCD')]
    except Exception as e:
        print(f"[QuizGen] {e}")
        return []


def _offline_questions(topic, difficulty, num_q):
    return [{'question': f'[Offline] Q{i+1} about "{topic}"',
             'options': {'A': 'Option A', 'B': 'Option B', 'C': 'Option C', 'D': 'Option D'},
             'correct_answer': 'A', 'explanation': 'Reconnect to generate real questions.',
             'difficulty': difficulty, 'topic_tag': topic}
            for i in range(num_q)]


def _get_or_create_quiz(topic, difficulty, num_q, user_id, subject_id=None):
    import hashlib
    cache_key = hashlib.md5(f"{topic}:{difficulty}:{num_q}".encode()).hexdigest()
    existing  = Quiz.query.filter_by(cache_key=cache_key, is_deleted=False).first()
    if existing and list(existing.questions):
        return existing

    subj_name     = Subject.query.get(subject_id).name if subject_id else ''
    raw_questions = _ai_generate(topic, subj_name, difficulty, num_q) or _offline_questions(topic, difficulty, num_q)

    quiz = Quiz(user_id=user_id, subject_id=subject_id,
                title=f"{topic} — {difficulty.capitalize()} Quiz",
                topic=topic, difficulty=difficulty,
                num_questions=len(raw_questions), cache_key=cache_key,
                duration_minutes=30, pass_marks=50, max_violations=3,
                fullscreen_req=True, shuffle_q=True, is_active=True)
    db.session.add(quiz)
    db.session.flush()

    for idx, q in enumerate(raw_questions):
        opts = q.get('options', {})
        db.session.add(Question(
            quiz_id=quiz.id, question_text=q.get('question', ''),
            option_a=opts.get('A', ''), option_b=opts.get('B', ''),
            option_c=opts.get('C', ''), option_d=opts.get('D', ''),
            correct_answer=q.get('correct_answer', 'A').upper(),
            explanation=q.get('explanation', ''),
            difficulty=q.get('difficulty', difficulty),
            topic_tag=q.get('topic_tag', topic), order_index=idx))

    db.session.commit()
    return quiz


# ── Student routes ─────────────────────────────────────────────────────────────
@quiz_bp.route('/')
@login_required
def quiz_home():
    subjects        = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    subject_ids     = [s.id for s in subjects]
    recent_attempts = (UserQuizAttempt.query.filter_by(user_id=current_user.id)
                       .order_by(UserQuizAttempt.submitted_at.desc()).limit(5).all())
    all_attempts    = UserQuizAttempt.query.filter_by(user_id=current_user.id,
                                                       status='completed').all()
    avg_score       = round(sum(a.accuracy_pct for a in all_attempts) / len(all_attempts), 1) if all_attempts else 0

    # Admin-created quizzes assigned to the student's subjects
    assigned_quizzes = []
    if subject_ids:
        assigned_quizzes = (Quiz.query
            .filter(Quiz.subject_id.in_(subject_ids))
            .filter(Quiz.is_active.is_(True))
            .filter(Quiz.is_deleted.is_(False))
            .filter(Quiz.cache_key.is_(None))
            .order_by(Quiz.created_at.desc())
            .limit(10)
            .all())

    return render_template('quiz/quiz_home.html', subjects=subjects,
        recent_attempts=recent_attempts, avg_score=avg_score,
        recommended_difficulty=_adaptive_difficulty(current_user.id),
        total_attempts=len(all_attempts),
        assigned_quizzes=assigned_quizzes)


@quiz_bp.route('/start', methods=['GET', 'POST'])
@login_required
def quiz_start():
    if request.method == 'POST':
        topic      = request.form.get('topic', '').strip()
        difficulty = request.form.get('difficulty', 'medium')
        num_q      = max(3, min(int(request.form.get('num_questions', 5)), 15))
        subject_id = request.form.get('subject_id') or None
        auto_diff  = request.form.get('auto_difficulty') == 'on'
        if not topic:
            flash('Please enter a topic.', 'warning')
            return redirect(url_for('quiz.quiz_start'))
        if difficulty not in ('easy', 'medium', 'hard'):
            difficulty = 'medium'
        subject_id = int(subject_id) if subject_id else None
        if auto_diff:
            difficulty = _adaptive_difficulty(current_user.id, subject_id)
        try:
            quiz = _get_or_create_quiz(topic, difficulty, num_q, current_user.id, subject_id)
        except Exception as e:
            flash(f'Could not generate quiz: {e}', 'error')
            return redirect(url_for('quiz.quiz_start'))
        # Create attempt
        attempt = UserQuizAttempt(
            user_id=current_user.id, quiz_id=quiz.id,
            subject_id=quiz.subject_id, difficulty_used=quiz.difficulty,
            ip_address=request.remote_addr, started_at=datetime.utcnow())
        db.session.add(attempt); db.session.commit()
        session['quiz_start_time'] = datetime.utcnow().isoformat()
        qs = list(quiz.questions)
        if quiz.shuffle_q: random.shuffle(qs)
        return render_template('quiz/quiz_take.html', quiz=quiz, attempt=attempt, questions=qs)

    subjects      = Subject.query.filter_by(user_id=current_user.id, is_active=True).all()
    auto_diff     = _adaptive_difficulty(current_user.id)
    return render_template('quiz/quiz_start.html', subjects=subjects, auto_difficulty=auto_diff)


@quiz_bp.route('/assigned/<int:quiz_id>/start')
@login_required
def assigned_quiz_start(quiz_id):
    """Start an admin-created quiz that has been assigned to the student."""
    quiz = Quiz.query.filter_by(id=quiz_id, is_deleted=False).first_or_404()

    # Only allow admin-created quizzes (no cache_key) for subjects owned by this user
    if quiz.cache_key is not None:
        flash('This quiz is not available as an assigned quiz.', 'warning')
        return redirect(url_for('quiz.quiz_home'))

    subj = quiz.subject
    if not subj or subj.user_id != current_user.id:
        flash('You are not allowed to access this quiz.', 'error')
        return redirect(url_for('quiz.quiz_home'))

    # Allow only a single completed attempt per student for admin quizzes
    existing = UserQuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz.id).first()
    if existing and existing.status in ('completed', 'flagged'):
        flash('You have already attempted this quiz.', 'info')
        return redirect(url_for('quiz.quiz_result', attempt_id=existing.id))

    attempt = UserQuizAttempt(
        user_id=current_user.id,
        quiz_id=quiz.id,
        subject_id=quiz.subject_id,
        difficulty_used=quiz.difficulty,
        ip_address=request.remote_addr,
        started_at=datetime.utcnow())
    db.session.add(attempt); db.session.commit()

    qs = list(quiz.questions)
    if quiz.shuffle_q:
        random.shuffle(qs)

    return render_template('quiz/quiz_take.html', quiz=quiz, attempt=attempt, questions=qs)


@quiz_bp.route('/assigned/u/<string:quiz_uuid>/start')
@login_required
def assigned_quiz_start_uuid(quiz_uuid):
    """UUID variant of assigned quiz start route for non-sequential URLs."""
    quiz = Quiz.query.filter_by(uuid=quiz_uuid, is_deleted=False).first_or_404()
    return redirect(url_for('quiz.assigned_quiz_start', quiz_id=quiz.id))


@quiz_bp.route('/<int:quiz_id>/violation', methods=['POST'])
@login_required
def log_violation(quiz_id):
    data    = request.get_json() or {}
    attempt = UserQuizAttempt.query.filter_by(
        user_id=current_user.id, quiz_id=quiz_id, status='in_progress').first()
    if not attempt:
        return jsonify({'error': 'No active attempt'}), 400
    quiz = Quiz.query.filter_by(id=quiz_id, is_deleted=False).first_or_404()
    vlog = json.loads(attempt.violation_log or '[]')
    vlog.append({'type': data.get('type', 'unknown'),
                 'detail': data.get('detail', ''),
                 'at': datetime.utcnow().isoformat()})
    attempt.violation_log = json.dumps(vlog)
    attempt.violations    = len(vlog)
    db.session.commit()
    max_v       = quiz.max_violations or 3
    auto_submit = attempt.violations >= max_v
    return jsonify({'ok': True, 'violations': attempt.violations,
                    'max': max_v, 'auto_submit': auto_submit})


@quiz_bp.route('/<int:quiz_id>/save-answer', methods=['POST'])
@login_required
def save_answer(quiz_id):
    data    = request.get_json() or {}
    attempt = UserQuizAttempt.query.filter_by(
        user_id=current_user.id, quiz_id=quiz_id, status='in_progress').first()
    if not attempt:
        return jsonify({'error': 'No active attempt'}), 400
    answers = json.loads(attempt.answers_json or '{}')
    answers[str(data.get('question_id', ''))] = str(data.get('answer', '')).upper()
    attempt.answers_json = json.dumps(answers)
    db.session.commit()
    return jsonify({'ok': True})


@quiz_bp.route('/<int:quiz_id>/submit', methods=['POST'])
@login_required
def quiz_submit(quiz_id=None):
    # Support JSON (anti-cheat JS) and form POST
    if request.is_json:
        data       = request.get_json() or {}
        quiz_id_in = quiz_id or data.get('quiz_id')
        answers_in = data.get('answers', {})
        auto_sub   = data.get('auto_submit', False)
    else:
        quiz_id_in = quiz_id or request.form.get('quiz_id', type=int)
        answers_in = {}
        auto_sub   = False

    quiz      = Quiz.query.filter_by(id=quiz_id_in, is_deleted=False).first_or_404()
    questions = list(quiz.questions)

    attempt = UserQuizAttempt.query.filter_by(
        user_id=current_user.id, quiz_id=quiz_id_in, status='in_progress').first()
    if not attempt:
        attempt = UserQuizAttempt(
            user_id=current_user.id, quiz_id=quiz_id_in,
            subject_id=quiz.subject_id, ip_address=request.remote_addr,
            started_at=datetime.utcnow())
        db.session.add(attempt); db.session.flush()

    # Merge saved + submitted answers
    saved = json.loads(attempt.answers_json or '{}')
    if answers_in:
        saved.update({str(k): str(v).upper() for k, v in answers_in.items()})
    if not answers_in and not request.is_json:
        for q in questions:
            val = request.form.get(f'q_{q.id}', '').upper()
            if val: saved[str(q.id)] = val

    score        = sum(1 for q in questions if saved.get(str(q.id)) == q.correct_answer)
    wrong_topics = list({q.topic_tag for q in questions
                         if saved.get(str(q.id)) != q.correct_answer and q.topic_tag})
    total        = len(questions)
    accuracy     = round(score / total * 100, 1) if total else 0
    time_taken   = int((datetime.utcnow() - attempt.started_at).total_seconds()) if attempt.started_at else 0

    attempt.answers_json    = json.dumps(saved)
    attempt.score           = score
    attempt.total_questions = total
    attempt.total_marks     = sum(getattr(q, 'marks', 1) for q in questions)
    attempt.accuracy_pct    = accuracy
    attempt.time_taken_sec  = time_taken
    attempt.wrong_topics    = json.dumps(wrong_topics)
    attempt.submitted_at    = datetime.utcnow()
    attempt.auto_submitted  = auto_sub
    attempt.passed          = accuracy >= (quiz.pass_marks or 50)
    attempt.status          = 'flagged' if (attempt.violations or 0) > 0 else 'completed'
    attempt.subject_id      = quiz.subject_id
    db.session.commit()

    # Update topic performance
    for q in questions:
        topic_tag = q.topic_tag or (quiz.topic or quiz.title)
        tp = TopicPerformance.query.filter_by(
            user_id=current_user.id, subject_id=quiz.subject_id, topic=topic_tag).first()
        if not tp:
            tp = TopicPerformance(user_id=current_user.id,
                                  subject_id=quiz.subject_id, topic=topic_tag)
            db.session.add(tp)
        tp.update_stats(saved.get(str(q.id)) == q.correct_answer)
    db.session.commit()

    # Issue certificate if passed
    if attempt.passed:
        try:
            from routes.certificates import issue_certificate
            cert = issue_certificate(current_user.id, quiz.id, attempt.id, quiz.title)
            # Email notification
            try:
                from integrations.email import send_quiz_result_email, send_certificate_email
                send_quiz_result_email(current_user, quiz, attempt)
                send_certificate_email(current_user, cert, quiz.title)
            except Exception: pass
        except Exception: pass
    else:
        try:
            from integrations.email import send_quiz_result_email
            send_quiz_result_email(current_user, quiz, attempt)
        except Exception: pass

    # Notify
    try:
        from database.models import Notification
        db.session.add(Notification(
            user_id=current_user.id,
            title=f'Quiz Result: {quiz.title}',
            message=f'You scored {accuracy}% — {"Passed ✅" if attempt.passed else "Failed ❌"}',
            notif_type='result',
            link=url_for('quiz.quiz_result', attempt_id=attempt.id)))
        db.session.commit()
    except Exception: pass

    if request.is_json:
        return jsonify({'redirect': url_for('quiz.quiz_result', attempt_id=attempt.id)})
    return redirect(url_for('quiz.quiz_result', attempt_id=attempt.id))


@quiz_bp.route('/submit/<int:quiz_id>', methods=['POST'])
@login_required
def quiz_submit_url(quiz_id):
    """URL-based submit used by anti-cheat JavaScript."""
    return quiz_submit(quiz_id)

@quiz_bp.route('/result/<int:attempt_id>')
@login_required
def quiz_result(attempt_id):
    attempt   = UserQuizAttempt.query.filter_by(
        id=attempt_id, user_id=current_user.id).first_or_404()
    quiz      = attempt.quiz
    questions = sorted(list(quiz.questions), key=lambda q: q.order_index)
    answers   = attempt.get_answers()
    result_data = [{'id': q.id, 'text': q.question_text,
        'options': {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d},
        'chosen': answers.get(str(q.id), ''), 'correct': q.correct_answer,
        'is_correct': answers.get(str(q.id), '') == q.correct_answer,
        'explanation': q.explanation, 'topic_tag': q.topic_tag}
        for q in questions]
    from database.models import Certificate
    cert = Certificate.query.filter_by(attempt_id=attempt_id).first()
    return render_template('quiz/quiz_result.html', attempt=attempt, quiz=quiz,
        result_data=result_data, next_difficulty=_adaptive_difficulty(current_user.id, quiz.subject_id),
        cert=cert)


@quiz_bp.route('/history')
@login_required
def quiz_history():
    attempts = (UserQuizAttempt.query.filter_by(user_id=current_user.id)
                .order_by(UserQuizAttempt.submitted_at.desc()).limit(50).all())
    return render_template('quiz/quiz_history.html', attempts=attempts)
