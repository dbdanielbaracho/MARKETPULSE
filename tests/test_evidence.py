from datetime import datetime, timedelta, timezone

import pytest

from app.domain.evidence import EvidenceBundle, EvidenceItem, EvidenceKind
from app.services.evidence import EvidencePolicy, can_explain_move, is_fresh, usable_bundle

NOW = datetime(2026, 8, 21, 21, 0, tzinfo=timezone.utc)


def item(url: str, hours_old: int, publisher: str = "Publisher") -> EvidenceItem:
    return EvidenceItem(
        title="Relevant market context",
        url=url,
        publisher=publisher,
        kind=EvidenceKind.NEWS,
        published_at=NOW - timedelta(hours=hours_old),
        retrieved_at=NOW,
    )


def test_stale_evidence_is_filtered():
    policy = EvidencePolicy(max_age_hours=24)
    assert is_fresh(item("https://a.example/story", 2), policy, NOW)
    assert not is_fresh(item("https://b.example/story", 30), policy, NOW)


def test_explanation_requires_distinct_publishers():
    policy = EvidencePolicy(max_age_hours=24, min_publishers_for_explanation=2)
    same_domain = EvidenceBundle(market_id="kalshi:test", items=[
        item("https://a.example/one", 1), item("https://a.example/two", 1)
    ])
    diverse = EvidenceBundle(market_id="kalshi:test", items=[
        item("https://a.example/one", 1), item("https://b.example/two", 1)
    ])
    assert not can_explain_move(same_domain, policy, NOW)
    assert can_explain_move(diverse, policy, NOW)


def test_bundle_keeps_provenance_and_stable_identifier():
    evidence = item("https://official.example/release", 1, "Official Source")
    same = item("https://official.example/release", 1, "Official Source")
    assert evidence.source_domain == "official.example"
    assert evidence.evidence_id == same.evidence_id


def test_invalid_policy_fails_closed():
    with pytest.raises(ValueError):
        EvidencePolicy(max_age_hours=0)
    with pytest.raises(ValueError):
        EvidencePolicy(min_publishers_for_explanation=0)


def test_missing_published_time_uses_retrieval_time_for_freshness():
    evidence = EvidenceItem(
        title="Undated official page",
        url="https://official.example/page",
        publisher="Official",
        kind=EvidenceKind.OFFICIAL,
        published_at=None,
        retrieved_at=NOW,
    )
    bundle = EvidenceBundle(market_id="m", items=[evidence])
    assert len(usable_bundle(bundle, EvidencePolicy(max_age_hours=1), NOW).items) == 1
