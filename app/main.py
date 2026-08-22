from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.config.runtime import RuntimeFlags
from app.services.ingestion import IngestionWorker, RefreshBatch
from app.storage.snapshots import SnapshotStore

APP_VERSION = "0.3.1"


class DiscoveryMarket(BaseModel):
    canonical_id: str
    title: str
    venue: Literal["kalshi", "polymarket"]
    category: str | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    probability_change: float | None = None
    volume_usd: float | None = Field(default=None, ge=0)
    trend_score: float = Field(ge=0, le=100)
    observed_at: datetime


_DISCOVERY: list[DiscoveryMarket] = []
_LAST_REFRESH_AT: datetime | None = None
_LAST_REFRESH_ERRORS: tuple[str, ...] = ()


def set_discovery_markets(markets: list[DiscoveryMarket]) -> None:
    """Replace the current read model atomically at process level."""
    global _DISCOVERY
    _DISCOVERY = list(markets)


def publish_refresh_batch(batch: RefreshBatch) -> None:
    """Publish a complete successful/partial batch without erasing good data on total failure."""
    global _LAST_REFRESH_AT, _LAST_REFRESH_ERRORS
    _LAST_REFRESH_AT = datetime.now(timezone.utc)
    _LAST_REFRESH_ERRORS = batch.errors
    if not batch.markets:
        return
    signal_by_id = {item.canonical_id: item for item in batch.signals}
    items = []
    for market in batch.markets:
        item = signal_by_id[market.canonical_id]
        items.append(
            DiscoveryMarket(
                canonical_id=market.canonical_id,
                title=market.title,
                venue=market.venue,
                category=market.category,
                probability=item.probability,
                probability_change=item.probability_change,
                volume_usd=item.volume_usd,
                trend_score=item.trend_score,
                observed_at=market.observed_at,
            )
        )
    set_discovery_markets(items)


def _refresh_interval() -> float:
    raw = os.getenv("MP_REFRESH_INTERVAL_SECONDS", "300")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("MP_REFRESH_INTERVAL_SECONDS must be numeric") from exc
    if value < 30 or value > 86_400:
        raise ValueError("MP_REFRESH_INTERVAL_SECONDS must be between 30 and 86400")
    return value


@asynccontextmanager
async def lifespan(_: FastAPI):
    flags = RuntimeFlags.from_env()
    store = SnapshotStore(os.getenv("MP_DATABASE_PATH", "/tmp/marketpulse.db"))
    worker = IngestionWorker(
        store=store,
        flags=flags,
        kalshi=KalshiAdapter(os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")),
        polymarket=PolymarketAdapter(os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")),
    )
    stop = asyncio.Event()
    task = asyncio.create_task(
        worker.run_forever(
            interval_seconds=_refresh_interval(),
            publish=publish_refresh_batch,
            stop=stop,
        ),
        name="marketpulse-ingestion",
    )
    try:
        yield
    finally:
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=3)
        except TimeoutError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="MarketPulse", version=APP_VERSION, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Deterministic readiness endpoint: never depends on external venues."""
    return {"status": "ok", "service": "marketpulse-web", "version": APP_VERSION}


@app.get("/api/v1/status")
def status() -> dict[str, object]:
    venue_counts = {
        venue: sum(1 for item in _DISCOVERY if item.venue == venue)
        for venue in ("kalshi", "polymarket")
    }
    return {
        "service": "marketpulse-web",
        "version": APP_VERSION,
        "country": "US",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_refresh_at": _LAST_REFRESH_AT.isoformat() if _LAST_REFRESH_AT else None,
        "last_refresh_errors": ",".join(_LAST_REFRESH_ERRORS) or None,
        "venue_market_counts": venue_counts,
    }


@app.get("/api/v1/markets", response_model=list[DiscoveryMarket])
def markets(
    sort: Literal["trending", "movers", "volume"] = "trending",
    category: str | None = None,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DiscoveryMarket]:
    items = _DISCOVERY
    if category:
        items = [item for item in items if (item.category or "").casefold() == category.casefold()]
    if q:
        needle = q.casefold().strip()
        items = [item for item in items if needle in item.title.casefold()]
    if sort == "movers":
        key = lambda item: abs(item.probability_change or 0.0)
    elif sort == "volume":
        key = lambda item: item.volume_usd or 0.0
    else:
        key = lambda item: item.trend_score
    return sorted(items, key=key, reverse=True)[:limit]


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    template = Path(__file__).parent / "templates" / "index.html"
    return template.read_text(encoding="utf-8")
