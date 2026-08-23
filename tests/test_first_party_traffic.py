from fastapi.testclient import TestClient

from app.entrypoint import app
from app.storage.traffic import TrafficStore


client = TestClient(app)


def test_successful_public_html_views_are_aggregated(tmp_path, monkeypatch):
    db = tmp_path / "traffic.db"
    monkeypatch.setenv("MP_DATABASE_PATH", str(db))
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")

    assert client.get("/?channel=organic").status_code == 200
    assert client.get("/methodology?channel=newsletter").status_code == 200
    assert client.get("/api/v1/status").status_code == 200
    assert client.get("/definitely-missing").status_code == 404

    data = TrafficStore(str(db)).summary(days=1)
    assert data["page_views"] == 2
    assert data["views_by_surface"] == {"home": 1, "methodology": 1}
    assert data["views_by_channel"] == {"newsletter": 1, "organic": 1}


def test_admin_traffic_summary_is_private_and_includes_funnel(tmp_path, monkeypatch):
    db = tmp_path / "traffic.db"
    token = "t" * 40
    monkeypatch.setenv("MP_DATABASE_PATH", str(db))
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)

    client.get("/")
    unauthorized = client.get("/api/v1/admin/traffic")
    assert unauthorized.status_code == 401

    response = client.get(
        "/api/v1/admin/traffic?days=30",
        headers={"X-MarketPulse-Admin-Token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["page_views"] >= 1
    assert payload["funnel"]["home_views"] >= 1
    assert payload["funnel"]["outbound_clicks"] == 0
    assert "visitor identifiers" in payload["privacy"]
