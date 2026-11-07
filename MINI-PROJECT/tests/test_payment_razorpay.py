"""Isolated tests for the Razorpay Test Mode gateway adapter (SE8-31 Phase 1).

Covers:
- MockGateway remains the default when no provider is configured.
- Explicit Razorpay selection via PAYMENT_GATEWAY=razorpay.
- Missing credentials fail safely without fallback.
- Valid payment signature verification.
- Invalid signature detection and error handling.
- Payment amount mismatch using exact Decimal comparison.
- Currency mismatch verification.
- Payment not captured status handling.
- Successful refund request and response parsing.
- Gateway timeout enforcement (SAD 3.0-second requirement).
- Gateway authentication and network communication errors.
- Strict rejection of raw card numbers (PCI-DSS OMH-F-011).
- Verification that no real external network calls are made during tests.
"""
from decimal import Decimal
import os
import socket
from unittest import mock

import pytest
import requests

from app.payment import service as payment_service
from app.payment.gateway import (
    DEFAULT_TIMEOUT,
    BadRequestError,
    MockGateway,
    PaymentError,
    RazorpayGateway,
    SignatureVerificationError,
    paise_to_rupees,
    rupees_to_paise,
)


@pytest.fixture(autouse=True)
def reset_payment_service_gateway():
    """Ensure payment_service._gateway is reset before and after every test."""
    original = payment_service._gateway
    payment_service._gateway = None
    yield
    payment_service._gateway = original


@pytest.fixture
def fake_razorpay_client():
    """Create a fully mocked Razorpay SDK client."""
    client = mock.MagicMock()
    client.retry_enabled = True
    client.max_retries = 3
    client.utility = mock.MagicMock()
    client.payment = mock.MagicMock()
    client.refund = mock.MagicMock()
    return client


# -----------------------------------------------------------------------------
# Gateway Selection & Configuration Tests
# -----------------------------------------------------------------------------


def test_mock_gateway_remains_default_when_unconfigured():
    """When PAYMENT_GATEWAY is unset or empty, MockGateway must be returned."""
    with mock.patch.dict(os.environ, {}, clear=True):
        gateway = payment_service.get_gateway()
        assert isinstance(gateway, MockGateway)

    with mock.patch.dict(os.environ, {"PAYMENT_GATEWAY": "mock"}):
        gateway = payment_service.get_gateway()
        assert isinstance(gateway, MockGateway)


def test_explicit_razorpay_selection_with_valid_credentials(fake_razorpay_client):
    """When PAYMENT_GATEWAY=razorpay and credentials exist, RazorpayGateway is instantiated."""
    env = {
        "PAYMENT_GATEWAY": "razorpay",
        "RAZORPAY_KEY_ID": "rzp_test_validkey123",
        "RAZORPAY_KEY_SECRET": "test_secret_abc456",
    }
    with mock.patch.dict(os.environ, env):
        with mock.patch("razorpay.Client", return_value=fake_razorpay_client):
            gateway = payment_service.get_gateway()
            assert isinstance(gateway, RazorpayGateway)
            assert gateway.key_id == "rzp_test_validkey123"
            assert gateway.key_secret == "test_secret_abc456"
            # Ensure secrets are never leaked in string representation
            assert "test_secret_abc456" not in repr(gateway)
            assert "rzp_test_validkey123" in repr(gateway)


def test_missing_credentials_fail_safely_without_silent_fallback():
    """When PAYMENT_GATEWAY=razorpay but credentials are missing, fail clearly with 500."""
    # Missing both
    with mock.patch.dict(os.environ, {"PAYMENT_GATEWAY": "razorpay"}, clear=True):
        with pytest.raises(PaymentError) as exc_info:
            payment_service.get_gateway()
        assert exc_info.value.code == "GATEWAY_CONFIGURATION_ERROR"
        assert exc_info.value.status == 500

    # Missing RAZORPAY_KEY_SECRET only
    env_no_secret = {
        "PAYMENT_GATEWAY": "razorpay",
        "RAZORPAY_KEY_ID": "rzp_test_123",
    }
    with mock.patch.dict(os.environ, env_no_secret, clear=True):
        with pytest.raises(PaymentError) as exc_info:
            payment_service.get_gateway()
        assert exc_info.value.code == "GATEWAY_CONFIGURATION_ERROR"
        assert exc_info.value.status == 500

    # Missing RAZORPAY_KEY_ID only
    env_no_key = {
        "PAYMENT_GATEWAY": "razorpay",
        "RAZORPAY_KEY_SECRET": "secret_123",
    }
    with mock.patch.dict(os.environ, env_no_key, clear=True):
        with pytest.raises(PaymentError) as exc_info:
            payment_service.get_gateway()
        assert exc_info.value.code == "GATEWAY_CONFIGURATION_ERROR"
        assert exc_info.value.status == 500


