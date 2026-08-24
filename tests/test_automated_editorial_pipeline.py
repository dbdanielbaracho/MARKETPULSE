from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.domain.evidence import EvidenceBundle, EvidenceItem, EvidenceKind
from app.main import run_content_drafts_forever, run_scheduled_publications_forever
from app.services.content_drafts import ContentDraft
from app.services.content_queue import ContentDecision, ContentPolicy, classify_content_candidate
from app.storage.content_queue import ContentQueueStore


NOW = datetime(2026, 8, 24, 14, 0, tzinfo=timezone.utc)


class FakeAIProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, market_id: str, evidence: tuple[EvidenceItem, ...]) -> ContentDraft:
        self.calls += 1
        assert market_id == "kalshi:auto"
        assert {item.publisher for item in evidence} == {"Federal Reserve", "NPR"}
        return ContentDraft(
            headline="Automated evidence brief",
            body="Generated only from the persisted evidence snapshot.",
            citation_ids=tuple(item.evidence_id for item in evidence),
            generator="test-ai",
        )


def _bundle() -> EvidenceBundle:
    return EvidenceBundle(
        market_id="kalshi:auto",
        generated_at=NOW,
        items=[
            EvidenceItem(
                title="Federal Reserve policy release relevant to automated market",
                url="https://www.federalreserve.gov/newsevents/pressreleases/auto.htm",
                publisher="Federal Reserve",
                kind=EvidenceKind.OFFICIAL,
                published_at=NOW - timedelta(minutes=20),
                retrieved_at=NOW,
            ),
            EvidenceItem(
                title="Independent reporting on automated market policy release",
                url="https://www.npr.org/sections/business/auto-market",
                publisher="NPR",
                kind=EvidenceKind.NEWS,
                published_at=NOW - timedelta(minutes=10),
                retrieved_at=NOW,
            ),
        ],
    )


async def _wait_until(predicate, timeout: float = 1.5) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("automated worker did not reach the expected state")
        await asyncio.sleep(0.01)


def test_diverse_evidence_runs_through_ai_worker_and_scheduled_publication(tmp_path):
    async def scenario() -> None:
        store = ContentQueueStore(tmp_path / "pipeline.db")
        bundle = _bundle()
        candidate = classify_content_candidate(
            market_id=bundle.market_id,
            score=90,
            evidence=bundle,
            policy=ContentPolicy(),
        )
        assert candidate.decision == ContentDecision.CREATE
        assert store.enqueue(candidate, bundle, NOW) is True

        provider = FakeAIProvider()
        draft_stop = asyncio.Event()
        draft_task = asyncio.create_task(
            run_content_drafts_forever(draft_stop, store, provider, ai_daily_limit=10)
        )
        await _wait_until(lambda: store.draft_counts()["pending_review"] == 1)
        draft_stop.set()
        await asyncio.wait_for(draft_task, timeout=1)
        assert provider.calls == 1

        draft = store.drafts("pending_review")[0]
        persisted = store.evidence(draft.candidate_id)
        assert set(draft.citation_ids).issubset({item.evidence_id for item in persisted})
        store.review_draft(draft.draft_id, "approved", "editor_verified_sources", NOW)
        store.schedule_publication(draft.draft_id, NOW - timedelta(seconds=1), "automated_due_release")

        publication_stop = asyncio.Event()
        publication_task = asyncio.create_task(run_scheduled_publications_forever(publication_stop, store))
        await _wait_until(lambda: store.publication_counts()["active"] == 1)
        publication_stop.set()
        await asyncio.wait_for(publication_task, timeout=1)

        published = store.publications()[0]
        assert published.headline == "Automated evidence brief"
        assert {item.publisher for item in store.publication_evidence(published.publication_id)} == {
            "Federal Reserve",
            "NPR",
        }
        assert store.schedule_counts() == {"published": 1}

    asyncio.run(scenario())
