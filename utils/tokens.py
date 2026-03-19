from typing import Optional, Dict, Any

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


def _get_serializer() -> URLSafeTimedSerializer:
    """Return a configured serializer for signing email tokens."""
    secret_key = current_app.config.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY is not configured")
    salt = current_app.config.get("SECURITY_TOKEN_SALT", "syllabus-engine-email")
    return URLSafeTimedSerializer(secret_key=secret_key, salt=salt)


def generate_token(payload: Dict[str, Any], purpose: str) -> str:
    """Generate a time-signed token for a specific purpose.

    payload is merged with a small metadata dict containing the purpose key.
    """
    data: Dict[str, Any] = {"p": purpose}
    if payload:
        data.update(payload)
    s = _get_serializer()
    return s.dumps(data)


def verify_token(token: str, purpose: str, max_age: int) -> Optional[Dict[str, Any]]:
    """Verify a token and return its payload dict or None if invalid/expired."""
    s = _get_serializer()
    try:
        data = s.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if data.get("p") != purpose:
        return None
    # Do not leak internal field name `p` to callers
    data.pop("p", None)
    return data
