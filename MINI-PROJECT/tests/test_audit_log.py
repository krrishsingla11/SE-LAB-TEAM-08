"""Structured audit logging tests (SE8-43): TC-SEC-07 (STP section 13.9)."""
import json
import logging
import uuid
from datetime import datetime, timedelta

import pytest
from flask_jwt_extended import decode_token

from app import audit_log

PASSWORD = "StrongP@ss123"


@pytest.fixture
def audit_entries(caplog):
    """Return a function that gives the audit log lines as parsed JSON."""
    caplog.set_level(logging.INFO, logger="audit")

    def read():
        return [json.loads(r.getMessage()) for r in caplog.records if r.name == "audit"]

    return read


def _register(client):
    email = f"audit_{uuid.uuid4().hex[:8]}@pes.edu"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Audit Tester", "role": "buyer"},
    )
    assert resp.status_code == 201, resp.get_json()
    return email


def _login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _event(entries, name):
    return [entry for entry in entries if entry["event"] == name]


def test_mask_hides_passwords_tokens_and_card_numbers():
    data = {
        "email": "a@pes.edu",
        "password": "Secret123!",
        "nested": {"access_token": "abc.def.ghi", "note": "card 4242424242424242 used"},
        "items": [{"payment_token": "tok_visa_success"}],
    }
    masked = audit_log.mask(data)
    assert masked["email"] == "a@pes.edu"
    assert masked["password"] == "***"
    assert masked["nested"]["access_token"] == "***"
    assert "4242424242424242" not in masked["nested"]["note"]
    assert masked["items"][0]["payment_token"] == "***"
    assert data["password"] == "Secret123!"  # the original is not changed


def test_tc_sec_07_login_is_logged_as_structured_json(client, audit_entries):
    """TC-SEC-07 (High) - OMH-SR-005
    Steps:    Execute a login; inspect the log output.
    Expected: JSON with a UTC timestamp and user id; password and token masked.
    """
    email = _register(client)
    assert _login(client, email).status_code == 200

    entry = _event(audit_entries(), "login")[0]
    assert entry["outcome"] == "success"
    assert entry["status_code"] == 200
    assert entry["user_id"] is not None
    assert entry["body"]["email"] == email
    assert entry["body"]["password"] == "***"

    stamp = datetime.fromisoformat(entry["timestamp"])
    assert stamp.utcoffset() == timedelta(0)


def test_secrets_never_appear_in_the_log(client, caplog, audit_entries):
    email = _register(client)
    token = _login(client, email).get_json()["token"]
    audit_entries()
    assert PASSWORD not in caplog.text
    assert token not in caplog.text


def test_failed_login_is_logged_without_a_user_id(client, audit_entries):
    email = _register(client)
    assert _login(client, email, "WrongP@ss999").status_code == 401

    entry = _event(audit_entries(), "login")[0]
    assert entry["outcome"] == "failure"
    assert entry["status_code"] == 401
    assert entry["user_id"] is None


def test_register_is_logged(client, audit_entries):
    email = _register(client)
    entry = _event(audit_entries(), "register")[0]
    assert entry["outcome"] == "success"
    assert entry["body"]["email"] == email
    assert entry["body"]["password"] == "***"


def test_product_attempt_is_logged_with_the_user_id(client, audit_entries):
    email = _register(client)
    token = _login(client, email).get_json()["token"]
    resp = client.post(
        "/api/products",
        json={"title": "Silk Scarf", "price": 450.00, "stock_qty": 20},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    entry = _event(audit_entries(), "product_created")[0]
    assert entry["outcome"] == "failure"
    assert entry["status_code"] == 403
    assert entry["user_id"] == decode_token(token)["sub"]


def test_health_check_is_not_logged(client, audit_entries):
    assert client.get("/api/health").status_code in (200, 503)
    assert audit_entries() == []