def test_razorpay_gateway_direct_instantiation_validates_credentials():
    """Direct instantiation without keys raises GATEWAY_CONFIGURATION_ERROR."""
    with pytest.raises(PaymentError) as exc:
        RazorpayGateway(key_id="", key_secret="")
    assert exc.value.code == "GATEWAY_CONFIGURATION_ERROR"
    assert exc.value.status == 500


# -----------------------------------------------------------------------------
# Signature Verification Tests
# -----------------------------------------------------------------------------


def test_valid_payment_signature(fake_razorpay_client):
    """Valid signature returns True through the SDK utility verification."""
    fake_razorpay_client.utility.verify_payment_signature.return_value = True
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    result = gateway.verify_payment_signature(
        razorpay_order_id="order_12345",
        razorpay_payment_id="pay_67890",
        razorpay_signature="valid_hmac_hex_sig",
    )
    assert result is True
    fake_razorpay_client.utility.verify_payment_signature.assert_called_once_with({
        "razorpay_order_id": "order_12345",
        "razorpay_payment_id": "pay_67890",
        "razorpay_signature": "valid_hmac_hex_sig",
    })


def test_invalid_payment_signature_raises_400(fake_razorpay_client):
    """SignatureVerificationError from the SDK raises PaymentError(INVALID_SIGNATURE, 400)."""
    fake_razorpay_client.utility.verify_payment_signature.side_effect = (
        SignatureVerificationError("Signature mismatch")
    )
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.verify_payment_signature(
            razorpay_order_id="order_12345",
            razorpay_payment_id="pay_67890",
            razorpay_signature="tampered_signature",
        )
    assert exc_info.value.code == "INVALID_SIGNATURE"
    assert exc_info.value.status == 400


def test_missing_signature_arguments_raise_400(fake_razorpay_client):
    """Missing order ID, payment ID, or signature raises INVALID_SIGNATURE 400."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    with pytest.raises(PaymentError) as exc:
        gateway.verify_payment_signature("", "pay_1", "sig_1")
    assert exc.value.code == "INVALID_SIGNATURE"
    assert exc.value.status == 400


# -----------------------------------------------------------------------------
# Amount, Currency & Captured Status Verification Tests
# -----------------------------------------------------------------------------


def test_payment_amount_mismatch_raises_400(fake_razorpay_client):
    """Mismatch between expected order amount and fetched payment amount raises 400."""
    # Fetched payment is 40000 paise (₹400.00), but expected is ₹450.00
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_test123",
        "amount": 40000,
        "currency": "INR",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.verify_payment("pay_test123", expected_amount=450.00, expected_currency="INR")
    assert exc_info.value.code == "AMOUNT_MISMATCH"
    assert exc_info.value.status == 400
    assert "45000" in exc_info.value.message
    assert "40000" in exc_info.value.message


def test_payment_currency_mismatch_raises_400(fake_razorpay_client):
    """Mismatch between expected currency (INR) and payment currency raises 400."""
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_test123",
        "amount": 45000,
        "currency": "USD",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.verify_payment("pay_test123", expected_amount=450.00, expected_currency="INR")
    assert exc_info.value.code == "CURRENCY_MISMATCH"
    assert exc_info.value.status == 400


@pytest.mark.parametrize("bad_status", ["authorized", "failed", "created", "refunded"])
def test_payment_not_captured_raises_400(fake_razorpay_client, bad_status):
    """A payment whose status is not 'captured' raises PAYMENT_NOT_CAPTURED 400."""
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_test123",
        "amount": 45000,
        "currency": "INR",
        "status": bad_status,
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.verify_payment("pay_test123", expected_amount=450.00)
    assert exc_info.value.code == "PAYMENT_NOT_CAPTURED"
    assert exc_info.value.status == 400
    assert bad_status in exc_info.value.message


def test_successful_payment_verification(fake_razorpay_client):
    """When amount, currency and captured status match, verify_payment returns details."""
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_test123",
        "amount": 45000,
        "currency": "INR",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    payment = gateway.verify_payment("pay_test123", expected_amount=450.00, expected_currency="INR")
    assert payment["id"] == "pay_test123"
    assert payment["status"] == "captured"


# -----------------------------------------------------------------------------
# Refund Functionality Tests
# -----------------------------------------------------------------------------


def test_successful_refund_request(fake_razorpay_client):
    """void_or_refund_charge calls client.payment.refund and returns standardized response."""
    fake_razorpay_client.payment.refund.return_value = {
        "id": "rfnd_test987",
        "entity": "refund",
        "amount": 45000,
        "currency": "INR",
        "payment_id": "pay_test123",
        "status": "processed",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    result = gateway.void_or_refund_charge(
        txn_ref="pay_test123",
        reason="stock ran out during checkout",
        amount=450.00,
    )
    assert result["transaction_ref"] == "pay_test123"
    assert result["payment_status"] == "refunded"
    assert result["refund_id"] == "rfnd_test987"
    assert result["reason"] == "stock ran out during checkout"

    fake_razorpay_client.payment.refund.assert_called_once_with(
        "pay_test123",
        {"amount": 45000, "notes": {"reason": "stock ran out during checkout"}},
        timeout=DEFAULT_TIMEOUT,
    )


def test_refund_missing_transaction_ref_raises_422(fake_razorpay_client):
    """Refund without transaction reference raises INVALID_TOKEN 422."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    with pytest.raises(PaymentError) as exc:
        gateway.void_or_refund_charge("", reason="fail")
    assert exc.value.code == "INVALID_TOKEN"
    assert exc.value.status == 422


