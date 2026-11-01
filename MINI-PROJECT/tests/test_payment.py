"""Payment tests (mock gateway) - STP section 13.4 (TC-PAY-01..03).

Note: the route is POST /api/payments/charge (the STP says /api/checkout) and the
mock gateway returns payment_status 'captured' with a random TXN-MOCK-... reference.
"""
import uuid

import pytest

from app.extensions import db
from app.models import Order

PASSWORD = "StrongP@ss123"
CHARGE_URL = "/api/payments/charge"


@pytest.fixture
def buyer_headers(client):
    email = f"pay_{uuid.uuid4().hex[:8]}@pes.edu"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Pay Tester", "role": "buyer"},
    )
    assert reg.status_code == 201, reg.get_json()
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.get_json()
    return {"Authorization": f"Bearer {login.get_json()['token']}"}


def _charge(client, headers, token, amount=450.00, idempotency_key=None):
    headers = dict(headers)
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return client.post(
        CHARGE_URL, json={"amount": amount, "payment_token": token}, headers=headers
    )


def test_tc_pay_01_payment_success_mock_stub(client, buyer_headers):
    """TC-PAY-01 (High) - OMH-F-010
    Steps:    POST /api/payments/charge with payment token 'tok_visa_success'.
    Expected: HTTP 201; payment captured; transaction reference 'TXN-MOCK-...'.
    """
    resp = _charge(client, buyer_headers, "tok_visa_success")
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["payment_status"] == "captured"
    assert body["transaction_ref"].startswith("TXN-MOCK-")
    assert body["amount"] == 450.0


def test_tc_pay_02_payment_declined(client, buyer_headers):
    """TC-PAY-02 (High) - OMH-F-010
    Steps:    POST /api/payments/charge with payment token 'tok_charge_declined'.
    Expected: HTTP 402; error 'Card declined'; no order created.
    """
    resp = _charge(client, buyer_headers, "tok_charge_declined")
    assert resp.status_code == 402
    body = resp.get_json()
    assert body["error"] == "CARD_DECLINED"
    assert body["message"] == "Card declined"

    orders = db.session.scalar(db.select(db.func.count()).select_from(Order))
    assert orders == 0


def test_tc_pay_03_idempotent_payment_retry(client, buyer_headers):
    """TC-PAY-03 (Medium) - OMH-F-010
    Steps:    POST the same charge twice with the same Idempotency-Key.
    Expected: both succeed with the same transaction reference (no second charge).
    """
    key = f"idem-{uuid.uuid4().hex}"
    first = _charge(client, buyer_headers, "tok_visa_success", idempotency_key=key)
    second = _charge(client, buyer_headers, "tok_visa_success", idempotency_key=key)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["transaction_ref"] == second.get_json()["transaction_ref"]

    other = _charge(client, buyer_headers, "tok_visa_success", idempotency_key="idem-other")
    assert other.get_json()["transaction_ref"] != first.get_json()["transaction_ref"]


def test_payment_rejects_raw_card_number(client, buyer_headers):
    """F-011: card numbers must never be accepted, only payment tokens."""
    resp = _charge(client, buyer_headers, "4242 4242 4242 4242")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "RAW_CARD_DATA_REJECTED"


def test_payment_rejects_invalid_amount(client, buyer_headers):
    resp = _charge(client, buyer_headers, "tok_visa_success", amount=-5)
    assert resp.status_code == 422
    assert resp.get_json()["error"] == "INVALID_AMOUNT"


def test_payment_requires_authentication(client):
    resp = client.post(CHARGE_URL, json={"amount": 10, "payment_token": "tok_visa_success"})
    assert resp.status_code == 401
