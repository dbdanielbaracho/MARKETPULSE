from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

import app.main as core
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.adapters.trades import KalshiTradesAdapter, PolymarketTradesAdapter
from app.services.execution_quality import execution_quality, kalshi_levels, polymarket_levels
from app.services.intelligence import attention_score, breaking_signal, consensus, market_quality
from app.services.large_trades import detect_large_trades, normalize_kalshi_trade, normalize_polymarket_trade
from app.storage.api_keys import ApiPrincipal
from app.storage.snapshots import SnapshotStore


router = APIRouter(prefix="/api/v1/commercial/intelligence", tags=["commercial-intelligence"])


class QualityView(BaseModel):
    score: int
    grade: str
    reasons: list[str]


class BreakingView(BaseModel):
    active: bool
    score: float
    probability_points: float
    volume_change_percent: float | None
    reasons: list[str]


class IntelligenceMarketView(BaseModel):
    market_id: str
    venue: str
    generated_at: datetime
    attention_score: int
    market_quality: QualityView
    breaking_signal: BreakingView
    disclaimer: str


class ConsensusView(BaseModel):
    left_id: str
    right_id: str
    equivalent_contracts: bool
    decision: str
    probability: float | None
    gap_points: float | None
    agreement: str | None
    reasons: list[str]
    disclaimer: str


class ExecutionView(BaseModel):
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
    disclaimer: str


class LargeTradeView(BaseModel):
    venue: str
    market_id: str
    occurred_at: datetime
    notional_usd: float
    price: float
    size: float
    side: str | None
    outcome: str | None
    actor_id: str | None
    severity: str
    multiple_of_median: float | None
    reasons: list[str]


class LargeTradesResponse(BaseModel):
    market_id: str
    generated_at: datetime
    sample_size: int
    signals: list[LargeTradeView]
    disclaimer: str


def _principal(
    response: Response,
    principal: ApiPrincipal = Depends(core._commercial_markets_key),
) -> ApiPrincipal:
    response.headers["Cache-Control"] = "no-store"
    return principal


def _market(market_id: str):
    return core._market_by_id(market_id)


def _hours_to_close(market) -> float | None:
    if market.closes_at is None:
        return None
    return (market.closes_at - datetime.now(timezone.utc)).total_seconds() / 3600


@router.get("/market", response_model=IntelligenceMarketView)
def commercial_market_intelligence(
    market_id: str = Query(min_length=1, max_length=200),
    principal: ApiPrincipal = Depends(_principal),
) -> IntelligenceMarketView:
    del principal
    market = _market(market_id)
    history = SnapshotStore(core._database_path()).history(market_id, hours=24, limit=500)
    quality = market_quality(
        probability=market.probability,
        volume_usd=market.volume_usd,
        observed_at=market.observed_at,
        closes_at=market.closes_at,
        source_url=market.source_url,
        history_count=len(history),
    )
    breaking = breaking_signal(history)
    attention = attention_score(
        trend_score_value=market.trend_score,
        probability_change_value=market.probability_change,
        volume_usd=market.volume_usd,
        hours_to_close=_hours_to_close(market),
    )
    return IntelligenceMarketView(
        market_id=market_id,
        venue=market.venue,
        generated_at=datetime.now(timezone.utc),
        attention_score=attention,
        market_quality=QualityView(score=quality.score, grade=quality.grade, reasons=list(quality.reasons)),
        breaking_signal=BreakingView(
            active=breaking.active,
            score=breaking.score,
            probability_points=breaking.probability_points,
            volume_change_percent=breaking.volume_change_percent,
            reasons=list(breaking.reasons),
        ),
        disclaimer="Attention, quality and breaking scores describe observed market data; they are not forecasts or trading advice.",
    )


@router.get("/compare", response_model=ConsensusView)
def commercial_verified_consensus(
    left_id: str = Query(min_length=1, max_length=200),
    right_id: str = Query(min_length=1, max_length=200),
    principal: ApiPrincipal = Depends(_principal),
) -> ConsensusView:
    del principal
    comparison = core.compare_markets(left_id=left_id, right_id=right_id)
    left = _market(left_id)
    right = _market(right_id)
    result = None
    if comparison.equivalent_contracts and left.probability is not None and right.probability is not None:
        result = consensus(left.probability, right.probability, equivalent_contracts=True)
    return ConsensusView(
        left_id=left_id,
        right_id=right_id,
        equivalent_contracts=comparison.equivalent_contracts,
        decision=comparison.decision,
        probability=result.probability if result else None,
        gap_points=result.gap_points if result else None,
        agreement=result.agreement if result else None,
        reasons=list(comparison.reasons),
        disclaimer="Consensus is returned only after the contract-equivalence gate passes; it is not a statistical forecast.",
    )


