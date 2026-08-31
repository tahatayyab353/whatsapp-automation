from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_system_info_endpoint():
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert data["environment"] == settings.ENVIRONMENT
    assert "X-Request-ID" in response.headers


def test_system_info_does_not_leak_secrets():
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    data_str = str(response.json()).lower()

    # Sensitive keys and patterns that must never appear in public responses
    sensitive_terms = [
        "password",
        "secret",
        "postgres://",
        "postgresql://",
        "bearer",
        "openai_api_key",
        "whatsapp_access_token",
        "whatsapp_app_secret",
        "c:\\",
        "/etc/",
    ]
    for term in sensitive_terms:
        assert term not in data_str, f"Found sensitive leak: {term}"


def test_404_structured_error_response():
    response = client.get("/api/v1/nonexistent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
    assert "X-Request-ID" in response.headers


def test_openapi_spec_available():
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "paths" in spec
    assert "/api/v1/health" in spec["paths"]
    assert "/api/v1/system/info" in spec["paths"]

