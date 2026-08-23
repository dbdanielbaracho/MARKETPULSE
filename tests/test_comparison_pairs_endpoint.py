from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
import app.routes.public_contract_verification as public_compare
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.entrypoint import app


client = TestClient(app)


def _seed():
    now = datetime.now(timezone.utc)
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id="kalshi:KXCAND",
            title="Will Candidate X win the 2026 presidential election?",
            venue="kalshi",
            category="Politics",
            probability=.58,
            trend_score=80,
            observed_at=now,
            closes_at=datetime(2026, 11, 3, 20, tzinfo=timezone.utc),
        ),
        core.DiscoveryMarket(
            canonical_id="polymarket:789",
            title="Will Candidate X win the presidential election in 2026?",
            venue="polymarket",
            category="Politics",
            probability=.62,
            trend_score=82,
            observed_at=now,
            closes_at=datetime(2026, 11, 3, 21, tzinfo=timezone.utc),
        ),
        core.DiscoveryMarket(
            canonical_id="polymarket:other",
            title="Will inflation exceed 5% in 2026?",
            venue="polymarket",
            category="Economy",
            probability=.3,
            trend_score=40,
            observed_at=now,
            closes_at=datetime(2026, 11, 3, 20, tzinfo=timezone.utc),
        ),
    ])


def test_pair_endpoint_discovers_near_title_and_verifies(monkeypatch):
    public_compare._FACT_CACHE.clear()
    _seed()

    async def fake_kalshi(self, ticker):
        return {"market": {
            "title": "Will Candidate X win the 2026 presidential election?",
            "close_time": "2026-11-03T20:00:00Z",
            "resolution_source": "https://apnews.com/elections",
            "rules_primary": "The Associated Press race call determines the winner of the 2026 presidential election.",
        }}

    async def fake_poly(self, market_id):
        return {
            "question": "Will Candidate X win the presidential election in 2026?",
            "endDate": "2026-11-03T21:00:00Z",
            "resolutionSource": "https://www.apnews.com/elections",
            "description": "This resolves based on the Associated Press race call for the 2026 presidential election winner.",
        }

    monkeypatch.setattr(KalshiAdapter, "fetch_market", fake_kalshi)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_poly)

    response = client.get("/api/v1/compare/pairs", params={"limit": 10, "candidate_limit": 20})
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] == 1
    assert payload["verified_count"] == 1
    assert len(payload["pairs"]) == 1
    row = payload["pairs"][0]
    assert row["left"]["canonical_id"] == "kalshi:KXCAND"
    assert row["right"]["canonical_id"] == "polymarket:789"
    assert row["verification"]["equivalent_contracts"] is True
    assert row["verification"]["consensus_probability"] == .6
    assert row["candidate_score"] > 0
    assert "Candidate discovery" in payload["disclaimer"]
    public_compare._FACT_CACHE.clear()


def test_verified_only_excludes_unverified_candidates(monkeypatch):
    public_compare._FACT_CACHE.clear()
    _seed()

    async def fake_kalshi(self, ticker):
        return {"market": {
            "title": "Will Candidate X win the 2026 presidential election?",
            "close_time": "2026-11-03T20:00:00Z",
        }}

    async def fake_poly(self, market_id):
        return {
            "question": "Will Candidate X win the presidential election in 2026?",
            "endDate": "2026-11-03T21:00:00Z",
        }

    monkeypatch.setattr(KalshiAdapter, "fetch_market", fake_kalshi)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_poly)

    response = client.get("/api/v1/compare/pairs", params={"verified_only": "true"})
    assert response.status_code == 200
    assert response.json()["pairs"] == []
    assert response.json()["verified_count"] == 0
    public_compare._FACT_CACHE.clear()


def test_pair_endpoint_is_bounded():
    response = client.get("/api/v1/compare/pairs", params={"limit": 31})
    assert response.status_code == 422
    response = client.get("/api/v1/compare/pairs", params={"candidate_limit": 61})
    assert response.status_code == 422
