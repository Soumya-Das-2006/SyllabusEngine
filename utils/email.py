from flask import current_app, render_template, url_for

from integrations.email import send_email as _send_raw_email
from utils.tokens import generate_token

APP_NAME = "Syllabus-to-Success Engine"


def _logo_url() -> str:
    return current_app.config.get("EMAIL_LOGO_URL", "https://yourdomain.com/static/logo.png")


def _render(template_name: str, **context) -> str:
    base_ctx = {
        "app_name": APP_NAME,
        "logo_url": _logo_url(),
    }
    base_ctx.update(context)
    return render_template(template_name, **base_ctx)


def _send(to_address: str, subject: str, html_body: str) -> bool:
    """Send an HTML email using the shared low-level sender.

    All emails are sent from the configured noreply sender (MAIL_DEFAULT_SENDER).
    """
    return _send_raw_email(to_address, subject, html_body)


def send_verification_email(user) -> bool:
    """Send signup verification email with a signed token."""
    token = generate_token({"uid": user.id, "email": user.email}, purpose="verify-email")
    verify_url = url_for("auth.verify_email", token=token, _external=True)
    html = _render("email/verify.html", user=user, verify_url=verify_url)
    subject = f"Verify your email for {APP_NAME}"
    return _send(user.email, subject, html)


def send_password_reset_email(user) -> bool:
    """Send password reset email with a time-limited token."""
    token = generate_token({"uid": user.id, "email": user.email}, purpose="reset-password")
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    html = _render("email/reset.html", user=user, reset_url=reset_url)
    subject = f"Reset your {APP_NAME} password"
    return _send(user.email, subject, html)
