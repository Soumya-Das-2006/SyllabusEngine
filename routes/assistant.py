from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from database.models import Subject, AIConversation, Week, Assignment, Exam, Syllabus, db
from datetime import date

assistant_bp = Blueprint('assistant', __name__)


# ── 8-mode system prompt builder ─────────────────────────────────────────────

def _build_system_prompt(mode, user_name, subject_name,
                         current_week_num, semester_length,
                         topics_str, deadlines_str, exam_str,
                         has_pdf=False):

    pdf_note = (
        "\n\nIMPORTANT: The student has uploaded a PDF document. "
        "Your answers must be based primarily on the content of that PDF. "
        "Reference specific sections, chapters, or topics from the PDF when answering."
        if has_pdf else ""
    )

    ctx = (
        f"Student: {user_name}\n"
        f"Subject: {subject_name}\n"
        f"Current week: Week {current_week_num} of {semester_length}\n"
        f"This week's topics: {topics_str}\n"
        f"Upcoming deadlines: {deadlines_str}\n"
        f"Next exam: {exam_str}"
    )

    PROMPTS = {

        'explain': f"""You are Kai, a brilliant and friendly tutor.
{ctx}{pdf_note}

TASK: Explain the given topic clearly and completely.
FORMAT:
1. **Simple definition** (1-2 sentences)
2. **Core concept** (with a real-world analogy)
3. **Step-by-step breakdown** (numbered steps)
4. **Two concrete examples** (clearly labelled)
5. **Common mistakes to avoid**
Use **bold** for key terms. Keep tone warm and encouraging.""",

        'notes': f"""You are Kai, an expert exam note-maker.
{ctx}{pdf_note}

TASK: Generate structured exam-ready notes on the given topic.
FORMAT:
# [Topic Name]
## Key Definitions
## Core Concepts & Principles
## Important Formulas / Rules / Dates
## Quick Memory Tips (mnemonics if possible)
## Likely Exam Questions (3-5)
Keep notes concise, scannable, and exam-focused.""",

        'quiz': f"""You are Kai, an exam prep specialist.
{ctx}{pdf_note}

TASK: Generate a comprehensive practice quiz.
FORMAT:
**MCQ Section — 5 Questions**
Q1. [Question]
A) [option]  B) [option]  C) [option]  D) [option]
✅ Answer: [letter] — [brief explanation]

**Short Answer — 3 Questions**
[Question]
→ Model answer: [2-3 sentences]

**Long Answer / Essay — 2 Questions**
[Question]
→ Key points to cover: [bullet list]""",

        'doubt': f"""You are Kai, a patient teacher who clears confusion.
{ctx}{pdf_note}

TASK: Resolve the student's doubt completely.
1. Identify the exact confusion point
2. Explain from scratch in simple language
3. Give a daily-life analogy
4. Walk through a concrete example step by step
5. End with: "Does this make sense now? Ask me if anything is still unclear."
Never make the student feel bad for not understanding.""",

        'important_qs': f"""You are Kai, an exam specialist.
{ctx}{pdf_note}

TASK: List the most important exam questions for the given topic.
FORMAT:
## ⭐⭐⭐⭐⭐ Very Likely — Must Prepare
- [Question] (Chapter/Unit X, ~N marks)

## ⭐⭐⭐⭐ Likely — High Chance
- [Question] (Chapter/Unit X, ~N marks)

## ⭐⭐⭐ Good to Know
- [Question]

Include chapter reference and expected marks for each.""",

        'revision': f"""You are Kai, a last-minute revision expert.
{ctx}{pdf_note}

TASK: Create an ultra-concise last-minute revision summary.
FORMAT:
## ⚡ 60-Second Overview
[2-3 sentence summary]

## 🔑 Key Points to Remember (max 10 bullets)
## 📊 Key Formulas / Dates / Data
## ⚠️ Common Exam Mistakes
## 🎯 Last-Minute Tips

Keep everything BRIEF. This is for the night before the exam.""",

        'math': f"""You are Kai, a precise mathematics solver.
{ctx}{pdf_note}

TASK: Solve the given math problem completely.
FORMAT:
**Problem Type:** [identify the type]
**Formula / Theorem Used:** [state clearly]

**Step-by-Step Solution:**
Step 1: [action] → [result]
Step 2: [action] → [result]
...
**▶ Final Answer:** [boxed]
**Verification:** [check if possible]
**Alternative Method:** [if one exists]

Never skip steps. Show every calculation.""",

        'essay': f"""You are Kai, an expert writing coach.
{ctx}{pdf_note}

TASK: Help with essay, letter, or application.
- For ESSAYS: Introduction + 3 body paragraphs + conclusion outline + key vocabulary
- For FORMAL LETTERS: Complete filled-in template with all parts
- For APPLICATIONS: Professional template ready to submit
Include: estimated word count, tone guidance, 5 key vocabulary words.""",
    }

    return PROMPTS.get(mode, PROMPTS['explain'])


# ── Pages ─────────────────────────────────────────────────────────────────────

