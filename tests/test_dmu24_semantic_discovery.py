from datetime import datetime, timedelta, timezone

import pytest

from app.services.discovery_semantics import (
    MIN_DISCOVERY_RELEVANCE_SCORE,
    MIN_DISCOVERY_VOLUME_USD,
    SEMANTIC_DISCOVERY_VERSION,
    curate_semantic_discovery,
    evaluate_discovery_market,
)

NOW = datetime(2026, 8, 26, 3, 54, tzinfo=timezone.utc)


def market(title: str, **overrides):
    item = {
        "canonical_id": f"kalshi:{title}",
        "title": title,
        "venue": "kalshi",
        "probability": 0.5,
        "probability_change": 0.04,
        "volume_usd": 20_000.0,
        "trend_score": 35.0,
        "observed_at": NOW.isoformat(),
        "closes_at": (NOW + timedelta(days=2)).isoformat(),
        "source_url": "https://kalshi.com/markets/example",
    }
    item.update(overrides)
    return item


def test_real_kalshi_escape_from_owner_evidence_is_reproduced_and_eliminated():
    items = [
        market(
            "Full Game: over 183.5 points?",
            probability=0.12,
            probability_change=0.045,
            volume_usd=20_800.0,
            trend_score=37.0,
            closes_at=(NOW + timedelta(days=1)).isoformat(),
        ),
        market(
            "Washington wins the game by over 21.5 points",
            probability=0.20,
            probability_change=0.105,
            volume_usd=149.0,
            trend_score=13.0,
            closes_at=(NOW + timedelta(days=1)).isoformat(),
        ),
        market(
            "Byron Buxton: 1+ RBIs?",
            probability=0.41,
            probability_change=-0.02,
            volume_usd=302.0,
            trend_score=11.0,
            closes_at=(NOW + timedelta(days=2)).isoformat(),
        ),
        market(
            "Byron Buxton: 2+ total bases?",
            probability=0.50,
            probability_change=0.005,
            volume_usd=289.0,
            trend_score=9.0,
            closes_at=(NOW + timedelta(days=3)).isoformat(),
        ),
    ]

    result = curate_semantic_discovery(items, now=NOW)

    assert [item["title"] for item in result] == ["Full Game: over 183.5 points?"]
    assert result[0]["semantic_discovery_version"] == SEMANTIC_DISCOVERY_VERSION
    assert result[0]["relevance_score"] >= MIN_DISCOVERY_RELEVANCE_SCORE
    assert result[0]["volume_usd"] >= MIN_DISCOVERY_VOLUME_USD


@pytest.mark.parametrize("volume", [0.0, 1.0, 99.0, 149.0, 289.0, 302.0, 999.99])
def test_thin_activity_never_becomes_attention_worthy_only_because_move_or_urgency_is_large(volume):
    escaped = market(
        "Thin but dramatic mover",
        probability_change=0.50,
        volume_usd=volume,
        trend_score=100.0,
        closes_at=(NOW + timedelta(hours=2)).isoformat(),
    )
    decision = evaluate_discovery_market(escaped, now=NOW)
    assert decision.eligible is False


def test_material_activity_boundary_is_explicit():
    rejected = market("Below semantic activity", volume_usd=MIN_DISCOVERY_VOLUME_USD - 0.01)
    accepted = market("At semantic activity", volume_usd=MIN_DISCOVERY_VOLUME_USD, trend_score=50.0)
    assert evaluate_discovery_market(rejected, now=NOW).eligible is False
    assert evaluate_discovery_market(accepted, now=NOW).eligible is True


def test_low_relevance_is_not_highlighted_even_with_large_volume():
    # Old curation treated any trend >=5 as homepage quality. The semantic gate
    # separately requires the product relevance oracle to pass.
    stale = market(
        "Large inventory but no current reason for attention",
        probability_change=0.0,
        volume_usd=1_000.0,
        trend_score=0.0,
        observed_at=(NOW - timedelta(days=3)).isoformat(),
        closes_at=(NOW + timedelta(days=120)).isoformat(),
        source_url=None,
    )
    decision = evaluate_discovery_market(stale, now=NOW)
    assert decision.relevance < MIN_DISCOVERY_RELEVANCE_SCORE
    assert decision.eligible is False


def test_empty_curated_state_is_truthful_instead_of_reintroducing_weak_fallback():
    items = [
        market("Thin A", volume_usd=149.0, trend_score=90.0),
        market("Thin B", volume_usd=302.0, trend_score=80.0),
    ]
    assert curate_semantic_discovery(items, now=NOW) == []


def test_semantic_decision_is_monotonic_for_activity_when_other_inputs_are_equal():
    volumes = [1000.0, 3000.0, 10_000.0, 100_000.0]
    decisions = [evaluate_discovery_market(market(f"M-{volume}", volume_usd=volume), now=NOW) for volume in volumes]
    confidences = [item.activity_confidence for item in decisions]
    assert confidences == sorted(confidences)
    assert all(item.eligible for item in decisions)
