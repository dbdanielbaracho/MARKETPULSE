from datetime import datetime, timezone

import pytest

from app.domain.evidence import EvidenceBundle, EvidenceItem, EvidenceKind
from app.services.content_queue import ContentCandidate, ContentDecision
from app.storage.content_queue import ContentQueueStore

NOW = datetime(2026, 8, 22, tzinfo=timezone.utc)


def evidence_bundle():
    return EvidenceBundle(
        market_id="kalshi:test",
        generated_at=NOW,
        items=[
            EvidenceItem(
                title="Federal Reserve policy decision",
                url="https://www.federalreserve.gov/newsevents/pressreleases/test.htm",
                publisher="Federal Reserve",
                kind=EvidenceKind.OFFICIAL,
                published_at=NOW,
                retrieved_at=NOW,
                summary="Official policy decision.",
            ),
            EvidenceItem(
                title="Market reaction analysis",
                url="https://www.npr.org/test-market-reaction",
                publisher="NPR",
                kind=EvidenceKind.NEWS,
                published_at=NOW,
                retrieved_at=NOW,
                summary="Independent reporting.",
            ),
        ],
    )


def candidate(decision=ContentDecision.CREATE):
    items = evidence_bundle().items
    identifiers = tuple(item.evidence_id for item in reversed(items)) + (items[0].evidence_id,)
    return ContentCandidate(
        market_id="kalshi:test",
        score=85,
        decision=decision,
        reason="evidence_gate_passed",
        evidence_ids=identifiers,
    )


def test_enqueue_is_idempotent_and_normalizes_evidence(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    assert store.enqueue(candidate(), evidence_bundle(), NOW) is True
    assert store.enqueue(candidate(), evidence_bundle(), NOW) is False
    assert store.counts()["queued"] == 1

    stored = store.get("cc_4c9799d502683302532e")
    if stored is None:
        # Candidate IDs are opaque; resolve the sole row through its audit identity.
        with store._connect() as connection:
            identifier = connection.execute("SELECT candidate_id FROM content_candidates").fetchone()[0]
        stored = store.get(identifier)
    assert stored is not None
    assert stored.evidence_ids == tuple(sorted(item.evidence_id for item in evidence_bundle().items))
    assert stored.state == "queued"


def test_rejected_classification_is_not_queued(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    assert store.enqueue(candidate(ContentDecision.REJECT), evidence_bundle(), NOW) is False
    assert sum(store.counts().values()) == 0


def test_state_transitions_are_guarded_and_audited(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    store.enqueue(candidate(), evidence_bundle(), NOW)
    with store._connect() as connection:
        identifier = connection.execute("SELECT candidate_id FROM content_candidates").fetchone()[0]

    store.transition(identifier, "claimed", "worker_claimed", NOW)
    store.transition(identifier, "failed", "provider_timeout", NOW)
    store.transition(identifier, "queued", "retry_approved", NOW)

    assert store.get(identifier).state == "queued"
    assert store.audit(identifier) == [
        (None, "queued", "candidate_enqueued"),
        ("queued", "claimed", "worker_claimed"),
        ("claimed", "failed", "provider_timeout"),
        ("failed", "queued", "retry_approved"),
    ]


def test_invalid_transition_fails_closed(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    store.enqueue(candidate(), evidence_bundle(), NOW)
    with store._connect() as connection:
        identifier = connection.execute("SELECT candidate_id FROM content_candidates").fetchone()[0]

    with pytest.raises(ValueError):
        store.transition(identifier, "completed", "skip_claim", NOW)
    with pytest.raises(ValueError):
        store.transition(identifier, "claimed", "", NOW)


def test_startup_probe_preserves_identity_and_increments(tmp_path):
    database = tmp_path / "queue.db"
    first_store = ContentQueueStore(database)
    first = first_store.record_startup(NOW)

    second_time = datetime(2026, 8, 22, 1, tzinfo=timezone.utc)
    second_store = ContentQueueStore(database)
    second = second_store.record_startup(second_time)

    assert second.identity == first.identity
    assert first.startup_count == 1
    assert second.startup_count == 2
    assert second.first_started_at == NOW
    assert second.last_started_at == second_time


def test_startup_probe_is_independent_per_database(tmp_path):
    first = ContentQueueStore(tmp_path / "first.db").record_startup(NOW)
    second = ContentQueueStore(tmp_path / "second.db").record_startup(NOW)

    assert first.identity != second.identity
    assert first.startup_count == second.startup_count == 1


def test_evidence_snapshot_is_complete_and_immutable(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    bundle = evidence_bundle()
    assert store.enqueue(candidate(), bundle, NOW) is True
    with store._connect() as connection:
        identifier = connection.execute("SELECT candidate_id FROM content_candidates").fetchone()[0]

    snapshot = store.evidence(identifier)
    assert {item.publisher for item in snapshot} == {"Federal Reserve", "NPR"}
    assert {item.kind for item in snapshot} == {EvidenceKind.OFFICIAL, EvidenceKind.NEWS}
    assert all(item.retrieved_at == NOW for item in snapshot)

    changed = bundle.model_copy(deep=True)
    changed.items[0].title = "Changed after enqueue"
    assert store.enqueue(candidate(), changed, NOW) is False
    assert all(item.title != "Changed after enqueue" for item in store.evidence(identifier))


def test_incomplete_or_wrong_market_evidence_fails_closed(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    incomplete = evidence_bundle().model_copy(deep=True)
    incomplete.items.pop()

    with pytest.raises(ValueError, match="incomplete"):
        store.enqueue(candidate(), incomplete, NOW)

    wrong_market = evidence_bundle().model_copy(update={"market_id": "other"})
    with pytest.raises(ValueError, match="does not match"):
        store.enqueue(candidate(), wrong_market, NOW)
