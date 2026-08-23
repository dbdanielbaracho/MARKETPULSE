import asyncio

from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter


def test_kalshi_normalizes_midpoint_probability():
    market = KalshiAdapter.normalize({
        "ticker": "FED-SEP",
        "title": "Will the Fed cut rates?",
        "yes_bid": 64,
        "yes_ask": 66,
        "volume": 1200,
        "close_time": "2026-09-18T18:00:00Z",
    })
    assert market.canonical_id == "kalshi:FED-SEP"
    assert market.yes_probability == 0.65
    assert market.closes_at is not None


def test_polymarket_normalizes_string_prices():
    market = PolymarketAdapter.normalize({
        "id": "42",
        "question": "Will the Fed cut rates?",
        "outcomePrices": '["0.67", "0.33"]',
        "volumeNum": 2000,
        "endDate": "2026-09-18T18:00:00Z",
        "slug": "fed-cut-september",
    })
    assert market.canonical_id == "polymarket:42"
    assert market.yes_probability == 0.67


def test_polymarket_uses_parent_event_slug_for_destination():
    market = PolymarketAdapter.normalize({
        "id": "3595811",
        "question": "Will Elon Musk post 240-259 tweets?",
        "slug": "elon-musk-of-tweets-august-18-august-25-240-259",
        "events": [{
            "slug": "elon-musk-of-tweets-august-18-august-25",
        }],
    })
    assert str(market.source_url) == (
        "https://polymarket.com/event/elon-musk-of-tweets-august-18-august-25"
    )


def test_polymarket_falls_back_to_market_slug_without_parent_event():
    market = PolymarketAdapter.normalize({
        "id": "42",
        "question": "Standalone market",
        "slug": "standalone-market",
    })
    assert str(market.source_url) == "https://polymarket.com/event/standalone-market"


def test_polymarket_bad_prices_fail_soft():
    market = PolymarketAdapter.normalize({
        "id": "43",
        "question": "Malformed external price should not crash ingestion",
        "outcomePrices": "not-json",
    })
    assert market.yes_probability is None


def test_kalshi_normalizes_current_decimal_fields():
    market = KalshiAdapter.normalize({
        "ticker": "FED-DECIMAL",
        "title": "Will the current Kalshi schema work?",
        "yes_bid_dollars": "0.6400",
        "yes_ask_dollars": "0.6600",
        "last_price_dollars": "0.6500",
        "volume_fp": "1234.50",
        "close_time": "2026-09-18T18:00:00Z",
    })
    assert market.yes_probability == 0.65
    assert market.volume_usd == 1234.5


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _RecordingClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params):
        self.calls.append((url, params))
        return _FakeResponse(self.payload)


def test_polymarket_fetch_prioritizes_current_volume(monkeypatch):
    client = _RecordingClient([])
    monkeypatch.setattr("app.adapters.polymarket.httpx.AsyncClient", lambda **kwargs: client)

    asyncio.run(PolymarketAdapter("https://gamma-api.polymarket.com").fetch_markets(limit=25))

    _, params = client.calls[0]
    assert params["order"] == "volume24hr"
    assert params["ascending"] == "false"
    assert params["active"] == "true"
    assert params["closed"] == "false"


def test_kalshi_fetch_excludes_multivariate_combos(monkeypatch):
    client = _RecordingClient({"markets": [], "cursor": None})
    monkeypatch.setattr("app.adapters.kalshi.httpx.AsyncClient", lambda **kwargs: client)

    asyncio.run(KalshiAdapter("https://external-api.kalshi.com/trade-api/v2").fetch_markets(limit=25))

    _, params = client.calls[0]
    assert params["mve_filter"] == "exclude"
    assert params["status"] == "open"
