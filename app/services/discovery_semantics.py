from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Mapping

from app.services.ranking import activity_confidence
from app.services.relevance import RelevanceSignal, relevance_score

# Semantic Product Truth Gate (DMU-SEM-001): being a valid/monitored contract is
# not enough to be highlighted as a market that "deserves attention now".
# The existing quiet-market fallback already treated USD 1,000 as materially
# active. Reuse that evidence-backed boundary instead of inventing a second,
# weaker editorial definition.
MIN_DISCOVERY_VOLUME_USD = 1_000.0
MIN_DISCOVERY_RELEVANCE_SCORE = 20
SEMANTIC_DISCOVERY_VERSION = "semantic-discovery-v1"


@dataclass(frozen=True)
class SemanticDiscoveryDecision:
    eligible: bool
    relevance: int
    activity_confidence: float
    reason_code: str
    reasons: tuple[str, ...]


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _reason_code(item: Mapping[str, object], signal: RelevanceSignal, *, now: datetime) -> str:
    volume = _number(item.get("volume_usd")) or 0.0
    change = abs(_number(item.get("probability_change")) or 0.0) * 100
    closes_at = _datetime(item.get("closes_at"))
    hours = None if closes_at is None else (closes_at - now).total_seconds() / 3600
    confidence = activity_confidence(volume)

    if change >= 10 and confidence >= 0.70:
        return "sharp_move_with_activity"
    if hours is not None and 0 < hours <= 72:
        return "closing_soon"
    if volume >= 100_000:
        return "high_activity"
    if change >= 2 and confidence >= 0.40:
        return "meaningful_move"
    if signal.score >= 40:
        return "high_relevance"
    return "balanced_signal"


def evaluate_discovery_market(item: Mapping[str, object], *, now: datetime | None = None) -> SemanticDiscoveryDecision:
    current = now or datetime.now(timezone.utc)
    volume = _number(item.get("volume_usd"))
    probability = _number(item.get("probability")) if item.get("probability") is not None else None
    change = _number(item.get("probability_change")) if item.get("probability_change") is not None else None
    trend = _number(item.get("trend_score"))
    observed_at = _datetime(item.get("observed_at"))
    closes_at = _datetime(item.get("closes_at"))

    structurally_valid = (
        bool(str(item.get("canonical_id") or "").strip())
        and bool(str(item.get("title") or "").strip())
        and str(item.get("venue") or "").casefold() in {"kalshi", "polymarket"}
        and volume is not None
        and volume >= 0
        and trend is not None
        and trend >= 0
        and observed_at is not None
        and (probability is None or 0 <= probability <= 1)
        and (closes_at is None or closes_at > current)
    )
    if not structurally_valid:
        return SemanticDiscoveryDecision(False, 0, activity_confidence(volume), "invalid_market", ("market data is incomplete or invalid",))

    market = SimpleNamespace(
        probability=probability,
        probability_change=change,
        volume_usd=volume,
        trend_score=trend,
        observed_at=observed_at,
        closes_at=closes_at,
        source_url=item.get("source_url"),
    )
    signal = relevance_score(market, now=current)
    confidence = activity_confidence(volume)
    eligible = volume >= MIN_DISCOVERY_VOLUME_USD and signal.score >= MIN_DISCOVERY_RELEVANCE_SCORE
    return SemanticDiscoveryDecision(
        eligible=eligible,
        relevance=signal.score,
        activity_confidence=round(confidence, 4),
        reason_code=_reason_code(item, signal, now=current),
        reasons=signal.reasons,
    )


def curate_semantic_discovery(items: list[dict[str, object]], *, now: datetime | None = None) -> list[dict[str, object]]:
    """Return only markets that satisfy the user-facing Discovery promise.

    There is intentionally no low-quality fallback. If nothing meets the semantic
    gate, the truthful product state is an empty curated set while monitored venue
    inventory remains visible separately in /api/v1/status.
    """
    current = now or datetime.now(timezone.utc)
    curated: list[dict[str, object]] = []
    for source in items:
        decision = evaluate_discovery_market(source, now=current)
        if not decision.eligible:
            continue
        item = dict(source)
        item["relevance_score"] = decision.relevance
        item["relevance_reasons"] = list(decision.reasons)
        item["activity_confidence"] = decision.activity_confidence
        item["attention_reason_code"] = decision.reason_code
        item["semantic_discovery_version"] = SEMANTIC_DISCOVERY_VERSION
        curated.append(item)
    return curated
