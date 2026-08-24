from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Response

import app.main as core
from app.services.relevance import relevance_score


router = APIRouter(prefix="/api/v1", tags=["public-relevance"])


class RankedDiscoveryMarket(core.DiscoveryMarket):
    relevance_score: int
    relevance_reasons: list[str]


def _ranked_market(market: core.DiscoveryMarket, *, now: datetime) -> RankedDiscoveryMarket:
    relevance = relevance_score(market, now=now)
    return RankedDiscoveryMarket(
        **market.model_dump(),
        relevance_score=relevance.score,
        relevance_reasons=list(relevance.reasons),
    )


def _is_open(market: core.DiscoveryMarket, *, now: datetime) -> bool:
    return market.closes_at is None or market.closes_at > now


@router.get("/markets/relevant", response_model=list[RankedDiscoveryMarket])
def relevant_markets(
    response: Response,
    category: str | None = None,
    venue: str | None = Query(default=None, pattern="^(kalshi|polymarket)$"),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[RankedDiscoveryMarket]:
    """Rank open markets by relevance; the score is not a forecast or expected return."""
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=30"
    now = datetime.now(timezone.utc)
    items = [item for item in core._DISCOVERY if _is_open(item, now=now)]
    if category:
        items = [item for item in items if (item.category or "").casefold() == category.casefold()]
    if venue:
        items = [item for item in items if item.venue == venue]
    if q:
        needle = q.casefold().strip()
        items = [item for item in items if needle in item.title.casefold()]

    ranked = [_ranked_market(item, now=now) for item in items]
    ranked.sort(key=lambda item: (item.relevance_score, item.trend_score), reverse=True)

    deduplicated: list[RankedDiscoveryMarket] = []
    seen: set[tuple[str, str]] = set()
    for item in ranked:
        identity = (" ".join(item.title.casefold().split()), item.closes_at.isoformat() if item.closes_at else "")
        if identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(item)

    return deduplicated[:limit]
