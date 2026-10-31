"""Product catalog & search tests - STP section 13.2"""
import io
import os

from flask_jwt_extended import create_access_token

import pytest

from app.models import Artisan, Category, Inventory, Product, ProductImage, User

SKIP = pytest.mark.skip(
    reason="Waiting for app skeleton / not implemented yet")

JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00"
    b"\xff\xd9"
)

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

WEBP_BYTES = (
    b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00"
    b"\x30\x01\x00\x9d\x01\x2a\x01\x00\x01\x00\x02\x00\x34\x25"
)


def _create_user(db, email, role, full_name="Test User", shop_name=None):
    user = User(
        email=email,
        password_hash="$2b$12$e80MvQ0fT9RkG82fD58Pge9BfD5w04vA4Lp7d.k4e.30v1.dE1eGe",
        full_name=full_name,
        role=role,
    )
    db.session.add(user)
    db.session.flush()

    artisan = None
    if role == "artisan" and shop_name:
        artisan = Artisan(
            user_id=user.user_id,
            shop_name=shop_name,
            bio="Handmade goods artisan",
        )
        db.session.add(artisan)
        db.session.flush()

    db.session.commit()
    return user, artisan


def _artisan_token(app, user_id, role="artisan", **kw):
    with app.app_context():
        return create_access_token(
            identity=str(user_id),
            additional_claims={"user_id": user_id, "role": role},
            **kw,
        )


def _category(db, name="Textiles", slug="textiles"):
    cat = db.session.scalar(db.select(Category).where(Category.slug == slug))
    if cat is None:
        cat = Category(name=name, slug=slug, description="Handcrafted fabrics and textiles")
        db.session.add(cat)
        db.session.commit()
    return cat


def test_tc_prod_01_artisan_creates_listing(client, app, db, tmp_path):
    """TC-PROD-01 (High) - OMH-F-005

    Steps:    POST /api/products (multipart) with title='Silk Scarf',
              price=450.00, stock=20, 2 JPG images.
    Expected: HTTP 201; product_id returned; images saved; inventory set to 20.
    """
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    user, _ = _create_user(db, "artisan_tc01@pes.edu", "artisan", shop_name="Silk Workshop")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    data = {
        "title": "Silk Scarf",
        "desc": "Handcrafted pure mulberry silk scarf",
        "category_id": str(cat.category_id),
        "price": "450.00",
        "stock_qty": "20",
        "images": [
            (io.BytesIO(JPEG_BYTES), "scarf1.jpg", "image/jpeg"),
            (io.BytesIO(JPEG_BYTES), "scarf2.jpg", "image/jpeg"),
        ],
    }

    res = client.post(
        "/api/products",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    body = res.get_json()
    assert "product_id" in body
    prod_id = body["product_id"]

    with app.app_context():
        prod = db.session.get(Product, prod_id)
        assert prod is not None
        assert prod.title == "Silk Scarf"
        assert float(prod.price) == 450.00
        assert prod.is_active is True

        inv = db.session.scalar(db.select(Inventory).where(Inventory.product_id == prod_id))
        assert inv is not None
        assert inv.stock_quantity == 20
        assert inv.low_stock_threshold == 5

        imgs = db.session.scalars(
            db.select(ProductImage).where(ProductImage.product_id == prod_id)
        ).all()
        assert len(imgs) == 2
        assert imgs[0].is_primary is True
        assert imgs[1].is_primary is False
        assert os.path.exists(os.path.join(str(tmp_path), os.path.basename(imgs[0].image_url)))
        assert os.path.exists(os.path.join(str(tmp_path), os.path.basename(imgs[1].image_url)))


def test_tc_prod_02_listing_negative_price(client, app, db):
    """TC-PROD-02 (High) - OMH-F-005

    Steps:    POST /api/products with price=-50.00 and stock_qty=-5.
    Expected: HTTP 422; validation error for price and stock.
    """
    user, _ = _create_user(db, "artisan_tc02@pes.edu", "artisan", shop_name="Pottery Works")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Pottery", "pottery")

    payload = {
        "title": "Clay Bowl",
        "desc": "Hand-thrown pottery bowl",
        "category_id": cat.category_id,
        "price": -50.00,
        "stock_qty": -5,
    }

    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 422
    body = res.get_json()
    assert body["error"] == "VALIDATION_ERROR"
    assert "Price must be greater than zero" in body["message"]
    assert "Stock quantity cannot be negative" in body["message"]


def test_artisan_creates_listing_json_without_images(client, app, db):
    """Positive: Artisan creates listing using JSON body without images."""
    user, _ = _create_user(db, "artisan_json@pes.edu", "artisan", shop_name="Carvings Studio")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Woodwork", "woodwork")

    payload = {
        "title": "Rosewood Coaster",
        "description": "Solid rosewood handmade coaster with oil finish",
        "category_id": cat.category_id,
        "price": 180.50,
        "stock_qty": 15,
    }

    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    body = res.get_json()
    assert "product_id" in body
    assert body["title"] == "Rosewood Coaster"
    assert body["price"] == 180.50
    assert body["stock_quantity"] == 15

    with app.app_context():
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == body["product_id"])
        )
        assert inv is not None
        assert inv.stock_quantity == 15


