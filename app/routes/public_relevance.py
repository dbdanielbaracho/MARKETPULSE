from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Response

import app.main as core
from app.middleware.home_client_dedup import MIN_HOMEPAGE_VOLUME_USD
from app.middleware.home_event_grouping import _family_title
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


def _is_homepage_quality_market(market: core.DiscoveryMarket, *, now: datetime) -> bool:
    """Fail closed for the homepage discovery feed.

    A market can be a valid provider contract and still be unsuitable for the
    homepage. The public relevant feed must not expose materially thin/unknown
    activity, zero attention, or contracts that are effectively closing now.
    """
    if market.volume_usd is None or market.volume_usd < MIN_HOMEPAGE_VOLUME_USD:
        return False
    if market.trend_score <= 0:
        return False
    if market.closes_at is not None and market.closes_at <= now + timedelta(hours=1):
        return False
    return True


@router.get("/markets/relevant", response_model=list[RankedDiscoveryMarket])
def relevant_markets(
    response: Response,
    category: str | None = None,
    venue: str | None = Query(default=None, pattern="^(kalshi|polymarket)$"),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[RankedDiscoveryMarket]:
    """Rank homepage-quality markets by relevance; the score is not a forecast or expected return."""
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=30"
    now = datetime.now(timezone.utc)
    items = [item for item in core._DISCOVERY if _is_homepage_quality_market(item, now=now)]
    if category:
        items = [item for item in items if (item.category or "").casefold() == category.casefold()]
    if venue:
        items = [item for item in items if item.venue == venue]
    if q:
        needle = q.casefold().strip()
        items = [item for item in items if needle in item.title.casefold()]

    ranked = [_ranked_market(item, now=now) for item in items]
    ranked = [item for item in ranked if item.relevance_score > 0]
    ranked.sort(key=lambda item: (item.relevance_score, item.trend_score), reverse=True)

    deduplicated: list[RankedDiscoveryMarket] = []
    seen_exact: set[tuple[str, str]] = set()
    seen_family: set[tuple[str, str]] = set()
    for item in ranked:
        normalized = " ".join(item.title.casefold().split())
        exact = (item.venue, normalized)
        family = (item.venue, _family_title(item.title))
        if exact in seen_exact or family in seen_family:
            continue
        seen_exact.add(exact)
        seen_family.add(family)
        deduplicated.append(item)

    return deduplicated[:limit]
