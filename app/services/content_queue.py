from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from app.domain.evidence import EvidenceBundle, EvidenceFreshness, EvidenceKind


class ContentDecision(StrEnum):
    REJECT = "reject"
    UPDATE = "update"
    CREATE = "create"


@dataclass(frozen=True)
class ContentPolicy:
    update_score: float = 55.0
    create_score: float = 75.0
    max_evidence_age_hours: int = 48
    min_publishers_for_create: int = 2
    require_official_or_venue_for_create: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.update_score <= self.create_score <= 100:
            raise ValueError("content thresholds must satisfy 0 <= update <= create <= 100")
        if self.max_evidence_age_hours <= 0:
            raise ValueError("max evidence age must be positive")
        if self.min_publishers_for_create < 1:
            raise ValueError("minimum publisher count must be positive")


@dataclass(frozen=True)
class ContentCandidate:
    market_id: str
    score: float
    decision: ContentDecision
    reason: str
    evidence_ids: tuple[str, ...]


def classify_content_candidate(*, market_id: str, score: float, evidence: EvidenceBundle, policy: ContentPolicy) -> ContentCandidate:
    if not 0 <= score <= 100:
        raise ValueError("score must be bounded 0..100")

    bundle = evidence.deduplicated()
    max_age = timedelta(hours=policy.max_evidence_age_hours)
    fresh = [item for item in bundle.items if item.freshness(max_age=max_age) == EvidenceFreshness.FRESH]
    publisher_count = len({item.source_domain for item in fresh})
    strong_source = any(item.kind in {EvidenceKind.OFFICIAL, EvidenceKind.VENUE} for item in fresh)

    if score < policy.update_score:
        return ContentCandidate(market_id, score, ContentDecision.REJECT, "score_below_update_threshold", tuple())
    if not fresh:
        return ContentCandidate(market_id, score, ContentDecision.REJECT, "no_fresh_evidence", tuple())
    if score < policy.create_score:
        return ContentCandidate(market_id, score, ContentDecision.UPDATE, "fresh_evidence_supports_update", tuple(item.evidence_id for item in fresh))
    if publisher_count < policy.min_publishers_for_create:
        return ContentCandidate(market_id, score, ContentDecision.UPDATE, "insufficient_source_diversity_for_create", tuple(item.evidence_id for item in fresh))
    if policy.require_official_or_venue_for_create and not strong_source:
        return ContentCandidate(market_id, score, ContentDecision.UPDATE, "missing_strong_source_for_create", tuple(item.evidence_id for item in fresh))
    return ContentCandidate(market_id, score, ContentDecision.CREATE, "evidence_gate_passed", tuple(item.evidence_id for item in fresh))
