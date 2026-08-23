from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
from app.entrypoint import app
from app.main import DiscoveryMarket


client = TestClient(app)


def _seed_routes():
    now = datetime.now(timezone.utc)
    core.set_discovery_markets([
        DiscoveryMarket(
            canonical_id="kalshi:launch",
            title="Launch readiness Kalshi",
            venue="kalshi",
            probability=.5,
            volume_usd=100,
            trend_score=50,
            observed_at=now,
            source_url="https://kalshi.com/markets/launch",
        ),
        DiscoveryMarket(
            canonical_id="polymarket:launch",
            title="Launch readiness Polymarket",
            venue="polymarket",
            probability=.5,
            volume_usd=100,
            trend_score=50,
            observed_at=now,
            source_url="https://polymarket.com/event/launch",
        ),
    ])


def test_launch_readiness_is_private_and_partner_status_does_not_fake_approval(tmp_path, monkeypatch):
    token = "a" * 40
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "launch.db"))
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")
    monkeypatch.delenv("MP_KALSHI_COMMERCIAL_VERIFIED", raising=False)
    monkeypatch.delenv("MP_KALSHI_PARTNER_ID", raising=False)
    monkeypatch.delenv("MP_POLYMARKET_COMMERCIAL_VERIFIED", raising=False)
    monkeypatch.delenv("MP_POLYMARKET_PARTNER_ID", raising=False)
    _seed_routes()

    assert client.get("/api/v1/admin/launch-readiness").status_code == 401
    response = client.get(
        "/api/v1/admin/launch-readiness",
        headers={"X-MarketPulse-Admin-Token": token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["partner_monetization"]["modes"] == {"kalshi": "organic", "polymarket": "organic"}
    assert data["partner_monetization"]["blocks_product_launch"] is False
    assert data["partner_monetization"]["active_partner_venues"] == []


def test_partner_mode_requires_both_verification_and_partner_id(tmp_path, monkeypatch):
    token = "b" * 40
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "launch.db"))
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com")
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "true")
    monkeypatch.setenv("MP_KALSHI_PARTNER_ID", "partner-123")
    monkeypatch.setenv("MP_POLYMARKET_COMMERCIAL_VERIFIED", "true")
    monkeypatch.delenv("MP_POLYMARKET_PARTNER_ID", raising=False)
    _seed_routes()

    data = client.get(
        "/api/v1/admin/launch-readiness",
        headers={"X-MarketPulse-Admin-Token": token},
    ).json()
    assert data["partner_monetization"]["modes"]["kalshi"] == "partner"
    assert data["partner_monetization"]["modes"]["polymarket"] == "organic"
    assert data["partner_monetization"]["active_partner_venues"] == ["kalshi"]
