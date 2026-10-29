"""Authentication & RBAC tests (SE8-12 / SE8-14 / SE8-16) - STP section 13.1"""
import bcrypt
import pytest

from app.models import User

SKIP = pytest.mark.skip(
    reason="Waiting for app skeleton / not implemented yet")


def test_tc_auth_01_valid_buyer_registration(client, app, db):
    """TC-AUTH-01 (High) - OMH-F-001
    Steps:    POST /api/auth/register with valid email, name, role=buyer.
    Expected: HTTP 201; user row in DB; password hashed with bcrypt.
    """
    payload = {
        "email": "test_buyer@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Test Buyer",
        "role": "buyer",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201

    data = response.get_json()
    assert "user_id" in data
    assert data["email"] == "test_buyer@pes.edu"
    assert data["full_name"] == "Test Buyer"
    assert data["role"] == "buyer"

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "test_buyer@pes.edu")
        )
        assert user is not None
        assert user.full_name == "Test Buyer"
        assert user.role == "buyer"
        assert user.user_id == data["user_id"]
        # Verify password is not plaintext
        assert user.password_hash != "StrongP@ss123"
        assert user.password_hash.startswith("$2b$12$")


def test_tc_auth_02_duplicate_email_registration(client, app, db):
    """TC-AUTH-02 (High) - OMH-F-001
    Steps:    POST /api/auth/register again with the same email.
    Expected: HTTP 409; error 'Email already registered'; no duplicate row.
    """
    payload = {
        "email": "test_buyer@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Test Buyer",
        "role": "buyer",
    }
    # Initial registration
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with identical email
    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    data2 = res2.get_json()
    assert data2.get("message") == "Email already registered"

    # Registration with case-variant email
    variant_payload = dict(payload, email="TEST_BUYER@PES.EDU")
    res3 = client.post("/api/auth/register", json=variant_payload)
    assert res3.status_code == 409
    data3 = res3.get_json()
    assert data3.get("message") == "Email already registered"

    with app.app_context():
        count = db.session.query(User).filter(User.email == "test_buyer@pes.edu").count()
        assert count == 1


def test_password_is_bcrypt_hash_and_verifiable(client, app, db):
    """OMH-SR-001 / TC-SEC-03: Stored password must be bcrypt hash ($2b$12$) and verifiable."""
    raw_password = "StrongP@ss123"
    payload = {
        "email": "artisan_secure@pes.edu",
        "password": raw_password,
        "full_name": "Secure Artisan",
        "role": "artisan",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "artisan_secure@pes.edu")
        )
        assert user is not None
        # Must start with $2b$12$
        assert user.password_hash.startswith("$2b$12$")
        assert len(user.password_hash) == 60
        # bcrypt verification succeeds with correct password
        assert bcrypt.checkpw(raw_password.encode("utf-8"), user.password_hash.encode("utf-8"))
        # bcrypt verification fails with wrong password
        assert not bcrypt.checkpw(b"WrongP@ss999", user.password_hash.encode("utf-8"))


def test_valid_artisan_registration(client, app, db):
    """Register user with artisan role."""
    payload = {
        "email": "clay_crafter@pes.edu",
        "password": "ArtisanPass123",
        "full_name": "Clay Crafter",
        "role": "artisan",
        "shop_name": "Clay Studio",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["role"] == "artisan"

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "clay_crafter@pes.edu")
        )
        assert user is not None
        assert user.role == "artisan"


@pytest.mark.parametrize(
    "invalid_payload,expected_err",
    [
        ({}, "Email is required"),
        ({"password": "Pass1234", "full_name": "A", "role": "buyer"}, "Email is required"),
        (
            {"email": "", "password": "Pass1234", "full_name": "A", "role": "buyer"},
            "Email is required",
        ),
        (
            {
                "email": "not-an-email",
                "password": "Pass1234",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Invalid email format",
        ),
        (
            {"email": "valid@pes.edu", "full_name": "Valid Name", "role": "buyer"},
            "Password is required",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "short",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "alllowercaseno1",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "ALLUPPERCASENO1",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "NoDigitsAtAllHere",
                "full_name": "Valid Name",
                "role": "buyer",
            },
            "Password must be at least 8 characters",
        ),
        (
            {"email": "valid@pes.edu", "password": "StrongP@ss123", "role": "buyer"},
            "Full name is required",
        ),
        (
            {
                "email": "valid@pes.edu",
                "password": "StrongP@ss123",
                "full_name": "X",
                "role": "buyer",
            },
            "Full name must be between 2 and 120 characters",
        ),
        (
            {"email": "valid@pes.edu", "password": "StrongP@ss123", "full_name": "Valid Name"},
            "Role is required",
        ),
    ],
)
def test_registration_missing_or_malformed_fields(client, invalid_payload, expected_err):
    """Missing or malformed input must return HTTP 400 with a descriptive error."""
    res = client.post("/api/auth/register", json=invalid_payload)
    assert res.status_code == 400
    data = res.get_json()
    assert expected_err in data["message"]


