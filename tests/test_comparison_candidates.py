from datetime import datetime, timezone

from app.main import DiscoveryMarket
from app.services.comparison_candidates import comparison_candidates


def market(identifier, title, venue, *, close_hour=20, category="Politics"):
    return DiscoveryMarket(
        canonical_id=identifier,
        title=title,
        venue=venue,
        category=category,
        probability=.5,
        trend_score=50,
        observed_at=datetime.now(timezone.utc),
        closes_at=datetime(2026, 11, 3, close_hour, tzinfo=timezone.utc),
    )


def test_candidate_discovery_accepts_close_wording_not_only_exact_titles():
    candidates = comparison_candidates([
        market("kalshi:a", "Will Candidate X win the 2026 presidential election?", "kalshi"),
        market("polymarket:b", "Will Candidate X win the presidential election in 2026?", "polymarket", close_hour=21),
    ])
    assert len(candidates) == 1
    assert candidates[0].title_similarity >= .72
    assert candidates[0].deadline_delta_hours == 1


def test_candidate_discovery_rejects_conflicting_numeric_terms():
    candidates = comparison_candidates([
        market("kalshi:a", "Will inflation exceed 3% in 2026?", "kalshi"),
        market("polymarket:b", "Will inflation exceed 4% in 2026?", "polymarket"),
    ])
    assert candidates == []


def test_candidate_discovery_rejects_incompatible_deadlines():
    left = market("kalshi:a", "Will Candidate X win the 2026 election?", "kalshi", close_hour=0)
    right = DiscoveryMarket(
        canonical_id="polymarket:b",
        title="Will Candidate X win the election in 2026?",
        venue="polymarket",
        category="Politics",
        probability=.5,
        trend_score=50,
        observed_at=datetime.now(timezone.utc),
        closes_at=datetime(2026, 11, 5, tzinfo=timezone.utc),
    )
    assert comparison_candidates([left, right]) == []


def test_candidate_is_not_equivalence_claim():
    candidate = comparison_candidates([
        market("kalshi:a", "Will Candidate X win the 2026 election?", "kalshi"),
        market("polymarket:b", "Will Candidate X win election in 2026?", "polymarket"),
    ])[0]
    assert not hasattr(candidate, "equivalent_contracts")
    assert "similarity" in candidate.reasons[0]
