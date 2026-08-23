from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
from app.entrypoint import app
from app.main import DiscoveryMarket


client = TestClient(app)


def _seed():
    core.set_discovery_markets([
        DiscoveryMarket(
            canonical_id="kalshi:mobile-privacy",
            slug="kalshi-mobile-privacy-market",
            title="Will the mobile market work?",
            venue="kalshi",
            probability=.61,
            volume_usd=12345,
            trend_score=80,
            observed_at=datetime.now(timezone.utc),
            source_url="https://kalshi.com/markets/mobile-privacy",
        )
    ])


def test_mobile_market_has_touch_navigation_and_no_commission_percentage(monkeypatch):
    _seed()
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "true")
    monkeypatch.setenv("MP_KALSHI_PARTNER_ID", "super-secret-partner-id")
    response = client.get("/markets/kalshi-mobile-privacy-market")
    assert response.status_code == 200
    body = response.text
    assert 'class="pb-mobile-nav"' in body
    assert 'min-height:52px' in body
    assert 'position:sticky;bottom:84px' in body
    assert "may receive compensation from approved partners" in body
    lowered = body.casefold()
    assert "super-secret-partner-id" not in body
    assert "commission_amount" not in lowered
    assert "commission rate" not in lowered
    assert "commission percentage" not in lowered
    assert "revenue share" not in lowered


def test_public_route_never_exposes_partner_id_or_commission(monkeypatch):
    _seed()
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "true")
    monkeypatch.setenv("MP_KALSHI_PARTNER_ID", "super-secret-partner-id")
    response = client.get("/api/v1/market/route", params={"market_id": "kalshi:mobile-privacy"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "partner"
    serialized = response.text.casefold()
    assert "super-secret-partner-id" not in response.text
    assert "commission" not in serialized
    assert "revenue" not in serialized


def test_outbound_location_is_venue_market_not_internal_commercial_data(tmp_path, monkeypatch):
    _seed()
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "mobile.db"))
    monkeypatch.setenv("MP_KALSHI_COMMERCIAL_VERIFIED", "true")
    monkeypatch.setenv("MP_KALSHI_PARTNER_ID", "super-secret-partner-id")
    response = client.get(
        "/out/kalshi",
        params={"market_id": "kalshi:mobile-privacy", "channel": "mobile"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://kalshi.com/markets/mobile-privacy"
    assert "super-secret-partner-id" not in response.headers["location"]
    assert "commission" not in response.headers["location"].casefold()
