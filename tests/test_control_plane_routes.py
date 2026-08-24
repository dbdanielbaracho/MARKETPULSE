from copy import deepcopy
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.entrypoint import app
from app.main import DiscoveryMarket, set_discovery_markets
from app.storage.control_plane import DEFAULT_CONTROL_PLANE


client = TestClient(app)


def _market() -> DiscoveryMarket:
    return DiscoveryMarket(
        canonical_id="kalshi:control-plane",
        title="Control Plane test market",
        venue="kalshi",
        probability=.5,
        trend_score=50,
        observed_at=datetime.now(timezone.utc),
        source_url="https://kalshi.com/markets/control-plane",
    )


def test_control_plane_admin_page_is_private_and_does_not_persist_token():
    response = client.get("/admin/control-plane")
    assert response.status_code == 200
    assert 'name="robots" content="noindex,nofollow"' in response.text
    assert "sessionStorage" not in response.text
    assert "localStorage" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"


def test_control_plane_requires_admin_and_publish_changes_live_route(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "control.db"))
    monkeypatch.setenv("MP_ADMIN_TOKEN", "a" * 32)
    set_discovery_markets([_market()])
    admin = {"X-MarketPulse-Admin-Token": "a" * 32}

    assert client.get("/api/v1/admin/control-plane").status_code == 401
    snapshot = client.get("/api/v1/admin/control-plane", headers=admin)
    assert snapshot.status_code == 200

    payload = deepcopy(DEFAULT_CONTROL_PLANE)
    payload["providers"]["kalshi"].update({
        "commercial_verified": True,
        "partner_id": "pb-test-partner",
        "tracking_parameter": "ref",
        "tracking_value": "pb-test-code",
    })
    saved = client.put("/api/v1/admin/control-plane/draft", headers=admin, json=payload)
    assert saved.status_code == 200

    before = client.get(
        "/api/v1/market/route",
        params={"market_id": "kalshi:control-plane"},
        headers={"CF-IPCountry": "US"},
    )
    assert before.status_code == 200
    assert before.json()["mode"] == "organic"

    published = client.post("/api/v1/admin/control-plane/publish", headers=admin)
    assert published.status_code == 200
    after = client.get(
        "/api/v1/market/route",
        params={"market_id": "kalshi:control-plane"},
        headers={"CF-IPCountry": "US"},
    )
    assert after.status_code == 200
    assert after.json()["mode"] == "partner"

    outbound = client.get(
        "/out/kalshi",
        params={"market_id": "kalshi:control-plane"},
        headers={"CF-IPCountry": "US"},
        follow_redirects=False,
    )
    assert outbound.status_code == 302
    assert outbound.headers["location"].endswith("?ref=pb-test-code")
    assert outbound.headers["x-predibeacon-route-mode"] == "partner"


def test_known_blocked_country_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "blocked.db"))
    set_discovery_markets([_market()])

    route = client.get(
        "/api/v1/market/route",
        params={"market_id": "kalshi:control-plane"},
        headers={"CF-IPCountry": "BR"},
    )
    assert route.status_code == 200
    assert route.json()["available"] is False
    assert route.json()["reason"] == "jurisdiction_unavailable"

    outbound = client.get(
        "/out/kalshi",
        params={"market_id": "kalshi:control-plane"},
        headers={"CF-IPCountry": "BR"},
        follow_redirects=False,
    )
    assert outbound.status_code == 451