def test_artisan_creates_listing_with_multiple_images(client, app, db, tmp_path):
    """Positive: Multipart upload with 3 supported image formats (JPEG, PNG, WebP)."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    user, _ = _create_user(db, "artisan_multi@pes.edu", "artisan", shop_name="Multi Format Shop")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Metalwork", "metalwork")

    data = {
        "title": "Brass Oil Lamp",
        "desc": "Hand-hammered brass oil lamp",
        "category_id": str(cat.category_id),
        "price": "750.00",
        "stock_qty": "8",
        "images": [
            (io.BytesIO(JPEG_BYTES), "lamp1.jpeg", "image/jpeg"),
            (io.BytesIO(PNG_BYTES), "lamp2.png", "image/png"),
            (io.BytesIO(WEBP_BYTES), "lamp3.webp", "image/webp"),
        ],
    }

    res = client.post(
        "/api/products",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    prod_id = res.get_json()["product_id"]

    with app.app_context():
        imgs = db.session.scalars(
            db.select(ProductImage).where(ProductImage.product_id == prod_id)
        ).all()
        assert len(imgs) == 3
        assert imgs[0].is_primary is True
        assert imgs[1].is_primary is False
        assert imgs[2].is_primary is False


@pytest.mark.parametrize(
    "missing_field,payload",
    [
        ("title", {"desc": "Description here", "category_id": 1, "price": 100, "stock_qty": 5}),
        ("description", {"title": "Valid Title", "category_id": 1, "price": 100, "stock_qty": 5}),
        ("category_id", {"title": "Valid Title", "desc": "Desc", "price": 100, "stock_qty": 5}),
        ("price", {"title": "Valid Title", "desc": "Desc", "category_id": 1, "stock_qty": 5}),
        ("stock_qty", {"title": "Valid Title", "desc": "Desc", "category_id": 1, "price": 100}),
    ],
)
def test_create_product_missing_required_fields(client, app, db, missing_field, payload):
    """Negative: Missing any mandatory field returns HTTP 422."""
    user, _ = _create_user(db, f"artisan_{missing_field}@pes.edu", "artisan", shop_name="Shop")
    token = _artisan_token(app, user.user_id)
    _category(db, "Textiles", "textiles")

    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 422
    assert res.get_json()["error"] == "VALIDATION_ERROR"


def test_create_product_invalid_title_length(client, app, db):
    """Boundary: Title must be between 3 and 200 characters."""
    user, _ = _create_user(db, "artisan_title@pes.edu", "artisan", shop_name="Shop")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    # Short title (< 3 chars)
    res_short = client.post(
        "/api/products",
        json={"title": "Ab", "desc": "Valid description", "category_id": cat.category_id,
              "price": 100, "stock_qty": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_short.status_code == 422
    assert "Title must be between 3 and 200 characters" in res_short.get_json()["message"]

    # Long title (> 200 chars)
    res_long = client.post(
        "/api/products",
        json={"title": "A" * 201, "desc": "Valid description", "category_id": cat.category_id,
              "price": 100, "stock_qty": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_long.status_code == 422
    assert "Title must be between 3 and 200 characters" in res_long.get_json()["message"]


def test_create_product_invalid_category(client, app, db):
    """Negative: Category ID must exist in categories table."""
    user, _ = _create_user(db, "artisan_cat@pes.edu", "artisan", shop_name="Shop")
    token = _artisan_token(app, user.user_id)

    res = client.post(
        "/api/products",
        json={"title": "Vase", "desc": "Clay vase", "category_id": 99999,
              "price": 300, "stock_qty": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "Category with id 99999 does not exist" in res.get_json()["message"]


def test_create_product_invalid_price_and_stock(client, app, db):
    """Negative/Boundary: Price must be > 0 and stock must be a non-negative integer."""
    user, _ = _create_user(db, "artisan_nums@pes.edu", "artisan", shop_name="Shop")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    base = {"title": "Loom Rug", "desc": "Handwoven rug", "category_id": cat.category_id}

    # Zero price
    res_zero = client.post("/api/products", json=dict(base, price=0, stock_qty=5),
                           headers={"Authorization": f"Bearer {token}"})
    assert res_zero.status_code == 422

    # NaN / Inf price
    res_nan = client.post("/api/products", json=dict(base, price="nan", stock_qty=5),
                          headers={"Authorization": f"Bearer {token}"})
    assert res_nan.status_code == 422

    # Float stock quantity
    res_float_stock = client.post("/api/products", json=dict(base, price=100, stock_qty=3.5),
                                  headers={"Authorization": f"Bearer {token}"})
    assert res_float_stock.status_code == 422

    # Negative stock
    res_neg_stock = client.post("/api/products", json=dict(base, price=100, stock_qty=-1),
                                headers={"Authorization": f"Bearer {token}"})
    assert res_neg_stock.status_code == 422


def test_create_product_unauthenticated_returns_401(client):
    """Security: Missing, tampered, or expired tokens must return HTTP 401."""
    # 1. No token
    res_none = client.post("/api/products", json={"title": "Unauth Test"})
    assert res_none.status_code == 401
    assert res_none.get_json()["error"] == "UNAUTHORIZED"

    # 2. Tampered token
    res_tampered = client.post(
        "/api/products",
        json={"title": "Unauth Test"},
        headers={"Authorization": "Bearer bad-token-value"},
    )
    assert res_tampered.status_code == 401


def test_create_product_buyer_role_returns_403(client, app, db):
    """Security: Non-artisan users (e.g. buyers) must receive HTTP 403."""
    buyer, _ = _create_user(db, "buyer_user@pes.edu", "buyer")
    token = _artisan_token(app, buyer.user_id, role="buyer")

    res = client.post(
        "/api/products",
        json={"title": "Unauthorized Listing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"
    assert res.get_json()["message"] == "Artisan privilege required"


def test_create_product_artisan_without_profile_returns_403(client, app, db):
    """Security: Artisan user without an Artisan shop profile receives HTTP 403."""
    user, _ = _create_user(db, "artisan_no_profile@pes.edu", "artisan", shop_name=None)
    token = _artisan_token(app, user.user_id, role="artisan")
    cat = _category(db, "Textiles", "textiles")

    res = client.post(
        "/api/products",
        json={"title": "Valid Scarf", "desc": "Good description",
              "category_id": cat.category_id, "price": 100, "stock_qty": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"
    assert "Artisan profile required" in res.get_json()["message"]


def test_create_product_more_than_five_images_returns_422(client, app, db):
    """Boundary: Uploading more than 5 images returns HTTP 422."""
    user, _ = _create_user(db, "artisan_max_imgs@pes.edu", "artisan", shop_name="Gallery")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    data = {
        "title": "Patchwork Quilt",
        "desc": "Hand-stitched quilt",
        "category_id": str(cat.category_id),
        "price": "1200.00",
        "stock_qty": "3",
        "images": [
            (io.BytesIO(JPEG_BYTES), f"img_{i}.jpg", "image/jpeg")
            for i in range(6)
        ],
    }

    res = client.post(
        "/api/products",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "Cannot upload more than 5 images" in res.get_json()["message"]


def test_create_product_invalid_image_format_returns_422(client, app, db):
    """Negative: Unsupported image extension or fake content returns HTTP 422."""
    user, _ = _create_user(db, "artisan_bad_img@pes.edu", "artisan", shop_name="Studio")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    # 1. Unsupported extension (.txt)
    data_txt = {
        "title": "Woven Basket",
        "desc": "Cane basket",
        "category_id": str(cat.category_id),
        "price": "350.00",
        "stock_qty": "5",
        "images": [(io.BytesIO(b"Hello world"), "note.txt", "text/plain")],
    }
    res_txt = client.post(
        "/api/products",
        data=data_txt,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_txt.status_code == 422

    # 2. Fake image (.jpg with plain text content)
    data_fake = {
        "title": "Woven Basket",
        "desc": "Cane basket",
        "category_id": str(cat.category_id),
        "price": "350.00",
        "stock_qty": "5",
        "images": [(io.BytesIO(b"Not a real jpeg"), "fake.jpg", "image/jpeg")],
    }
    res_fake = client.post(
        "/api/products",
        data=data_fake,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_fake.status_code == 422


def test_create_product_artisan_spoofing_prevented(client, app, db):
    """Security (STRIDE SO-1): Passed artisan_id in request body is ignored."""
    user_a, artisan_a = _create_user(db, "artisan_a@pes.edu", "artisan", shop_name="Artisan A")
    _, artisan_b = _create_user(db, "artisan_b@pes.edu", "artisan", shop_name="Artisan B")
    token_a = _artisan_token(app, user_a.user_id)
    cat = _category(db, "Textiles", "textiles")

    # Artisan A attempts to create listing specifying Artisan B's ID
    payload = {
        "title": "Spoof Attempt Scarf",
        "desc": "Trying to impersonate Artisan B",
        "category_id": cat.category_id,
        "price": 500.00,
        "stock_qty": 10,
        "artisan_id": artisan_b.artisan_id,
    }

    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 201
    prod_id = res.get_json()["product_id"]

    with app.app_context():
        prod = db.session.get(Product, prod_id)
        # Must be owned by Artisan A, never Artisan B
        assert prod.artisan_id == artisan_a.artisan_id
        assert prod.artisan_id != artisan_b.artisan_id


def test_create_product_json_with_arbitrary_image_urls_rejected(client, app, db):
    """Negative: Reject arbitrary user-provided image URLs in JSON payload."""
    user, _ = _create_user(db, "artisan_urls@pes.edu", "artisan", shop_name="Shop")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    payload = {
        "title": "Ceramic Bowl",
        "desc": "Glazed bowl",
        "category_id": cat.category_id,
        "price": 200.00,
        "stock_qty": 5,
        "images": ["https://malicious.example.com/exploit.jpg"],
    }

    res = client.post(
        "/api/products",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "Image URLs in JSON body are not supported" in res.get_json()["message"]


def test_get_uploaded_image_serves_file(client, app, db, tmp_path):
    """File serving: Uploaded images can be fetched via /api/uploads/ and /uploads/."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    user, _ = _create_user(db, "artisan_fetch@pes.edu", "artisan", shop_name="Photo Shop")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    data = {
        "title": "Photo Showcase",
        "desc": "Piece with photo",
        "category_id": str(cat.category_id),
        "price": "299.00",
        "stock_qty": "5",
        "images": [(io.BytesIO(JPEG_BYTES), "showcase.jpg", "image/jpeg")],
    }

    res = client.post(
        "/api/products",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    prod_id = res.get_json()["product_id"]

    with app.app_context():
        img = db.session.scalar(
            db.select(ProductImage).where(ProductImage.product_id == prod_id)
        )
        assert img is not None
        filename = os.path.basename(img.image_url)

    # Fetch via /api/uploads/<filename>
    res_api = client.get(f"/api/uploads/{filename}")
    assert res_api.status_code == 200
    assert res_api.data == JPEG_BYTES

    # Fetch via /uploads/<filename>
    res_root = client.get(f"/uploads/{filename}")
    assert res_root.status_code == 200
    assert res_root.data == JPEG_BYTES


def test_create_product_cleans_up_files_on_rollback(client, app, db, tmp_path, monkeypatch):
    """Integrity: Ensure uploaded files are deleted from disk if DB transaction fails."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    user, _ = _create_user(db, "artisan_fail@pes.edu", "artisan", shop_name="Fail Shop")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    def mock_commit():
        raise RuntimeError("Simulated DB connection failure during commit")

    monkeypatch.setattr(db.session, "commit", mock_commit)

    data = {
        "title": "Cleanup Test",
        "desc": "Testing file cleanup on abort",
        "category_id": str(cat.category_id),
        "price": "199.00",
        "stock_qty": "10",
        "images": [(io.BytesIO(JPEG_BYTES), "temp_cleanup.jpg", "image/jpeg")],
    }

    with pytest.raises(RuntimeError, match="Simulated DB connection failure"):
        client.post(
            "/api/products",
            data=data,
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {token}"},
        )

    # File must not linger in tmp_path
    remaining_files = os.listdir(str(tmp_path))
    assert len(remaining_files) == 0


def test_get_uploaded_webp_image_serves_correct_content_type(client, app, db, tmp_path):
    """File serving: Uploaded WebP images are served with Content-Type: image/webp."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    user, _ = _create_user(db, "artisan_webp@pes.edu", "artisan", shop_name="WebP Studio")
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    data = {
        "title": "WebP Showcase",
        "desc": "Piece with webp photo",
        "category_id": str(cat.category_id),
        "price": "299.00",
        "stock_qty": "5",
        "images": [(io.BytesIO(WEBP_BYTES), "showcase.webp", "image/webp")],
    }

    res = client.post(
        "/api/products",
        data=data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    prod_id = res.get_json()["product_id"]

    with app.app_context():
        img = db.session.scalar(
            db.select(ProductImage).where(ProductImage.product_id == prod_id)
        )
        assert img is not None
        filename = os.path.basename(img.image_url)

    # Fetch via /api/uploads/<filename>
    res_api = client.get(f"/api/uploads/{filename}")
    assert res_api.status_code == 200
    assert res_api.headers.get("Content-Type") == "image/webp"
    assert res_api.data == WEBP_BYTES

    # Fetch via root /uploads/<filename>
    res_root = client.get(f"/uploads/{filename}")
    assert res_root.status_code == 200
    assert res_root.headers.get("Content-Type") == "image/webp"
    assert res_root.data == WEBP_BYTES


def test_create_product_payload_too_large_returns_413(client, app, db):
    """Security: Requests exceeding MAX_CONTENT_LENGTH return HTTP 413 JSON error."""
    app.config["MAX_CONTENT_LENGTH"] = 1024
    user, _ = _create_user(db, "artisan_oversized@pes.edu", "artisan", shop_name="Studio")
    token = _artisan_token(app, user.user_id)

    oversized_data = {
        "title": "Oversized Listing",
        "desc": "A" * 2000,
        "category_id": "1",
        "price": "100.00",
        "stock_qty": "5",
    }

    res = client.post(
        "/api/products",
        data=oversized_data,
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 413
    body = res.get_json()
    assert body["error"] == "PAYLOAD_TOO_LARGE"
    assert body["status_code"] == 413
    assert "30 MB" in body["message"] or "maximum" in body["message"].lower()
    assert "timestamp" in body


def _create_test_product(
    db, artisan, category, title="Test Craft", price=100.00, stock=10, is_active=True
):
    prod = Product(
        artisan_id=artisan.artisan_id,
        category_id=category.category_id,
        title=title,
        description="Handcrafted authentic item",
        price=price,
        is_active=is_active,
    )
    db.session.add(prod)
    db.session.flush()
    inv = Inventory(
        product_id=prod.product_id,
        stock_quantity=stock,
        low_stock_threshold=5,
    )
    db.session.add(inv)
    db.session.commit()
    return prod, inv


def test_tc_prod_03_artisan_updates_own_listing(client, app, db):
    """TC-PROD-03 (High) - OMH-F-006

    Steps:    PUT /api/products/101 with price=499.00, stock_qty=35 (own product).
    Expected: HTTP 200; price 499.00; inventory 35.
    """
    user, artisan = _create_user(
        db, "artisan_tc03@pes.edu", "artisan", shop_name="Weaving Shed"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, inv = _create_test_product(
        db, artisan, cat, title="Woolen Shawl", price=450.00, stock=20
    )

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 499.00, "stock_qty": 35},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    body = res.get_json()
    assert body["product_id"] == prod.product_id
    assert body["price"] == 499.00
    assert body["stock_quantity"] == 35
    assert body["message"] == "Product listing updated successfully"

    with app.app_context():
        p = db.session.get(Product, prod.product_id)
        assert float(p.price) == 499.00
        i = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod.product_id)
        )
        assert i.stock_quantity == 35


def test_tc_prod_04_modify_other_artisans_product(client, app, db):
    """TC-PROD-04 (High) - OMH-F-006

    Steps:    Artisan A sends PUT /api/products/102 (owned by Artisan B).
    Expected: HTTP 403; error 'Not authorized to modify this listing'; data untouched.
    """
    user_a, _ = _create_user(
        db, "artisan_a_tc04@pes.edu", "artisan", shop_name="Studio Alpha"
    )
    token_a = _artisan_token(app, user_a.user_id)

    user_b, artisan_b = _create_user(
        db, "artisan_b_tc04@pes.edu", "artisan", shop_name="Studio Beta"
    )
    cat = _category(db, "Pottery", "pottery")
    prod_b, inv_b = _create_test_product(
        db, artisan_b, cat, title="Ceramic Teapot", price=320.00, stock=15
    )

    res = client.put(
        f"/api/products/{prod_b.product_id}",
        json={"price": 500.00, "stock_qty": 50},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert res.status_code == 403
    body = res.get_json()
    assert body["error"] == "FORBIDDEN"
    assert body["message"] == "Not authorized to modify this listing"

    with app.app_context():
        p = db.session.get(Product, prod_b.product_id)
        assert float(p.price) == 320.00
        i = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod_b.product_id)
        )
        assert i.stock_quantity == 15


