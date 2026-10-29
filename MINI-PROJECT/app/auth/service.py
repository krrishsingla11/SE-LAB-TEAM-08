"""Authentication service (SE8-14 / OMH-F-001).

Implements user registration with bcrypt hashing (work factor 12),
payload validation, and duplicate email enforcement.
"""
import re

import bcrypt

from app.extensions import db
from app.models import Artisan, User

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
ALLOWED_PUBLIC_ROLES = {"buyer", "artisan", "seller"}


class AuthError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def hash_password(password: str) -> str:
    """Hash password using bcrypt with work factor 12 (OMH-SR-001)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def validate_registration_payload(data: dict):
    """Validate and sanitize registration payload fields.

    Returns:
        tuple: (email, password, full_name, role)
    Raises:
        AuthError: On missing or invalid input.
    """
    if not isinstance(data, dict):
        raise AuthError("INVALID_INPUT", "Request body must be a JSON object", 400)

    # 1. Email validation
    email = data.get("email")
    if email is None or not isinstance(email, str) or not email.strip():
        raise AuthError("INVALID_INPUT", "Email is required", 400)
    email = email.strip().lower()
    if len(email) > 255 or not EMAIL_REGEX.match(email):
        raise AuthError("INVALID_EMAIL", "Invalid email format", 400)

    # 2. Password validation (OMH-F-001, OMH-SR-001)
    password = data.get("password")
    if password is None or not isinstance(password, str):
        raise AuthError("INVALID_INPUT", "Password is required", 400)
    if (
        len(password) < 8
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[a-z]", password)
        or not re.search(r"[0-9]", password)
    ):
        raise AuthError(
            "INVALID_PASSWORD",
            "Password must be at least 8 characters long and contain at least "
            "one uppercase letter, one lowercase letter, and one number",
            400,
        )

    # 3. Full name validation
    full_name = data.get("full_name")
    if full_name is None or not isinstance(full_name, str) or not full_name.strip():
        raise AuthError("INVALID_INPUT", "Full name is required", 400)
    full_name = full_name.strip()
    if len(full_name) < 2 or len(full_name) > 120:
        raise AuthError("INVALID_INPUT", "Full name must be between 2 and 120 characters", 400)

    # 4. Role validation & privilege escalation prevention
    role = data.get("role")
    if role is None or not isinstance(role, str) or not role.strip():
        raise AuthError("INVALID_ROLE", "Role is required", 400)
    role = role.strip().lower()

    if role == "admin":
        raise AuthError("FORBIDDEN", "Registration as administrator is not permitted", 403)
    if role not in ALLOWED_PUBLIC_ROLES:
        raise AuthError("INVALID_ROLE", "Role must be 'buyer' or 'artisan'", 400)
    if role == "seller":
        role = "artisan"

    return email, password, full_name, role


def register_user(data: dict) -> dict:
    """Register a new user, hash credentials with bcrypt, and persist to DB.

    Returns:
        dict: Non-sensitive user summary (user_id, email, full_name, role).
    Raises:
        AuthError: On validation failure or duplicate email.
    """
    email, password, full_name, role = validate_registration_payload(data)

    # Enforce email uniqueness
    existing_user = db.session.scalar(db.select(User).where(User.email == email))
    if existing_user is not None:
        raise AuthError("CONFLICT", "Email already registered", 409)

    hashed_pw = hash_password(password)

    user = User(
        email=email,
        password_hash=hashed_pw,
        full_name=full_name,
        role=role,
    )
    db.session.add(user)

    # Optional artisan shop profile creation if shop_name provided
    shop_name = data.get("shop_name")
    if role == "artisan" and isinstance(shop_name, str) and shop_name.strip():
        db.session.flush()
        artisan = Artisan(
            user_id=user.user_id,
            shop_name=shop_name.strip()[:150],
        )
        db.session.add(artisan)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise AuthError("CONFLICT", "Email already registered", 409)

    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }
