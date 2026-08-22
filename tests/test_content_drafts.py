from datetime import datetime, timezone

import pytest

from app.domain.evidence import EvidenceItem, EvidenceKind
from app.services.content_drafts import generate_evidence_brief

NOW = datetime(2026, 8, 22, tzinfo=timezone.utc)


def item(title, publisher, kind, url):
    return EvidenceItem(
        title=title,
        publisher=publisher,
        kind=kind,
        url=url,
        published_at=NOW,
        retrieved_at=NOW,
    )


def test_draft_is_grounded_and_cited():
    venue = item(
        "Primary venue contract: Will rates fall?",
        "Kalshi",
        EvidenceKind.VENUE,
        "https://kalshi.com/markets/rates",
    )
    news = item(
        "Federal Reserve signals policy path",
        "NPR",
        EvidenceKind.NEWS,
        "https://npr.org/rates",
    )

    draft = generate_evidence_brief(market_id="kalshi:rates", evidence=(news, venue))

    assert draft.headline == "Will rates fall?"
    assert "Kalshi (venue)" in draft.body
    assert "NPR (news)" in draft.body
    assert "not a statement that related contracts are equivalent" in draft.body
    assert set(draft.citation_ids) == {venue.evidence_id, news.evidence_id}


def test_draft_generation_fails_without_persisted_evidence():
    with pytest.raises(ValueError, match="requires persisted evidence"):
        generate_evidence_brief(market_id="kalshi:rates", evidence=())
