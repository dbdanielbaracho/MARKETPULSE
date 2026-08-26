from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.markets import NormalizedMarket
from app.services.ranking import activity_component, movement_component


@dataclass(frozen=True)
class MarketSnapshot:
    canonical_id: str
    probability: float | None
    volume_usd: float | None
    observed_at: datetime


@dataclass(frozen=True)
class MarketSignal:
    canonical_id: str
    probability: float | None
    probability_change: float | None
    volume_usd: float | None
    trend_score: float


@dataclass(frozen=True)
class QualitySignal:
    score: int
    grade: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class BreakingSignal:
    active: bool
    score: float
    probability_points: float
    volume_change_percent: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ConsensusSignal:
    probability: float
    gap_points: float
    agreement: str


def snapshot(market: NormalizedMarket) -> MarketSnapshot:
    return MarketSnapshot(
        canonical_id=market.canonical_id,
        probability=market.yes_probability,
        volume_usd=market.volume_usd,
        observed_at=market.observed_at,
    )


def probability_change(current: MarketSnapshot, previous: MarketSnapshot | None) -> float | None:
    if previous is None or current.probability is None or previous.probability is None:
        return None
    return current.probability - previous.probability


def trend_score(current: MarketSnapshot, previous: MarketSnapshot | None) -> float:
    """Bounded discovery score using the shared activity-confidence contract."""
    change = probability_change(current, previous)
    movement = movement_component(change, current.volume_usd, max_points=70.0)
    activity = activity_component(current.volume_usd, max_points=30.0)
    return round(min(100.0, movement + activity), 2)


def signal(current: MarketSnapshot, previous: MarketSnapshot | None = None) -> MarketSignal:
    return MarketSignal(
        canonical_id=current.canonical_id,
        probability=current.probability,
        probability_change=probability_change(current, previous),
        volume_usd=current.volume_usd,
        trend_score=trend_score(current, previous),
    )


def market_quality(
    *,
    probability: float | None,
    volume_usd: float | None,
    observed_at: datetime,
    closes_at: datetime | None,
    source_url: str | None,
    history_count: int,
    now: datetime | None = None,
) -> QualitySignal:
    """Score signal completeness/freshness, never outcome confidence."""
    now = now or datetime.now(timezone.utc)
    score = 20
    reasons: list[str] = ["base market record"]
    if probability is not None:
        score += 20
        reasons.append("probability available")
    if volume_usd is not None:
        score += 12
        reasons.append("reported volume available")
    if closes_at is not None:
        score += 10
        reasons.append("deadline available")
    if source_url:
        score += 8
        reasons.append("primary source available")
    age_hours = max(0.0, (now - observed_at).total_seconds() / 3600)
    if age_hours <= 0.25:
        score += 15
        reasons.append("observed within 15 minutes")
    elif age_hours <= 1:
        score += 10
        reasons.append("observed within one hour")
    elif age_hours <= 6:
        score += 4
        reasons.append("observed within six hours")
    if history_count >= 12:
        score += 15
        reasons.append("deep recent history")
    elif history_count >= 4:
        score += 8
        reasons.append("usable recent history")
    score = min(100, score)
    grade = "excellent" if score >= 85 else "good" if score >= 70 else "limited" if score >= 50 else "weak"
    return QualitySignal(score=score, grade=grade, reasons=tuple(reasons))


def breaking_signal(history: list[MarketSnapshot], *, threshold: float = 3.0) -> BreakingSignal:
    """Detect acceleration from recorded observations without claiming causation."""
    usable = [item for item in history if item.probability is not None]
    if len(usable) < 2:
        return BreakingSignal(False, 0.0, 0.0, None, ("insufficient probability history",))
    usable.sort(key=lambda item: item.observed_at)
    first, last = usable[0], usable[-1]
    probability_points = abs(float(last.probability) - float(first.probability)) * 100
    volume_change: float | None = None
    if first.volume_usd is not None and last.volume_usd is not None and first.volume_usd > 0:
        volume_change = max(0.0, (last.volume_usd - first.volume_usd) / first.volume_usd * 100)
    score = probability_points + min(12.0, (volume_change or 0.0) / 10)
    reasons = [f"probability moved {probability_points:.1f} points"]
    if volume_change is not None and volume_change > 0:
        reasons.append(f"reported volume increased {volume_change:.0f}%")
    return BreakingSignal(score >= threshold, round(score, 2), round(probability_points, 2), None if volume_change is None else round(volume_change, 2), tuple(reasons))


def consensus(left_probability: float, right_probability: float, *, equivalent_contracts: bool) -> ConsensusSignal | None:
    """Return consensus only after an external contract-equivalence gate passes."""
    if not equivalent_contracts:
        return None
    if not 0 <= left_probability <= 1 or not 0 <= right_probability <= 1:
        raise ValueError("probabilities must be between 0 and 1")
    gap = abs(left_probability - right_probability) * 100
    agreement = "tight" if gap < 2 else "moderate" if gap < 5 else "divergent"
    return ConsensusSignal(
        probability=round((left_probability + right_probability) / 2, 6),
        gap_points=round(gap, 2),
        agreement=agreement,
    )


def attention_score(*, trend_score_value: float, probability_change_value: float | None, volume_usd: float | None, hours_to_close: float | None) -> int:
    """Rank attention with the same activity-confidence contract used by trend_score."""
    score = max(0.0, min(70.0, trend_score_value * 0.7))
    score += movement_component(probability_change_value, volume_usd, max_points=15.0)
    score += activity_component(volume_usd, max_points=10.0)
    if hours_to_close is not None and 0 < hours_to_close <= 72:
        score += 5
    return round(min(100.0, score))
