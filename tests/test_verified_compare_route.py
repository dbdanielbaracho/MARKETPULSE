from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.entrypoint import app
from app.storage.api_keys import ApiKeyStore


client = TestClient(app)


def _auth(tmp_path, monkeypatch):
    path = str(tmp_path / "verified-compare.db")
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    token = "pbi_" + "v" * 40
    ApiKeyStore(path).create(
        key_id="verify-key",
        raw_token=token,
        name="verification test",
        plan="business",
        scopes=("markets:read",),
        daily_limit=50,
    )
    return {"X-PrediBeacon-API-Key": token}


def _seed_pair():
    now = datetime.now(timezone.utc)
    closes = datetime(2026, 11, 3, 20, tzinfo=timezone.utc)
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id="kalshi:KXELECTION",
            title="Will candidate X win the 2026 election?",
            venue="kalshi",
            probability=.58,
            trend_score=80,
            observed_at=now,
            closes_at=closes,
        ),
        core.DiscoveryMarket(
            canonical_id="polymarket:123",
            title="Will candidate X win the 2026 election?",
            venue="polymarket",
            probability=.62,
            trend_score=82,
            observed_at=now,
            closes_at=closes,
        ),
    ])


def test_verified_compare_route_is_registered():
    assert "/api/v1/commercial/intelligence/verified-compare" in app.openapi()["paths"]


def test_verified_compare_uses_live_resolution_evidence(tmp_path, monkeypatch):
    _seed_pair()
    headers = _auth(tmp_path, monkeypatch)

    async def fake_kalshi(self, ticker):
        assert ticker == "KXELECTION"
        return {"market": {
            "title": "Will candidate X win the 2026 election?",
            "close_time": "2026-11-03T20:00:00Z",
            "resolution_source": "https://apnews.com/elections",
            "rules_primary": "The Associated Press race call determines the winner of the 2026 election.",
        }}

    async def fake_poly(self, market_id):
        assert market_id == "123"
        return {
            "question": "Will candidate X win the 2026 election?",
            "endDate": "2026-11-03T21:00:00Z",
            "resolutionSource": "https://www.apnews.com/elections",
            "description": "This market resolves based on the Associated Press race call for the 2026 election winner.",
        }

    monkeypatch.setattr(KalshiAdapter, "fetch_market", fake_kalshi)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_poly)

    response = client.get(
        "/api/v1/commercial/intelligence/verified-compare",
        params={"left_id": "kalshi:KXELECTION", "right_id": "polymarket:123"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["equivalent_contracts"] is True
    assert payload["decision"] == "equivalent"
    assert payload["source_match"] is True
    assert payload["consensus_probability"] == .6
    assert payload["gap_points"] == 4
    assert payload["confidence"] >= 85
    assert response.headers["cache-control"] == "no-store"


def test_verified_compare_fails_closed_when_rules_are_missing(tmp_path, monkeypatch):
    _seed_pair()
    headers = _auth(tmp_path, monkeypatch)

    async def fake_kalshi(self, ticker):
        return {"market": {
            "title": "Will candidate X win the 2026 election?",
            "close_time": "2026-11-03T20:00:00Z",
        }}

    async def fake_poly(self, market_id):
        return {
            "question": "Will candidate X win the 2026 election?",
            "endDate": "2026-11-03T20:00:00Z",
        }

    monkeypatch.setattr(KalshiAdapter, "fetch_market", fake_kalshi)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_poly)

    response = client.get(
        "/api/v1/commercial/intelligence/verified-compare",
        params={"left_id": "kalshi:KXELECTION", "right_id": "polymarket:123"},
        headers=headers,
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["equivalent_contracts"] is False
    assert payload["decision"] == "insufficient_evidence"
    assert payload["consensus_probability"] is None


def test_verified_compare_rejects_different_numeric_contract_terms(tmp_path, monkeypatch):
    _seed_pair()
    headers = _auth(tmp_path, monkeypatch)

    async def fake_kalshi(self, ticker):
        return {"market": {
            "title": "Will candidate X win by 5 points in 2026?",
            "close_time": "2026-11-03T20:00:00Z",
            "resolution_source": "https://example.com",
        }}

    async def fake_poly(self, market_id):
        return {
            "question": "Will candidate X win by 10 points in 2026?",
            "endDate": "2026-11-03T20:00:00Z",
            "resolutionSource": "https://example.com",
        }

    monkeypatch.setattr(KalshiAdapter, "fetch_market", fake_kalshi)
    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_poly)

    response = client.get(
        "/api/v1/commercial/intelligence/verified-compare",
        params={"left_id": "kalshi:KXELECTION", "right_id": "polymarket:123"},
        headers=headers,
    )
    payload = response.json()
    assert payload["decision"] == "not_equivalent"
    assert payload["equivalent_contracts"] is False
