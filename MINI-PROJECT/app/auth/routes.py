"""Authentication routes (SE8-14 / OMH-F-001)."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.auth import service
from app.auth.service import AuthError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.errorhandler(AuthError)
def handle_auth_error(e):
    body = {
        "error": e.code,
        "message": e.message,
        "status_code": e.status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(body), e.status


@bp.post("/register", strict_slashes=False)
def register():
    data = request.get_json(silent=True)
    if data is None:
        raise AuthError("INVALID_INPUT", "Request body must be valid JSON", 400)
    result = service.register_user(data)
    return jsonify(result), 201


@bp.post("/login", strict_slashes=False)
def login():
    data = request.get_json(silent=True)
    if data is None:
        raise AuthError("INVALID_INPUT", "Request body must be valid JSON", 400)
    result = service.login_user(data)
    return jsonify(result), 200
