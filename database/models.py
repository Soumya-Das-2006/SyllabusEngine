from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import secrets

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), default='student')
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_expires = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    google_calendar_token = db.Column(db.Text, nullable=True)
    email_preferences = db.Column(db.Text, default='{"weekly_preview":true,"monday_alert":true,"exam_warning":true}')

    # ── Profile completion fields (NEW) ──────────────────────────────────
    college    = db.Column(db.String(200), nullable=True)
    course     = db.Column(db.String(100), nullable=True)
    year       = db.Column(db.String(20),  nullable=True)
    phone      = db.Column(db.String(20),  nullable=True)
    avatar     = db.Column(db.String(300), default='default_avatar.png')
    bio        = db.Column(db.Text,        nullable=True)
    dark_mode  = db.Column(db.Boolean,     default=False)
    last_seen  = db.Column(db.DateTime,    default=datetime.utcnow)

    subjects      = db.relationship('Subject', backref='user', lazy=True, cascade='all, delete-orphan')
    notes         = db.relationship('Note', backref='user', lazy=True, cascade='all, delete-orphan')
    chat_messages  = db.relationship('ChatMessage',   backref='user', lazy=True, cascade='all, delete-orphan')
    notifications  = db.relationship('Notification',  backref='user', lazy=True, cascade='all, delete-orphan')
    activity_logs  = db.relationship('ActivityLog',   backref='user', lazy=True, cascade='all, delete-orphan')
    certificates   = db.relationship('Certificate',   backref='user', lazy=True, cascade='all, delete-orphan')
    quiz_attempts  = db.relationship('UserQuizAttempt', backref='user', lazy=True, cascade='all, delete-orphan')
    attendance_records = db.relationship('AttendanceRecord', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    @property
    def is_student(self):
        return self.role == 'student'
    def get_email_prefs(self):
        return json.loads(self.email_preferences)

    @property
    def profile_complete(self):
        return all([self.name, self.email, self.college, self.course, self.year])

    @property
    def profile_pct(self):
        fields = [self.name, self.email, self.college, self.course, self.year,
                  self.phone, self.avatar != 'default_avatar.png']
        return int(sum(bool(f) for f in fields) / len(fields) * 100)

    @property
    def unread_notifications(self):
        return self.notifications.filter_by(is_read=False).count()

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_expires = datetime.utcnow() + timedelta(hours=24)
        db.session.commit()

    def confirm_reset_token(self, token):
        if self.reset_token and self.reset_token == token \
           and self.reset_expires > datetime.utcnow():
            return True
        return False


class Subject(db.Model):
    __tablename__ = 'subjects'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name            = db.Column(db.String(200), nullable=False)
    color           = db.Column(db.String(7), default='#6366f1')
    semester_length = db.Column(db.Integer, default=15)
    start_date      = db.Column(db.Date, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    is_active       = db.Column(db.Boolean, default=True)

    syllabi         = db.relationship('Syllabus', backref='subject', lazy=True, cascade='all, delete-orphan')
    study_plans     = db.relationship('StudyPlan', backref='subject', lazy=True, cascade='all, delete-orphan')
    assignments     = db.relationship('Assignment', backref='subject', lazy=True, cascade='all, delete-orphan')
    calendar_events = db.relationship('CalendarEvent', backref='subject', lazy=True, cascade='all, delete-orphan')
    conversations   = db.relationship('AIConversation', backref='subject', lazy=True, cascade='all, delete-orphan')
    notes           = db.relationship('Note', backref='subject', lazy=True, cascade='all, delete-orphan')

    @property
    def latest_plan(self):
        return StudyPlan.query.filter_by(subject_id=self.id).order_by(StudyPlan.generated_at.desc()).first()

    @property
    def completion_pct(self):
        plan = self.latest_plan
        if not plan:
            return 0
        total = Week.query.filter_by(study_plan_id=plan.id).count()
        if total == 0:
            return 0
        completed = Progress.query.filter_by(subject_id=self.id, is_completed=True).count()
        return min(100, int((completed / (total * 3)) * 100))


class Syllabus(db.Model):
    __tablename__ = 'syllabi'
    id                 = db.Column(db.Integer, primary_key=True)
    subject_id         = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    file_path          = db.Column(db.String(500), nullable=False)
    original_filename  = db.Column(db.String(200))
    uploaded_at        = db.Column(db.DateTime, default=datetime.utcnow)
    processing_status  = db.Column(db.String(50), default='queued')
    ocr_used           = db.Column(db.Boolean, default=False)
    confidence_score   = db.Column(db.Float, default=0.0)
    extracted_text     = db.Column(db.Text, nullable=True)
    raw_ai_output      = db.Column(db.Text, nullable=True)
    error_message      = db.Column(db.Text, nullable=True)


class StudyPlan(db.Model):
    __tablename__ = 'study_plans'
    id           = db.Column(db.Integer, primary_key=True)
    subject_id   = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    syllabus_id  = db.Column(db.Integer, db.ForeignKey('syllabi.id'), nullable=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    course_title = db.Column(db.String(200))
    instructor   = db.Column(db.String(200))
    json_raw     = db.Column(db.Text)

    weeks = db.relationship('Week', backref='study_plan', lazy=True, cascade='all, delete-orphan', order_by='Week.week_number')
    exams = db.relationship('Exam', backref='study_plan', lazy=True, cascade='all, delete-orphan')

    def get_json(self):
        return json.loads(self.json_raw) if self.json_raw else {}


class Week(db.Model):
    __tablename__ = 'weeks'
    id                = db.Column(db.Integer, primary_key=True)
    study_plan_id     = db.Column(db.Integer, db.ForeignKey('study_plans.id'), nullable=False)
    week_number       = db.Column(db.Integer, nullable=False)
    date_start        = db.Column(db.Date, nullable=True)
    date_end          = db.Column(db.Date, nullable=True)
    topics            = db.Column(db.Text, default='[]')
    key_concepts      = db.Column(db.Text, default='[]')
    difficulty        = db.Column(db.String(20), default='medium')
    recommended_hours = db.Column(db.Integer, default=6)
    readings          = db.Column(db.Text, default='[]')
    revision_tasks    = db.Column(db.Text, default='[]')
    study_advice      = db.Column(db.Text)
    is_exam_week      = db.Column(db.Boolean, default=False)
    completion_pct    = db.Column(db.Integer, default=0)

    assignments = db.relationship('Assignment', backref='week', lazy=True)

    def get_topics(self):       return json.loads(self.topics) if self.topics else []
    def get_concepts(self):     return json.loads(self.key_concepts) if self.key_concepts else []
    def get_readings(self):     return json.loads(self.readings) if self.readings else []
    def get_revision_tasks(self): return json.loads(self.revision_tasks) if self.revision_tasks else []


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id                = db.Column(db.Integer, primary_key=True)
    week_id           = db.Column(db.Integer, db.ForeignKey('weeks.id'), nullable=True)
    subject_id        = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    title             = db.Column(db.String(300), nullable=False)
    description       = db.Column(db.Text)
    due_date          = db.Column(db.Date, nullable=True)
    estimated_hours   = db.Column(db.Float, default=2.0)
    preparation_steps = db.Column(db.Text, default='[]')
    is_completed      = db.Column(db.Boolean, default=False)
    confidence        = db.Column(db.String(10), default='high')
    google_event_id   = db.Column(db.String(200))

    def get_steps(self):
        return json.loads(self.preparation_steps) if self.preparation_steps else []


class Exam(db.Model):
    __tablename__ = 'exams'
    id               = db.Column(db.Integer, primary_key=True)
    study_plan_id    = db.Column(db.Integer, db.ForeignKey('study_plans.id'), nullable=False)
    name             = db.Column(db.String(200), nullable=False)
    exam_date        = db.Column(db.Date, nullable=True)
    coverage_weeks   = db.Column(db.Text, default='[]')
    preparation_plan = db.Column(db.Text)
    is_completed     = db.Column(db.Boolean, default=False)
    confidence       = db.Column(db.String(10), default='high')
    google_event_id  = db.Column(db.String(200))

    def get_coverage(self):
        return json.loads(self.coverage_weeks) if self.coverage_weeks else []


class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id       = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    event_type       = db.Column(db.String(30))
    title            = db.Column(db.String(300))
    description      = db.Column(db.Text)
    event_date       = db.Column(db.Date)
    duration_minutes = db.Column(db.Integer, default=60)
    google_event_id  = db.Column(db.String(200))
    synced_at        = db.Column(db.DateTime)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


class Progress(db.Model):
    __tablename__ = 'progress'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id    = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    week_id       = db.Column(db.Integer, db.ForeignKey('weeks.id'), nullable=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=True)
    item_type     = db.Column(db.String(30))
    item_key      = db.Column(db.String(200))
    is_completed  = db.Column(db.Boolean, default=False)
    marked_at     = db.Column(db.DateTime, default=datetime.utcnow)


class AIConversation(db.Model):
    __tablename__ = 'ai_conversations'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    role       = db.Column(db.String(10))
    message    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OAuthToken(db.Model):
    __tablename__ = 'oauth_tokens'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider   = db.Column(db.String(30), default='google')
    token_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─────────────────────── QUIZ ───────────────────────────────────────────────

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id       = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title            = db.Column(db.String(300), nullable=False)
    topic            = db.Column(db.String(300), nullable=True)
    description      = db.Column(db.Text, nullable=True)
    difficulty       = db.Column(db.String(20), default='medium')
    num_questions    = db.Column(db.Integer, default=5)
    cache_key        = db.Column(db.String(500), unique=True, nullable=True)
    # Admin-managed quiz fields
    duration_minutes = db.Column(db.Integer, default=30)
    pass_marks       = db.Column(db.Integer, default=50)
    total_marks      = db.Column(db.Integer, default=0)
    max_violations   = db.Column(db.Integer, default=3)
    fullscreen_req   = db.Column(db.Boolean, default=True)
    webcam_req       = db.Column(db.Boolean, default=False)
    shuffle_q        = db.Column(db.Boolean, default=True)
    is_active        = db.Column(db.Boolean, default=True)
    starts_at        = db.Column(db.DateTime, nullable=True)
    ends_at          = db.Column(db.DateTime, nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship('Question', backref='quiz', lazy=True, cascade='all, delete-orphan')
    attempts  = db.relationship('UserQuizAttempt', backref='quiz', lazy=True, cascade='all, delete-orphan')

    @property
    def subject(self):
        return Subject.query.get(self.subject_id) if self.subject_id else None


class Question(db.Model):
    __tablename__ = 'questions'
    id             = db.Column(db.Integer, primary_key=True)
    quiz_id        = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    question_text  = db.Column(db.Text, nullable=False)
    option_a       = db.Column(db.String(500), nullable=False)
    option_b       = db.Column(db.String(500), nullable=False)
    option_c       = db.Column(db.String(500), nullable=False)
    option_d       = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    explanation    = db.Column(db.Text)
    difficulty     = db.Column(db.String(20), default='medium')
    topic_tag      = db.Column(db.String(200))
    order_index    = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id, 'question': self.question_text,
            'options': {'A': self.option_a, 'B': self.option_b, 'C': self.option_c, 'D': self.option_d},
            'correct_answer': self.correct_answer, 'explanation': self.explanation,
            'difficulty': self.difficulty, 'topic_tag': self.topic_tag,
        }


class UserQuizAttempt(db.Model):
    __tablename__ = 'user_quiz_attempts'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id         = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    subject_id      = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    score           = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    accuracy_pct    = db.Column(db.Float, default=0.0)
    time_taken_sec  = db.Column(db.Integer, default=0)
    difficulty_used = db.Column(db.String(20), default='medium')
    answers_json    = db.Column(db.Text, default='{}')
    violation_log  = db.Column(db.Text, default='[]')
    violations     = db.Column(db.Integer, default=0)
    status         = db.Column(db.String(20), default='in_progress')
    passed         = db.Column(db.Boolean, default=False)
    wrong_topics    = db.Column(db.Text, default='[]')
    completed_at    = db.Column(db.DateTime, default=datetime.utcnow)
    started_at      = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at    = db.Column(db.DateTime, nullable=True)
    auto_submitted  = db.Column(db.Boolean, default=False)
    total_marks     = db.Column(db.Integer, default=0)
    ip_address      = db.Column(db.String(50), nullable=True)

    def get_answers(self):     return json.loads(self.answers_json) if self.answers_json else {}
    def get_wrong_topics(self): return json.loads(self.wrong_topics) if self.wrong_topics else []


class TopicPerformance(db.Model):
    __tablename__ = 'topic_performance'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id     = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    topic          = db.Column(db.String(300), nullable=False)
    attempts       = db.Column(db.Integer, default=0)
    correct_count  = db.Column(db.Integer, default=0)
    wrong_count    = db.Column(db.Integer, default=0)
    accuracy_pct   = db.Column(db.Float, default=0.0)
    last_attempted = db.Column(db.DateTime, default=datetime.utcnow)

    def update_stats(self, correct: bool):
        self.attempts = (self.attempts or 0) + 1
        self.last_attempted = datetime.utcnow()
        if correct:
            self.correct_count = (self.correct_count or 0) + 1
        else:
            self.wrong_count = (self.wrong_count or 0) + 1
        self.accuracy_pct = ((self.correct_count or 0) / self.attempts) * 100 if self.attempts > 0 else 0.0


# ─────────────────────── ANALYTICS ─────────────────────────────────────────

class StudyAnalytics(db.Model):
    __tablename__ = 'study_analytics'
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id        = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    completion_rate   = db.Column(db.Float, default=0.0)
    consistency_score = db.Column(db.Float, default=0.0)
    avg_score         = db.Column(db.Float, default=0.0)
    total_quiz_taken  = db.Column(db.Integer, default=0)
    weak_topics       = db.Column(db.Text, default='[]')
    active_days       = db.Column(db.Integer, default=0)
    last_updated      = db.Column(db.DateTime, default=datetime.utcnow)

    def get_weak_topics(self):
        return json.loads(self.weak_topics) if self.weak_topics else []


# ─────────────────────── SCHEDULE ───────────────────────────────────────────

class StudySchedule(db.Model):
    __tablename__ = 'study_schedules'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    date       = db.Column(db.Date, nullable=False)
    topic      = db.Column(db.String(400), nullable=False)
    duration   = db.Column(db.Integer, default=60)
    priority   = db.Column(db.Float, default=0.5)
    difficulty = db.Column(db.String(20), default='medium')
    is_done    = db.Column(db.Boolean, default=False)
    time_slot  = db.Column(db.String(50), nullable=True)
    notes      = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────── NOTES ──────────────────────────────────────────────

class Note(db.Model):
    __tablename__ = 'notes'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title      = db.Column(db.String(300), nullable=False)
    content    = db.Column(db.Text, default='')
    tags       = db.Column(db.String(500), default='')
    color      = db.Column(db.String(7), default='#ffffff')
    is_pinned  = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_tags(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()] if self.tags else []


# ─────────────────────── CHAT ───────────────────────────────────────────────

class ChatRoom(db.Model):
    __tablename__ = 'chat_rooms'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_public  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship('ChatMessage', backref='room', lazy=True, cascade='all, delete-orphan')


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id         = db.Column(db.Integer, primary_key=True)
    room_id    = db.Column(db.Integer, db.ForeignKey('chat_rooms.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'room_id': self.room_id,
            'user_id': self.user_id, 'username': self.user.name,
            'message': self.message,
            'created_at': self.created_at.strftime('%H:%M'),
        }


# 
# ─────────────────────── PUBLIC CMS MODELS ────────────────────────────────
# 

class News(db.Model):
    __tablename__ = 'news'
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    summary    = db.Column(db.String(500))
    content    = db.Column(db.Text, nullable=False)
    image_url  = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Testimonial(db.Model):
    __tablename__ = 'testimonials'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    photo_url  = db.Column(db.String(300))
    feedback   = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read    = db.Column(db.Boolean, default=False)


# ─────────────────────── NOTIFICATION (NEW) ─────────────────────────────────

class Notification(db.Model):
    __tablename__ = 'notifications'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title      = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text)
    notif_type = db.Column(db.String(30), default='info')  # info|quiz|result|warning|broadcast
    link       = db.Column(db.String(300))
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────── ACTIVITY LOG (NEW) ─────────────────────────────────

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action     = db.Column(db.String(100), nullable=False)
    detail     = db.Column(db.Text)
    ip         = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# ─────────────────────── CERTIFICATE (NEW) ──────────────────────────────────

class Certificate(db.Model):
    __tablename__ = 'certificates'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id     = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=True)
    attempt_id  = db.Column(db.Integer, db.ForeignKey('user_quiz_attempts.id'), nullable=True)
    title       = db.Column(db.String(300), nullable=False)
    file_path   = db.Column(db.String(500))
    cert_number = db.Column(db.String(50), unique=True)
    issued_at   = db.Column(db.DateTime, default=datetime.utcnow)

# ─────────────────────── ATTENDANCE (NEW) ──────────────────────────────────

class AttendanceSession(db.Model):
    """Admin creates a session; students are auto-marked or manually updated."""
    __tablename__ = 'attendance_sessions'
    id         = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title      = db.Column(db.String(200), nullable=False, default='Class')
    date       = db.Column(db.Date, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    records = db.relationship('AttendanceRecord', backref='session', lazy='dynamic', cascade='all,delete-orphan')


class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_sessions.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status     = db.Column(db.String(20), default='present')  # present|absent|late
    note       = db.Column(db.String(200))
    marked_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_attendance_records_session_user', 'session_id', 'user_id'),
        db.UniqueConstraint('session_id', 'user_id', name='unique_attendance_per_session')
    )


