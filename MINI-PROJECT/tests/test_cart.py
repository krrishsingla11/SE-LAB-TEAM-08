"""Cart & pre-checkout tests - STP section 13.3"""
import pytest

SKIP = pytest.mark.skip(
    reason="Waiting for app skeleton / not implemented yet")


@SKIP
def test_tc_cart_01_add_item_and_update_quantity():
    """TC-CART-01 (High) - OMH-F-008
    Steps:    POST /api/cart/items product_id=101 qty=2; then PUT /api/cart/items/101 qty=3.
    Expected: HTTP 200; subtotal recalculates to 3 * unit_price; saved in DB.
    """
    pass


@SKIP
def test_tc_cart_02_add_quantity_exceeding_stock():
    """TC-CART-02 (High) - OMH-F-008
    Steps:    Product #101 stock=5; POST /api/cart/items qty=10.
    Expected: HTTP 400; error 'Requested quantity exceeds available inventory (5)'.
    """
    pass


@SKIP
def test_tc_cart_03_remove_last_item():
    """TC-CART-03 (Medium) - OMH-F-008
    Steps:    DELETE /api/cart/items/101; then GET /api/cart.
    Expected: HTTP 200; items array empty; subtotal 0.00.
    """
    pass


@SKIP
def test_tc_chk_01_checkout_with_depleted_stock():
    """TC-CHK-01 (High) - OMH-F-009
    Steps:    Cart has Product #103 qty=2 but stock is 0; POST /api/checkout.
    Expected: HTTP 400; checkout aborted BEFORE payment; error names Product #103.
    """
    pass
