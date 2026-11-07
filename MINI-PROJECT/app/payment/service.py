from decimal import Decimal
import os

from app.payment.gateway import (
    BasePaymentGateway,
    MockGateway,
    PaymentError,
    RazorpayGateway,
)

_default_mock_gateway = MockGateway()
_gateway = None  # Explicit override point for tests/monkeypatching


def get_gateway() -> BasePaymentGateway:
    """Return the active payment gateway based on configuration.

    - Defaults to MockGateway when PAYMENT_GATEWAY is unset or 'mock'.
    - If PAYMENT_GATEWAY is 'razorpay', reads RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.
      Fails safely with PaymentError if credentials are missing.
    - If _gateway has been monkeypatched, returns the overridden instance.
    """
    if _gateway is not None:
        return _gateway

    provider = os.getenv("PAYMENT_GATEWAY", "mock").strip().lower()
    if provider in ("mock", ""):
        return _default_mock_gateway
    elif provider == "razorpay":
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        if not key_id or not key_secret:
            raise PaymentError(
                "GATEWAY_CONFIGURATION_ERROR",
                "Razorpay credentials not configured: RAZORPAY_KEY_ID and "
                "RAZORPAY_KEY_SECRET are required",
                500,
            )
        return RazorpayGateway(key_id=key_id, key_secret=key_secret)
    else:
        raise PaymentError(
            "GATEWAY_CONFIGURATION_ERROR",
            f"Unsupported payment gateway provider '{provider}'",
            500,
        )


def capture_charge(amount, token, idem_key=None):
    valid = isinstance(amount, (int, float, Decimal)) and not isinstance(amount, bool)
    if not valid or amount <= 0:
        raise PaymentError(
            "INVALID_AMOUNT", "amount must be a positive number", 422)
    return get_gateway().capture_charge(amount, token, idem_key)


def void_or_refund_charge(txn_ref, reason=None, amount=None, idempotency_key=None):
    gateway = get_gateway()
    import inspect
    sig = inspect.signature(gateway.void_or_refund_charge)
    params = sig.parameters
    kwargs = {}
    if "amount" in params:
        kwargs["amount"] = amount
    elif amount is not None:
        from app.payment.gateway import rupees_to_paise
        rupees_to_paise(amount)

    if "idempotency_key" in params:
        kwargs["idempotency_key"] = idempotency_key

    if "reason" in params:
        return gateway.void_or_refund_charge(txn_ref, reason, **kwargs)
    return gateway.void_or_refund_charge(txn_ref, **kwargs)
