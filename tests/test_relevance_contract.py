from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.relevance import relevance_score


NOW = datetime(2026, 8, 23, 18, 0, tzinfo=timezone.utc)


def market(**overrides):
    values = dict(
        probability=.5,
        probability_change=0.0,
        volume_usd=0.0,
        trend_score=0.0,
        observed_at=NOW,
        closes_at=NOW + timedelta(days=30),
        source_url="https://kalshi.com/markets/example",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_closed_contract_is_never_relevant():
    result = relevance_score(market(closes_at=NOW - timedelta(seconds=1)), now=NOW)
    assert result.score == 0
    assert "no longer open" in result.reasons[0]


def test_probability_movement_is_monotonic_until_cap_for_material_activity():
    scores = [
        relevance_score(market(probability_change=change, volume_usd=100), now=NOW).score
        for change in (0.0, .05, .10, .20, .40)
    ]
    assert scores == sorted(scores)
    assert scores[-1] == scores[-2]


def test_volume_never_reduces_relevance():
    scores = [
        relevance_score(market(volume_usd=volume), now=NOW).score
        for volume in (0, 100, 1_000, 10_000, 1_000_000)
    ]
    assert scores == sorted(scores)


def test_regression_one_dollar_market_cannot_get_full_credit_for_large_move():
    thin = relevance_score(
        market(probability_change=-0.285, volume_usd=1, trend_score=70),
        now=NOW,
    )
    material = relevance_score(
        market(probability_change=-0.285, volume_usd=100, trend_score=70),
        now=NOW,
    )

    assert thin.score < material.score
    assert any("discounted" in reason for reason in thin.reasons)


def test_nearer_valid_deadline_is_more_urgent_than_distant_deadline():
    near = relevance_score(market(closes_at=NOW + timedelta(hours=12)), now=NOW)
    medium = relevance_score(market(closes_at=NOW + timedelta(hours=48)), now=NOW)
    far = relevance_score(market(closes_at=NOW + timedelta(days=30)), now=NOW)
    assert near.score > medium.score > far.score


def test_fresher_observation_never_scores_lower_than_stale_observation():
    fresh = relevance_score(market(observed_at=NOW), now=NOW)
    hour_old = relevance_score(market(observed_at=NOW - timedelta(hours=1)), now=NOW)
    day_old = relevance_score(market(observed_at=NOW - timedelta(days=1)), now=NOW)
    assert fresh.score >= hour_old.score >= day_old.score


def test_score_is_always_bounded_and_reasons_are_bounded():
    result = relevance_score(
        market(
            probability_change=1.0,
            volume_usd=10**15,
            trend_score=100,
            closes_at=NOW + timedelta(hours=1),
        ),
        now=NOW,
    )
    assert 0 <= result.score <= 100
    assert 1 <= len(result.reasons) <= 4


def test_missing_optional_market_data_does_not_crash_or_invent_values():
    result = relevance_score(
        market(
            probability=None,
            probability_change=None,
            volume_usd=None,
            closes_at=None,
            source_url=None,
        ),
        now=NOW,
    )
    assert 0 <= result.score <= 100
    assert result.reasons
