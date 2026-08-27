from datetime import datetime, timezone

import pytest

import app.main as main
from app.domain.markets import NormalizedMarket
from app.services.ingestion import RefreshBatch
from app.services.intelligence import MarketSignal


def test_publish_refresh_batch_feeds_discovery_api_model(monkeypatch):
    monkeypatch.setattr(main, "_DISCOVERY", [])
    observed = datetime(2026, 8, 22, tzinfo=timezone.utc)
    market = NormalizedMarket(
        venue="kalshi",
        venue_market_id="K1",
        title="Will runtime wiring work?",
        category="Tech",
        yes_probability=0.65,
        volume_usd=5000,
        observed_at=observed,
    )
    signal = MarketSignal(
        canonical_id=market.canonical_id,
        probability=0.65,
        probability_change=0.05,
        volume_usd=5000,
        trend_score=32.5,
    )

    main.publish_refresh_batch(RefreshBatch((market,), (signal,), ()))

    assert len(main._DISCOVERY) == 1
    assert main._DISCOVERY[0].canonical_id == "kalshi:K1"
    assert main._DISCOVERY[0].probability_change == pytest.approx(0.05)


def test_total_provider_failure_keeps_last_good_read_model():
    existing = list(main._DISCOVERY)

    main.publish_refresh_batch(
        RefreshBatch((), (), ("kalshi:RuntimeError", "polymarket:RuntimeError"))
    )

    assert main._DISCOVERY == existing
    assert main._LAST_REFRESH_ERRORS == (
        "kalshi:RuntimeError",
        "polymarket:RuntimeError",
    )


def test_partial_refresh_preserves_absent_venue_and_replaces_present_venue(monkeypatch):
    observed = datetime(2026, 8, 22, tzinfo=timezone.utc)
    previous_kalshi = main.DiscoveryMarket(
        canonical_id="kalshi:K1",
        title="Last known Kalshi market",
        venue="kalshi",
        probability=0.55,
        volume_usd=None,
        trend_score=20,
        observed_at=observed,
    )
    previous_polymarket = main.DiscoveryMarket(
        canonical_id="polymarket:P-OLD",
        title="Old Polymarket market",
        venue="polymarket",
        probability=0.40,
        volume_usd=100,
        trend_score=10,
        observed_at=observed,
    )
    monkeypatch.setattr(main, "_DISCOVERY", [previous_kalshi, previous_polymarket])

    replacement = NormalizedMarket(
        venue="polymarket",
        venue_market_id="P-NEW",
        title="New Polymarket market",
        yes_probability=0.70,
        volume_usd=200,
        observed_at=observed,
    )
    signal = MarketSignal(
        canonical_id=replacement.canonical_id,
        probability=0.70,
        probability_change=None,
        volume_usd=200,
        trend_score=30,
    )

    main.publish_refresh_batch(
        RefreshBatch((replacement,), (signal,), ("kalshi:RuntimeError",))
    )

    ids = {item.canonical_id for item in main._DISCOVERY}
    assert ids == {"kalshi:K1", "polymarket:P-NEW"}
    assert "polymarket:P-OLD" not in ids
    assert main._LAST_REFRESH_ERRORS == ("kalshi:RuntimeError",)


def test_silent_empty_venue_result_preserves_last_good_slice(monkeypatch):
    observed = datetime(2026, 8, 22, tzinfo=timezone.utc)
    previous_kalshi = main.DiscoveryMarket(
        canonical_id="kalshi:K1",
        title="Last known Kalshi market",
        venue="kalshi",
        probability=0.55,
        volume_usd=None,
        trend_score=20,
        observed_at=observed,
    )
    monkeypatch.setattr(main, "_DISCOVERY", [previous_kalshi])

    replacement = NormalizedMarket(
        venue="polymarket",
        venue_market_id="P-NEW",
        title="New Polymarket market",
        yes_probability=0.70,
        volume_usd=200,
        observed_at=observed,
    )
    signal = MarketSignal(
        canonical_id=replacement.canonical_id,
        probability=0.70,
        probability_change=None,
        volume_usd=200,
        trend_score=30,
    )

    main.publish_refresh_batch(RefreshBatch((replacement,), (signal,), ()))

    assert {item.canonical_id for item in main._DISCOVERY} == {
        "kalshi:K1",
        "polymarket:P-NEW",
    }


def test_refresh_interval_is_bounded(monkeypatch):
    monkeypatch.setenv("MP_REFRESH_INTERVAL_SECONDS", "5")
    with pytest.raises(ValueError):
        main._refresh_interval()

    monkeypatch.setenv("MP_REFRESH_INTERVAL_SECONDS", "300")
    assert main._refresh_interval() == 300


def test_freshness_states_are_explicit(monkeypatch):
    now = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(main, "_DISCOVERY", [object()])
    monkeypatch.setattr(main, "_LAST_REFRESH_AT", now)
    monkeypatch.setenv("MP_STALE_AFTER_SECONDS", "600")

    assert main.freshness(now)[0] == "fresh"
    assert main.freshness(datetime(2026, 8, 22, 12, 11, tzinfo=timezone.utc))[0] == "stale"
    assert main.freshness(datetime(2026, 8, 22, 11, 59, tzinfo=timezone.utc))[0] == "future"


def test_freshness_is_unavailable_without_data(monkeypatch):
    monkeypatch.setattr(main, "_DISCOVERY", [])
    monkeypatch.setattr(main, "_LAST_REFRESH_AT", None)
    assert main.freshness()[0] == "unavailable"


def test_stale_threshold_is_bounded(monkeypatch):
    monkeypatch.setenv("MP_STALE_AFTER_SECONDS", "10")
    with pytest.raises(ValueError):
        main._stale_after_seconds()
