from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_revenue_page_is_hardened():
    response = client.get("/admin/revenue")
    assert response.status_code == 200
    assert 'noindex,nofollow' in response.text
    assert 'type="password"' in response.text
    assert "Administrator sign in" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"


def test_revenue_api_fails_closed(monkeypatch):
    monkeypatch.setenv("MP_ADMIN_TOKEN", "a" * 32)
    assert client.get("/api/v1/admin/revenue").status_code == 401


def test_revenue_api_truthful_zero_state(monkeypatch, tmp_path):
    token = "b" * 32
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "marketpulse.db"))
    response = client.get(
        "/api/v1/admin/revenue",
        headers={"X-MarketPulse-Admin-Token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["record_count"] == 0
    assert payload["known_commission_totals"] == {}
    assert payload["commercial_intake_enabled"] is False