# -----------------------------------------------------------------------------
# Timeout and Error Handling Tests (SAD 3.0s Requirement)
# -----------------------------------------------------------------------------


def test_gateway_timeout_on_fetch(fake_razorpay_client):
    """Request timeout on payment fetch raises GATEWAY_TIMEOUT 504."""
    fake_razorpay_client.payment.fetch.side_effect = requests.exceptions.Timeout("Read timed out")
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.fetch_payment("pay_timeout123")
    assert exc_info.value.code == "GATEWAY_TIMEOUT"
    assert exc_info.value.status == 504


def test_gateway_timeout_on_refund(fake_razorpay_client):
    """Request timeout on payment refund raises GATEWAY_TIMEOUT 504."""
    fake_razorpay_client.payment.refund.side_effect = (
        requests.exceptions.Timeout("Connect timed out")
    )
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.void_or_refund_charge("pay_timeout123", reason="cancel")
    assert exc_info.value.code == "GATEWAY_TIMEOUT"
    assert exc_info.value.status == 504


def test_gateway_authentication_error(fake_razorpay_client):
    """BadRequestError (e.g. 401 invalid key) raises GATEWAY_AUTHENTICATION_ERROR 502."""
    fake_razorpay_client.payment.fetch.side_effect = BadRequestError("Invalid key_id or secret")
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.fetch_payment("pay_auth_fail")
    assert exc_info.value.code == "GATEWAY_AUTHENTICATION_ERROR"
    assert exc_info.value.status == 502


def test_gateway_network_connection_error(fake_razorpay_client):
    """Network connection failure raises GATEWAY_ERROR 502."""
    fake_razorpay_client.payment.fetch.side_effect = requests.exceptions.ConnectionError(
        "Connection refused"
    )
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    with pytest.raises(PaymentError) as exc_info:
        gateway.fetch_payment("pay_conn_fail")
    assert exc_info.value.code == "GATEWAY_ERROR"
    assert exc_info.value.status == 502


def test_gateway_disables_retries_and_sets_3s_timeout(fake_razorpay_client):
    """Verify that SDK retry mechanism is explicitly disabled and timeout is configured."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    assert fake_razorpay_client.retry_enabled is False
    assert fake_razorpay_client.max_retries == 1
    # Connect timeout (1.0) + Read timeout (2.0) = 3.0s total maximum deadline
    assert gateway.timeout == (1.0, 2.0)
    assert sum(gateway.timeout) <= 3.0


# -----------------------------------------------------------------------------
# Security & Raw Card Data Rejection Tests (OMH-F-011)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_card",
    [
        "4242 4242 4242 4242",
        "4111111111111111",
        "5500-0000-0000-0004",
    ],
)
def test_raw_card_numbers_rejected_immediately(fake_razorpay_client, raw_card):
    """Raw card numbers must be rejected before any external call (PCI-DSS)."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    with pytest.raises(PaymentError) as exc:
        gateway.capture_charge(100.0, raw_card)
    assert exc.value.code == "RAW_CARD_DATA_REJECTED"
    assert exc.value.status == 400

    with pytest.raises(PaymentError) as exc2:
        gateway.fetch_payment(raw_card)
    assert exc2.value.code == "RAW_CARD_DATA_REJECTED"
    assert exc2.value.status == 400

    fake_razorpay_client.payment.fetch.assert_not_called()


