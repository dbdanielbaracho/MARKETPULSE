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


def test_kalshi_uses_series_ticker_for_ui_destination():
    market = KalshiAdapter.normalize({
        "ticker": "KXALLSVENSKANSPREAD-26AUG24MALDJU-DJU4",
        "series_ticker": "KXALLSVENSKANSPREAD",
        "event_ticker": "KXALLSVENSKANSPREAD-26AUG24MALDJU",
        "title": "Example Kalshi contract",
    })
    assert str(market.source_url) == "https://kalshi.com/markets/kxallsvenskanspread"


def test_kalshi_does_not_guess_ui_destination_from_contract_ticker():
    market = KalshiAdapter.normalize({
        "ticker": "KXALLSVENSKANSPREAD-26AUG24MALDJU-DJU4",
        "title": "Contract without series metadata",
    })
    assert market.source_url is None


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


def test_polymarket_preserves_lifetime_and_24h_volume_as_distinct_provider_fields():
    market = PolymarketAdapter.normalize({
        "id": "42-volume",
        "question": "Separate activity periods",
        "volumeNum": 2_000_000,
        "volume24hr": 12_345.67,
    })
    assert market.volume_usd == 2_000_000
    assert market.volume_24h_usd == 12_345.67


def test_polymarket_zero_24h_activity_is_preserved_not_treated_as_missing():
    market = PolymarketAdapter.normalize({
        "id": "42-zero",
        "question": "Dormant today",
        "volumeNum": 2_000_000,
        "volume24hr": 0,
    })
    assert market.volume_usd == 2_000_000
    assert market.volume_24h_usd == 0


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
        "volume_24h_fp": "321.25",
        "close_time": "2026-09-18T18:00:00Z",
    })
    assert market.yes_probability == 0.65
    assert market.volume_usd == 1234.5
    assert market.volume_24h_usd == 321.25


def test_kalshi_contract_counts_are_converted_with_provider_notional_value():
    market = KalshiAdapter.normalize({
        "ticker": "NOTIONAL",
        "title": "Notional conversion",
        "volume_fp": "1000",
        "volume_24h_fp": "250",
        "notional_value_dollars": "0.50",
    })
    assert market.volume_usd == 500
    assert market.volume_24h_usd == 125


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

    async def get(self, url, params=None):
        self.calls.append((url, params or {}))
        return _FakeResponse(self.payload)


class _KalshiEnrichmentClient(_RecordingClient):
    async def get(self, url, params=None):
        self.calls.append((url, params or {}))
        if url.endswith("/markets"):
            return _FakeResponse({
                "markets": [{
                    "ticker": "KXMLBTEST-26AUG24-ONE",
                    "event_ticker": "KXMLBTEST-26AUG24",
                    "title": "Missing series in market payload",
                }],
                "cursor": None,
            })
        if url.endswith("/events/KXMLBTEST-26AUG24"):
            return _FakeResponse({
                "event": {
                    "event_ticker": "KXMLBTEST-26AUG24",
                    "series_ticker": "KXMLBTEST",
                }
            })
        if url.endswith("/series/KXMLBTEST"):
            return _FakeResponse({
                "series": {
                    "ticker": "KXMLBTEST",
                    "category": "Sports",
                    "tags": ["baseball"],
                }
            })
        raise AssertionError(f"unexpected URL: {url}")


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


def test_kalshi_fetch_enriches_missing_series_from_canonical_event(monkeypatch):
    client = _KalshiEnrichmentClient({})
    monkeypatch.setattr("app.adapters.kalshi.httpx.AsyncClient", lambda **kwargs: client)

    markets, cursor = asyncio.run(
        KalshiAdapter("https://external-api.kalshi.com/trade-api/v2").fetch_markets(limit=25)
    )

    assert cursor is None
    assert len(markets) == 1
    assert str(markets[0].source_url) == "https://kalshi.com/markets/kxmlbtest"
    assert any(url.endswith("/events/KXMLBTEST-26AUG24") for url, _ in client.calls)
    assert any(url.endswith("/series/KXMLBTEST") for url, _ in client.calls)
