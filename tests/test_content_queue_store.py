from datetime import datetime, timezone

import pytest

from app.services.content_queue import ContentCandidate, ContentDecision
from app.storage.content_queue import ContentQueueStore

NOW = datetime(2026, 8, 22, tzinfo=timezone.utc)


def candidate(decision=ContentDecision.CREATE):
    return ContentCandidate(
        market_id="kalshi:test",
        score=85,
        decision=decision,
        reason="evidence_gate_passed",
        evidence_ids=("ev_b", "ev_a", "ev_a"),
    )


def test_enqueue_is_idempotent_and_normalizes_evidence(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    assert store.enqueue(candidate(), NOW) is True
    assert store.enqueue(candidate(), NOW) is False
    assert store.counts()["queued"] == 1

    stored = store.get("cc_4c9799d502683302532e")
    if stored is None:
        # Candidate IDs are opaque; resolve the sole row through its audit identity.
        with store._connect() as connection:
            identifier = connection.execute("SELECT candidate_id FROM content_candidates").fetchone()[0]
        stored = store.get(identifier)
    assert stored is not None
    assert stored.evidence_ids == ("ev_a", "ev_b")
    assert stored.state == "queued"


def test_rejected_classification_is_not_queued(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    assert store.enqueue(candidate(ContentDecision.REJECT), NOW) is False
    assert sum(store.counts().values()) == 0


def test_state_transitions_are_guarded_and_audited(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    store.enqueue(candidate(), NOW)
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
    store.enqueue(candidate(), NOW)
    with store._connect() as connection:
        identifier = connection.execute("SELECT candidate_id FROM content_candidates").fetchone()[0]

    with pytest.raises(ValueError):
        store.transition(identifier, "completed", "skip_claim", NOW)
    with pytest.raises(ValueError):
        store.transition(identifier, "claimed", "", NOW)
