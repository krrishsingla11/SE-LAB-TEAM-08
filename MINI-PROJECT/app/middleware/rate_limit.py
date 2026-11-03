"""Login rate limiter (SE8-42 / OMH-SR-004, STP TC-SEC-06).

An IP address may make 5 failed logins within the window (10 minutes). The
next login request from that IP is blocked with HTTP 429 and a Retry-After
header. A successful login clears the counter.

The counters live on the Flask app object (app.extensions), so every app
created in the tests starts with a clean state. Set RATE_LIMIT_ENABLED=False
in the app config to switch the limiter off.
"""
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import current_app, jsonify, request

LOGIN_PATH = "/api/auth/login"
MAX_FAILED_ATTEMPTS = 5
WINDOW_SECONDS = 10 * 60


def _failures():
    return current_app.extensions.setdefault("login_failures", defaultdict(deque))


def _is_login_request():
    if not current_app.config.get("RATE_LIMIT_ENABLED", True):
        return False
    return request.method == "POST" and request.path.rstrip("/") == LOGIN_PATH


def _recent_failures(ip, now):
    attempts = _failures()[ip]
    while attempts and now - attempts[0] > WINDOW_SECONDS:
        attempts.popleft()
    return attempts


def register_login_rate_limit(bp):
    """Attach the limiter to the auth blueprint."""

    @bp.before_request
    def block_if_limited():
        if not _is_login_request():
            return None
        now = time.monotonic()
        attempts = _recent_failures(request.remote_addr, now)
        if len(attempts) < MAX_FAILED_ATTEMPTS:
            return None

        retry_after = max(1, int(WINDOW_SECONDS - (now - attempts[0])))
        response = jsonify(
            {
                "error": "TOO_MANY_REQUESTS",
                "message": "Too many failed login attempts. Try again later.",
                "status_code": 429,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response

    @bp.after_request
    def record_login_result(response):
        if not _is_login_request():
            return response
        ip = request.remote_addr
        if response.status_code == 401:
            now = time.monotonic()
            _recent_failures(ip, now).append(now)
        elif response.status_code == 200:
            _failures().pop(ip, None)
        return response
