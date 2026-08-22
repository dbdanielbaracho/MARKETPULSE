from datetime import datetime, timezone

import pytest

from app.main import DiscoveryMarket
from app.services.content_candidates import CandidateAction, ContentPolicy, classify
from app.services.matching import MatchDecision, MarketContractFacts, decide_match


def facts(identifier: str, question: str, close: str = "2026-09-01T12:00:00+00:00", source: str | None = None, rules: str | None = None):
    return MarketContractFacts(identifier, question.casefold(), datetime.fromisoformat(close), source, rules)


def test_same_title_different_deadline_is_not_equivalent():
    left = facts("kalshi:a", "Will X happen?", "2026-09-01T12:00:00+00:00")
    right = facts("polymarket:b", "Will X happen?", "2026-09-02T12:00:00+00:00")
    assert decide_match(left, right).decision is MatchDecision.NOT_EQUIVALENT


def test_same_title_different_resolution_source_is_not_equivalent():
    left = facts("kalshi:a", "Will X happen?", source="Agency A")
    right = facts("polymarket:b", "Will X happen?", source="Agency B")
    assert decide_match(left, right).decision is MatchDecision.NOT_EQUIVALENT


def test_same_title_without_rules_is_insufficient_evidence():
    left = facts("kalshi:a", "Will X happen?")
    right = facts("polymarket:b", "Will X happen?")
    result = decide_match(left, right)
    assert result.decision is MatchDecision.INSUFFICIENT_EVIDENCE


def test_matching_rules_hash_can_establish_equivalence():
    left = facts("kalshi:a", "Will X happen?", source="Agency A", rules="abc")
    right = facts("polymarket:b", "Will X happen?", source="agency a", rules="abc")
    assert decide_match(left, right).decision is MatchDecision.EQUIVALENT


def market(score: float) -> DiscoveryMarket:
    return DiscoveryMarket(canonical_id="kalshi:a", title="Test", venue="kalshi", probability=.5, probability_change=.1, volume_usd=1000, trend_score=score, observed_at=datetime.now(timezone.utc))


def test_content_policy_routes_high_score_to_content():
    assert classify(market(80), ContentPolicy(35, 65)).action is CandidateAction.CREATE_CONTENT


def test_content_policy_routes_middle_score_to_site_only():
    assert classify(market(50), ContentPolicy(35, 65)).action is CandidateAction.UPDATE_SITE


def test_content_policy_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        classify(market(50), ContentPolicy(80, 60))
