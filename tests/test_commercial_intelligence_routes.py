from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
from app.adapters.kalshi import KalshiAdapter
from app.adapters.trades import KalshiTradesAdapter
from app.entrypoint import app
from app.storage.api_keys import ApiKeyStore


client = TestClient(app)


def _headers(tmp_path, monkeypatch):
    path = str(tmp_path / "commercial-intelligence.db")
    monkeypatch.setenv("MP_DATABASE_PATH", path)
    token = "pbi_" + "x" * 40
    ApiKeyStore(path).create(
        key_id="test-key",
        raw_token=token,
        name="test",
        plan="business",
        scopes=("markets:read", "history:read"),
        daily_limit=100,
    )
    return {"X-PrediBeacon-API-Key": token}


def _seed_market():
    now = datetime.now(timezone.utc)
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id="kalshi:KXTEST",
            title="Will the test happen?",
            venue="kalshi",
            probability=.55,
            probability_change=.05,
            volume_usd=50_000,
            trend_score=82,
            observed_at=now,
            source_url="https://kalshi.com/markets/KXTEST",
        )
    ])


def test_commercial_intelligence_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/commercial/intelligence/market" in paths
    assert "/api/v1/commercial/intelligence/compare" in paths
    assert "/api/v1/commercial/intelligence/execution" in paths
    assert "/api/v1/commercial/intelligence/large-trades" in paths


def test_commercial_intelligence_requires_api_key(tmp_path, monkeypatch):
    _seed_market()
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "missing-key.db"))
    response = client.get("/api/v1/commercial/intelligence/market", params={"market_id": "kalshi:KXTEST"})
    assert response.status_code == 401


def test_market_intelligence_uses_existing_commercial_auth_and_no_store(tmp_path, monkeypatch):
    _seed_market()
    headers = _headers(tmp_path, monkeypatch)
    response = client.get(
        "/api/v1/commercial/intelligence/market",
        params={"market_id": "kalshi:KXTEST"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert 0 <= payload["attention_score"] <= 100
    assert payload["market_quality"]["score"] >= 0
    assert "not forecasts" in payload["disclaimer"]
    assert response.headers["cache-control"] == "no-store"


def test_consensus_endpoint_fails_closed_except_verified_contracts(tmp_path, monkeypatch):
    _seed_market()
    headers = _headers(tmp_path, monkeypatch)
    response = client.get(
        "/api/v1/commercial/intelligence/compare",
        params={"left_id": "kalshi:KXTEST", "right_id": "kalshi:KXTEST"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["equivalent_contracts"] is True
    assert payload["probability"] == .55
    assert payload["gap_points"] == 0


def test_execution_endpoint_normalizes_live_book(tmp_path, monkeypatch):
    _seed_market()
    headers = _headers(tmp_path, monkeypatch)

    async def fake_orderbook(self, ticker, depth=20):
        assert ticker == "KXTEST"
        return {"orderbook_fp": {"yes_dollars": [["0.54", "2000"]], "no_dollars": [["0.45", "2500"]]}}

    monkeypatch.setattr(KalshiAdapter, "fetch_orderbook", fake_orderbook)
    response = client.get(
        "/api/v1/commercial/intelligence/execution",
        params={"market_id": "kalshi:KXTEST"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["best_bid"] == .54
    assert payload["best_ask"] == .55
    assert payload["spread_points"] == 1
    assert "best-execution guarantee" in payload["disclaimer"]


def test_large_trade_endpoint_reports_unusual_observed_size(tmp_path, monkeypatch):
    _seed_market()
    headers = _headers(tmp_path, monkeypatch)

    async def fake_trades(self, *, ticker, limit=200):
        assert ticker == "KXTEST"
        base = {
            "ticker": ticker,
            "yes_price_dollars": "0.50",
            "taker_side": "yes",
            "taker_outcome_side": "yes",
            "created_time": "2026-08-23T04:00:00Z",
        }
        return [
            {**base, "trade_id": "a", "count_fp": "200"},
            {**base, "trade_id": "b", "count_fp": "220"},
            {**base, "trade_id": "c", "count_fp": "180"},
            {**base, "trade_id": "big", "count_fp": "40000"},
        ]

    monkeypatch.setattr(KalshiTradesAdapter, "fetch_trades", fake_trades)
    response = client.get(
        "/api/v1/commercial/intelligence/large-trades",
        params={"market_id": "kalshi:KXTEST"},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_size"] == 4
    assert len(payload["signals"]) == 1
    assert payload["signals"][0]["notional_usd"] == 20000
    assert payload["signals"][0]["actor_id"] is None
    assert "do not imply insider knowledge" in payload["disclaimer"]
