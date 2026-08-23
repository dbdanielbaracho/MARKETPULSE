from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

import app.main as core
from app.routes.public_execution_quality import PublicExecutionQualityView, public_execution_quality
from app.routes.public_market_comparison import market_cross_platform


router = APIRouter(prefix="/api/v1", tags=["public-venue-conditions"])


class VenueConditionView(BaseModel):
    market_id: str
    venue: str
    probability: float | None
    reported_volume_usd: float | None
    execution_available: bool
    best_bid: float | None = None
    best_ask: float | None = None
    midpoint: float | None = None
    spread_points: float | None = None
    bid_depth_units: float | None = None
    ask_depth_units: float | None = None
    execution_score: int | None = None
    execution_grade: str | None = None


class VerifiedVenueConditionsView(BaseModel):
    market_id: str
    generated_at: datetime
    equivalent_contracts: bool
    verification_confidence: int | None
    available: bool
    venues: list[VenueConditionView]
    reasons: list[str]
    disclaimer: str


async def _safe_execution(market_id: str) -> PublicExecutionQualityView | None:
    try:
        return await public_execution_quality(Response(), market_id=market_id)
    except HTTPException as exc:
        if exc.status_code == 503:
            return None
        raise


def _condition(market, execution: PublicExecutionQualityView | None) -> VenueConditionView:
    return VenueConditionView(
        market_id=market.canonical_id,
        venue=market.venue,
        probability=market.probability,
        reported_volume_usd=market.volume_usd,
        execution_available=bool(execution and execution.available),
        best_bid=execution.best_bid if execution else None,
        best_ask=execution.best_ask if execution else None,
        midpoint=execution.midpoint if execution else None,
        spread_points=execution.spread_points if execution else None,
        bid_depth_units=execution.bid_depth_units if execution else None,
        ask_depth_units=execution.ask_depth_units if execution else None,
        execution_score=execution.score if execution else None,
        execution_grade=execution.grade if execution else None,
    )


@router.get("/market/venue-conditions", response_model=VerifiedVenueConditionsView)
async def verified_venue_conditions(
    response: Response,
    market_id: str = Query(min_length=1, max_length=200),
) -> VerifiedVenueConditionsView:
    """Compare observable venue conditions only after contract equivalence is verified."""
    response.headers["Cache-Control"] = "public, max-age=10, stale-while-revalidate=20"
    target = core._market_by_id(market_id)
    try:
        cross = await market_cross_platform(Response(), market_id=market_id, candidate_limit=3)
    except HTTPException as exc:
        if exc.status_code == 503:
            return VerifiedVenueConditionsView(
                market_id=market_id,
                generated_at=datetime.now(timezone.utc),
                equivalent_contracts=False,
                verification_confidence=None,
                available=False,
                venues=[],
                reasons=["cross-platform verification metadata is temporarily unavailable"],
                disclaimer="PrediBeacon does not compare venue conditions without verified equivalent contracts.",
            )
        raise

    verification = cross.verification
    if cross.counterpart is None or verification is None or not verification.equivalent_contracts:
        return VerifiedVenueConditionsView(
            market_id=market_id,
            generated_at=datetime.now(timezone.utc),
            equivalent_contracts=False,
            verification_confidence=verification.confidence if verification else None,
            available=False,
            venues=[],
            reasons=(list(verification.reasons) if verification else ["no verified equivalent cross-platform counterpart is available"]),
            disclaimer="PrediBeacon does not compare venue conditions without verified equivalent contracts.",
        )

    counterpart = cross.counterpart
    target_execution, counterpart_execution = await asyncio.gather(
        _safe_execution(target.canonical_id),
        _safe_execution(counterpart.canonical_id),
    )
    venues = [_condition(target, target_execution), _condition(counterpart, counterpart_execution)]
    venues.sort(key=lambda item: item.venue)
    return VerifiedVenueConditionsView(
        market_id=market_id,
        generated_at=datetime.now(timezone.utc),
        equivalent_contracts=True,
        verification_confidence=verification.confidence,
        available=any(item.execution_available for item in venues),
        venues=venues,
        reasons=["contract equivalence verified before venue-condition comparison"],
        disclaimer=(
            "Venue Conditions compares observed probability, reported volume, visible spread and displayed depth for "
            "verified equivalent contracts. It does not rank a best venue and does not include every fee, settlement "
            "difference, slippage, fill probability or other trading friction."
        ),
    )
