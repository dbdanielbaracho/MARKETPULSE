from datetime import datetime, timezone

import pytest

import app.main as main
from app.domain.markets import NormalizedMarket
from app.services.ingestion import RefreshBatch
from app.services.intelligence import MarketSignal


def test_publish_refresh_batch_feeds_discovery_api_model():
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


def test_refresh_interval_is_bounded(monkeypatch):
    monkeypatch.setenv("MP_REFRESH_INTERVAL_SECONDS", "5")
    with pytest.raises(ValueError):
        main._refresh_interval()

    monkeypatch.setenv("MP_REFRESH_INTERVAL_SECONDS", "300")
    assert main._refresh_interval() == 300