# -----------------------------------------------------------------------------
# capture_charge Integration with Tokens
# -----------------------------------------------------------------------------


def test_capture_charge_with_valid_dict_token(fake_razorpay_client):
    """capture_charge accepts dictionary with order_id, payment_id, and signature."""
    fake_razorpay_client.utility.verify_payment_signature.return_value = True
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_success123",
        "order_id": "order_xyz",
        "amount": 120000,
        "currency": "INR",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    token = {
        "razorpay_order_id": "order_xyz",
        "razorpay_payment_id": "pay_success123",
        "razorpay_signature": "sig_valid_123",
    }
    result = gateway.capture_charge(1200.00, token)
    assert result["transaction_ref"] == "pay_success123"
    assert result["payment_status"] == "captured"
    assert result["amount"] == 1200.00


def test_capture_charge_with_json_encoded_token(fake_razorpay_client):
    """capture_charge accepts JSON string with Razorpay credentials."""
    fake_razorpay_client.utility.verify_payment_signature.return_value = True
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_json123",
        "order_id": "order_j1",
        "amount": 35000,
        "currency": "INR",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    json_token = (
        '{"razorpay_order_id":"order_j1","razorpay_payment_id":"pay_json123",'
        '"razorpay_signature":"sig_j1"}'
    )
    result = gateway.capture_charge(350.00, json_token)
    assert result["transaction_ref"] == "pay_json123"
    assert result["payment_status"] == "captured"


def test_capture_charge_with_pipe_delimited_token(fake_razorpay_client):
    """capture_charge accepts 'order_id|payment_id|signature' token."""
    fake_razorpay_client.utility.verify_payment_signature.return_value = True
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_pipe123",
        "order_id": "order_p1",
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    result = gateway.capture_charge(500.00, "order_p1|pay_pipe123|sig_p1")
    assert result["transaction_ref"] == "pay_pipe123"
    assert result["payment_status"] == "captured"


def test_bare_payment_id_rejected_by_razorpay_gateway(fake_razorpay_client):
    """F-02: Bare payment ID 'pay_...' without signature is rejected by RazorpayGateway."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    with pytest.raises(PaymentError) as exc:
        gateway.capture_charge(750.00, "pay_direct123")
    assert exc.value.code == "INVALID_TOKEN"
    assert exc.value.status == 422
    fake_razorpay_client.payment.fetch.assert_not_called()


def test_capture_charge_order_id_mismatch_raises_400(fake_razorpay_client):
    """F-02: When fetched payment order_id does not match the token's razorpay_order_id, reject."""
    fake_razorpay_client.utility.verify_payment_signature.return_value = True
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_test123",
        "order_id": "order_DIFFERENT",
        "amount": 10000,
        "currency": "INR",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    token = {
        "razorpay_order_id": "order_EXPECTED",
        "razorpay_payment_id": "pay_test123",
        "razorpay_signature": "sig_valid",
    }
    with pytest.raises(PaymentError) as exc:
        gateway.capture_charge(100.00, token)
    assert exc.value.code == "ORDER_MISMATCH"
    assert exc.value.status == 400