@assistant_bp.route('/assistant')
@login_required
def assistant():
    """General AI assistant page without requiring specific subject."""
    subjects = Subject.query.filter_by(
        user_id=current_user.id, is_active=True
    ).order_by(Subject.created_at.desc()).all()

    # Prefer opening assistant on a valid subject to keep chat endpoint inserts valid.
    default_subject = subjects[0] if subjects else None
    recent_history = []
    if default_subject:
        recent_history = AIConversation.query.filter_by(
            user_id=current_user.id,
            subject_id=default_subject.id,
        ).order_by(AIConversation.created_at.desc()).limit(10).all()

    return render_template('dashboard/assistant.html',
        subject=default_subject,
        subjects=subjects,
        history=recent_history
    )


@assistant_bp.route('/subjects/<int:subject_id>/assistant')
@assistant_bp.route('/assistant/<int:subject_id>')
@login_required
def chat_page(subject_id):
    subject = Subject.query.filter_by(
        id=subject_id, user_id=current_user.id
    ).first_or_404()

    history = AIConversation.query.filter_by(
        user_id=current_user.id, subject_id=subject_id
    ).order_by(AIConversation.created_at).limit(50).all()

    subjects = Subject.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()

    return render_template('dashboard/assistant.html',
        subject=subject,
        subjects=subjects,
        history=history,
    )


@assistant_bp.route('/ai_assist')
@assistant_bp.route('/ai_assist/<int:subject_id>')
@login_required
def ai_assist_page(subject_id=None):
    subjects = Subject.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()
    subject = None
    recent_sessions = []

    if subject_id:
        subject = Subject.query.filter_by(
            id=subject_id, user_id=current_user.id
        ).first()

        if subject:
            recent_convos = AIConversation.query.filter_by(
                user_id=current_user.id,
                subject_id=subject_id,
                role='user',
            ).order_by(AIConversation.created_at.desc()).limit(8).all()
        else:
            recent_convos = []

        recent_sessions = [
            {
                'id':         c.id,
                'topic':      c.message[:50],
                'mode':       getattr(c, 'mode', 'explain') or 'explain',
                'updated_at': c.created_at,
            }
            for c in recent_convos
        ]
    else:
        # Show recent sessions across all subjects (subject_id=None ok)
        recent_convos = AIConversation.query.filter_by(
            user_id=current_user.id,
            role='user',
        ).order_by(AIConversation.created_at.desc()).limit(8).all()

        recent_sessions = [
            {
                'id':         c.id,
                'topic':      c.message[:50],
                'mode':       getattr(c, 'mode', 'explain') or 'explain',
                'updated_at': c.created_at,
            }
            for c in recent_convos
        ]

    return render_template('dashboard/ai_assist.html',
        subject=subject,
        subjects=subjects,
        recent_sessions=recent_sessions,
    )


# ── PDF Text Extraction ───────────────────────────────────────────────────────

@assistant_bp.route('/api/assistant/pdf-extract', methods=['POST'])
@login_required
def pdf_extract():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF file provided.'}), 400

    file = request.files['pdf']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are accepted.'}), 400

    import os, uuid, tempfile
    tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.pdf")
    try:
        file.save(tmp_path)
        from pdf.extractor import extract_text
        text, ocr_used = extract_text(tmp_path)

        pages = 1
        try:
            import pdfplumber
            with pdfplumber.open(tmp_path) as pdf:
                pages = len(pdf.pages)
        except Exception:
            pass

        MAX_CHARS = 12000
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + f'\n\n[PDF truncated — showing first {MAX_CHARS} of {len(text)} characters]'

        return jsonify({'pdf_text': text, 'pages': pages, 'ocr_used': ocr_used})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ── AI Chat (all 8 modes + PDF context) ──────────────────────────────────────

