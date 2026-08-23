from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as core
import app.routes.public_trade_activity as public_activity
from app.adapters.trades import KalshiTradesAdapter
from app.entrypoint import app


client = TestClient(app)


def _seed() -> str:
    market_id = "kalshi:KXTRADES"
    core.set_discovery_markets([
        core.DiscoveryMarket(
            canonical_id=market_id,
            title="Will X happen?",
            venue="kalshi",
            probability=.55,
            trend_score=70,
            observed_at=datetime.now(timezone.utc),
        )
    ])
    public_activity._CACHE.clear()
    return market_id


def test_public_trade_activity_detects_size_anomaly_without_identity(monkeypatch):
    market_id = _seed()
    calls = 0

    async def fake_trades(self, *, ticker, limit=200):
        nonlocal calls
        calls += 1
        assert ticker == "KXTRADES"
        items = []
        for index in range(20):
            items.append({
                "ticker": ticker,
                "yes_price_dollars": "0.50",
                "count_fp": "100",
                "created_time": f"2026-08-23T05:{index:02d}:00Z",
                "trade_id": f"small-{index}",
            })
        items.append({
            "ticker": ticker,
            "yes_price_dollars": "0.50",
            "count_fp": "30000",
            "created_time": "2026-08-23T05:30:00Z",
            "trade_id": "large-1",
        })
        return items

    monkeypatch.setattr(KalshiTradesAdapter, "fetch_trades", fake_trades)
    first = client.get("/api/v1/market/large-trade-activity", params={"market_id": market_id})
    second = client.get("/api/v1/market/large-trade-activity", params={"market_id": market_id})

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload["sample_size"] == 21
    assert payload["signal_count"] == 1
    assert payload["signals"][0]["notional_usd"] == 15000
    assert "actor_id" not in payload["signals"][0]
    assert "wallet" not in " ".join(payload["signals"][0]["reasons"]).lower()
    assert "insider knowledge" in payload["disclaimer"]
    assert first.headers["cache-control"].startswith("public, max-age=15")
    assert calls == 1


def test_public_trade_activity_returns_empty_signal_without_inventing(monkeypatch):
    market_id = _seed()

    async def fake_trades(self, *, ticker, limit=200):
        return [{
            "ticker": ticker,
            "yes_price_dollars": "0.50",
            "count_fp": "100",
            "created_time": "2026-08-23T05:00:00Z",
        }]

    monkeypatch.setattr(KalshiTradesAdapter, "fetch_trades", fake_trades)
    response = client.get("/api/v1/market/large-trade-activity", params={"market_id": market_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_size"] == 1
    assert payload["signal_count"] == 0
    assert payload["signals"] == []


def test_market_page_exposes_large_trade_activity_with_safe_language():
    market_id = _seed()
    response = client.get("/market", params={"market_id": market_id})
    assert response.status_code == 200
    assert "LARGE TRADE ACTIVITY" in response.text
    assert "/api/v1/market/large-trade-activity?" in response.text
    assert "does not identify a trader" in response.text
    assert "insider knowledge" in response.text
    assert "setInterval(loadLargeTradeActivity,60000)" in response.text
    assert "WHALE" not in response.text


def test_public_trade_activity_endpoint_is_registered():
    assert "/api/v1/market/large-trade-activity" in app.openapi()["paths"]