def test_capture_charge_with_invalid_token_format_raises_422(fake_razorpay_client):
    """Unknown token string that does not match any format raises INVALID_TOKEN 422."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    with pytest.raises(PaymentError) as exc:
        gateway.capture_charge(100.0, "unknown_garbage_token")
    assert exc.value.code == "INVALID_TOKEN"
    assert exc.value.status == 422


# -----------------------------------------------------------------------------
# Decimal Monetary Conversion Tests (F-03)
# -----------------------------------------------------------------------------


def test_rupees_to_paise_and_paise_to_rupees_exact_decimal():
    """Verify exact Decimal arithmetic avoids IEEE-754 floating-point inaccuracies."""
    test_cases = [
        (450.00, 45000, Decimal("450.00")),
        (19.99, 1999, Decimal("19.99")),
        (0.01, 1, Decimal("0.01")),
        (1200.50, 120050, Decimal("1200.50")),
        ("299.95", 29995, Decimal("299.95")),
        (Decimal("89.90"), 8990, Decimal("89.90")),
    ]
    for rupees_in, paise_expected, rupees_expected in test_cases:
        paise_calc = rupees_to_paise(rupees_in)
        assert paise_calc == paise_expected
        assert isinstance(paise_calc, int)
        rupees_calc = paise_to_rupees(paise_calc)
        assert rupees_calc == rupees_expected
        assert isinstance(rupees_calc, Decimal)


def test_rupees_to_paise_valid_amounts():
    """F-03: Whole numbers, two-decimal amounts, and trailing zeros convert accurately."""
    assert rupees_to_paise(10) == 1000
    assert rupees_to_paise("10") == 1000
    assert rupees_to_paise(10.0) == 1000
    assert rupees_to_paise("10.00") == 1000
    assert rupees_to_paise("10.000") == 1000
    assert rupees_to_paise(Decimal("10.000")) == 1000
    assert rupees_to_paise(10.50) == 1050
    assert rupees_to_paise("10.99") == 1099
    assert rupees_to_paise(Decimal("299.95")) == 29995


def test_rupees_to_paise_fractional_paise_rejected():
    """F-03: Amounts with genuine precision beyond 2 decimal places raise INVALID_AMOUNT 422."""
    for invalid in [10.005, "10.005", Decimal("10.005"), "0.001", 99.999, "100.123"]:
        with pytest.raises(PaymentError) as exc:
            rupees_to_paise(invalid)
        assert exc.value.code == "INVALID_AMOUNT"
        assert exc.value.status == 422


def test_rupees_to_paise_zero_and_negative_rejected():
    """F-03: Zero and negative amounts raise INVALID_AMOUNT 422."""
    for invalid in [0, 0.0, "0", Decimal("0.00"), -5, -10.50, "-10.00"]:
        with pytest.raises(PaymentError) as exc:
            rupees_to_paise(invalid)
        assert exc.value.code == "INVALID_AMOUNT"
        assert exc.value.status == 422


# -----------------------------------------------------------------------------
# Service Layer Precision Tests (F-05)
# -----------------------------------------------------------------------------


def test_service_capture_charge_preserves_decimal_precision():
    """F-05: service.capture_charge forwards Decimal to gateway without float conversion."""
    mock_gw = mock.MagicMock(spec=MockGateway)
    mock_gw.capture_charge.return_value = {"payment_status": "captured"}
    payment_service._gateway = mock_gw

    payment_service.capture_charge(Decimal("450.99"), "tok_visa_success")
    passed_amount = mock_gw.capture_charge.call_args[0][0]
    assert isinstance(passed_amount, Decimal)
    assert passed_amount == Decimal("450.99")
    assert not isinstance(passed_amount, float)

    payment_service.capture_charge(500, "tok_visa_success")
    passed_amount_int = mock_gw.capture_charge.call_args[0][0]
    assert passed_amount_int == 500
    assert not isinstance(passed_amount_int, float)


# -----------------------------------------------------------------------------
# Error Information Leakage Tests (F-04)
# -----------------------------------------------------------------------------


def test_gateway_exceptions_do_not_leak_raw_cause_chain(fake_razorpay_client):
    """F-04: Gateway exceptions must suppress __cause__ chaining (raise ... from None)."""
    fake_razorpay_client.payment.fetch.side_effect = requests.exceptions.RequestException(
        "Sensitive URL https://api.razorpay.com/v1/payments with secret auth header"
    )
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    with pytest.raises(PaymentError) as exc_info:
        gateway.fetch_payment("pay_sensitive123")
    assert exc_info.value.__cause__ is None
    assert "https://api.razorpay.com" not in str(exc_info.value)


# -----------------------------------------------------------------------------
# Refund Validation Tests (Requirement 6)
# -----------------------------------------------------------------------------


def test_refund_zero_or_negative_amount_rejected(fake_razorpay_client):
    """Explicit zero or negative refund amount is rejected with INVALID_AMOUNT 422."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    for invalid_amt in [0, 0.0, -10, -50.00, Decimal("-0.01")]:
        with pytest.raises(PaymentError) as exc:
            gateway.void_or_refund_charge("pay_test123", amount=invalid_amt)
        assert exc.value.code == "INVALID_AMOUNT"
        assert exc.value.status == 422

    # MockGateway also rejects zero/negative refund amounts
    mock_gw = MockGateway()
    for invalid_amt in [0, -25.0]:
        with pytest.raises(PaymentError) as exc:
            mock_gw.void_or_refund_charge("TXN-123", amount=invalid_amt)
        assert exc.value.code == "INVALID_AMOUNT"
        assert exc.value.status == 422


