from datetime import datetime, timedelta, timezone

import pytest

from app.services.intelligence import MarketSnapshot, attention_score, breaking_signal, consensus, market_quality


def test_quality_scores_signal_completeness_not_outcome_confidence():
    now = datetime.now(timezone.utc)
    result = market_quality(
        probability=.52,
        volume_usd=150_000,
        observed_at=now - timedelta(minutes=5),
        closes_at=now + timedelta(days=2),
        source_url="https://example.test/market",
        history_count=12,
        now=now,
    )
    assert result.score == 100
    assert result.grade == "excellent"
    assert "probability available" in result.reasons


def test_breaking_signal_uses_recorded_change_and_volume_acceleration():
    now = datetime.now(timezone.utc)
    result = breaking_signal([
        MarketSnapshot("m", .40, 10_000, now - timedelta(hours=2)),
        MarketSnapshot("m", .46, 18_000, now),
    ])
    assert result.active is True
    assert result.probability_points == 6
    assert result.volume_change_percent == 80
    assert result.score == 14


def test_breaking_signal_fails_closed_without_history():
    now = datetime.now(timezone.utc)
    result = breaking_signal([MarketSnapshot("m", .40, 10_000, now)])
    assert result.active is False
    assert "insufficient" in result.reasons[0]


def test_consensus_requires_verified_equivalence():
    assert consensus(.60, .64, equivalent_contracts=False) is None
    result = consensus(.60, .64, equivalent_contracts=True)
    assert result is not None
    assert result.probability == .62
    assert result.gap_points == 4
    assert result.agreement == "moderate"


def test_consensus_rejects_invalid_probabilities():
    with pytest.raises(ValueError):
        consensus(1.2, .5, equivalent_contracts=True)


def test_attention_is_bounded_and_not_a_forecast():
    assert 0 <= attention_score(trend_score_value=100, probability_change_value=.50, volume_usd=10_000_000, hours_to_close=1) <= 100
