from datetime import datetime, timedelta, timezone

from app.domain.evidence import EvidenceBundle, EvidenceFreshness, EvidenceItem, EvidenceKind
from app.services.content_queue import ContentDecision, ContentPolicy, classify_content_candidate

NOW = datetime(2026, 8, 21, 22, 0, tzinfo=timezone.utc)


def ev(url: str, kind: EvidenceKind, hours_ago: int = 1) -> EvidenceItem:
    return EvidenceItem(
        title="Relevant market evidence",
        url=url,
        publisher=url.split('/')[2],
        kind=kind,
        published_at=NOW - timedelta(hours=hours_ago),
        retrieved_at=NOW,
    )


def test_freshness_states():
    item = ev("https://example.com/a", EvidenceKind.NEWS, 1)
    assert item.freshness(max_age=timedelta(hours=2), now=NOW) == EvidenceFreshness.FRESH
    assert item.freshness(max_age=timedelta(minutes=30), now=NOW) == EvidenceFreshness.STALE


def test_future_dated_evidence_is_not_fresh():
    item = EvidenceItem(title="Future", url="https://example.com/future", publisher="example", kind=EvidenceKind.NEWS, published_at=NOW + timedelta(hours=1), retrieved_at=NOW)
    assert item.freshness(max_age=timedelta(hours=48), now=NOW) == EvidenceFreshness.FUTURE_DATED


def test_bundle_deduplicates_tracking_variants():
    a = ev("https://example.com/story?utm_source=x", EvidenceKind.NEWS)
    b = ev("https://example.com/story?utm_source=y", EvidenceKind.NEWS)
    bundle = EvidenceBundle(market_id="kalshi:x", generated_at=NOW, items=[a, b]).deduplicated()
    assert len(bundle.items) == 1


def test_high_score_without_diverse_sources_does_not_create():
    bundle = EvidenceBundle(market_id="kalshi:x", generated_at=NOW, items=[ev("https://example.com/a", EvidenceKind.OFFICIAL)])
    candidate = classify_content_candidate(market_id="kalshi:x", score=90, evidence=bundle, policy=ContentPolicy())
    assert candidate.decision == ContentDecision.UPDATE
    assert candidate.reason == "insufficient_source_diversity_for_create"


def test_high_score_with_diverse_fresh_and_strong_sources_can_create():
    bundle = EvidenceBundle(market_id="kalshi:x", generated_at=NOW, items=[
        ev("https://agency.gov/release", EvidenceKind.OFFICIAL),
        ev("https://news.example/story", EvidenceKind.NEWS),
    ])
    candidate = classify_content_candidate(market_id="kalshi:x", score=90, evidence=bundle, policy=ContentPolicy())
    assert candidate.decision == ContentDecision.CREATE


def test_stale_evidence_fails_closed():
    bundle = EvidenceBundle(market_id="kalshi:x", generated_at=NOW, items=[ev("https://agency.gov/old", EvidenceKind.OFFICIAL, 72)])
    candidate = classify_content_candidate(market_id="kalshi:x", score=90, evidence=bundle, policy=ContentPolicy(max_evidence_age_hours=48))
    assert candidate.decision == ContentDecision.REJECT
    assert candidate.reason == "no_fresh_evidence"


def test_invalid_policy_thresholds_rejected():
    try:
        ContentPolicy(update_score=80, create_score=70)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid policy must fail closed")
