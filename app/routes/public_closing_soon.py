from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app import main as main_app
from app.main import DiscoveryMarket

router = APIRouter()


@router.get("/api/v1/markets/closing-soon", response_model=list[DiscoveryMarket])
def closing_soon_markets(
    venue: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DiscoveryMarket]:
    """Return open markets with known deadlines, nearest close first.

    Unknown/closed deadlines are excluded so the UI never implies urgency where
    we do not have evidence for it. The discovery list is read dynamically so
    ingestion refreshes are reflected immediately.
    """
    now = datetime.now(timezone.utc)
    items = [
        item
        for item in main_app._DISCOVERY
        if item.closes_at is not None and item.closes_at > now
    ]
    if venue in {"kalshi", "polymarket"}:
        items = [item for item in items if item.venue == venue]
    items.sort(key=lambda item: item.closes_at)
    return items[:limit]
