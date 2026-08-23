from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as core
import app.routes.public_venue_conditions as venue_routes
from app.entrypoint import app


client = TestClient(app)


def _seed():
    now = datetime.now(timezone.utc)
    kalshi = core.DiscoveryMarket(
        canonical_id="kalshi:KXVENUE",
        title="Will X happen?",
        venue="kalshi",
        probability=.58,
        volume_usd=100_000,
        trend_score=70,
        observed_at=now,
    )
    poly = core.DiscoveryMarket(
        canonical_id="polymarket:77",
        title="Will X happen?",
        venue="polymarket",
        probability=.62,
        volume_usd=200_000,
        trend_score=72,
        observed_at=now,
    )
    core.set_discovery_markets([kalshi, poly])
    return kalshi, poly


def _execution(score, spread, bid_depth, ask_depth):
    return SimpleNamespace(
        available=True,
        best_bid=.55,
        best_ask=.55 + spread / 100,
        midpoint=.56,
        spread_points=spread,
        bid_depth_units=bid_depth,
        ask_depth_units=ask_depth,
        score=score,
        grade="good",
    )


def test_venue_conditions_compare_only_verified_equivalent_contracts(monkeypatch):
    kalshi, poly = _seed()

    async def fake_cross(response, market_id, candidate_limit=3):
        return SimpleNamespace(
            counterpart=poly,
            verification=SimpleNamespace(equivalent_contracts=True, confidence=93, reasons=[]),
        )

    async def fake_execution(market_id):
        return _execution(82, 1.0, 2500, 2200) if market_id == kalshi.canonical_id else _execution(74, 2.0, 1800, 1600)

    monkeypatch.setattr(venue_routes, "market_cross_platform", fake_cross)
    monkeypatch.setattr(venue_routes, "_safe_execution", fake_execution)
    response = client.get("/api/v1/market/venue-conditions", params={"market_id": kalshi.canonical_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["equivalent_contracts"] is True
    assert payload["verification_confidence"] == 93
    assert len(payload["venues"]) == 2
    by_venue = {item["venue"]: item for item in payload["venues"]}
    assert by_venue["kalshi"]["spread_points"] == 1
    assert by_venue["polymarket"]["spread_points"] == 2
    assert by_venue["kalshi"]["reported_volume_usd"] == 100000
    assert "does not rank a best venue" in payload["disclaimer"]
    assert response.headers["cache-control"].startswith("public, max-age=10")


def test_unverified_pair_never_triggers_execution_comparison(monkeypatch):
    kalshi, poly = _seed()
    calls = 0

    async def fake_cross(response, market_id, candidate_limit=3):
        return SimpleNamespace(
            counterpart=poly,
            verification=SimpleNamespace(equivalent_contracts=False, confidence=40, reasons=["resolution evidence insufficient"]),
        )

    async def should_not_call(_):
        nonlocal calls
        calls += 1
        raise AssertionError("execution comparison must not run for an unverified pair")

    monkeypatch.setattr(venue_routes, "market_cross_platform", fake_cross)
    monkeypatch.setattr(venue_routes, "_safe_execution", should_not_call)
    response = client.get("/api/v1/market/venue-conditions", params={"market_id": kalshi.canonical_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["equivalent_contracts"] is False
    assert payload["venues"] == []
    assert calls == 0


def test_market_page_shows_verified_venue_conditions_without_best_venue_claim():
    kalshi, _ = _seed()
    response = client.get("/market", params={"market_id": kalshi.canonical_id})
    assert response.status_code == 200
    assert "VERIFIED VENUE CONDITIONS" in response.text
    assert "/api/v1/market/venue-conditions?" in response.text
    assert "does not label a best venue" in response.text
    assert "No best-venue ranking" in response.text
    assert "setInterval(loadVenueConditions,30000)" in response.text


def test_venue_conditions_endpoint_is_registered():
    assert "/api/v1/market/venue-conditions" in app.openapi()["paths"]
