from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_operations_page_is_noindex_and_hardened():
    response = client.get("/admin/operations")
    assert response.status_code == 200
    assert '<meta name="robots" content="noindex,nofollow">' in response.text
    assert 'type="password"' in response.text
    assert "localStorage" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"


def test_operations_api_fails_closed_without_credentials(monkeypatch):
    monkeypatch.setenv("MP_ADMIN_TOKEN", "a" * 32)
    response = client.get("/api/v1/admin/operations")
    assert response.status_code == 401


def test_operations_api_reports_checks_without_echoing_secret(monkeypatch):
    secret = "b" * 32
    monkeypatch.setenv("MP_ADMIN_TOKEN", secret)
    response = client.get(
        "/api/v1/admin/operations",
        headers={"X-MarketPulse-Admin-Token": secret},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall"] in {"healthy", "warning", "critical"}
    assert payload["checks"]
    assert all({"name", "ok", "severity", "detail"} <= item.keys() for item in payload["checks"])
    assert secret not in response.text
    assert "MP_OPENAI_API_KEY" not in response.text
