from app.payment.gateway import MockGateway, PaymentError

_gateway = MockGateway()


def capture_charge(amount, token, idem_key=None):
    valid = isinstance(amount, (int, float)) and not isinstance(amount, bool)
    if not valid or amount <= 0:
        raise PaymentError(
            "INVALID_AMOUNT", "amount must be a positive number", 422)
    return _gateway.capture_charge(round(float(amount), 2), token, idem_key)


def void_or_refund_charge(txn_ref, reason):
    return _gateway.void_or_refund_charge(txn_ref, reason)
