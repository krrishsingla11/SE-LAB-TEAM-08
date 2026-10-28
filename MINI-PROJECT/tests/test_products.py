"""Product catalog & search tests - STP section 13.2"""
import pytest

SKIP = pytest.mark.skip(
    reason="Waiting for app skeleton / not implemented yet")


@SKIP
def test_tc_prod_01_artisan_creates_listing():
    """TC-PROD-01 (High) - OMH-F-005
    Steps:    POST /api/products (multipart) with title='Silk Scarf',
          price=450.00, stock=20, 2 JPG images.
    Expected: HTTP 201; product_id returned; images saved; inventory set to 20.
    """
    pass


@SKIP
def test_tc_prod_02_listing_negative_price():
    """TC-PROD-02 (High) - OMH-F-005
    Steps:    POST /api/products with price=-50.00 and stock_qty=-5.
    Expected: HTTP 422; validation error for price and stock.
    """
    pass


@SKIP
def test_tc_prod_03_artisan_updates_own_listing():
    """TC-PROD-03 (High) - OMH-F-006
    Steps:    PUT /api/products/101 with price=499.00, stock_qty=35 (own product).
    Expected: HTTP 200; price 499.00; inventory 35.
    """
    pass


@SKIP
def test_tc_prod_04_modify_other_artisans_product():
    """TC-PROD-04 (High) - OMH-F-006
    Steps:    Artisan A sends PUT /api/products/102 (owned by Artisan B).
    Expected: HTTP 403; error 'Not authorized to modify this listing'; data untouched.
    """
    pass


@SKIP
def test_tc_prod_05_catalog_keyword_search_filter():
    """TC-PROD-05 (High) - OMH-F-007
    Steps:    GET /api/products?q=ceramic&category=1.
    Expected: HTTP 200; only active pottery products containing 'ceramic'.
    """
    pass
