"""
integrations/email.py
Unified email sender using SMTP only.
Includes all transactional email templates.
"""
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app, url_for

# ── Brand colors/styles reused in every template ──────────────────────────
_BASE = """
<div style="font-family:'Inter',Arial,sans-serif;max-width:560px;margin:0 auto;background:#ffffff;
     border-radius:16px;overflow:hidden;border:1px solid #e8e5dd">
  <div style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);
       padding:2rem;text-align:center">
    <div style="font-size:2rem;margin-bottom:.4rem">📚</div>
    <h1 style="color:#fff;font-size:1.35rem;margin:0;font-weight:700">SyllabusEngine</h1>
    <p style="color:rgba(255,255,255,.8);font-size:.82rem;margin:.3rem 0 0">
      AI-Powered Study Platform
    </p>
  </div>
  <div style="padding:2rem">
    {BODY}
  </div>
  <div style="background:#f7f6f2;padding:1rem 2rem;text-align:center;
       font-size:.75rem;color:#98968e;border-top:1px solid #e8e5dd">
    © 2025 SyllabusEngine &nbsp;|&nbsp;
    You're receiving this because you have an account with us.
  </div>
</div>
"""

def _wrap(body: str) -> str:
    return _BASE.replace('{BODY}', body)

def _btn(text: str, url: str) -> str:
    return f"""
    <div style="text-align:center;margin:1.5rem 0">
      <a href="{url}" style="display:inline-block;background:#4f46e5;color:#fff;
         padding:.75rem 2rem;border-radius:40px;font-weight:700;font-size:.95rem;
         text-decoration:none;box-shadow:0 8px 18px -8px #4f46e5">{text}</a>
    </div>"""

def _heading(text: str) -> str:
    return f'<h2 style="color:#1a1916;font-size:1.25rem;margin:0 0 .75rem">{text}</h2>'

def _para(text: str) -> str:
    return f'<p style="color:#5a5850;line-height:1.7;margin:.5rem 0">{text}</p>'

def _highlight(text: str) -> str:
    return f'<div style="background:#eef2ff;border-left:4px solid #4f46e5;padding:.75rem 1rem;border-radius:0 8px 8px 0;margin:.75rem 0;color:#3730a3;font-weight:600">{text}</div>'


# ── Low-level sender (SMTP only) ───────────────────────────────────────────

def _send_via_smtp(sender, to_address, subject, html_body):
    host     = current_app.config.get('SMTP_HOST', '')
    username = current_app.config.get('SMTP_USERNAME', '')
    password = current_app.config.get('SMTP_PASSWORD', '')
    port     = current_app.config.get('SMTP_PORT', 587)
    use_tls  = current_app.config.get('SMTP_USE_TLS', True)
    if not host or not username or not password:
        return False
    msg = MIMEMultipart('alternative')
    msg['Subject'], msg['From'], msg['To'] = subject, sender, to_address
    msg.attach(MIMEText(html_body, 'html'))
    try:
        if use_tls:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(host, port) as s:
                s.starttls(context=ctx); s.login(username, password); s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port) as s:
                s.login(username, password); s.send_message(msg)
        return True
    except Exception as exc:
        current_app.logger.error('SMTP error: %s', exc)
        return False


def send_email(to_address: str, subject: str, html_body: str) -> bool:
    sender = current_app.config.get('MAIL_FROM', '')
    if not sender:
        current_app.logger.warning('Email not sent: MAIL_FROM not configured.')
        return False
    if _send_via_smtp(sender, to_address, subject, html_body):
        return True
    current_app.logger.warning('Email not sent: SMTP configuration appears invalid.')
    return False


# ── Transactional email templates ──────────────────────────────────────────

def send_password_reset_email(user) -> bool:
    if not user.reset_token:
        return False
    reset_url = url_for('auth.reset_password', token=user.reset_token, _external=True)
    html = _wrap(
        _heading('Reset Your Password') +
        _para(f'Hi <strong>{user.name}</strong>,') +
        _para('We received a request to reset your SyllabusEngine password. Click the button below — this link expires in 24 hours.') +
        _btn('🔑 Reset My Password', reset_url) +
        _para("If you didn't request this, you can safely ignore this email. Your account is secure.") +
        _highlight('⏰ This link will expire in 24 hours for your security.')
    )
    return send_email(user.email, '🔑 Reset your SyllabusEngine password', html)


