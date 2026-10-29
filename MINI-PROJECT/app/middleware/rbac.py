"""RBAC middleware (SE8-16).

Usage:
    from app.middleware.rbac import role_required

    @bp.route("/api/seller/dashboard")
    @role_required("artisan")
    def dashboard(): ...

Rules (SAD / STP TC-AUTH-05, TC-SEC-04):
    - no token, or a bad / tampered / expired token  -> 401
    - valid token but the `role` claim is not allowed -> 403
    - the role is read from the `role` claim of the JWT
"""
from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError


def _error(code, message, status):
    # Keep this in ONE place. If the team's error JSON looks different
    # (see app/cart/routes.py), change only this function.
    return jsonify({"error": code, "message": message}), status


def role_required(*allowed_roles):
    """Allow the request only if the JWT `role` claim is in allowed_roles."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except (JWTExtendedException, PyJWTError):
                # missing, malformed, tampered or expired token
                return _error("UNAUTHORIZED", "Authentication required", 401)

            if get_jwt().get("role") not in allowed_roles:
                who = " or ".join(r.capitalize() for r in allowed_roles)
                return _error("FORBIDDEN", f"{who} privilege required", 403)

            return fn(*args, **kwargs)

        return wrapper

    return decorator