from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

import app.main as core
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.services.execution_quality import execution_quality, kalshi_levels, polymarket_levels


router = APIRouter(prefix="/api/v1", tags=["public-execution-quality"])
_CACHE_TTL_SECONDS = 20
_CACHE_MAX_ITEMS = 500
_CACHE_LOCK = asyncio.Lock()


class PublicExecutionQualityView(BaseModel):
    market_id: str
    venue: str
    generated_at: datetime
    available: bool
    best_bid: float | None = None
    best_ask: float | None = None
    midpoint: float | None = None
    spread_points: float | None = None
    bid_depth_units: float | None = None
    ask_depth_units: float | None = None
    score: int | None = None
    grade: str | None = None
    reasons: list[str]
    cache_ttl_seconds: int
    disclaimer: str


@dataclass(frozen=True)
class _CachedExecution:
    expires_at: float
    value: PublicExecutionQualityView


_CACHE: dict[str, _CachedExecution] = {}


def _prune(now: float) -> None:
    for key in [key for key, item in _CACHE.items() if item.expires_at <= now]:
        _CACHE.pop(key, None)
    if len(_CACHE) > _CACHE_MAX_ITEMS:
        oldest = sorted(_CACHE.items(), key=lambda item: item[1].expires_at)
        for key, _ in oldest[: len(_CACHE) - _CACHE_MAX_ITEMS]:
            _CACHE.pop(key, None)


def _view(market, quality, *, reasons: list[str] | None = None) -> PublicExecutionQualityView:
    return PublicExecutionQualityView(
        market_id=market.canonical_id,
        venue=market.venue,
        generated_at=datetime.now(timezone.utc),
        available=quality.two_sided if quality is not None else False,
        best_bid=quality.best_bid if quality is not None else None,
        best_ask=quality.best_ask if quality is not None else None,
        midpoint=quality.midpoint if quality is not None else None,
        spread_points=quality.spread_points if quality is not None else None,
        bid_depth_units=quality.bid_depth_units if quality is not None else None,
        ask_depth_units=quality.ask_depth_units if quality is not None else None,
        score=quality.score if quality is not None else None,
        grade=quality.grade if quality is not None else None,
        reasons=reasons if reasons is not None else list(quality.reasons),
        cache_ttl_seconds=_CACHE_TTL_SECONDS,
        disclaimer=(
            "Execution Quality describes the currently displayed order book only. It is not a fill, liquidity, "
            "profitability, fee-adjusted, or best-execution guarantee, and the book may change before an order is placed."
        ),
    )


async def _load(market) -> PublicExecutionQualityView:
    if market.venue == "kalshi":
        ticker = market.canonical_id.split(":", 1)[1]
        adapter = KalshiAdapter(os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2"))
        payload = await adapter.fetch_orderbook(ticker, depth=20)
        bids, asks = kalshi_levels(payload)
    elif market.venue == "polymarket":
        venue_id = market.canonical_id.split(":", 1)[1]
        adapter = PolymarketAdapter(
            os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com"),
            clob_base_url=os.getenv("MP_POLYMARKET_CLOB_BASE_URL", "https://clob.polymarket.com"),
        )
        raw = await adapter.fetch_market(venue_id)
        token_id = adapter.yes_token_id(raw)
        if not token_id:
            return _view(market, None, reasons=["YES outcome token is unavailable from current venue metadata"])
        payload = await adapter.fetch_orderbook(token_id)
        bids, asks = polymarket_levels(payload)
    else:
        return _view(market, None, reasons=["execution-quality adapter is unavailable for this venue"])

    return _view(market, execution_quality(bids, asks))


@router.get("/market/execution-quality", response_model=PublicExecutionQualityView)
async def public_execution_quality(
    response: Response,
    market_id: str = Query(min_length=1, max_length=200),
) -> PublicExecutionQualityView:
    """Return a short-lived, read-only description of visible execution conditions."""
    response.headers["Cache-Control"] = "public, max-age=10, stale-while-revalidate=10"
    market = core._market_by_id(market_id)
    now = time.monotonic()
    cached = _CACHE.get(market_id)
    if cached and cached.expires_at > now:
        return cached.value

    async with _CACHE_LOCK:
        now = time.monotonic()
        cached = _CACHE.get(market_id)
        if cached and cached.expires_at > now:
            return cached.value
        try:
            value = await _load(market)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"execution data unavailable: {type(exc).__name__}") from exc
        _CACHE[market_id] = _CachedExecution(now + _CACHE_TTL_SECONDS, value)
        _prune(now)
        return value