@assistant_bp.route('/api/assistant/chat', methods=['POST'])
@login_required
def chat():
    data       = request.get_json()
    subject_id = data.get('subject_id')
    message    = data.get('message', '').strip()
    mode       = data.get('mode', 'explain')
    language   = data.get('language', 'en')
    image_text = data.get('image_text', '')
    pdf_text   = data.get('pdf_text', '')

    if not message:
        return jsonify({'error': 'Please enter a question or topic.'}), 400

    valid_modes = ['explain', 'notes', 'quiz', 'doubt',
                   'important_qs', 'revision', 'math', 'essay']
    if mode not in valid_modes:
        mode = 'explain'

    # Build syllabus context
    today            = date.today()
    current_week_num = 1
    semester_length  = 15
    subject_name     = 'General Study'
    topics_str       = 'Not set up yet'
    deadlines_str    = 'None upcoming'
    exam_str         = 'None upcoming'
    syllabus_context = ''

    # Normalize subject id from JSON input (may arrive as "", null, or string).
    try:
        subject_id = int(subject_id) if subject_id not in (None, '', 'null') else None
    except (TypeError, ValueError):
        subject_id = None

    subject = None
    if subject_id:
        subject = Subject.query.filter_by(
            id=subject_id, user_id=current_user.id
        ).first()

    # Fallback to the user's first active subject to avoid null subject inserts.
    if not subject:
        subject = Subject.query.filter_by(
            user_id=current_user.id,
            is_active=True,
        ).order_by(Subject.created_at.desc()).first()

    if not subject:
        return jsonify({
            'error': 'Please create a subject first, then ask Kai your question.'
        }), 400

    effective_subject_id = subject.id

    if subject:
        subject_name    = subject.name
        semester_length = subject.semester_length
        plan = subject.latest_plan

        if plan and subject.start_date:
            elapsed = (today - subject.start_date).days // 7 + 1
            current_week_num = min(max(elapsed, 1), subject.semester_length)

            week = Week.query.filter_by(
                study_plan_id=plan.id, week_number=current_week_num
            ).first()
            if week:
                topics_str = ', '.join(week.get_topics()) or 'No topics listed'

            upcoming = (
                Assignment.query
                .filter_by(subject_id=effective_subject_id, is_completed=False)
                .filter(Assignment.due_date >= today)
                .order_by(Assignment.due_date)
                .limit(3).all()
            )
            deadlines_str = (
                ', '.join(f"{a.title} (due {a.due_date})" for a in upcoming)
                or 'None upcoming'
            )

            next_exam = (
                Exam.query
                .filter_by(study_plan_id=plan.id)
                .filter(Exam.exam_date >= today)
                .order_by(Exam.exam_date)
                .first()
            )
            if next_exam:
                exam_str = f"{next_exam.name} on {next_exam.exam_date}"

        # Study material context from syllabi
        syllabi = Syllabus.query.filter_by(subject_id=effective_subject_id).order_by(Syllabus.uploaded_at.desc()).limit(2).all()
        for syllabus in syllabi:
            if syllabus.extracted_text:
                syllabus_context += f"\n\n=== SYLLABUS: {syllabus.original_filename} ===\n{syllabus.extracted_text[:4000]}\n"

        if syllabus_context:
            syllabus_context = f"\n*** FULL SYLLABUS CONTEXT (PRIMARY REFERENCE) ***\n{syllabus_context}\n*** END SYLLABUS ***"

    # Build user message with PDF / image context
    full_message = message
    if pdf_text:
        full_message = (
            f"[STUDENT UPLOADED PDF — USE AS PRIMARY SOURCE]\n"
            f"{pdf_text}\n\n"
            f"[STUDENT'S QUESTION]\n{message}"
        )
    elif image_text:
        full_message = (
            f"[Student uploaded a photo of their question/textbook]\n"
            f"{image_text}\n\n"
            f"Student's question: {message}"
        )

    system_prompt = _build_system_prompt(
        mode, current_user.name, subject_name,
        current_week_num, semester_length,
        topics_str, deadlines_str, exam_str,
        has_pdf=bool(pdf_text),
    )

    # Language instruction
    language_map = {
        'en': 'English',
        'bn': 'Bengali (বাংলা)',
        'hi': 'Hindi (हिन्दी)',
        'es': 'Spanish (Español)',
        'fr': 'French (Français)',
        'ar': 'Arabic (العربية)',
    }
    language = (language or 'en').strip().lower()
    if language not in language_map:
        language = 'en'

    if language != 'en':
        system_prompt += (
            f"\n\n🌐 IMPORTANT: Respond ENTIRELY in {language_map[language]}. "
            "Use English only for technical terms that have no natural translation."
        )

    # Recent conversation history (last 6 exchanges for context)
    history = AIConversation.query.filter_by(
        user_id=current_user.id,
        subject_id=effective_subject_id,
    ).order_by(AIConversation.created_at.desc()).limit(6).all()
    history.reverse()

    messages = [{'role': h.role, 'content': h.message} for h in history]
    messages.append({'role': 'user', 'content': full_message})

    try:
        from ai.groq_processor import chat_with_assistant
        response = chat_with_assistant(system_prompt, messages)

        # Save to DB — store original message (not the PDF-injected version)
        user_convo = AIConversation(
            user_id=current_user.id, 
            subject_id=effective_subject_id,
            role='user', message=message
        )
        db.session.add(user_convo)
        ai_entry = AIConversation(
            user_id=current_user.id, 
            subject_id=effective_subject_id,
            role='assistant', message=response
        )
        if mode != 'explain':
            ai_entry.mode = mode
        db.session.add(ai_entry)
        db.session.commit()

        return jsonify({
            'response':   response,
            'session_id': ai_entry.id,
            'mode':       mode,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Session API ───────────────────────────────────────────────────────────────

@assistant_bp.route('/api/assistant/session/<int:session_id>')
@login_required
def get_session(session_id):
    msg = AIConversation.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first_or_404()

    history = AIConversation.query.filter_by(
        user_id=current_user.id, subject_id=msg.subject_id
    ).order_by(AIConversation.created_at).all()

    return jsonify({
        'id':       session_id,
        'mode':     getattr(msg, 'mode', None) or 'explain',
        'topic':    msg.message if msg.role == 'user' else '',
        'messages': [{'role': h.role, 'content': h.message} for h in history],
    })

