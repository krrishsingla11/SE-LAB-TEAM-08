"""Sprint 2 tests (SE8-44): PDF invoices, order history and the not-yet-built features.

Working tests : TC-INV-03, TC-INV-04, invoice access rules, order history.
Expected fail : TC-ORD-02, TC-INV-02, TC-RPT-01, TC-RPT-02. These routes are not in
                the app yet (found 7 Nov), so the tests are marked xfail. When the
                feature is built the test passes and pytest reports it as XPASS.
Already covered by teammates: TC-ORD-01 (test_checkout.py), TC-INV-01 (PostgreSQL only).
"""
import uuid

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import Artisan, Category, Inventory, Product, User

PASSWORD = "StrongP@ss123"
ADDRESS = "42 Residency Road, Bengaluru 560025"
NOT_BUILT = pytest.mark.xfail(reason="Endpoint is not implemented in main yet", strict=False)


# ---------------------------------------------------------------- helpers
def _buyer(client, name="Invoice Buyer"):
    email = f"s2_{uuid.uuid4().hex[:8]}@pes.edu"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": name, "role": "buyer"},
    )
    assert reg.status_code == 201, reg.get_json()
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.get_json()
    return {"Authorization": f"Bearer {login.get_json()['token']}"}


def _make_product(title, price, stock):
    """Insert an artisan, a category and a product; return (product_id, seller_user_id)."""
    tag = uuid.uuid4().hex[:8]
    seller = User(
        email=f"seller_{tag}@pes.edu",
        password_hash="not-a-real-hash",
        full_name="Test Seller",
        role="artisan",
    )
    db.session.add(seller)
    db.session.flush()
    artisan = Artisan(user_id=seller.user_id, shop_name=f"Shop {tag}")
    category = Category(name=f"Category {tag}", slug=f"cat-{tag}")
    db.session.add_all([artisan, category])
    db.session.flush()
    product = Product(
        artisan_id=artisan.artisan_id,
        category_id=category.category_id,
        title=title,
        description="Handmade " + title.lower(),
        price=price,
        is_active=True,
    )
    db.session.add(product)
    db.session.flush()
    db.session.add(
        Inventory(product_id=product.product_id, stock_quantity=stock, low_stock_threshold=5)
    )
    db.session.commit()
    return product.product_id, seller.user_id


def _artisan_headers(seller_id):
    token = create_access_token(identity=str(seller_id), additional_claims={"role": "artisan"})
    return {"Authorization": f"Bearer {token}"}


