import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()   # loads .env file when running locally


class Config:
    # ── Core ──────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'syllabus-engine-dev-secret-change-in-production')

    # ── Database ──────────────────────────────────────────────────────────
    # SQLite locally, PostgreSQL on Render (DATABASE_URL env var set automatically)
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///syllabus_engine.db')
    # Render uses postgres:// but SQLAlchemy needs postgresql://
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI       = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── File uploads ──────────────────────────────────────────────────────
    UPLOAD_FOLDER       = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH  = 16 * 1024 * 1024   # 16 MB max upload
    ALLOWED_EXTENSIONS  = {'pdf'}

    # ── Sessions ──────────────────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # ── Groq AI ───────────────────────────────────────────────────────────
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    GROQ_MODEL   = 'llama3-70b-8192'

    # ── Email (SMTP only) ────────────────────────────────────────────────
    # SENDGRID_API_KEY can exist in env but is not used when running SMTP-only.
    SENDGRID_API_KEY    = os.environ.get('SENDGRID_API_KEY', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'Syllabus Engine <noreply@syllabusengine.com>')
    # All integrations use MAIL_FROM as the from-address, always the noreply alias
    MAIL_FROM           = MAIL_DEFAULT_SENDER
    EMAIL_LOGO_URL      = os.environ.get('EMAIL_LOGO_URL', 'https://yourdomain.com/static/logo.png')

    # Optional raw SMTP settings (used when SENDGRID_API_KEY is empty)
    SMTP_HOST     = os.environ.get('SMTP_HOST') or os.environ.get('MAIL_SERVER', '')
    SMTP_PORT     = int(os.environ.get('SMTP_PORT') or os.environ.get('MAIL_PORT', '587'))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME') or os.environ.get('MAIL_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or os.environ.get('MAIL_PASSWORD', '')
    SMTP_USE_TLS  = (os.environ.get('SMTP_USE_TLS') or os.environ.get('MAIL_USE_TLS', 'true')).lower() == 'true'

    # ── Google Calendar OAuth ─────────────────────────────────────────────
    GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

    # Create upload folder if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
