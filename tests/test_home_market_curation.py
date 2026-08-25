from datetime import datetime, timedelta, timezone

import pytest

from app.middleware.home_client_dedup import (
    CURATION_VERSION,
    MAX_PER_SUBJECT_PER_VENUE,
    MIN_HOMEPAGE_RELEVANCE,
    RENDER_CURATION_VERSION,
    _curate_market_payload,
    _family_title,
    _subject_title,
)

NOW = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)


def market(title: str, **overrides):
    item = {
        "canonical_id": f"kalshi:{title}",
        "title": title,
        "venue": "kalshi",
        "probability": 0.5,
        "probability_change": 0.1,
        "volume_usd": 1000.0,
        "trend_score": 70.0,
        "observed_at": NOW.isoformat(),
        "closes_at": (NOW + timedelta(days=2)).isoformat(),
    }
    item.update(overrides)
    if "venue" in overrides and "canonical_id" not in overrides:
        item["canonical_id"] = f"{overrides['venue']}:{title}"
    return item


def titles(items):
    return [item["title"] for item in items]


def test_quality_gate_removes_zero_volume_low_relevance_and_imminent_closures():
    items = [
        market("Useful market"),
        market("Zero volume", volume_usd=0.0),
        market("Zero relevance", trend_score=0.0),
        market("Almost no relevance", trend_score=4.999),
        market("Closing now", closes_at=(NOW + timedelta(minutes=30)).isoformat()),
        market("Closing at boundary", closes_at=(NOW + timedelta(hours=1)).isoformat()),
    ]
    assert titles(_curate_market_payload(items, now=NOW)) == ["Useful market"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("volume_usd", None),
        ("volume_usd", "100"),
        ("volume_usd", float("nan")),
        ("trend_score", None),
        ("trend_score", "70"),
        ("trend_score", float("inf")),
        ("probability", -0.01),
        ("probability", 1.01),
        ("probability", "0.5"),
        ("title", ""),
        ("canonical_id", ""),
        ("venue", "unknown"),
    ],
)
def test_quality_gate_fails_closed_on_missing_malformed_or_impossible_values(field, value):
    item = market("Malformed market")
    item[field] = value
    assert _curate_market_payload([item], now=NOW) == []


def test_minimum_relevance_boundary_is_explicit_and_stable():
    rejected = market("Below threshold", trend_score=MIN_HOMEPAGE_RELEVANCE - 0.001)
    accepted = market("At threshold", trend_score=MIN_HOMEPAGE_RELEVANCE)
    assert titles(_curate_market_payload([rejected, accepted], now=NOW)) == ["At threshold"]


def test_quality_gate_collapses_threshold_ladders_from_same_provider():
    items = [
        market("Over 26.5 games"),
        market("Over 21.5 games"),
        market("Over 16.5 games"),
        market("Will the silver close price be above 68.149 USD/ounce on August 25, 2026 at 11:00 PM ET?"),
        market("Will the silver close price be above 68.249 USD/ounce on August 25, 2026 at 11:00 PM ET?"),
    ]
    assert titles(_curate_market_payload(items, now=NOW)) == [
        "Over 26.5 games",
        "Will the silver close price be above 68.149 USD/ounce on August 25, 2026 at 11:00 PM ET?",
    ]


def test_regression_real_platinum_ladder_from_production_collapses_to_one_card():
    strikes = [1859.49, 1858.99, 1858.49, 1857.99, 1857.49, 1856.99, 1856.49, 1855.99]
    items = [
        market(
            f"Will the platinum close price be above {strike} USD/ounce on August 25, 2026 at 10:00 AM ET?",
            volume_usd=100.0,
            trend_score=20.0,
            closes_at=(NOW + timedelta(hours=4)).isoformat(),
        )
        for strike in strikes
    ]
    result = _curate_market_payload(items, now=NOW)
    assert len(result) == 1
    assert result[0]["title"].startswith("Will the platinum close price be above 1859.49")
    assert len({_family_title(item["title"]) for item in items}) == 1


def test_regression_real_bad_production_cards_are_all_rejected():
    items = [
        market("Bridget Carleton: 5+ threes", volume_usd=0.0, trend_score=32.0),
        market("Paige Bueckers: 25+ points", volume_usd=0.0, trend_score=30.0),
        market("Carla Leite: 10+ points", volume_usd=6.5, trend_score=4.0),
        market("Arike Ogunbowale: 4+ assists", volume_usd=18.0, trend_score=2.0),
        market("Filip Peliwo wins", volume_usd=0.0, trend_score=0.0),
    ]
    assert _curate_market_payload(items, now=NOW) == []


def test_same_family_can_exist_once_per_provider_for_cross_venue_comparison():
    items = [
        market("Over 26.5 games", venue="kalshi"),
        market("Over 21.5 games", venue="polymarket"),
    ]
    result = _curate_market_payload(items, now=NOW)
    assert len(result) == 2
    assert {item["venue"] for item in result} == {"kalshi", "polymarket"}


def test_exact_duplicate_is_removed_even_when_ids_differ():
    items = [
        market("Same market", canonical_id="kalshi:a"),
        market("  SAME   MARKET  ", canonical_id="kalshi:b"),
    ]
    assert len(_curate_market_payload(items, now=NOW)) == 1


def test_subject_diversity_prevents_one_player_from_monopolizing_homepage():
    items = [
        market("Paige Bueckers: 25+ points"),
        market("Paige Bueckers: 6+ assists"),
        market("Paige Bueckers: 6+ rebounds"),
        market("Paige Bueckers: 3+ threes"),
        market("Other player: 10+ points"),
    ]
    result = _curate_market_payload(items, now=NOW)
    paige = [item for item in result if _subject_title(item["title"]) == "paige bueckers"]
    assert len(paige) == MAX_PER_SUBJECT_PER_VENUE
    assert "Other player: 10+ points" in titles(result)


def test_input_order_preserves_best_ranked_representative():
    first = market("Will gold be above 2500 USD/ounce?", trend_score=90.0)
    sibling = market("Will gold be above 2600 USD/ounce?", trend_score=80.0)
    result = _curate_market_payload([first, sibling], now=NOW)
    assert result == [first]


def test_curation_is_idempotent():
    items = [
        market("Useful A"),
        market("Useful B"),
        market("Zero", volume_usd=0.0),
        market("Over 20.5 games"),
        market("Over 21.5 games"),
    ]
    once = _curate_market_payload(items, now=NOW)
    twice = _curate_market_payload(once, now=NOW)
    assert twice == once


def test_curation_does_not_mutate_source_objects():
    item = market("Immutable input")
    before = dict(item)
    _curate_market_payload([item], now=NOW)
    assert item == before


def test_curation_versions_are_explicit_for_production_verification():
    assert CURATION_VERSION == "quality-v3"
    assert RENDER_CURATION_VERSION == "prerender-v2"
