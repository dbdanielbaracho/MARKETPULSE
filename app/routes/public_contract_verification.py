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
from app.services.contract_verification import (
    VenueContractFacts,
    kalshi_contract_facts,
    polymarket_contract_facts,
    verify_contracts,
)
from app.services.intelligence import consensus


router = APIRouter(prefix="/api/v1", tags=["public-contract-verification"])
_CACHE_TTL_SECONDS = 300
_CACHE_MAX_ITEMS = 500
_CACHE_LOCK = asyncio.Lock()


@dataclass(frozen=True)
class _CachedFacts:
    expires_at: float
    facts: VenueContractFacts


_FACT_CACHE: dict[str, _CachedFacts] = {}


class PublicVerifiedCompareView(BaseModel):
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
    cache_ttl_seconds: int
    disclaimer: str


def _prune_cache(now: float) -> None:
    expired = [key for key, item in _FACT_CACHE.items() if item.expires_at <= now]
    for key in expired:
        _FACT_CACHE.pop(key, None)
    if len(_FACT_CACHE) > _CACHE_MAX_ITEMS:
        oldest = sorted(_FACT_CACHE.items(), key=lambda item: item[1].expires_at)
        for key, _ in oldest[: len(_FACT_CACHE) - _CACHE_MAX_ITEMS]:
            _FACT_CACHE.pop(key, None)


async def _fetch_facts(market) -> VenueContractFacts:
    now = time.monotonic()
    cached = _FACT_CACHE.get(market.canonical_id)
    if cached and cached.expires_at > now:
        return cached.facts

    async with _CACHE_LOCK:
        now = time.monotonic()
        cached = _FACT_CACHE.get(market.canonical_id)
        if cached and cached.expires_at > now:
            return cached.facts
        venue_id = market.canonical_id.split(":", 1)[1]
        if market.venue == "kalshi":
            adapter = KalshiAdapter(os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2"))
            raw = await adapter.fetch_market(venue_id)
            facts = kalshi_contract_facts(market.canonical_id, raw)
        else:
            adapter = PolymarketAdapter(os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com"))
            raw = await adapter.fetch_market(venue_id)
            facts = polymarket_contract_facts(market.canonical_id, raw)
        _FACT_CACHE[market.canonical_id] = _CachedFacts(now + _CACHE_TTL_SECONDS, facts)
        _prune_cache(now)
        return facts


@router.get("/compare", response_model=PublicVerifiedCompareView)
@router.get("/compare/verified", response_model=PublicVerifiedCompareView)
async def public_verified_compare(
    response: Response,
    left_id: str = Query(min_length=1, max_length=200),
    right_id: str = Query(min_length=1, max_length=200),
) -> PublicVerifiedCompareView:
    left = core._market_by_id(left_id)
    right = core._market_by_id(right_id)
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=240"

    if left_id == right_id:
        facts = VenueContractFacts(left_id, left.venue, left.title, left.closes_at)
        result = verify_contracts(facts, facts)
    else:
        if left.venue == right.venue:
            raise HTTPException(status_code=422, detail="verified comparison is cross-platform only")

        # Cheap local gate prevents arbitrary unrelated pairs from generating external venue calls.
        preliminary = core.compare_markets(left_id=left_id, right_id=right_id)
        if preliminary.decision in {"related", "not_equivalent"}:
            return PublicVerifiedCompareView(
                left_id=left_id,
                right_id=right_id,
                generated_at=datetime.now(timezone.utc),
                decision=preliminary.decision,
                equivalent_contracts=False,
                confidence=0,
                question_similarity=0.0,
                rules_similarity=None,
                source_match=None,
                deadline_delta_hours=None,
                consensus_probability=None,
                gap_points=None,
                agreement=None,
                reasons=list(preliminary.reasons),
                cache_ttl_seconds=_CACHE_TTL_SECONDS,
                disclaimer="Similar titles alone never qualify as equivalent contracts.",
            )

        try:
            left_facts, right_facts = await asyncio.gather(_fetch_facts(left), _fetch_facts(right))
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"verification metadata unavailable: {type(exc).__name__}") from exc
        result = verify_contracts(left_facts, right_facts)

    market_consensus = None
    if result.equivalent_contracts and left.probability is not None and right.probability is not None:
        market_consensus = consensus(left.probability, right.probability, equivalent_contracts=True)

    return PublicVerifiedCompareView(
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
        cache_ttl_seconds=_CACHE_TTL_SECONDS,
        disclaimer=(
            "PrediBeacon verifies question, timing and resolution evidence. Similar titles alone never qualify. "
            "Consensus, when present, is market aggregation rather than a forecast."
        ),
    )
