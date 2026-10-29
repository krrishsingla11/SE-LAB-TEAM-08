import pytest

from app.payment.gateway import MockGateway, PaymentError


def test_success_returns_captured():
    result = MockGateway().capture_charge(450.0, "tok_visa_success")
    assert result["payment_status"] == "captured"
    assert result["transaction_ref"].startswith("TXN-MOCK-")


def test_declined_returns_402():
    with pytest.raises(PaymentError) as err:
        MockGateway().capture_charge(450.0, "tok_charge_declined")
    assert err.value.status == 402


def test_raw_card_number_is_rejected():
    with pytest.raises(PaymentError) as err:
        MockGateway().capture_charge(450.0, "4111 1111 1111 1111")
    assert err.value.code == "RAW_CARD_DATA_REJECTED"


def test_same_idempotency_key_returns_same_charge():
    gateway = MockGateway()
    first = gateway.capture_charge(450.0, "tok_visa_success", "key-1")
    second = gateway.capture_charge(450.0, "tok_visa_success", "key-1")
    assert first == second
