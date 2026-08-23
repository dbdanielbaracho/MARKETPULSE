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
from app.adapters.polymarket import PolymarketAdapter
from app.adapters.trades import KalshiTradesAdapter, PolymarketTradesAdapter
from app.services.large_trades import detect_large_trades, normalize_kalshi_trade, normalize_polymarket_trade


router = APIRouter(prefix="/api/v1", tags=["public-trade-activity"])
_CACHE_TTL_SECONDS = 30
_CACHE_MAX_ITEMS = 500
_CACHE_LOCK = asyncio.Lock()


class PublicLargeTradeSignal(BaseModel):
    occurred_at: datetime
    notional_usd: float
    price: float
    size: float
    side: str | None
    outcome: str | None
    severity: str
    multiple_of_median: float | None
    reasons: list[str]


class PublicLargeTradeActivityView(BaseModel):
    market_id: str
    venue: str
    generated_at: datetime
    sample_size: int
    signal_count: int
    sample_median_usd: float | None
    signals: list[PublicLargeTradeSignal]
    cache_ttl_seconds: int
    disclaimer: str


@dataclass(frozen=True)
class _CachedActivity:
    expires_at: float
    value: PublicLargeTradeActivityView


_CACHE: dict[str, _CachedActivity] = {}


def _prune(now: float) -> None:
    for key in [key for key, item in _CACHE.items() if item.expires_at <= now]:
        _CACHE.pop(key, None)
    if len(_CACHE) > _CACHE_MAX_ITEMS:
        oldest = sorted(_CACHE.items(), key=lambda item: item[1].expires_at)
        for key, _ in oldest[: len(_CACHE) - _CACHE_MAX_ITEMS]:
            _CACHE.pop(key, None)


def _response(market, normalized, *, limit: int) -> PublicLargeTradeActivityView:
    signals = detect_large_trades(normalized, limit=limit)
    public_signals = [
        PublicLargeTradeSignal(
            occurred_at=signal.trade.occurred_at,
            notional_usd=signal.trade.notional_usd,
            price=signal.trade.price,
            size=signal.trade.size,
            side=signal.trade.side,
            outcome=signal.trade.outcome,
            severity=signal.severity,
            multiple_of_median=signal.multiple_of_median,
            reasons=[reason for reason in signal.reasons if "wallet identifier" not in reason and "identify the trader" not in reason],
        )
        for signal in signals
    ]
    median_value = signals[0].sample_median_usd if signals else None
    return PublicLargeTradeActivityView(
        market_id=market.canonical_id,
        venue=market.venue,
        generated_at=datetime.now(timezone.utc),
        sample_size=len(normalized),
        signal_count=len(public_signals),
        sample_median_usd=median_value,
        signals=public_signals,
        cache_ttl_seconds=_CACHE_TTL_SECONDS,
        disclaimer=(
            "Large Trade Activity identifies unusually large observed trades relative to a recent public sample. "
            "It does not imply insider knowledge, manipulation, trader identity, profitability, causation or future direction."
        ),
    )


async def _load(market, *, limit: int) -> PublicLargeTradeActivityView:
    normalized = []
    if market.venue == "kalshi":
        ticker = market.canonical_id.split(":", 1)[1]
        raw_trades = await KalshiTradesAdapter(
            os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")
        ).fetch_trades(ticker=ticker, limit=200)
        for item in raw_trades:
            try:
                normalized.append(normalize_kalshi_trade(item))
            except (TypeError, ValueError):
                continue
    elif market.venue == "polymarket":
        venue_id = market.canonical_id.split(":", 1)[1]
        raw_market = await PolymarketAdapter(
            os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")
        ).fetch_market(venue_id)
        condition_id = str(raw_market.get("conditionId") or raw_market.get("condition_id") or "")
        if not condition_id:
            return _response(market, [], limit=limit)
        raw_trades = await PolymarketTradesAdapter(
            os.getenv("MP_POLYMARKET_DATA_BASE_URL", "https://data-api.polymarket.com")
        ).fetch_trades(condition_id=condition_id, limit=200)
        for item in raw_trades:
            try:
                normalized.append(normalize_polymarket_trade(item))
            except (TypeError, ValueError):
                continue
    return _response(market, normalized, limit=limit)


@router.get("/market/large-trade-activity", response_model=PublicLargeTradeActivityView)
async def public_large_trade_activity(
    response: Response,
    market_id: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=5, ge=1, le=10),
) -> PublicLargeTradeActivityView:
    response.headers["Cache-Control"] = "public, max-age=15, stale-while-revalidate=15"
    market = core._market_by_id(market_id)
    cache_key = f"{market_id}:{limit}"
    now = time.monotonic()
    cached = _CACHE.get(cache_key)
    if cached and cached.expires_at > now:
        return cached.value

    async with _CACHE_LOCK:
        now = time.monotonic()
        cached = _CACHE.get(cache_key)
        if cached and cached.expires_at > now:
            return cached.value
        try:
            value = await _load(market, limit=limit)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"trade activity unavailable: {type(exc).__name__}") from exc
        _CACHE[cache_key] = _CachedActivity(now + _CACHE_TTL_SECONDS, value)
        _prune(now)
        return value
