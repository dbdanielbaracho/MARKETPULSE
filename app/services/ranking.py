from __future__ import annotations

from math import log10

MIN_SIGNAL_ACTIVITY_USD = 100.0
FULL_SIGNAL_CONFIDENCE_USD = 100_000.0
BASE_CONFIDENCE_AT_MIN_ACTIVITY = 0.15


def activity_confidence(volume_usd: float | None) -> float:
    """Return a continuous 0..1 confidence factor for reported market activity.

    Confidence grows smoothly across orders of magnitude instead of jumping to 100%
    at the homepage's minimum activity threshold. This factor is about signal
    reliability only; it is not liquidity, execution quality, or outcome confidence.
    """
    volume = max(0.0, float(volume_usd or 0.0))
    if volume <= 0:
        return 0.0
    if volume < MIN_SIGNAL_ACTIVITY_USD:
        return BASE_CONFIDENCE_AT_MIN_ACTIVITY * (volume / MIN_SIGNAL_ACTIVITY_USD)
    if volume >= FULL_SIGNAL_CONFIDENCE_USD:
        return 1.0
    decades = log10(volume / MIN_SIGNAL_ACTIVITY_USD)
    full_decades = log10(FULL_SIGNAL_CONFIDENCE_USD / MIN_SIGNAL_ACTIVITY_USD)
    return BASE_CONFIDENCE_AT_MIN_ACTIVITY + (1.0 - BASE_CONFIDENCE_AT_MIN_ACTIVITY) * (decades / full_decades)


def movement_component(
    probability_change: float | None,
    volume_usd: float | None,
    *,
    max_points: float,
    full_move: float = 0.20,
) -> float:
    """Score probability movement with the shared activity-confidence contract."""
    raw = min(abs(probability_change or 0.0) / full_move, 1.0) * max_points
    return raw * activity_confidence(volume_usd)


def activity_component(volume_usd: float | None, *, max_points: float) -> float:
    """Map reported activity to a bounded component using the same confidence curve."""
    return activity_confidence(volume_usd) * max_points
