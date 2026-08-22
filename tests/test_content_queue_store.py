from datetime import datetime, timedelta, timezone

import pytest

from app.domain.evidence import EvidenceBundle, EvidenceItem, EvidenceKind
from app.services.content_queue import ContentCandidate, ContentDecision
from app.services.content_drafts import ContentDraft
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

    assert store.enqueue(candidate(), bundle, NOW) is False
    bundle.items[0].title = "Changed after enqueue"
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


def test_claim_and_save_draft_are_atomic_and_audited(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    bundle = evidence_bundle()
    store.enqueue(candidate(), bundle, NOW)

    claimed = store.claim_next(NOW)
    assert claimed is not None
    assert claimed.state == "claimed"
    assert store.claim_next(NOW) is None

    draft = ContentDraft(
        headline="Evidence brief",
        body="Grounded only in persisted evidence.",
        citation_ids=tuple(item.evidence_id for item in bundle.items),
    )
    stored = store.save_draft(claimed.candidate_id, draft, NOW)

    assert stored.state == "pending_review"
    assert store.get(claimed.candidate_id).state == "completed"
    assert store.draft_counts()["pending_review"] == 1
    assert store.audit(claimed.candidate_id)[-2:] == [
        ("queued", "claimed", "draft_worker_claimed"),
        ("claimed", "completed", "evidence_draft_created"),
    ]


def test_draft_rejects_unknown_citation_and_wrong_state(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    store.enqueue(candidate(), evidence_bundle(), NOW)
    claimed = store.claim_next(NOW)

    unknown = ContentDraft(
        headline="Unsafe",
        body="Unsafe",
        citation_ids=("ev_not_persisted",),
    )
    with pytest.raises(ValueError, match="persisted evidence"):
        store.save_draft(claimed.candidate_id, unknown, NOW)

    valid = ContentDraft(
        headline="Safe",
        body="Safe",
        citation_ids=(evidence_bundle().items[0].evidence_id,),
    )
    store.save_draft(claimed.candidate_id, valid, NOW)
    with pytest.raises(ValueError, match="must be claimed"):
        store.save_draft(claimed.candidate_id, valid, NOW)



def test_draft_review_is_listed_guarded_and_audited(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    bundle = evidence_bundle()
    store.enqueue(candidate(), bundle, NOW)
    claimed = store.claim_next(NOW)
    stored = store.save_draft(
        claimed.candidate_id,
        ContentDraft(
            headline="Review me",
            body="Grounded draft.",
            citation_ids=tuple(item.evidence_id for item in bundle.items),
        ),
        NOW,
    )

    pending = store.drafts("pending_review")
    assert [item.draft_id for item in pending] == [stored.draft_id]

    approved = store.review_draft(stored.draft_id, "approved", "editor_verified_sources", NOW)
    assert approved.state == "approved"
    assert store.drafts("pending_review") == []
    assert store.draft_audit(stored.draft_id) == [
        (None, "pending_review", "draft_created"),
        ("pending_review", "approved", "editor_verified_sources"),
    ]

    with pytest.raises(ValueError, match="not pending"):
        store.review_draft(stored.draft_id, "rejected", "second_decision", NOW)
    with pytest.raises(ValueError, match="reason"):
        store.review_draft("missing", "approved", "", NOW)
    with pytest.raises(ValueError, match="invalid draft state"):
        store.drafts("published")


def test_drafts_created_since_supports_daily_limit(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    bundle = evidence_bundle()
    store.enqueue(candidate(), bundle, NOW)
    claimed = store.claim_next(NOW)
    store.save_draft(
        claimed.candidate_id,
        ContentDraft(
            headline="Safe",
            body="Safe",
            citation_ids=(bundle.items[0].evidence_id,),
        ),
        NOW,
    )

    assert store.drafts_created_since(datetime(2026, 8, 22, tzinfo=timezone.utc)) == 1
    assert store.drafts_created_since(datetime(2026, 8, 23, tzinfo=timezone.utc)) == 0
    with pytest.raises(ValueError, match="timezone-aware"):
        store.drafts_created_since(datetime(2026, 8, 22))


def test_approved_draft_publication_is_versioned_idempotent_and_rollbackable(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    bundle = evidence_bundle()
    store.enqueue(candidate(), bundle, NOW)
    claimed = store.claim_next(NOW)
    draft = store.save_draft(
        claimed.candidate_id,
        ContentDraft(
            headline="Federal Reserve outlook",
            body="Evidence-grounded article body.",
            citation_ids=tuple(item.evidence_id for item in bundle.items),
        ),
        NOW,
    )

    with pytest.raises(ValueError, match="must be approved"):
        store.publish_draft(draft.draft_id, "publish_before_review", NOW)

    store.review_draft(draft.draft_id, "approved", "sources_verified", NOW)
    published = store.publish_draft(draft.draft_id, "editor_released", NOW)
    repeated = store.publish_draft(draft.draft_id, "idempotent_retry", NOW)

    assert repeated == published
    assert published.state == "active"
    assert published.version == 1
    assert published.slug.startswith("federal-reserve-outlook-")
    assert store.publication(published.slug) == published
    assert store.publications() == [published]
    assert {item.publisher for item in store.publication_evidence(published.publication_id)} == {
        "Federal Reserve",
        "NPR",
    }
    assert store.publication_counts() == {"active": 1, "rolled_back": 0}
    assert store.publication_audit(published.publication_id) == [
        (None, "active", "editor_released"),
    ]

    rolled_back = store.rollback_publication(
        published.publication_id,
        "material_source_correction",
        NOW,
    )
    assert rolled_back.state == "rolled_back"
    assert store.publication(published.slug) is None
    assert store.publication(published.slug, include_rolled_back=True) == rolled_back
    assert store.publication_counts() == {"active": 0, "rolled_back": 1}
    assert store.publication_audit(published.publication_id) == [
        (None, "active", "editor_released"),
        ("active", "rolled_back", "material_source_correction"),
    ]

    with pytest.raises(ValueError, match="not active"):
        store.rollback_publication(published.publication_id, "repeat", NOW)


def test_publication_requires_reason_and_known_records(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")

    with pytest.raises(ValueError, match="reason"):
        store.publish_draft("missing", "", NOW)
    with pytest.raises(KeyError):
        store.publish_draft("missing", "manual_release", NOW)
    with pytest.raises(ValueError, match="reason"):
        store.rollback_publication("missing", "", NOW)
    with pytest.raises(KeyError):
        store.rollback_publication("missing", "editor_rollback", NOW)
    with pytest.raises(ValueError, match="invalid publication state"):
        store.publications("invalid")


def test_approved_draft_can_be_scheduled_and_published_when_due(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    bundle = evidence_bundle()
    store.enqueue(candidate(), bundle, NOW)
    claimed = store.claim_next(NOW)
    draft = store.save_draft(
        claimed.candidate_id,
        ContentDraft(
            headline="Scheduled Federal Reserve outlook",
            body="Evidence-grounded scheduled article.",
            citation_ids=tuple(item.evidence_id for item in bundle.items),
        ),
        NOW,
    )
    store.review_draft(draft.draft_id, "approved", "editor_verified", NOW)
    scheduled_at = NOW + timedelta(hours=1)
    schedule = store.schedule_publication(draft.draft_id, scheduled_at, "morning_release")
    duplicate = store.schedule_publication(draft.draft_id, scheduled_at, "morning_release")

    assert duplicate == schedule
    assert schedule["state"] == "scheduled"
    assert store.publish_due(NOW) == []
    assert store.schedule_counts() == {"scheduled": 1}

    results = store.publish_due(scheduled_at)
    assert results[0]["state"] == "published"
    assert results[0]["publication_id"]
    assert store.schedule_counts() == {"published": 1}
    assert len(store.publications()) == 1
    assert store.publish_due(scheduled_at + timedelta(minutes=1)) == []


def test_schedule_rejects_unapproved_draft_and_naive_time(tmp_path):
    store = ContentQueueStore(tmp_path / "queue.db")
    bundle = evidence_bundle()
    store.enqueue(candidate(), bundle, NOW)
    claimed = store.claim_next(NOW)
    draft = store.save_draft(claimed.candidate_id, ContentDraft(headline="Pending", body="Pending", citation_ids=tuple(item.evidence_id for item in bundle.items)), NOW)
    with pytest.raises(ValueError, match="approved"):
        store.schedule_publication(draft.draft_id, NOW, "too_early")
    store.review_draft(draft.draft_id, "approved", "verified", NOW)
    with pytest.raises(ValueError, match="timezone"):
        store.schedule_publication(draft.draft_id, datetime(2026, 8, 23), "naive")
