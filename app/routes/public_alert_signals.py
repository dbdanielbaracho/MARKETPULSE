from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

import app.main as core
from app.routes.public_execution_quality import PublicExecutionQualityView, public_execution_quality
from app.routes.public_market_comparison import MarketCrossPlatformView, market_cross_platform
from app.routes.public_trade_activity import PublicLargeTradeActivityView, public_large_trade_activity
from app.services.intelligence import breaking_signal
from app.storage.snapshots import SnapshotStore


router = APIRouter(prefix="/api/v1", tags=["public-alert-signals"])


class BreakingAlertView(BaseModel):
    available: bool
    active: bool
    score: float | None = None
    probability_points: float | None = None
    volume_change_percent: float | None = None
    reasons: list[str]


class ExecutionAlertView(BaseModel):
    available: bool
    score: int | None = None
    grade: str | None = None
    spread_points: float | None = None


class LargeTradeAlertView(BaseModel):
    available: bool
    signal_count: int
    largest_notional_usd: float | None = None
    latest_signal_key: str | None = None


class CrossPlatformAlertView(BaseModel):
    available: bool
    equivalent_contracts: bool
    confidence: int | None = None
    gap_points: float | None = None
    counterpart_id: str | None = None


class MarketAlertSnapshot(BaseModel):
    market_id: str
    generated_at: datetime
    probability: float | None
    probability_change: float | None
    breaking: BreakingAlertView
    execution: ExecutionAlertView
    large_trade_activity: LargeTradeAlertView
    cross_platform: CrossPlatformAlertView
    disclaimer: str


async def _safe_execution(market_id: str) -> PublicExecutionQualityView | None:
    try:
        return await public_execution_quality(Response(), market_id=market_id)
    except HTTPException as exc:
        if exc.status_code == 503:
            return None
        raise


async def _safe_trade_activity(market_id: str) -> PublicLargeTradeActivityView | None:
    try:
        return await public_large_trade_activity(Response(), market_id=market_id, limit=5)
    except HTTPException as exc:
        if exc.status_code == 503:
            return None
        raise


async def _safe_cross_platform(market_id: str) -> MarketCrossPlatformView | None:
    try:
        return await market_cross_platform(Response(), market_id=market_id, candidate_limit=3)
    except HTTPException as exc:
        if exc.status_code == 503:
            return None
        raise


@router.get("/market/alert-signals", response_model=MarketAlertSnapshot)
async def market_alert_signals(
    response: Response,
    market_id: str = Query(min_length=1, max_length=200),
) -> MarketAlertSnapshot:
    """Aggregate bounded, observable signals for browser-side alert transitions."""
    response.headers["Cache-Control"] = "private, max-age=10"
    market = core._market_by_id(market_id)
    history = SnapshotStore(core._database_path()).history(market_id, hours=24, limit=500)
    breaking = breaking_signal(history)

    execution, activity, cross = await asyncio.gather(
        _safe_execution(market_id),
        _safe_trade_activity(market_id),
        _safe_cross_platform(market_id),
    )

    latest_key = None
    largest = None
    if activity and activity.signals:
        largest_signal = max(activity.signals, key=lambda signal: signal.notional_usd)
        largest = largest_signal.notional_usd
        latest_signal = max(activity.signals, key=lambda signal: signal.occurred_at)
        latest_key = f"{latest_signal.occurred_at.isoformat()}:{latest_signal.notional_usd:.4f}"

    verified = bool(cross and cross.verification and cross.verification.equivalent_contracts)
    return MarketAlertSnapshot(
        market_id=market_id,
        generated_at=datetime.now(timezone.utc),
        probability=market.probability,
        probability_change=market.probability_change,
        breaking=BreakingAlertView(
            available=len(history) >= 2,
            active=breaking.active,
            score=breaking.score if len(history) >= 2 else None,
            probability_points=breaking.probability_points if len(history) >= 2 else None,
            volume_change_percent=breaking.volume_change_percent if len(history) >= 2 else None,
            reasons=list(breaking.reasons),
        ),
        execution=ExecutionAlertView(
            available=bool(execution and execution.available),
            score=execution.score if execution else None,
            grade=execution.grade if execution else None,
            spread_points=execution.spread_points if execution else None,
        ),
        large_trade_activity=LargeTradeAlertView(
            available=activity is not None and activity.sample_size > 0,
            signal_count=activity.signal_count if activity else 0,
            largest_notional_usd=largest,
            latest_signal_key=latest_key,
        ),
        cross_platform=CrossPlatformAlertView(
            available=cross is not None and cross.counterpart is not None,
            equivalent_contracts=verified,
            confidence=cross.verification.confidence if cross and cross.verification else None,
            gap_points=cross.verification.gap_points if verified and cross and cross.verification else None,
            counterpart_id=cross.counterpart.canonical_id if cross and cross.counterpart else None,
        ),
        disclaimer=(
            "Alert signals report observable market conditions only. Missing data never triggers a signal, and no alert "
            "is a forecast, trading recommendation, fill guarantee, insider indicator or claim of causation."
        ),
    )
