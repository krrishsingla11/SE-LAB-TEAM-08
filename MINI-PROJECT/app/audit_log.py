"""Structured audit logging (SE8-43 / OMH-SR-005, STP TC-SEC-07).

Every important API call writes ONE JSON line to stdout, for example:
  {"timestamp": "2026-11-04T09:15:02+00:00", "level": "INFO", "event": "login",
   "user_id": "7", "outcome": "success", "status_code": 200, "method": "POST",
   "path": "/api/auth/login", "ip": "127.0.0.1", "body": {"email": "a@b.c", "password": "***"}}

Timestamps are UTC. Passwords, tokens and card-like numbers are masked.
Use it by calling setup_audit_logging(app) inside create_app().
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone

from flask import request
from flask_jwt_extended import decode_token, get_jwt_identity, verify_jwt_in_request

logger = logging.getLogger("audit")

MASK = "***"
SENSITIVE_KEYS = {
    "password", "new_password", "token", "access_token", "authorization",
    "payment_token", "card_number", "cvv", "secret",
}
_CARD_NUMBER = re.compile(r"\b\d{13,19}\b")

AUDIT_EVENTS = {
    ("POST", "/api/auth/register"): "register",
    ("POST", "/api/auth/login"): "login",
    ("POST", "/api/auth/reset-password"): "password_reset_requested",
    ("POST", "/api/auth/reset-password/confirm"): "password_reset_confirmed",
    ("POST", "/api/products"): "product_created",
    ("POST", "/api/checkout"): "checkout",
    ("POST", "/api/payments/charge"): "payment_charge",
}


def mask(value):
    """Return a copy of value with sensitive fields and card-like numbers hidden."""
    if isinstance(value, dict):
        return {
            key: MASK if str(key).lower() in SENSITIVE_KEYS else mask(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask(item) for item in value]
    if isinstance(value, str):
        return _CARD_NUMBER.sub(MASK, value)
    return value


def log_event(event, user_id=None, **details):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "event": event,
        "user_id": user_id,
    }
    entry.update(mask(details))
    logger.info(json.dumps(entry, default=str))


def _configure_logger():
    logger.setLevel(logging.INFO)
    if any(getattr(handler, "_audit", False) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler._audit = True
    logger.addHandler(handler)


def _user_id(event, response):
    """The user id from the request token, or from the new token after a login."""
    try:
        if event == "login" and response.status_code == 200:
            data = response.get_json(silent=True) or {}
            return decode_token(data["token"])["sub"]
        verify_jwt_in_request(optional=True)
        return get_jwt_identity()
    except Exception:  # a bad or missing token must never break the response
        return None


def setup_audit_logging(app):
    _configure_logger()

    @app.after_request
    def audit_request(response):
        key = (request.method, request.path.rstrip("/") or "/")
        event = AUDIT_EVENTS.get(key)
        if event is None:
            return response

        body = request.get_json(silent=True)
        log_event(
            event,
            user_id=_user_id(event, response),
            outcome="success" if response.status_code < 400 else "failure",
            status_code=response.status_code,
            method=request.method,
            path=request.path,
            ip=request.remote_addr,
            body=body if isinstance(body, dict) else {},
        )
        return response