def test_registration_empty_body(client):
    """Submitting empty or non-JSON body must return HTTP 400."""
    res = client.post("/api/auth/register", data="not json", content_type="text/plain")
    assert res.status_code == 400


def test_registration_invalid_or_unauthorized_roles(client, app, db):
    """Registration with unauthorized 'admin' role or invalid role must be rejected."""
    # Attempting to register as admin (privilege escalation)
    admin_payload = {
        "email": "hacker@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Hacker Admin",
        "role": "admin",
    }
    res_admin = client.post("/api/auth/register", json=admin_payload)
    assert res_admin.status_code in (400, 403)
    assert "administrator" in res_admin.get_json()["message"].lower()

    # Verify no admin user was created in DB
    with app.app_context():
        admin_user = db.session.scalar(
            db.select(User).where(User.email == "hacker@pes.edu")
        )
        assert admin_user is None

    # Invalid role
    res_invalid = client.post(
        "/api/auth/register",
        json={
            "email": "invalid_role@pes.edu",
            "password": "StrongP@ss123",
            "full_name": "Invalid Role",
            "role": "superman",
        },
    )
    assert res_invalid.status_code == 400
    assert "role" in res_invalid.get_json()["message"].lower()


def test_registration_response_does_not_expose_password_or_hash(client):
    """Responses must never expose plaintext password or password hash."""
    payload = {
        "email": "safe_user@pes.edu",
        "password": "StrongP@ss123",
        "full_name": "Safe User",
        "role": "buyer",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201

    data = res.get_json()
    assert "password" not in data
    assert "password_hash" not in data
    assert "StrongP@ss123" not in res.get_data(as_text=True)
    assert "$2b$" not in res.get_data(as_text=True)


def test_registration_normalizes_email(client, app, db):
    """Email must be trimmed and converted to lowercase."""
    payload = {
        "email": "   User.Normalized@PES.EDU   ",
        "password": "StrongP@ss123",
        "full_name": "Normalized User",
        "role": "buyer",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    assert res.get_json()["email"] == "user.normalized@pes.edu"

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "user.normalized@pes.edu")
        )
        assert user is not None
        assert user.email == "user.normalized@pes.edu"


@SKIP
def test_tc_auth_03_login_returns_jwt():
    """TC-AUTH-03 (High) - OMH-F-002
    Steps:    POST /api/auth/login with valid credentials; decode the JWT.
    Expected: HTTP 200; token returned; payload has user_id, role='buyer', exp=24 hours.
    """
    pass


@SKIP
def test_tc_auth_04_login_wrong_password():
    """TC-AUTH-04 (High) - OMH-F-002
    Steps:    POST /api/auth/login with a wrong password.
    Expected: HTTP 401; error 'Invalid credentials'; no token issued.
    """
    pass


@SKIP
def test_tc_auth_05_rbac_denies_buyer_on_artisan_route():
    """TC-AUTH-05 (High) - OMH-F-003
    Steps:    GET /api/seller/dashboard with a Buyer JWT.
    Expected: HTTP 403; error 'Artisan privilege required'.
    """
    pass


@SKIP
def test_tc_auth_06_password_reset_flow():
    """TC-AUTH-06 (Medium) - OMH-F-004
    Steps:    POST /api/auth/reset-password; take token from Mailtrap;
          POST /api/auth/reset-password/confirm.
    Expected: HTTP 200; password updated; login with new password works. (SE8-17 stretch)
    """
    pass


@SKIP
def test_tc_auth_07_password_reset_expired_token():
    """TC-AUTH-07 (Medium) - OMH-F-004
    Steps:    Submit a token older than 15 minutes to /api/auth/reset-password/confirm.
    Expected: HTTP 400; error 'Reset token has expired'; password unchanged. (SE8-17 stretch)
    """
    pass