def _checkout(client, headers, product_id, quantity=1):
    added = client.post(
        "/api/cart/items",
        json={"product_id": product_id, "quantity": quantity},
        headers=headers,
    )
    assert added.status_code == 200, added.get_json()
    resp = client.post(
        "/api/checkout",
        json={"shipping_address": ADDRESS, "payment_token": "tok_visa_success"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _order_id(order):
    return int(order["invoice_url"].strip("/").split("/")[2])  # /api/orders/<id>/invoice


@pytest.fixture
def completed_order(client):
    headers = _buyer(client)
    product_id, seller_id = _make_product("Ceramic Vase", 450.00, 20)
    order = _checkout(client, headers, product_id)
    return {"headers": headers, "order": order, "seller_id": seller_id}


# ----------------------------------------------------- invoices (TC-INV-03/04)
def test_tc_inv_03_invoice_pdf_is_generated(client, completed_order):
    """TC-INV-03 (High) - OMH-F-017
    Steps:    Complete an order, then download its invoice.
    Expected: HTTP 200; the response is a real PDF file.
    """
    url = completed_order["order"]["invoice_url"]
    resp = client.get(url, headers=completed_order["headers"])
    assert resp.status_code == 200
    assert "application/pdf" in resp.content_type
    assert resp.data.startswith(b"%PDF")
    assert len(resp.data) > 500


def test_tc_inv_03_invoice_contains_order_details(client, completed_order):
    """TC-INV-03 (High) - OMH-F-017: the PDF shows order id, buyer name and the total.
    Needs PyMuPDF (py -m pip install pymupdf); skipped when it is not installed.
    """
    fitz = pytest.importorskip("fitz")
    order = completed_order["order"]
    resp = client.get(order["invoice_url"], headers=completed_order["headers"])
    document = fitz.open(stream=resp.data, filetype="pdf")
    text = "".join(page.get_text() for page in document)
    assert str(_order_id(order)) in text
    assert "Invoice Buyer" in text
    assert "450" in text


def test_tc_inv_04_other_buyer_cannot_download_invoice(client, completed_order):
    """TC-INV-04 (Medium) - OMH-F-018
    Steps:    Buyer B requests the invoice of Buyer A's order.
    Expected: HTTP 403; the PDF is not returned.
    """
    other = _buyer(client, name="Other Buyer")
    resp = client.get(completed_order["order"]["invoice_url"], headers=other)
    assert resp.status_code == 403
    assert "application/pdf" not in resp.content_type


def test_invoice_requires_authentication(client, completed_order):
    assert client.get(completed_order["order"]["invoice_url"]).status_code == 401


def test_invoice_for_missing_order_returns_404(client):
    headers = _buyer(client)
    assert client.get("/api/orders/999999/invoice", headers=headers).status_code == 404


# ------------------------------------------------------------- order history
def test_order_history_lists_the_new_order(client, completed_order):
    resp = client.get("/api/orders", headers=completed_order["headers"])
    assert resp.status_code == 200
    assert "Processing" in resp.get_data(as_text=True)


def test_order_history_requires_authentication(client):
    assert client.get("/api/orders").status_code == 401


# ----------------------------------- not built yet (xfail until implemented)
def test_tc_ord_02_artisan_progresses_order_status(client, completed_order):
    """TC-ORD-02 (High) - OMH-F-013
    Steps:    Artisan sends PUT /api/orders/{id}/status Shipped, then Delivered.
    Expected: HTTP 200 each time; the buyer sees the new status in order history.
    """
    order_id = _order_id(completed_order["order"])
    artisan = _artisan_headers(completed_order["seller_id"])
    for status in ("Shipped", "Delivered"):
        resp = client.put(
            f"/api/orders/{order_id}/status", json={"status": status}, headers=artisan
        )
        assert resp.status_code == 200, resp.get_json()
    history = client.get("/api/orders", headers=completed_order["headers"])
    assert "Delivered" in history.get_data(as_text=True)


def test_tc_inv_02_low_stock_alert_on_dashboard(client):
    """TC-INV-02 (Medium) - OMH-F-016
    Steps:    Stock 6, threshold 5; buy 1 unit; GET /api/seller/dashboard as the artisan.
    Expected: HTTP 200; the dashboard shows a low-stock alert for the product.
    """
    headers = _buyer(client)
    product_id, seller_id = _make_product("Low Stock Lamp", 300.00, 6)
    _checkout(client, headers, product_id)
    resp = client.get("/api/seller/dashboard", headers=_artisan_headers(seller_id))
    assert resp.status_code == 200
    assert "low" in resp.get_data(as_text=True).lower()


@NOT_BUILT
def test_tc_rpt_01_monthly_sales_report(client, completed_order):
    """TC-RPT-01 (High) - OMH-F-019
    Steps:    After one completed order (450.00), GET /api/reports/sales?period=monthly.
    Expected: HTTP 200; JSON with revenue 450.0 and order_count 1.
    """
    artisan = _artisan_headers(completed_order["seller_id"])
    resp = client.get("/api/reports/sales?period=monthly", headers=artisan)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["revenue"] == 450.0
    assert body["order_count"] == 1


@NOT_BUILT
def test_tc_rpt_02_export_sales_report(client, completed_order):
    """TC-RPT-02 (Medium) - OMH-F-020
    Steps:    GET /api/reports/export?format=csv and ?format=pdf as the artisan.
    Expected: HTTP 200 with Content-Type text/csv and application/pdf.
    """
    artisan = _artisan_headers(completed_order["seller_id"])
    csv_resp = client.get("/api/reports/export?format=csv", headers=artisan)
    pdf_resp = client.get("/api/reports/export?format=pdf", headers=artisan)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.content_type
    assert pdf_resp.status_code == 200
    assert "application/pdf" in pdf_resp.content_type
