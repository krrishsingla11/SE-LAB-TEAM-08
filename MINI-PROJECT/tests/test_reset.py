"""Password reset tests (SE8-17): TC-AUTH-06 and TC-AUTH-07 (STP section 13.1)."""
import uuid

import pytest

from app.auth import reset

OLD_PASSWORD = "StrongP@ss123"
NEW_PASSWORD = "NewStr0ng@Pass1"


@pytest.fixture
def sent_emails(monkeypatch):
    """Replace the Mailtrap sender so the tests can read the token."""
    sent = []

    def fake_send(to_email, token):
        sent.append((to_email, token))
        return True

    monkeypatch.setattr(reset, "send_reset_email", fake_send)
    return sent


@pytest.fixture
def user_email(client):
    email = f"reset_{uuid.uuid4().hex[:8]}@pes.edu"
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": OLD_PASSWORD,
            "full_name": "Reset Tester",
            "role": "buyer",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    return email


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _request_token(client, sent_emails, email):
    resp = client.post("/api/auth/reset-password", json={"email": email})
    assert resp.status_code == 200, resp.get_json()
    assert sent_emails[-1][0] == email
    return sent_emails[-1][1]


def _confirm(client, token, password=NEW_PASSWORD):
    return client.post(
        "/api/auth/reset-password/confirm",
        json={"token": token, "new_password": password},
    )


def test_tc_auth_06_password_reset_flow(client, sent_emails, user_email):
    """TC-AUTH-06 (Medium) - OMH-F-004
    Steps:    POST /api/auth/reset-password; take the token; POST .../confirm.
    Expected: HTTP 200; password updated; login with the new password works.
    """
    resp = client.post("/api/auth/reset-password", json={"email": user_email})
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Reset email dispatched"

    token = sent_emails[-1][1]
    assert _confirm(client, token).status_code == 200

    assert _login(client, user_email, NEW_PASSWORD).status_code == 200
    assert _login(client, user_email, OLD_PASSWORD).status_code == 401


def test_tc_auth_07_password_reset_expired_token(
    client, sent_emails, user_email, monkeypatch
):
    """TC-AUTH-07 (Medium) - OMH-F-004
    Steps:    Submit an expired token to /api/auth/reset-password/confirm.
    Expected: HTTP 400; error 'Reset token has expired'; password unchanged.
    """
    token = _request_token(client, sent_emails, user_email)
    monkeypatch.setattr(reset, "TOKEN_MAX_AGE_SECONDS", -1)  # token is now too old

    resp = _confirm(client, token)
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Reset token has expired"
    assert _login(client, user_email, OLD_PASSWORD).status_code == 200


def test_reset_token_lifetime_is_15_minutes():
    assert reset.TOKEN_MAX_AGE_SECONDS == 15 * 60


def test_reset_unknown_email_returns_404(client, sent_emails):
    resp = client.post("/api/auth/reset-password", json={"email": "nobody@pes.edu"})
    assert resp.status_code == 404
    assert sent_emails == []


def test_reset_token_can_only_be_used_once(client, sent_emails, user_email):
    token = _request_token(client, sent_emails, user_email)
    assert _confirm(client, token).status_code == 200
    assert _confirm(client, token, "AnotherP@ss456").status_code == 400


def test_reset_rejects_invalid_token(client):
    resp = _confirm(client, "not-a-real-token")
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "Invalid reset token"


def test_reset_rejects_short_password(client, sent_emails, user_email):
    token = _request_token(client, sent_emails, user_email)
    assert _confirm(client, token, "short").status_code == 422
    assert _login(client, user_email, OLD_PASSWORD).status_code == 200
