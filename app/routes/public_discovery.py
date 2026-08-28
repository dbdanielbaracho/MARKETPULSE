from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.main import markets
from app.services.discovery_semantics import (
    SEMANTIC_DISCOVERY_VERSION,
    curate_best_available,
    curate_semantic_discovery,
)
from app.services.intelligence import attention_score


router = APIRouter()

_PUBLIC_CATEGORIES = ("Economy", "Politics", "Sports", "Tech")
_MIN_VISIBLE_MOVE = 0.0005  # 0.05 percentage points; avoids rendering 0.0 pts as a mover.


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _hours_to_close(value: object, *, now: datetime) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        closes_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=timezone.utc)
    return (closes_at.astimezone(timezone.utc) - now).total_seconds() / 3600


def _candidate_universe(
    *,
    sort: Literal["trending", "movers", "volume"],
    category: str | None,
    venue: Literal["kalshi", "polymarket"] | None,
    q: str | None,
) -> list[dict[str, object]]:
    """Build a representative universe before semantic curation.

    The raw inventory endpoint is intentionally ranking-oriented and bounded to
    100 results. Querying only its global top 100 can hide an entire valid
    category before semantic curation even begins. When no category is selected,
    combine the global leaders with category leaders, deduplicate by canonical
    market id, and only then apply the public quality gate and final ranking.
    This is candidate coverage, not a display quota.
    """
    groups = [markets(sort=sort, category=category, venue=venue, q=q, limit=100)]
    if category is None and not q:
        groups.extend(
            markets(sort=sort, category=name, venue=venue, q=None, limit=50)
            for name in _PUBLIC_CATEGORIES
        )

    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item.canonical_id in seen:
                continue
            seen.add(item.canonical_id)
            candidates.append(item.model_dump(mode="json"))
    return candidates


def _rank_value(item: dict[str, object], sort: str) -> tuple[float, ...]:
    change = abs(_number(item.get("probability_change")) or 0.0)
    volume = _number(item.get("volume_usd")) or 0.0
    trend = _number(item.get("trend_score")) or 0.0
    relevance = _number(item.get("relevance_score")) or 0.0
    attention = _number(item.get("attention_score")) or 0.0
    if sort == "movers":
        return (change, attention, volume)
    if sort == "volume":
        return (volume, attention, relevance)
    return (attention, relevance, trend, volume)


def _soft_category_diversity(
    items: list[dict[str, object]],
    *,
    sort: str,
    limit: int,
) -> list[dict[str, object]]:
    """Prevent a near-tied category from producing a long single-topic streak.

    This never guarantees category slots. It only substitutes a different
    category when its rank value is close enough to the current leader.
    """
    remaining = list(items)
    result: list[dict[str, object]] = []
    last_category: str | None = None
    streak = 0
    while remaining and len(result) < limit:
        selected_index = 0
        leader = remaining[0]
        leader_category = str(leader.get("category") or "")
        if leader_category and leader_category == last_category and streak >= 4:
            leader_score = _rank_value(leader, sort)[0]
            alternative_index = next(
                (
                    index
                    for index, item in enumerate(remaining[1:], start=1)
                    if str(item.get("category") or "") not in {"", leader_category}
                    and (
                        leader_score <= 0
                        or _rank_value(item, sort)[0] >= leader_score * 0.85
                    )
                ),
                None,
            )
            if alternative_index is not None:
                selected_index = alternative_index
        selected = remaining.pop(selected_index)
        result.append(selected)
        selected_category = str(selected.get("category") or "")
        if selected_category and selected_category == last_category:
            streak += 1
        else:
            last_category = selected_category or None
            streak = 1
    return result


@router.get("/api/v1/discovery", include_in_schema=True)
def semantic_discovery(
    sort: Literal["trending", "movers", "volume"] = "trending",
    category: str | None = None,
    venue: Literal["kalshi", "polymarket"] | None = None,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
) -> JSONResponse:
    """Return quality-screened, representative public Discovery cards."""
    candidates = _candidate_universe(sort=sort, category=category, venue=venue, q=q)

    curated = curate_semantic_discovery(candidates)
    response_mode = "attention"
    if not curated and venue == "kalshi" and candidates:
        curated = curate_best_available(candidates, limit=max(limit, 20))
        if curated:
            response_mode = "best-available"

    now = datetime.now(timezone.utc)
    for item in curated:
        item["attention_score"] = attention_score(
            trend_score_value=_number(item.get("trend_score")) or 0.0,
            probability_change_value=_number(item.get("probability_change")),
            volume_usd=_number(item.get("volume_usd")),
            hours_to_close=_hours_to_close(item.get("closes_at"), now=now),
        )

    # A market with no measurable probability movement can be active and
    # relevant, but it is not a "biggest mover". Keep it available under
    # Most relevant / Most volume rather than displaying a misleading 0.0 pts.
    if sort == "movers":
        curated = [
            item for item in curated
            if abs(_number(item.get("probability_change")) or 0.0) >= _MIN_VISIBLE_MOVE
        ]

    curated.sort(key=lambda item: _rank_value(item, sort), reverse=True)
    curated = _soft_category_diversity(curated, sort=sort, limit=limit)

    coverage = Counter(str(item.get("category") or "Unclassified") for item in curated)
    coverage_header = ",".join(f"{name}:{count}" for name, count in sorted(coverage.items()))
    return JSONResponse(
        curated,
        headers={
            "X-PrediBeacon-Semantic-Discovery": SEMANTIC_DISCOVERY_VERSION,
            "X-PrediBeacon-Discovery-Mode": response_mode,
            "X-PrediBeacon-Monitored-Candidate-Count": str(len(candidates)),
            "X-PrediBeacon-Curated-Count": str(len(curated)),
            "X-PrediBeacon-Category-Coverage": coverage_header,
        },
    )