def test_refund_fractional_paise_amount_rejected(fake_razorpay_client):
    """Explicit refund amount with fractional paise is rejected with INVALID_AMOUNT 422."""
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    with pytest.raises(PaymentError) as exc:
        gateway.void_or_refund_charge("pay_test123", amount=50.005)
    assert exc.value.code == "INVALID_AMOUNT"
    assert exc.value.status == 422


def test_refund_full_refund_when_amount_omitted(fake_razorpay_client):
    """When amount is None, full repayment is established via payment fetch and marked refunded."""
    fake_razorpay_client.payment.refund.return_value = {
        "id": "rfnd_full123",
        "entity": "refund",
        "status": "processed",
        "amount": 20000,
    }
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_full_ref",
        "amount": 20000,
        "amount_refunded": 20000,
        "refund_status": "full",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    result = gateway.void_or_refund_charge("pay_full_ref", reason="order cancellation")
    assert result["payment_status"] == "refunded"
    assert result["refund_id"] == "rfnd_full123"
    fake_razorpay_client.payment.refund.assert_called_once_with(
        "pay_full_ref",
        {"notes": {"reason": "order cancellation"}},
        timeout=DEFAULT_TIMEOUT,
    )


def test_refund_omitted_amount_partial_refund_detected(fake_razorpay_client):
    """When amount is None and payment fetch establishes a smaller refund, mark partial_refunded."""
    fake_razorpay_client.payment.refund.return_value = {
        "id": "rfnd_part123",
        "entity": "refund",
        "status": "processed",
        "amount": 10000,
    }
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_part_ref",
        "amount": 20000,
        "amount_refunded": 10000,
        "refund_status": "partial",
        "status": "captured",
    }
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    result = gateway.void_or_refund_charge("pay_part_ref", reason="order modification")
    assert result["payment_status"] == "partial_refunded"
    assert result["amount_refunded"] == 10000


def test_refund_omitted_amount_insufficient_data_returns_manual_review(fake_razorpay_client):
    """When amount is None and payment fetch fails, return manual_review
    instead of falsely reporting full.
    """
    fake_razorpay_client.payment.refund.return_value = {
        "id": "rfnd_insuf123",
        "entity": "refund",
        "status": "processed",
    }
    fake_razorpay_client.payment.fetch.side_effect = Exception("Fetch payment failed")
    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )
    result = gateway.void_or_refund_charge("pay_insuf_ref", reason="cancellation")
    assert result["payment_status"] == "manual_review"


# -----------------------------------------------------------------------------
# Guarantee No External Network Calls
# -----------------------------------------------------------------------------


def test_no_real_external_network_calls_guaranteed(monkeypatch, fake_razorpay_client):
    """Ensure socket connections are blocked and all tests use mocks."""
    def _blocked_connect(*args, **kwargs):
        raise RuntimeError("External network connection attempted during test!")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)

    fake_razorpay_client.utility.verify_payment_signature.return_value = True
    fake_razorpay_client.payment.fetch.return_value = {
        "id": "pay_isolated",
        "amount": 25000,
        "currency": "INR",
        "status": "captured",
    }
    fake_razorpay_client.payment.refund.return_value = {
        "id": "rfnd_isolated",
        "status": "processed",
    }

    gateway = RazorpayGateway(
        key_id="rzp_test_1",
        key_secret="sec_1",
        client=fake_razorpay_client,
    )

    # All of these succeed without any socket connect attempt
    assert gateway.verify_payment_signature("order_1", "pay_isolated", "sig_1") is True
    assert gateway.verify_payment("pay_isolated", expected_amount=250.00)["id"] == "pay_isolated"
    assert gateway.void_or_refund_charge("pay_isolated")["refund_id"] == "rfnd_isolated"
