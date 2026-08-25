from app.adapters.kalshi import KalshiAdapter


def test_kalshi_volume_uses_usd_notional_value():
    item = {
        "ticker": "TEST-MKT",
        "title": "Test market",
        "volume_fp": "2500.00",
        "notional_value_dollars": "1.0000",
    }
    assert KalshiAdapter._usd_notional_volume(item) == 2500.0


def test_kalshi_fractional_notional_volume_is_multiplied():
    item = {
        "ticker": "TEST-MKT",
        "title": "Test market",
        "volume_fp": "10.00",
        "notional_value_dollars": "0.5600",
    }
    assert KalshiAdapter._usd_notional_volume(item) == 5.6


def test_kalshi_volume_falls_back_to_one_dollar_notional_when_missing():
    item = {
        "ticker": "TEST-MKT",
        "title": "Test market",
        "volume_fp": "123.50",
    }
    assert KalshiAdapter._usd_notional_volume(item) == 123.5


def test_kalshi_normalized_market_exposes_dollar_volume():
    market = KalshiAdapter.normalize({
        "ticker": "TEST-MKT",
        "title": "Will the Fed cut rates?",
        "volume_fp": "100.00",
        "notional_value_dollars": "1.0000",
        "yes_bid_dollars": "0.40",
        "yes_ask_dollars": "0.42",
    })
    assert market.volume_usd == 100.0
    assert market.yes_probability == 0.41
