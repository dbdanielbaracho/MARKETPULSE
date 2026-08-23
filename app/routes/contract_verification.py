from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

import app.main as core
from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.services.contract_verification import (
    VenueContractFacts,
    kalshi_contract_facts,
    polymarket_contract_facts,
    verify_contracts,
)
from app.services.intelligence import consensus
from app.storage.api_keys import ApiPrincipal


router = APIRouter(prefix="/api/v1/commercial/intelligence", tags=["contract-verification"])


class VerifiedCompareView(BaseModel):
    left_id: str
    right_id: str
    generated_at: datetime
    decision: str
    equivalent_contracts: bool
    confidence: int
    question_similarity: float
    rules_similarity: float | None
    source_match: bool | None
    deadline_delta_hours: float | None
    consensus_probability: float | None
    gap_points: float | None
    agreement: str | None
    reasons: list[str]
    disclaimer: str


def _principal(
    response: Response,
    principal: ApiPrincipal = Depends(core._commercial_markets_key),
) -> ApiPrincipal:
    response.headers["Cache-Control"] = "no-store"
    return principal


async def _facts(market) -> VenueContractFacts:
    venue_id = market.canonical_id.split(":", 1)[1]
    if market.venue == "kalshi":
        adapter = KalshiAdapter(os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2"))
        raw = await adapter.fetch_market(venue_id)
        return kalshi_contract_facts(market.canonical_id, raw)
    adapter = PolymarketAdapter(os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com"))
    raw = await adapter.fetch_market(venue_id)
    return polymarket_contract_facts(market.canonical_id, raw)


@router.get("/verified-compare", response_model=VerifiedCompareView)
async def verified_compare(
    left_id: str = Query(min_length=1, max_length=200),
    right_id: str = Query(min_length=1, max_length=200),
    principal: ApiPrincipal = Depends(_principal),
) -> VerifiedCompareView:
    del principal
    left = core._market_by_id(left_id)
    right = core._market_by_id(right_id)

    if left_id == right_id:
        left_facts = VenueContractFacts(
            left_id, left.venue, left.title, left.closes_at, None, None
        )
        result = verify_contracts(left_facts, left_facts)
    else:
        try:
            left_facts, right_facts = await _facts(left), await _facts(right)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"contract verification data unavailable: {type(exc).__name__}") from exc
        result = verify_contracts(left_facts, right_facts)

    market_consensus = None
    if result.equivalent_contracts and left.probability is not None and right.probability is not None:
        market_consensus = consensus(left.probability, right.probability, equivalent_contracts=True)

    return VerifiedCompareView(
        left_id=left_id,
        right_id=right_id,
        generated_at=datetime.now(timezone.utc),
        decision=result.decision,
        equivalent_contracts=result.equivalent_contracts,
        confidence=result.confidence,
        question_similarity=result.question_similarity,
        rules_similarity=result.rules_similarity,
        source_match=result.source_match,
        deadline_delta_hours=result.deadline_delta_hours,
        consensus_probability=market_consensus.probability if market_consensus else None,
        gap_points=market_consensus.gap_points if market_consensus else None,
        agreement=market_consensus.agreement if market_consensus else None,
        reasons=list(result.reasons),
        disclaimer=(
            "Verified equivalence requires compatible question meaning, timing and resolution evidence. "
            "Similar titles alone never qualify. Consensus is market aggregation, not a forecast."
        ),
    )
