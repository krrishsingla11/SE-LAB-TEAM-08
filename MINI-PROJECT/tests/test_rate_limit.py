"""Login rate limiting tests (SE8-42): TC-SEC-06 (STP section 13.9)."""
import uuid

import pytest

from app.middleware import rate_limit

PASSWORD = "StrongP@ss123"
WRONG_PASSWORD = "WrongP@ss999"


@pytest.fixture
def email(client):
    address = f"limit_{uuid.uuid4().hex[:8]}@pes.edu"
    resp = client.post(
        "/api/auth/register",
        json={"email": address, "password": PASSWORD, "full_name": "Limit Tester", "role": "buyer"},
    )
    assert resp.status_code == 201, resp.get_json()
    return address


def _login(client, email, password=WRONG_PASSWORD, ip=None):
    kwargs = {"environ_base": {"REMOTE_ADDR": ip}} if ip else {}
    return client.post("/api/auth/login", json={"email": email, "password": password}, **kwargs)


def test_tc_sec_06_sixth_failed_login_returns_429(client, email):
    """TC-SEC-06 (High) - OMH-SR-004
    Steps:    Send 6 consecutive failed login requests from the same IP.
    Expected: Requests 1 to 5 return 401; the 6th is blocked with 429.
    """
    statuses = [_login(client, email).status_code for _ in range(6)]
    assert statuses == [401, 401, 401, 401, 401, 429]


def test_blocked_response_format(client, email):
    for _ in range(5):
        _login(client, email)
    resp = _login(client, email)
    body = resp.get_json()
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0
    assert body["error"] == "TOO_MANY_REQUESTS"
    assert body["status_code"] == 429
    assert "timestamp" in body


def test_blocked_ip_cannot_login_even_with_correct_password(client, email):
    for _ in range(5):
        _login(client, email)
    assert _login(client, email, PASSWORD).status_code == 429


def test_successful_login_resets_the_counter(client, email):
    for _ in range(4):
        assert _login(client, email).status_code == 401
    assert _login(client, email, PASSWORD).status_code == 200

    statuses = [_login(client, email).status_code for _ in range(5)]
    assert statuses == [401] * 5


def test_limit_is_per_ip(client, email):
    for _ in range(5):
        _login(client, email, ip="10.0.0.1")
    assert _login(client, email, ip="10.0.0.1").status_code == 429
    assert _login(client, email, ip="10.0.0.2").status_code == 401


def test_block_ends_after_the_window(client, email, monkeypatch):
    for _ in range(5):
        _login(client, email)
    assert _login(client, email).status_code == 429

    monkeypatch.setattr(rate_limit, "WINDOW_SECONDS", -1)  # old failures count as expired
    assert _login(client, email).status_code == 401


def test_only_login_is_limited(client, email):
    for _ in range(6):
        _login(client, email)
    payload = {
        "email": "other@pes.edu",
        "password": PASSWORD,
        "full_name": "Other",
        "role": "buyer",
    }
    assert client.post("/api/auth/register", json=payload).status_code == 201
