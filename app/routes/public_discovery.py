from __future__ import annotations

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


@router.get("/api/v1/discovery", include_in_schema=True)
def semantic_discovery(
    sort: Literal["trending", "movers", "volume"] = "trending",
    category: str | None = None,
    venue: Literal["kalshi", "polymarket"] | None = None,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
) -> JSONResponse:
    """Return Discovery cards without turning an active Kalshi venue into a dead page.

    Strict semantic-attention cards remain the first choice. If a user explicitly
    selects Kalshi and none pass the strict gate, a bounded quality-screened
    best-available set is returned. Known thin/weak Kalshi cards remain excluded.
    `/api/v1/markets` continues to expose the complete monitored inventory.
    """
    raw = markets(sort=sort, category=category, venue=venue, q=q, limit=100)
    candidates = [item.model_dump(mode="json") for item in raw]

    curated = curate_semantic_discovery(candidates)
    response_mode = "attention"
    if not curated and venue == "kalshi" and candidates:
        curated = curate_best_available(candidates, limit=limit)
        if curated:
            response_mode = "best-available"
    curated = curated[:limit]

    now = datetime.now(timezone.utc)
    for item in curated:
        item["attention_score"] = attention_score(
            trend_score_value=_number(item.get("trend_score")) or 0.0,
            probability_change_value=_number(item.get("probability_change")),
            volume_usd=_number(item.get("volume_usd")),
            hours_to_close=_hours_to_close(item.get("closes_at"), now=now),
        )
    return JSONResponse(
        curated,
        headers={
            "X-PrediBeacon-Semantic-Discovery": SEMANTIC_DISCOVERY_VERSION,
            "X-PrediBeacon-Discovery-Mode": response_mode,
            "X-PrediBeacon-Monitored-Candidate-Count": str(len(candidates)),
            "X-PrediBeacon-Curated-Count": str(len(curated)),
        },
    )
