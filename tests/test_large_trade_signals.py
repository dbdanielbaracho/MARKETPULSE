from datetime import datetime, timezone

from app.services.large_trades import (
    NormalizedTrade,
    detect_large_trades,
    normalize_kalshi_trade,
    normalize_polymarket_trade,
)


def test_normalize_kalshi_trade_has_no_fake_actor_identity():
    trade = normalize_kalshi_trade({
        "trade_id": "t1",
        "ticker": "KXTEST",
        "count_fp": "100.00",
        "yes_price_dollars": "0.5600",
        "taker_side": "yes",
        "taker_outcome_side": "yes",
        "created_time": "2026-08-23T04:00:00Z",
    })
    assert trade.notional_usd == 56
    assert trade.actor_id is None
    assert trade.market_id == "KXTEST"


def test_normalize_polymarket_trade_keeps_public_wallet_when_present():
    trade = normalize_polymarket_trade({
        "proxyWallet": "0xabc",
        "side": "BUY",
        "conditionId": "0xmarket",
        "size": 1000,
        "price": .6,
        "timestamp": 1787457600,
        "outcome": "YES",
        "transactionHash": "0xtx",
    })
    assert trade.notional_usd == 600
    assert trade.actor_id == "0xabc"
    assert trade.trade_id == "0xtx"


def test_large_trade_detector_requires_absolute_and_relative_significance():
    now = datetime.now(timezone.utc)
    trades = [
        NormalizedTrade("kalshi", "m", .5, 200, 100, "yes", "yes", now),
        NormalizedTrade("kalshi", "m", .5, 220, 110, "yes", "yes", now),
        NormalizedTrade("kalshi", "m", .5, 180, 90, "yes", "yes", now),
        NormalizedTrade("kalshi", "m", .5, 40_000, 20_000, "yes", "yes", now),
    ]
    signals = detect_large_trades(trades, absolute_floor_usd=5_000, median_multiple=8)
    assert len(signals) == 1
    assert signals[0].trade.notional_usd == 20_000
    assert signals[0].multiple_of_median is not None
    assert "venue data does not identify the trader" in signals[0].reasons


def test_large_trade_detector_does_not_label_normal_activity():
    now = datetime.now(timezone.utc)
    trades = [
        NormalizedTrade("polymarket", "m", .5, 100, 50, "BUY", "YES", now, "0xa"),
        NormalizedTrade("polymarket", "m", .5, 110, 55, "BUY", "YES", now, "0xb"),
    ]
    assert detect_large_trades(trades) == []
