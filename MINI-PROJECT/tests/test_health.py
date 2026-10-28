from app import create_app


def test_health_returns_ok_when_database_is_available():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
        }
    )

    client = app.test_client()
    response = client.get("/api/health")

    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "uptime_seconds" in data
