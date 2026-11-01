"""Password reset (SE8-17 / OMH-F-004).

POST /api/auth/reset-password          {"email"}                  -> 200 / 404
POST /api/auth/reset-password/confirm  {"token", "new_password"}  -> 200 / 400

The reset token is a signed, time-limited token (15 minutes). It contains a
fingerprint of the current password hash, so it stops working after the
password is changed (single use). The email is sent through Mailtrap (SMTP).
"""
import hashlib
import logging
import os
import smtplib
from email.message import EmailMessage

import bcrypt
from flask import current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.auth.service import AuthError
from app.extensions import db
from app.models import User

logger = logging.getLogger(__name__)

TOKEN_MAX_AGE_SECONDS = 15 * 60
MIN_PASSWORD_LENGTH = 8
_SALT = "password-reset"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt=_SALT)


def _fingerprint(password_hash):
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def make_reset_token(user):
    return _serializer().dumps(
        {"uid": user.user_id, "fp": _fingerprint(user.password_hash)}
    )


def send_reset_email(to_email, token):
    """Send the reset link through Mailtrap. Returns True if an email was sent."""
    username = os.getenv("MAILTRAP_USER")
    password = os.getenv("MAILTRAP_PASS")
    if not username or not password:
        logger.warning("Mailtrap credentials are not set; reset email not sent")
        return False

    host = os.getenv("MAILTRAP_HOST", "sandbox.smtp.mailtrap.io")
    port = int(os.getenv("MAILTRAP_PORT", "2525"))
    base_url = os.getenv("FRONTEND_URL", "http://localhost:5000")

    msg = EmailMessage()
    msg["Subject"] = "Reset your password"
    msg["From"] = os.getenv("MAIL_FROM", "no-reply@marketplace.test")
    msg["To"] = to_email
    msg.set_content(
        "Use this link within 15 minutes to reset your password:\n"
        f"{base_url}/reset-password?token={token}\n\n"
        "If you did not ask for this, you can ignore this email."
    )
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(msg)
    return True


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AuthError("INVALID_INPUT", "Request body must be valid JSON", 400)
    return data


def register_reset_routes(bp):
    """Add the two reset routes to the auth blueprint."""

    @bp.post("/reset-password", strict_slashes=False)
    def request_reset():
        data = _json_body()
        email = str(data.get("email") or "").strip().lower()
        if not email:
            raise AuthError("INVALID_INPUT", "Email is required", 422)

        user = db.session.scalar(db.select(User).where(User.email == email))
        if user is None:
            raise AuthError("NOT_FOUND", "Email not registered", 404)

        try:
            send_reset_email(user.email, make_reset_token(user))
        except (OSError, smtplib.SMTPException):
            logger.exception("Could not send the reset email")
            raise AuthError("EMAIL_FAILED", "Could not send reset email", 503) from None
        return jsonify({"message": "Reset email dispatched"}), 200

    @bp.post("/reset-password/confirm", strict_slashes=False)
    def confirm_reset():
        data = _json_body()
        token = data.get("token")
        new_password = data.get("new_password") or data.get("password")
        if not token or not isinstance(token, str):
            raise AuthError("INVALID_INPUT", "Reset token is required", 422)
        if not isinstance(new_password, str) or len(new_password) < MIN_PASSWORD_LENGTH:
            raise AuthError(
                "INVALID_INPUT", "Password must be at least 8 characters", 422
            )
        if len(new_password.encode()) > 72:
            raise AuthError("INVALID_INPUT", "Password is too long", 422)

        try:
            payload = _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        except SignatureExpired:
            raise AuthError("TOKEN_EXPIRED", "Reset token has expired", 400) from None
        except BadSignature:
            raise AuthError("INVALID_TOKEN", "Invalid reset token", 400) from None

        user_id = payload.get("uid")
        user = db.session.get(User, user_id) if user_id is not None else None
        if user is None or payload.get("fp") != _fingerprint(user.password_hash):
            raise AuthError("INVALID_TOKEN", "Invalid reset token", 400)

        user.password_hash = bcrypt.hashpw(
            new_password.encode(), bcrypt.gensalt(12)
        ).decode()
        db.session.commit()
        return jsonify({"message": "Password updated"}), 200
