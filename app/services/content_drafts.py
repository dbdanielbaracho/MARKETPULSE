from __future__ import annotations

from dataclasses import dataclass

from app.domain.evidence import EvidenceItem, EvidenceKind


@dataclass(frozen=True)
class ContentDraft:
    headline: str
    body: str
    citation_ids: tuple[str, ...]
    generator: str = "evidence_brief_v1"


def generate_evidence_brief(
    *,
    market_id: str,
    evidence: tuple[EvidenceItem, ...],
) -> ContentDraft:
    if not evidence:
        raise ValueError("draft generation requires persisted evidence")

    venue = next((item for item in evidence if item.kind == EvidenceKind.VENUE), None)
    primary = venue or evidence[0]
    headline = primary.title.removeprefix("Primary venue contract: ").strip()
    if not headline:
        raise ValueError("draft headline cannot be empty")
    headline = headline[:180].rstrip()

    ordered = sorted(
        evidence,
        key=lambda item: (item.kind != EvidenceKind.VENUE, item.publisher.casefold(), item.evidence_id),
    )
    evidence_lines = [
        f"- {item.publisher} ({item.kind.value}): {item.title}"
        for item in ordered
    ]
    body = "\n".join(
        [
            f"Market: {headline}",
            "",
            "Evidence checked:",
            *evidence_lines,
            "",
            "This is an evidence brief, not a statement that related contracts are equivalent.",
            f"Market reference: {market_id}",
        ]
    )
    return ContentDraft(
        headline=headline,
        body=body,
        citation_ids=tuple(item.evidence_id for item in ordered),
    )
