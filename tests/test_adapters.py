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
