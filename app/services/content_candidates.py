from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.main import DiscoveryMarket


class CandidateAction(str, Enum):
    IGNORE = "ignore"
    UPDATE_SITE = "update_site"
    CREATE_CONTENT = "create_content"


@dataclass(frozen=True)
class ContentPolicy:
    update_site_threshold: float = 35.0
    create_content_threshold: float = 65.0

    def validate(self) -> None:
        if not (0 <= self.update_site_threshold <= self.create_content_threshold <= 100):
            raise ValueError("content thresholds must satisfy 0 <= update <= create <= 100")


@dataclass(frozen=True)
class ContentCandidate:
    market_id: str
    action: CandidateAction
    score: float
    reason: str
    created_at: datetime


def classify(market: DiscoveryMarket, policy: ContentPolicy) -> ContentCandidate:
    policy.validate()
    score = market.trend_score
    if score >= policy.create_content_threshold:
        action = CandidateAction.CREATE_CONTENT
        reason = "trend score qualifies for evidence-backed content generation"
    elif score >= policy.update_site_threshold:
        action = CandidateAction.UPDATE_SITE
        reason = "trend score qualifies for site refresh only"
    else:
        action = CandidateAction.IGNORE
        reason = "below configured content threshold"
    return ContentCandidate(
        market_id=market.canonical_id,
        action=action,
        score=score,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
