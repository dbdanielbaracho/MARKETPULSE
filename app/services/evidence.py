from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.evidence import EvidenceBundle, EvidenceItem


@dataclass(frozen=True)
class EvidencePolicy:
    max_age_hours: int = 72
    min_publishers_for_explanation: int = 2

    def __post_init__(self) -> None:
        if self.max_age_hours <= 0:
            raise ValueError("max_age_hours must be positive")
        if self.min_publishers_for_explanation <= 0:
            raise ValueError("min_publishers_for_explanation must be positive")


def is_fresh(item: EvidenceItem, policy: EvidencePolicy, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    published = item.published_at or item.retrieved_at
    return published >= now - timedelta(hours=policy.max_age_hours)


def usable_bundle(bundle: EvidenceBundle, policy: EvidencePolicy, now: datetime | None = None) -> EvidenceBundle:
    fresh = [item for item in bundle.items if is_fresh(item, policy, now)]
    return EvidenceBundle(market_id=bundle.market_id, generated_at=bundle.generated_at, items=fresh)


def can_explain_move(bundle: EvidenceBundle, policy: EvidencePolicy, now: datetime | None = None) -> bool:
    usable = usable_bundle(bundle, policy, now)
    return usable.publisher_count >= policy.min_publishers_for_explanation