def send_welcome_email(user) -> bool:
    dashboard_url = url_for('dashboard.index', _external=True)
    html = _wrap(
        _heading(f'Welcome to SyllabusEngine, {user.name}! 🎉') +
        _para('Your account is ready. Here\'s how to get started:') +
        '<ol style="color:#5a5850;line-height:2;padding-left:1.5rem">' +
        '<li>📚 Add your subjects in the Dashboard</li>' +
        '<li>⬆️ Upload your syllabus PDF</li>' +
        '<li>🤖 Let AI create your study plan</li>' +
        '<li>🧪 Take quizzes to test your knowledge</li>' +
        '</ol>' +
        _btn('🚀 Go to My Dashboard', dashboard_url) +
        _highlight('💡 Tip: Complete your profile to unlock all features including quizzes!')
    )
    return send_email(user.email, '🎉 Welcome to SyllabusEngine!', html)


def send_quiz_created_email(user, quiz) -> bool:
    """Notify a student that a new quiz has been created for them."""
    quiz_url     = url_for('quiz.quiz_home', _external=True)
    subject_obj  = getattr(quiz, 'subject', None)
    subject_name = subject_obj.name if subject_obj else 'General'
    try:
        question_count = len(list(quiz.questions))
    except Exception:
        question_count = getattr(quiz, 'num_questions', 0) or 0
    duration = getattr(quiz, 'duration_minutes', 30) or 30

    html = _wrap(
        _heading('📝 New Quiz Assigned') +
        _para(f'Hi <strong>{user.name}</strong>, a new quiz has been published for your course.') +
        f'''<div style="background:#eef2ff;border-radius:12px;padding:1rem 1.25rem;margin:1rem 0">
          <div style="font-weight:700;color:#1a1916;margin-bottom:.25rem">{quiz.title}</div>
          <div style="font-size:.85rem;color:#5a5850">
            {subject_name} &nbsp;·&nbsp; {question_count} questions &nbsp;·&nbsp; {duration} minutes
          </div>
        </div>''' +
        _highlight('You can also find this quiz inside the app under the Quiz Center and your notification bell.') +
        _btn('🧪 Open Quiz Center', quiz_url)
    )
    return send_email(user.email, f'New Quiz: {quiz.title}', html)


def send_quiz_result_email(user, quiz, attempt) -> bool:
    result_url = url_for('quiz.quiz_result', attempt_id=attempt.id, _external=True)
    passed = attempt.passed
    emoji  = '🏆' if attempt.accuracy_pct >= 80 else ('👍' if attempt.accuracy_pct >= 50 else '📚')
    html = _wrap(
        _heading(f'{emoji} Quiz Result: {quiz.title}') +
        _para(f'Hi <strong>{user.name}</strong>, here are your results:') +
        f'''<div style="background:{"#f0fdf4" if passed else "#fef2f2"};border:1px solid {"#bbf7d0" if passed else "#fecaca"};
            border-radius:12px;padding:1.5rem;text-align:center;margin:1rem 0">
          <div style="font-size:3rem;margin-bottom:.5rem">{"✅" if passed else "❌"}</div>
          <div style="font-size:2.5rem;font-weight:800;color:{"#16a34a" if passed else "#dc2626"}">{attempt.accuracy_pct:.1f}%</div>
          <div style="color:{"#16a34a" if passed else "#dc2626"};font-weight:700">{"PASSED" if passed else "NEEDS IMPROVEMENT"}</div>
          <div style="color:#5a5850;font-size:.88rem;margin-top:.5rem">
            {attempt.score}/{attempt.total_marks} correct &nbsp;·&nbsp;
            {attempt.time_taken_sec // 60}m {attempt.time_taken_sec % 60}s
          </div>
        </div>''' +
        (_highlight('🎓 Congratulations! You earned a certificate for this quiz.') if passed else
         _highlight('💪 Keep practicing! Review your mistakes and try again.')) +
        _btn('📊 View Full Result', result_url)
    )
    return send_email(user.email, f'Quiz Result: {quiz.title} — {attempt.accuracy_pct:.1f}%', html)


