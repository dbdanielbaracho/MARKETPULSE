from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
import app.routes.public_execution_quality as public_execution
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.entrypoint import app


client = TestClient(app)


def _seed(venue: str = "kalshi") -> str:
    market_id = "kalshi:KXBOOK" if venue == "kalshi" else "polymarket:789"
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id=market_id,
            title="Will X happen?",
            venue=venue,
            probability=.55,
            trend_score=70,
            observed_at=datetime.now(timezone.utc),
        )
    ])
    public_execution._CACHE.clear()
    return market_id


def test_public_kalshi_execution_quality_is_cached(monkeypatch):
    market_id = _seed("kalshi")
    calls = 0

    async def fake_orderbook(self, ticker, depth=20):
        nonlocal calls
        calls += 1
        assert ticker == "KXBOOK"
        return {"orderbook_fp": {"yes_dollars": [["0.54", "1500"]], "no_dollars": [["0.45", "1200"]]}}

    monkeypatch.setattr(KalshiAdapter, "fetch_orderbook", fake_orderbook)
    first = client.get("/api/v1/market/execution-quality", params={"market_id": market_id})
    second = client.get("/api/v1/market/execution-quality", params={"market_id": market_id})

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload["available"] is True
    assert payload["best_bid"] == .54
    assert payload["best_ask"] == .55
    assert payload["spread_points"] == 1
    assert payload["score"] >= 70
    assert payload["cache_ttl_seconds"] == 20
    assert "best-execution guarantee" in payload["disclaimer"]
    assert first.headers["cache-control"].startswith("public, max-age=10")
    assert calls == 1


def test_public_polymarket_execution_quality_resolves_yes_token(monkeypatch):
    market_id = _seed("polymarket")
    calls = {"market": 0, "book": 0}

    async def fake_market(self, value):
        calls["market"] += 1
        assert value == "789"
        return {"outcomes": ["Yes", "No"], "clobTokenIds": ["YES789", "NO789"]}

    async def fake_book(self, token_id):
        calls["book"] += 1
        assert token_id == "YES789"
        return {"bids": [{"price": "0.51", "size": "900"}], "asks": [{"price": "0.53", "size": "800"}]}

    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_market)
    monkeypatch.setattr(PolymarketAdapter, "fetch_orderbook", fake_book)
    response = client.get("/api/v1/market/execution-quality", params={"market_id": market_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["best_bid"] == .51
    assert payload["best_ask"] == .53
    assert payload["spread_points"] == 2
    assert calls == {"market": 1, "book": 1}


def test_public_execution_quality_fails_closed_when_yes_token_missing(monkeypatch):
    market_id = _seed("polymarket")

    async def fake_market(self, value):
        return {"outcomes": ["Yes", "No"]}

    async def should_not_call(*args, **kwargs):
        raise AssertionError("order book must not be called without a token id")

    monkeypatch.setattr(PolymarketAdapter, "fetch_market", fake_market)
    monkeypatch.setattr(PolymarketAdapter, "fetch_orderbook", should_not_call)
    response = client.get("/api/v1/market/execution-quality", params={"market_id": market_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["score"] is None
    assert "YES outcome token" in payload["reasons"][0]


def test_public_execution_quality_is_registered():
    assert "/api/v1/market/execution-quality" in app.openapi()["paths"]
