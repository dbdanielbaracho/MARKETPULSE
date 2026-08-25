from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Response

import app.main as core
from app.routes.public_relevance import relevant_markets


def _market(
    market_id: str,
    title: str,
    *,
    venue: str = "kalshi",
    volume: float | None = 1000,
    trend: float = 50,
    closes_in_hours: float = 24,
    probability_change: float | None = 0.05,
) -> core.DiscoveryMarket:
    now = datetime.now(timezone.utc)
    return core.DiscoveryMarket(
        canonical_id=f"{venue}:{market_id}",
        title=title,
        venue=venue,
        category="Sports",
        probability=0.5,
        probability_change=probability_change,
        volume_usd=volume,
        trend_score=trend,
        observed_at=now,
        closes_at=now + timedelta(hours=closes_in_hours),
        source_url=(
            "https://kalshi.com/markets/example"
            if venue == "kalshi"
            else "https://polymarket.com/event/example"
        ),
    )


def test_relevant_feed_rejects_zero_or_unknown_activity_zero_attention_and_immediate_expiry(monkeypatch):
    good = _market("good", "Useful market", volume=2500, trend=60, closes_in_hours=24)
    zero_volume = _market("zero-volume", "Seattle wins by over 8.5 runs?", volume=0, trend=70)
    unknown_volume = _market("unknown-volume", "Unknown activity", volume=None, trend=80)
    zero_trend = _market("zero-trend", "Chicago C wins by over 7.5 runs?", volume=1400, trend=0)
    closing_now = _market(
        "closing-now",
        "Will the Nikkei 225 be at least 65,645 at August 25, 2026 at 12:30am ET?",
        volume=100,
        trend=30,
        closes_in_hours=0.5,
    )
    monkeypatch.setattr(core, "_DISCOVERY", [zero_volume, unknown_volume, zero_trend, closing_now, good])

    result = relevant_markets(Response(), limit=100)

    assert [item.canonical_id for item in result] == [good.canonical_id]
    assert all((item.volume_usd or 0) > 0 for item in result)
    assert all(item.trend_score > 0 for item in result)
    assert all(item.relevance_score > 0 for item in result)


def test_relevant_feed_collapses_same_provider_threshold_ladders(monkeypatch):
    markets = [
        _market("sea-85", "Seattle wins by over 8.5 runs?", volume=3000, trend=80, probability_change=0.20),
        _market("sea-75", "Seattle wins by over 7.5 runs?", volume=2500, trend=70, probability_change=0.15),
        _market("sea-65", "Seattle wins by over 6.5 runs?", volume=2000, trend=60, probability_change=0.10),
        _market("other", "Will Team B win the game?", volume=5000, trend=55),
    ]
    monkeypatch.setattr(core, "_DISCOVERY", markets)

    result = relevant_markets(Response(), limit=100)
    seattle = [item for item in result if item.title.startswith("Seattle wins by over")]

    assert len(seattle) == 1
    assert seattle[0].canonical_id == "kalshi:sea-85"


def test_relevant_feed_preserves_same_family_across_providers(monkeypatch):
    monkeypatch.setattr(
        core,
        "_DISCOVERY",
        [
            _market("kalshi-family", "Candidate wins by over 6.5 points?", venue="kalshi", trend=70),
            _market("poly-family", "Candidate wins by over 7.5 points?", venue="polymarket", trend=65),
        ],
    )

    result = relevant_markets(Response(), limit=100)

    assert {item.venue for item in result} == {"kalshi", "polymarket"}