def send_deadline_reminder(user, assignment) -> bool:
    from datetime import date
    days_left = (assignment.due_date - date.today()).days
    dashboard_url = url_for('dashboard.index', _external=True)
    urgency = '🚨 TODAY' if days_left == 0 else (f'⏰ {days_left} day{"s" if days_left>1 else ""} left')
    html = _wrap(
        _heading(f'{urgency} — Deadline Reminder') +
        _para(f'Hi <strong>{user.name}</strong>,') +
        _highlight(f'📋 {assignment.title}') +
        _para(f'Subject: <strong>{assignment.subject.name}</strong>') +
        _para(f'Due date: <strong>{assignment.due_date.strftime("%B %d, %Y")}</strong>') +
        ('⚠️ <strong>This is due TODAY!</strong>' if days_left == 0 else
         f'<p style="color:#5a5850">You have <strong>{days_left} day{"s" if days_left>1 else ""}</strong> to complete this assignment.</p>') +
        _btn('📚 Go to Dashboard', dashboard_url)
    )
    return send_email(user.email, f'⏰ Deadline Reminder: {assignment.title}', html)


def send_exam_reminder(user, exam) -> bool:
    from datetime import date
    days_left = (exam.exam_date - date.today()).days if exam.exam_date else None
    dashboard_url = url_for('dashboard.index', _external=True)
    urgency = '🚨 TOMORROW' if days_left == 1 else (f'📅 {days_left} days away' if days_left else 'Coming up')
    html = _wrap(
        _heading(f'Exam Reminder — {urgency}') +
        _para(f'Hi <strong>{user.name}</strong>, your exam is coming up!') +
        _highlight(f'📝 {exam.name}') +
        (f'<p style="color:#dc2626;font-weight:700">Exam Date: {exam.exam_date.strftime("%B %d, %Y")}</p>' if exam.exam_date else '') +
        _para('Make sure you review all covered topics. Good luck! 💪') +
        _btn('📅 Open Study Planner', dashboard_url)
    )
    subject_line = f'📝 Exam in {days_left} day{"s" if days_left and days_left>1 else ""}: {exam.name}' if days_left else f'📝 Upcoming Exam: {exam.name}'
    return send_email(user.email, subject_line, html)


def send_weekly_digest(user, upcoming_deadlines, upcoming_exams) -> bool:
    dashboard_url = url_for('dashboard.index', _external=True)
    deadline_items = ''.join(
        f'<li style="padding:.3rem 0">{a.title} — <strong>{a.due_date.strftime("%b %d")}</strong> ({a.subject.name})</li>'
        for a in upcoming_deadlines[:5]
    ) if upcoming_deadlines else '<li style="color:#98968e">No upcoming deadlines 🎉</li>'
    exam_items = ''.join(
        f'<li style="padding:.3rem 0">{e.name} — <strong>{e.exam_date.strftime("%b %d") if e.exam_date else "TBD"}</strong></li>'
        for e in upcoming_exams[:3]
    ) if upcoming_exams else '<li style="color:#98968e">No upcoming exams 🎉</li>'
    html = _wrap(
        _heading(f'Your Weekly Study Digest 📅') +
        _para(f'Hi <strong>{user.name}</strong>, here\'s what\'s coming up this week:') +
        '<h3 style="color:#1a1916;margin:1rem 0 .4rem">📋 Upcoming Deadlines</h3>' +
        f'<ul style="color:#5a5850;line-height:1.8;padding-left:1.5rem">{deadline_items}</ul>' +
        '<h3 style="color:#1a1916;margin:1rem 0 .4rem">📝 Upcoming Exams</h3>' +
        f'<ul style="color:#5a5850;line-height:1.8;padding-left:1.5rem">{exam_items}</ul>' +
        _btn('📚 Open My Dashboard', dashboard_url) +
        _highlight('💡 Tip: Use the AI assistant Kai to prepare for your exams!')
    )
    return send_email(user.email, '📅 Your Weekly Study Digest', html)


def send_certificate_email(user, cert, quiz_title) -> bool:
    cert_url = url_for('certificates.index', _external=True)
    html = _wrap(
        _heading(f'🎓 Certificate Earned!') +
        _para(f'Congratulations <strong>{user.name}</strong>! You passed the quiz and earned a certificate.') +
        f'''<div style="background:linear-gradient(135deg,#eef2ff,#f0fdf4);border:1px solid #bbf7d0;
            border-radius:16px;padding:1.75rem;text-align:center;margin:1rem 0">
          <div style="font-size:3rem;margin-bottom:.5rem">🏅</div>
          <div style="font-size:1.1rem;font-weight:700;color:#1a1916">{cert.title}</div>
          <div style="font-size:.8rem;color:#98968e;font-family:monospace;margin-top:.3rem">{cert.cert_number}</div>
        </div>''' +
        _btn('📥 Download Certificate', cert_url)
    )
    return send_email(user.email, f'🎓 Certificate: {quiz_title}', html)