def test_update_product_price_only_preserves_stock_and_desc(client, app, db):
    """Update only price: description and stock quantity remain unchanged."""
    user, artisan = _create_user(
        db, "artisan_price_only@pes.edu", "artisan", shop_name="Wood Shop"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Woodwork", "woodwork")
    prod, _ = _create_test_product(
        db, artisan, cat, title="Teak Table", price=250.00, stock=8
    )

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 310.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["price"] == 310.00
    assert body["description"] == "Handcrafted authentic item"
    assert body["stock_quantity"] == 8

    with app.app_context():
        p = db.session.get(Product, prod.product_id)
        assert float(p.price) == 310.00
        assert p.description == "Handcrafted authentic item"
        inv = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod.product_id)
        )
        assert inv.stock_quantity == 8


def test_update_product_description_aliases(client, app, db):
    """Update description via 'description' and 'desc' aliases."""
    user, artisan = _create_user(
        db, "artisan_desc_alias@pes.edu", "artisan", shop_name="Glass Art"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Glass", "glass")
    prod, _ = _create_test_product(
        db, artisan, cat, title="Glass Ornament", price=120.00, stock=5
    )

    # 1. Update using 'description'
    res1 = client.put(
        f"/api/products/{prod.product_id}",
        json={"description": "First updated description"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 200
    assert res1.get_json()["description"] == "First updated description"

    # 2. Update using 'desc' alias
    res2 = client.put(
        f"/api/products/{prod.product_id}",
        json={"desc": "Second updated description"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200
    assert res2.get_json()["description"] == "Second updated description"


def test_update_product_stock_aliases(client, app, db):
    """Update stock quantity via 'stock_qty' and 'stock_quantity' aliases."""
    user, artisan = _create_user(
        db, "artisan_stock_alias@pes.edu", "artisan", shop_name="Metalworks"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Metalwork", "metalwork")
    prod, _ = _create_test_product(
        db, artisan, cat, title="Bronze Bell", price=85.00, stock=10
    )

    # 1. Update using 'stock_qty'
    res1 = client.put(
        f"/api/products/{prod.product_id}",
        json={"stock_qty": 22},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 200
    assert res1.get_json()["stock_quantity"] == 22

    # 2. Update using 'stock_quantity'
    res2 = client.put(
        f"/api/products/{prod.product_id}",
        json={"stock_quantity": 40},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200
    assert res2.get_json()["stock_quantity"] == 40


def test_update_product_partial_preserves_omitted_fields(client, app, db):
    """Partial update preserves title, category, description, and images."""
    user, artisan = _create_user(
        db, "artisan_preserve@pes.edu", "artisan", shop_name="Pottery Loft"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Pottery", "pottery")
    prod, _ = _create_test_product(
        db, artisan, cat, title="Ceramic Pitcher", price=95.00, stock=14
    )

    # Add an image record
    img = ProductImage(
        product_id=prod.product_id,
        image_url="/uploads/pitcher.jpg",
        is_primary=True,
    )
    db.session.add(img)
    db.session.commit()

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 105.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    with app.app_context():
        p = db.session.get(Product, prod.product_id)
        assert p.title == "Ceramic Pitcher"
        assert p.category_id == cat.category_id
        assert p.description == "Handcrafted authentic item"
        assert float(p.price) == 105.00
        images = db.session.scalars(
            db.select(ProductImage).where(ProductImage.product_id == prod.product_id)
        ).all()
        assert len(images) == 1
        assert images[0].image_url == "/uploads/pitcher.jpg"


@pytest.mark.parametrize(
    "invalid_price",
    [0, 0.00, -1, -50.50, "abc", "nan", "inf", None, True],
)
def test_update_product_invalid_and_zero_price_rejected(client, app, db, invalid_price):
    """Invalid or zero price is rejected with HTTP 422 VALIDATION_ERROR."""
    user, artisan = _create_user(
        db, f"artisan_price_{abs(hash(str(invalid_price)))}@pes.edu", "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": invalid_price},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    body = res.get_json()
    assert body["error"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "invalid_stock",
    [-1, -10, 10.5, "10.5", "invalid", None, True],
)
def test_update_product_negative_and_fractional_stock_rejected(client, app, db, invalid_stock):
    """Negative, fractional, or non-integer stock is rejected with HTTP 422."""
    user, artisan = _create_user(
        db, f"artisan_stock_{abs(hash(str(invalid_stock)))}@pes.edu", "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"stock_qty": invalid_stock},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    body = res.get_json()
    assert body["error"] == "VALIDATION_ERROR"


def test_update_product_empty_body_rejected(client, app, db):
    """Empty JSON body is rejected with HTTP 400 INVALID_INPUT."""
    user, artisan = _create_user(
        db, "artisan_empty_body@pes.edu", "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.get_json()["error"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "unsupported_payload",
    [
        {"title": "New Title"},
        {"category_id": 2},
        {"is_active": False},
        {"artisan_id": 99},
        {"images": ["/uploads/fake.jpg"]},
    ],
)
def test_update_product_unsupported_fields_rejected(client, app, db, unsupported_payload):
    """Fields outside F-006 scope (title, category, is_active, images) return HTTP 422."""
    user, artisan = _create_user(
        db, f"artisan_unsupp_{abs(hash(str(unsupported_payload)))}@pes.edu",
        "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json=unsupported_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    body = res.get_json()
    assert body["error"] == "VALIDATION_ERROR"
    assert "not editable" in body["message"]


def test_update_product_missing_product_returns_404(client, app, db):
    """PUT to nonexistent product returns HTTP 404 NOT_FOUND."""
    user, _ = _create_user(
        db, "artisan_missing_prod@pes.edu", "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)

    res = client.put(
        "/api/products/999999",
        json={"price": 100.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.get_json()["error"] == "NOT_FOUND"


def test_update_product_already_inactive_returns_404(client, app, db):
    """Updating an already inactive product treats it as not found (HTTP 404)."""
    user, artisan = _create_user(
        db, "artisan_inactive_prod@pes.edu", "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(
        db, artisan, cat, price=100.00, stock=5, is_active=False
    )

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 200.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.get_json()["error"] == "NOT_FOUND"


def test_update_product_artisan_without_profile_returns_403(client, app, db):
    """Artisan user without an Artisan profile receives HTTP 403."""
    user, _ = _create_user(
        db, "artisan_no_profile_put@pes.edu", "artisan", shop_name=None
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")

    # Create product under another artisan so product exists
    _, artisan_other = _create_user(
        db, "artisan_other_prof@pes.edu", "artisan", shop_name="Other Shop"
    )
    prod, _ = _create_test_product(db, artisan_other, cat, price=100.00, stock=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 200.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Artisan profile required" in res.get_json()["message"]


def test_update_product_buyer_returns_403(client, app, db):
    """Buyer account receives HTTP 403 Forbidden."""
    buyer, _ = _create_user(db, "buyer_put@pes.edu", "buyer")
    buyer_token = _artisan_token(app, buyer.user_id, role="buyer")

    _, artisan = _create_user(
        db, "artisan_for_buyer_put@pes.edu", "artisan", shop_name="Shop"
    )
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 200.00},
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"


def test_update_product_unauthenticated_returns_401(client, app, db):
    """Unauthenticated request returns HTTP 401 Unauthorized."""
    _, artisan = _create_user(
        db, "artisan_unauth_put@pes.edu", "artisan", shop_name="Shop"
    )
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.put(
        f"/api/products/{prod.product_id}",
        json={"price": 200.00},
    )
    assert res.status_code == 401
    assert res.get_json()["error"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Soft-Delete Tests (OMH-F-006)
# ---------------------------------------------------------------------------

def test_soft_delete_product_artisan_success(client, app, db):
    """Artisan successfully soft-deletes own product (HTTP 200)."""
    user, artisan = _create_user(
        db, "artisan_soft_del@pes.edu", "artisan", shop_name="Pottery Lab"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Pottery", "pottery")
    prod, _ = _create_test_product(
        db, artisan, cat, title="Clay Mug", price=80.00, stock=12
    )

    res = client.delete(
        f"/api/products/{prod.product_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["product_id"] == prod.product_id
    assert body["is_active"] is False
    assert body["message"] == "Product listing soft-deleted successfully"

    with app.app_context():
        p = db.session.get(Product, prod.product_id)
        assert p is not None
        assert p.is_active is False


def test_soft_delete_preserves_database_records(client, app, db):
    """Soft deletion preserves Product, ProductImage, and Inventory rows."""
    user, artisan = _create_user(
        db, "artisan_preserve_del@pes.edu", "artisan", shop_name="Carvers"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Woodwork", "woodwork")
    prod, inv = _create_test_product(
        db, artisan, cat, title="Teak Figurine", price=220.00, stock=5
    )

    img = ProductImage(
        product_id=prod.product_id,
        image_url="/uploads/figurine.jpg",
        is_primary=True,
    )
    db.session.add(img)
    db.session.commit()

    res = client.delete(
        f"/api/products/{prod.product_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    with app.app_context():
        p = db.session.get(Product, prod.product_id)
        assert p is not None
        assert p.is_active is False
        assert p.title == "Teak Figurine"

        i = db.session.scalar(
            db.select(Inventory).where(Inventory.product_id == prod.product_id)
        )
        assert i is not None
        assert i.stock_quantity == 5

        imgs = db.session.scalars(
            db.select(ProductImage).where(ProductImage.product_id == prod.product_id)
        ).all()
        assert len(imgs) == 1
        assert imgs[0].image_url == "/uploads/figurine.jpg"


def test_soft_delete_product_disappears_from_catalog_search(client, app, db):
    """Soft-deleted product disappears from catalog search results."""
    user, artisan = _create_user(
        db, "artisan_catalog_search_del@pes.edu", "artisan", shop_name="Silk Co"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(
        db, artisan, cat, title="Unique Indigo Tapestry", price=950.00, stock=2
    )

    # 1. Before deletion: product is returned in catalog search
    res_before = client.get("/api/products?q=Indigo")
    assert res_before.status_code == 200
    ids_before = [p["product_id"] for p in res_before.get_json()["products"]]
    assert prod.product_id in ids_before

    # 2. Soft-delete product
    res_del = client.delete(
        f"/api/products/{prod.product_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_del.status_code == 200

    # 3. After deletion: product is excluded from catalog search
    res_after = client.get("/api/products?q=Indigo")
    assert res_after.status_code == 200
    ids_after = [p["product_id"] for p in res_after.get_json()["products"]]
    assert prod.product_id not in ids_after


def test_soft_delete_product_returns_404_on_public_detail(client, app, db):
    """Soft-deleted product returns HTTP 404 from public detail endpoint."""
    user, artisan = _create_user(
        db, "artisan_detail_del@pes.edu", "artisan", shop_name="Jewelry"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Metalwork", "metalwork")
    prod, _ = _create_test_product(
        db, artisan, cat, title="Silver Brooch", price=340.00, stock=3
    )

    # 1. Before deletion: 200 OK
    res_before = client.get(f"/api/products/{prod.product_id}")
    assert res_before.status_code == 200

    # 2. Soft-delete
    client.delete(
        f"/api/products/{prod.product_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    # 3. After deletion: 404 NOT_FOUND
    res_after = client.get(f"/api/products/{prod.product_id}")
    assert res_after.status_code == 404
    assert res_after.get_json()["error"] == "NOT_FOUND"


def test_soft_delete_buyer_returns_403(client, app, db):
    """Buyer account cannot delete products (HTTP 403 Forbidden)."""
    buyer, _ = _create_user(db, "buyer_del@pes.edu", "buyer")
    buyer_token = _artisan_token(app, buyer.user_id, role="buyer")

    _, artisan = _create_user(
        db, "artisan_del_by_buyer@pes.edu", "artisan", shop_name="Shop"
    )
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.delete(
        f"/api/products/{prod.product_id}",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert res.status_code == 403
    assert res.get_json()["error"] == "FORBIDDEN"


def test_soft_delete_non_owner_returns_403(client, app, db):
    """Artisan cannot soft-delete another artisan's product (HTTP 403)."""
    user_a, _ = _create_user(
        db, "artisan_a_del@pes.edu", "artisan", shop_name="Shop A"
    )
    token_a = _artisan_token(app, user_a.user_id)

    _, artisan_b = _create_user(
        db, "artisan_b_del@pes.edu", "artisan", shop_name="Shop B"
    )
    cat = _category(db, "Textiles", "textiles")
    prod_b, _ = _create_test_product(db, artisan_b, cat, price=100.00, stock=5)

    res = client.delete(
        f"/api/products/{prod_b.product_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 403
    body = res.get_json()
    assert body["error"] == "FORBIDDEN"
    assert body["message"] == "Not authorized to modify this listing"

    with app.app_context():
        p = db.session.get(Product, prod_b.product_id)
        assert p.is_active is True


def test_soft_delete_missing_product_returns_404(client, app, db):
    """DELETE to nonexistent product returns HTTP 404 NOT_FOUND."""
    user, _ = _create_user(
        db, "artisan_del_missing@pes.edu", "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)

    res = client.delete(
        "/api/products/999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.get_json()["error"] == "NOT_FOUND"


def test_soft_delete_already_inactive_product_returns_404(client, app, db):
    """DELETE on already soft-deleted product returns HTTP 404 NOT_FOUND."""
    user, artisan = _create_user(
        db, "artisan_del_twice@pes.edu", "artisan", shop_name="Shop"
    )
    token = _artisan_token(app, user.user_id)
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(
        db, artisan, cat, price=100.00, stock=5, is_active=False
    )

    res = client.delete(
        f"/api/products/{prod.product_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.get_json()["error"] == "NOT_FOUND"


def test_soft_delete_unauthenticated_returns_401(client, app, db):
    """Unauthenticated DELETE returns HTTP 401 Unauthorized."""
    _, artisan = _create_user(
        db, "artisan_del_unauth@pes.edu", "artisan", shop_name="Shop"
    )
    cat = _category(db, "Textiles", "textiles")
    prod, _ = _create_test_product(db, artisan, cat, price=100.00, stock=5)

    res = client.delete(f"/api/products/{prod.product_id}")
    assert res.status_code == 401
    assert res.get_json()["error"] == "UNAUTHORIZED"


@SKIP
def test_tc_prod_05_catalog_keyword_search_filter():
    """TC-PROD-05 (High) - OMH-F-007
    Steps:    GET /api/products?q=ceramic&category=1.
    Expected: HTTP 200; only active pottery products containing 'ceramic'.
    """
    pass
