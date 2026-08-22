from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.markets import NormalizedMarket


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
    """Bounded discovery score; it is not financial advice or expected return."""
    change = probability_change(current, previous)
    movement_component = min(abs(change or 0.0) / 0.20, 1.0) * 70.0
    volume = current.volume_usd or 0.0
    volume_component = min(volume / 100_000.0, 1.0) * 30.0
    return round(movement_component + volume_component, 2)


def signal(current: MarketSnapshot, previous: MarketSnapshot | None = None) -> MarketSignal:
    return MarketSignal(
        canonical_id=current.canonical_id,
        probability=current.probability,
        probability_change=probability_change(current, previous),
        volume_usd=current.volume_usd,
        trend_score=trend_score(current, previous),
    )
