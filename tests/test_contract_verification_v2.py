from datetime import datetime, timezone

from app.services.contract_verification import (
    VenueContractFacts,
    kalshi_contract_facts,
    polymarket_contract_facts,
    verify_contracts,
)


def dt(hour=20):
    return datetime(2026, 11, 3, hour, tzinfo=timezone.utc)


def test_same_contract_is_equivalent():
    facts = VenueContractFacts("kalshi:x", "kalshi", "Will X happen?", dt())
    result = verify_contracts(facts, facts)
    assert result.equivalent_contracts is True
    assert result.confidence == 100


def test_similar_title_without_resolution_evidence_fails_closed():
    left = VenueContractFacts("kalshi:x", "kalshi", "Will X happen by 2026?", dt())
    right = VenueContractFacts("polymarket:x", "polymarket", "Will X happen by 2026?", dt())
    result = verify_contracts(left, right)
    assert result.decision == "insufficient_evidence"
    assert result.equivalent_contracts is False


def test_matching_source_can_verify_highly_similar_contracts():
    left = VenueContractFacts(
        "kalshi:x", "kalshi", "Will candidate X win the 2026 election?", dt(),
        "https://apnews.com/elections", "The Associated Press race call determines the winner of the 2026 election.",
    )
    right = VenueContractFacts(
        "polymarket:x", "polymarket", "Will candidate X win the 2026 election?", dt(21),
        "https://www.apnews.com/elections", "This market resolves based on the Associated Press race call for the 2026 election winner.",
    )
    result = verify_contracts(left, right)
    assert result.equivalent_contracts is True
    assert result.source_match is True
    assert result.confidence >= 85


def test_numeric_anchor_difference_is_hard_rejection():
    left = VenueContractFacts("kalshi:x", "kalshi", "Will inflation exceed 3% in 2026?", dt(), "BLS")
    right = VenueContractFacts("polymarket:x", "polymarket", "Will inflation exceed 4% in 2026?", dt(), "BLS")
    result = verify_contracts(left, right)
    assert result.decision == "not_equivalent"
    assert result.equivalent_contracts is False
    assert "numeric/date anchors" in result.reasons[0]


def test_large_deadline_difference_is_hard_rejection():
    left = VenueContractFacts("kalshi:x", "kalshi", "Will X happen in 2026?", dt(0), "AP")
    right = VenueContractFacts(
        "polymarket:x", "polymarket", "Will X happen in 2026?",
        datetime(2026, 11, 5, tzinfo=timezone.utc), "AP",
    )
    result = verify_contracts(left, right)
    assert result.decision == "not_equivalent"
    assert result.deadline_delta_hours > 24


def test_explicit_resolution_source_conflict_is_rejected():
    left = VenueContractFacts("kalshi:x", "kalshi", "Will X happen in 2026?", dt(), "https://apnews.com")
    right = VenueContractFacts("polymarket:x", "polymarket", "Will X happen in 2026?", dt(), "https://reuters.com")
    result = verify_contracts(left, right)
    assert result.decision == "not_equivalent"
    assert result.source_match is False


def test_url_only_sources_keep_hostname_signal():
    left = VenueContractFacts("kalshi:x", "kalshi", "Will X happen in 2026?", dt(), "https://www.example.com/path")
    right = VenueContractFacts("polymarket:x", "polymarket", "Will X happen in 2026?", dt(), "https://example.com/other")
    result = verify_contracts(left, right)
    assert result.source_match is True
    assert result.equivalent_contracts is True


def test_kalshi_fact_parser_uses_public_rule_fields():
    facts = kalshi_contract_facts("kalshi:KX", {
        "market": {
            "title": "Will X happen in 2026?",
            "close_time": "2026-11-03T20:00:00Z",
            "rules_primary": "Primary rules text",
            "rules_secondary": "Secondary rules text",
        }
    })
    assert facts.question == "Will X happen in 2026?"
    assert "Primary rules text" in facts.resolution_text
    assert "Secondary rules text" in facts.resolution_text


def test_polymarket_fact_parser_uses_resolution_source_and_description():
    facts = polymarket_contract_facts("polymarket:1", {
        "question": "Will X happen in 2026?",
        "endDate": "2026-11-03T20:00:00Z",
        "resolutionSource": "https://example.com",
        "description": "Detailed resolution criteria",
    })
    assert facts.resolution_source == "https://example.com"
    assert facts.resolution_text == "Detailed resolution criteria"
