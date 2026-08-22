from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import DiscoveryMarket, app, set_discovery_markets
from app.storage.revenue import RevenueStore


client = TestClient(app, follow_redirects=False)


def test_discovery_campaign_outbound_and_api_key_lifecycle(tmp_path, monkeypatch):
    database = tmp_path / "journey.db"
    monkeypatch.setenv("MP_DATABASE_PATH", str(database))
    monkeypatch.setenv("MP_ADMIN_TOKEN", "a" * 32)
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")
    market = DiscoveryMarket(
        canonical_id="kalshi:e2e",
        title="Will the test journey finish successfully?",
        venue="kalshi",
        category="Technology",
        probability=0.63,
        probability_change=0.04,
        volume_usd=1200,
        trend_score=82,
        observed_at=datetime.now(timezone.utc),
        source_url="https://kalshi.com/markets/e2e",
    )
    set_discovery_markets([market])
    admin = {"X-MarketPulse-Admin-Token": "a" * 32}
    try:
        listing = client.get("/api/v1/markets")
        assert listing.status_code == 200
        slug = listing.json()[0]["slug"]

        campaign = client.post(
            "/api/v1/admin/campaign-links",
            headers=admin,
            json={
                "slug": "e2e-release",
                "market_id": market.canonical_id,
                "creator_id": "creator-e2e",
                "channel": "x",
            },
        )
        assert campaign.status_code == 200
        assert campaign.json()["public_url"] == "https://predibeacon.com/go/e2e-release"

        entry = client.get("/go/e2e-release")
        assert entry.status_code == 302
        assert entry.headers["location"].startswith(f"/markets/{slug}?")
        assert "creator_id=creator-e2e" in entry.headers["location"]

        detail = client.get(f"/markets/{slug}")
        assert detail.status_code == 200
        assert "PrediBeacon" in detail.text

        outbound = client.get(
            "/out/kalshi",
            params={
                "market_id": market.canonical_id,
                "campaign_id": "e2e-release",
                "creator_id": "creator-e2e",
                "channel": "x",
            },
            headers={"Referer": f"https://predibeacon.com/markets/{slug}"},
        )
        assert outbound.status_code == 302
        assert outbound.headers["location"] == market.source_url
        assert outbound.headers["x-predibeacon-click-id"]
        summary = RevenueStore(str(database)).creator_summary("creator-e2e")
        assert summary["click_count"] == 1
        assert summary["market_count"] == 1
        assert summary["paid_partner_revenue_totals"] == {}

        created = client.post(
            "/api/v1/admin/api-keys",
            headers=admin,
            json={"name": "E2E client", "scopes": ["markets:read"], "daily_limit": 10},
        )
        assert created.status_code == 200
        old_key = created.json()["api_key"]
        commercial = client.get(
            "/api/v1/commercial/markets",
            headers={"X-PrediBeacon-API-Key": old_key},
        )
        assert commercial.status_code == 200
        assert commercial.json()[0]["canonical_id"] == market.canonical_id

        rotated = client.post(
            f"/api/v1/admin/api-keys/{created.json()['key_id']}/rotate",
            headers=admin,
        )
        assert rotated.status_code == 200
        assert client.get(
            "/api/v1/commercial/markets",
            headers={"X-PrediBeacon-API-Key": old_key},
        ).status_code == 401
        assert client.get(
            "/api/v1/commercial/markets",
            headers={"X-PrediBeacon-API-Key": rotated.json()["api_key"]},
        ).status_code == 200
    finally:
        set_discovery_markets([])