async def _polymarket_raw(market) -> dict:
    market_id = market.canonical_id.split(":", 1)[1]
    adapter = PolymarketAdapter(
        os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com"),
        clob_base_url=os.getenv("MP_POLYMARKET_CLOB_BASE_URL", "https://clob.polymarket.com"),
    )
    return await adapter.fetch_market(market_id)


@router.get("/execution", response_model=ExecutionView)
async def commercial_execution_quality(
    market_id: str = Query(min_length=1, max_length=200),
    principal: ApiPrincipal = Depends(_principal),
) -> ExecutionView:
    del principal
    market = _market(market_id)
    try:
        if market.venue == "kalshi":
            ticker = market.canonical_id.split(":", 1)[1]
            adapter = KalshiAdapter(os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2"))
            payload = await adapter.fetch_orderbook(ticker, depth=20)
            bids, asks = kalshi_levels(payload)
        else:
            raw = await _polymarket_raw(market)
            adapter = PolymarketAdapter(
                os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com"),
                clob_base_url=os.getenv("MP_POLYMARKET_CLOB_BASE_URL", "https://clob.polymarket.com"),
            )
            token_id = adapter.yes_token_id(raw)
            if not token_id:
                return ExecutionView(
                    market_id=market_id,
                    venue=market.venue,
                    generated_at=datetime.now(timezone.utc),
                    available=False,
                    reasons=["YES outcome token is unavailable from the current venue metadata"],
                    disclaimer="Execution Quality describes visible spread and depth only; it is not a fill or liquidity guarantee.",
                )
            payload = await adapter.fetch_orderbook(token_id)
            bids, asks = polymarket_levels(payload)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"execution data unavailable: {type(exc).__name__}") from exc

    quality = execution_quality(bids, asks)
    return ExecutionView(
        market_id=market_id,
        venue=market.venue,
        generated_at=datetime.now(timezone.utc),
        available=quality.two_sided,
        best_bid=quality.best_bid,
        best_ask=quality.best_ask,
        midpoint=quality.midpoint,
        spread_points=quality.spread_points,
        bid_depth_units=quality.bid_depth_units,
        ask_depth_units=quality.ask_depth_units,
        score=quality.score,
        grade=quality.grade,
        reasons=list(quality.reasons),
        disclaimer="Execution Quality describes visible spread and displayed depth only; it is not a fill, liquidity, profitability, or best-execution guarantee.",
    )


@router.get("/large-trades", response_model=LargeTradesResponse)
async def commercial_large_trades(
    market_id: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    principal: ApiPrincipal = Depends(_principal),
) -> LargeTradesResponse:
    del principal
    market = _market(market_id)
    normalized = []
    try:
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
        else:
            raw_market = await _polymarket_raw(market)
            condition_id = str(raw_market.get("conditionId") or raw_market.get("condition_id") or "")
            if not condition_id:
                return LargeTradesResponse(
                    market_id=market_id,
                    generated_at=datetime.now(timezone.utc),
                    sample_size=0,
                    signals=[],
                    disclaimer="No condition id is available for a public trade-history lookup.",
                )
            raw_trades = await PolymarketTradesAdapter(
                os.getenv("MP_POLYMARKET_DATA_BASE_URL", "https://data-api.polymarket.com")
            ).fetch_trades(condition_id=condition_id, limit=200)
            for item in raw_trades:
                try:
                    normalized.append(normalize_polymarket_trade(item))
                except (TypeError, ValueError):
                    continue
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"trade data unavailable: {type(exc).__name__}") from exc

    signals = detect_large_trades(normalized, limit=limit)
    return LargeTradesResponse(
        market_id=market_id,
        generated_at=datetime.now(timezone.utc),
        sample_size=len(normalized),
        signals=[
            LargeTradeView(
                venue=signal.trade.venue,
                market_id=signal.trade.market_id,
                occurred_at=signal.trade.occurred_at,
                notional_usd=signal.trade.notional_usd,
                price=signal.trade.price,
                size=signal.trade.size,
                side=signal.trade.side,
                outcome=signal.trade.outcome,
                actor_id=signal.trade.actor_id,
                severity=signal.severity,
                multiple_of_median=signal.multiple_of_median,
                reasons=list(signal.reasons),
            )
            for signal in signals
        ],
        disclaimer="Large-trade signals identify unusual observed trade size only; they do not imply insider knowledge, manipulation, intent, profitability, or future direction.",
    )
