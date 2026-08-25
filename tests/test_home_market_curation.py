from datetime import datetime, timedelta, timezone

from app.middleware.home_client_dedup import _curate_market_payload


def market(title: str, **overrides):
    now = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
    item = {
        "canonical_id": title,
        "title": title,
        "venue": "kalshi",
        "probability": 0.5,
        "probability_change": 0.1,
        "volume_usd": 1000.0,
        "trend_score": 70.0,
        "observed_at": now.isoformat(),
        "closes_at": (now + timedelta(days=2)).isoformat(),
    }
    item.update(overrides)
    return item


def test_quality_gate_removes_zero_volume_zero_relevance_and_imminent_closures():
    now = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
    items = [
        market("Useful market"),
        market("Zero volume", volume_usd=0.0),
        market("Zero relevance", trend_score=0.0),
        market("Closing now", closes_at=(now + timedelta(minutes=30)).isoformat()),
    ]

    result = _curate_market_payload(items, now=now)

    assert [item["title"] for item in result] == ["Useful market"]


def test_quality_gate_collapses_threshold_ladders_from_same_provider():
    now = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
    items = [
        market("Over 26.5 games"),
        market("Over 21.5 games"),
        market("Over 16.5 games"),
        market("Will the silver close price be above 68.149 USD/ounce on August 24, 2026 at 11:00 PM ET?"),
        market("Will the silver close price be above 68.249 USD/ounce on August 24, 2026 at 11:00 PM ET?"),
    ]

    result = _curate_market_payload(items, now=now)

    assert [item["title"] for item in result] == [
        "Over 26.5 games",
        "Will the silver close price be above 68.149 USD/ounce on August 24, 2026 at 11:00 PM ET?",
    ]


def test_quality_gate_keeps_same_family_on_different_providers_for_comparison():
    now = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
    items = [
        market("Over 26.5 games", venue="kalshi"),
        market("Over 21.5 games", venue="polymarket"),
    ]

    result = _curate_market_payload(items, now=now)

    assert len(result) == 2
    assert {item["venue"] for item in result} == {"kalshi", "polymarket"}


def test_unknown_volume_is_not_silently_treated_as_zero():
    now = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)
    result = _curate_market_payload([market("Unknown volume", volume_usd=None)], now=now)
    assert [item["title"] for item in result] == ["Unknown volume"]
