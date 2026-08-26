from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import log10
from typing import Protocol


class RelevanceMarket(Protocol):
    probability: float | None
    probability_change: float | None
    volume_usd: float | None
    trend_score: float
    observed_at: datetime
    closes_at: datetime | None
    source_url: str | None


@dataclass(frozen=True)
class RelevanceSignal:
    score: int
    reasons: tuple[str, ...]


MIN_FULL_CONFIDENCE_VOLUME_USD = 100.0


def relevance_score(market: RelevanceMarket, *, now: datetime | None = None) -> RelevanceSignal:
    """Rank what deserves attention now without forecasting outcomes or returns.

    Large probability moves in extremely thin markets are deliberately discounted.
    A one-dollar market must not outrank materially active markets merely because its
    displayed probability moved sharply.
    """
    current = now or datetime.now(timezone.utc)
    reasons: list[tuple[float, str]] = []
    score = 0.0

    volume = max(0.0, market.volume_usd or 0.0)
    movement_points = abs(market.probability_change or 0.0) * 100
    raw_movement_component = min(30.0, movement_points / 20.0 * 30.0)
    movement_confidence = min(1.0, volume / MIN_FULL_CONFIDENCE_VOLUME_USD)
    movement_component = raw_movement_component * movement_confidence
    score += movement_component
    if movement_component >= 15:
        reasons.append((movement_component, f"meaningful probability move ({movement_points:.1f} pts)"))
    elif raw_movement_component >= 15 and movement_confidence < 1.0:
        reasons.append((movement_component, "probability move discounted because reported activity is thin"))

    activity_component = 0.0
    if volume > 0:
        activity_component = min(20.0, max(3.0, (log10(volume + 1) - 2.0) * 5.0))
        score += activity_component
        if activity_component >= 10:
            reasons.append((activity_component, "substantial reported market activity"))

    urgency_component = 0.0
    if market.closes_at is not None:
        hours = (market.closes_at - current).total_seconds() / 3600
        if hours <= 0:
            return RelevanceSignal(0, ("contract is no longer open by its displayed deadline",))
        if hours <= 24:
            urgency_component = 15.0
            reasons.append((urgency_component, "scheduled to close within 24 hours"))
        elif hours <= 72:
            urgency_component = 10.0
            reasons.append((urgency_component, "scheduled to close within 72 hours"))
        elif hours <= 168:
            urgency_component = 5.0
            reasons.append((urgency_component, "scheduled to close within seven days"))
    score += urgency_component

    age_hours = max(0.0, (current - market.observed_at).total_seconds() / 3600)
    if age_hours <= .25:
        freshness_component = 15.0
        reasons.append((freshness_component, "observed within 15 minutes"))
    elif age_hours <= 1:
        freshness_component = 12.0
        reasons.append((freshness_component, "observed within one hour"))
    elif age_hours <= 6:
        freshness_component = 7.0
    elif age_hours <= 24:
        freshness_component = 2.0
    else:
        freshness_component = 0.0
    score += freshness_component

    completeness_component = 0.0
    if market.probability is not None:
        completeness_component += 3.0
    if market.volume_usd is not None:
        completeness_component += 2.0
    if market.closes_at is not None:
        completeness_component += 2.0
    if market.source_url:
        completeness_component += 3.0
    score += completeness_component
    if completeness_component >= 8:
        reasons.append((completeness_component, "complete primary market metadata"))

    context_component = min(10.0, max(0.0, market.trend_score) / 10.0)
    score += context_component

    if not reasons:
        reasons.append((0.0, "ranked from current movement, activity, recency and metadata"))
    reasons.sort(key=lambda item: item[0], reverse=True)
    return RelevanceSignal(
        score=round(min(100.0, max(0.0, score))),
        reasons=tuple(reason for _, reason in reasons[:4]),
    )
