from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
import app.routes.public_contract_verification as public_compare
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.entrypoint import app


client = TestClient(app)


def _seed_pair(*, same_title: bool = True):
    now = datetime.now(timezone.utc)
    closes = datetime(2026, 11, 3, 20, tzinfo=timezone.utc)
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id="kalshi:KXPUBLIC",
            title="Will candidate X win the 2026 election?",
            venue="kalshi",
            probability=.58,
            trend_score=80,
            observed_at=now,
            closes_at=closes,
        ),
        core.DiscoveryMarket(
            canonical_id="polymarket:456",
            title=("Will candidate X win the 2026 election?" if same_title else "Will inflation exceed 5% in 2026?"),
            venue="polymarket",
            probability=.62,
            trend_score=82,
            observed_at=now,
            closes_at=closes,
        ),
    ])


def _clear_cache():
    public_compare._FACT_CACHE.clear()


def test_public_verified_compare_is_registered_and_templates_use_it():
    assert "/api/v1/compare/verified" in app.openapi()["paths"]
    index = open("app/templates/index.html", encoding="utf-8").read()
    top = open("app/templates/top.html", encoding="utf-8").read()
    assert "/api/v1/compare/verified?" in index
    assert "/api/v1/compare/verified?" in top


def test_public_verified_compare_uses_resolution_evidence_and_cache(monkeypatch):
    _clear_cache()
    _seed_pair()
    calls = {"kalshi": 0, "polymarket": 0}

    async def fake_kalshi(self, ticker):
        calls["kalshi"] += 1
        return {"market": {
            "title": "Will candidate X win the 2026 election?",
            "close_time": "2026-11-03T20:00:00Z",
            "resolution_source": "https://apnews.com/elections",
            "rules_primary": "The Associated Press race call determines the winner of the 2026 election.",
        }}

    async def fake_poly(self, market_id):
        calls["polymarket"] += 1
        return {
            "question": "Will candidate X win the 2026 election?",
            "endDate": "2026-11-03T21:00:00Z",
            "resolutionSource": "https://www.apnews.com/elections",
            "description": "This market resolves based on the Associated Press race call for the 2026 election winner.",
        }

    monkeypatch.setattr(KalshiAdapter, "fetch_market", fake_kalshi)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_poly)

    params = {"left_id": "kalshi:KXPUBLIC", "right_id": "polymarket:456"}
    first = client.get("/api/v1/compare/verified", params=params)
    second = client.get("/api/v1/compare/verified", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload["equivalent_contracts"] is True
    assert payload["consensus_probability"] == .6
    assert payload["gap_points"] == 4
    assert payload["source_match"] is True
    assert payload["confidence"] >= 85
    assert first.headers["cache-control"].startswith("public, max-age=60")
    assert calls == {"kalshi": 1, "polymarket": 1}
    _clear_cache()


def test_unrelated_pair_is_rejected_without_external_calls(monkeypatch):
    _clear_cache()
    _seed_pair(same_title=False)
    calls = 0

    async def should_not_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("external venue lookup should not run for an unrelated pair")

    monkeypatch.setattr(KalshiAdapter, "fetch_market", should_not_call)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", should_not_call)

    response = client.get(
        "/api/v1/compare/verified",
        params={"left_id": "kalshi:KXPUBLIC", "right_id": "polymarket:456"},
    )
    assert response.status_code == 200
    assert response.json()["equivalent_contracts"] is False
    assert calls == 0
    _clear_cache()


def test_cross_platform_verifier_rejects_two_distinct_same_venue_markets():
    _clear_cache()
    now = datetime.now(timezone.utc)
    core.set_discovery_markets([
        core.DiscoveryMarket(canonical_id="kalshi:A", title="Will X happen?", venue="kalshi", probability=.5, trend_score=1, observed_at=now),
        core.DiscoveryMarket(canonical_id="kalshi:B", title="Will X happen?", venue="kalshi", probability=.5, trend_score=1, observed_at=now),
    ])
    response = client.get(
        "/api/v1/compare/verified",
        params={"left_id": "kalshi:A", "right_id": "kalshi:B"},
    )
    assert response.status_code == 422
