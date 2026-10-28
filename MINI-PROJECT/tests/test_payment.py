"""Payment tests (mock payment stub) - STP section 13.4"""
import pytest

SKIP = pytest.mark.skip(
    reason="Waiting for app skeleton / not implemented yet")


@SKIP
def test_tc_pay_01_payment_success_mock_stub():
    """TC-PAY-01 (High) - OMH-F-010
    Steps:    POST /api/checkout with payment token 'tok_visa_success'.
    Expected: HTTP 201; payment captured; status 'Processing'; txn_ref 'TXN-MOCK-OK'.
    """
    pass


@SKIP
def test_tc_pay_02_payment_declined():
    """TC-PAY-02 (High) - OMH-F-010
    Steps:    POST /api/checkout with payment token 'tok_charge_declined'.
    Expected: HTTP 402; error 'Card declined'; stock lock rolled back; no order created.
    """
    pass


@SKIP
def test_tc_pay_03_idempotent_payment_retry():
    """TC-PAY-03 (Medium) - OMH-F-010
    Steps:    Re-POST /api/checkout with the same Idempotency-Key.
    Expected: HTTP 200/201 with the original outcome; no duplicate charge or order.
    """
    pass
