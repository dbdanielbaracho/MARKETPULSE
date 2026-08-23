from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

import app.main as core
from app.routes.public_contract_verification import PublicVerifiedCompareView, _verify_pair
from app.services.comparison_candidates import comparison_candidates


router = APIRouter(prefix="/api/v1", tags=["public-market-comparison"])


class MarketCrossPlatformView(BaseModel):
    market_id: str
    generated_at: datetime
    candidates_checked: int
    counterpart: core.DiscoveryMarket | None
    candidate_score: float | None
    title_similarity: float | None
    verification: PublicVerifiedCompareView | None
    disclaimer: str


@router.get("/market/cross-platform", response_model=MarketCrossPlatformView)
async def market_cross_platform(
    response: Response,
    market_id: str = Query(min_length=1, max_length=200),
    candidate_limit: int = Query(default=3, ge=1, le=8),
) -> MarketCrossPlatformView:
    """Find the best cross-platform counterpart for one market and verify it.

    Candidate discovery is intentionally broader than equivalence. A counterpart is
    never treated as equivalent until the separate v2 contract-verification gate
    passes using live venue rules/resolution metadata.
    """
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=240"
    target = core._market_by_id(market_id)
    by_id = {market.canonical_id: market for market in core._DISCOVERY}
    candidates = [
        candidate
        for candidate in comparison_candidates(core._DISCOVERY, limit=60)
        if candidate.left_id == market_id or candidate.right_id == market_id
    ][:candidate_limit]

    if not candidates:
        return MarketCrossPlatformView(
            market_id=market_id,
            generated_at=datetime.now(timezone.utc),
            candidates_checked=0,
            counterpart=None,
            candidate_score=None,
            title_similarity=None,
            verification=None,
            disclaimer=(
                "No plausible counterpart cleared candidate discovery. Candidate discovery is not contract equivalence."
            ),
        )

    semaphore = asyncio.Semaphore(3)

    async def verify(candidate):
        other_id = candidate.right_id if candidate.left_id == market_id else candidate.left_id
        other = by_id.get(other_id)
        if other is None:
            return None
        left = target if target.venue == "kalshi" else other
        right = other if target.venue == "kalshi" else target
        async with semaphore:
            try:
                verification = await _verify_pair(left, right, candidate_score=candidate.score)
            except HTTPException as exc:
                if exc.status_code == 503:
                    return None
                raise
        return candidate, other, verification

    checked = await asyncio.gather(*(verify(candidate) for candidate in candidates))
    rows = [row for row in checked if row is not None]
    if not rows:
        raise HTTPException(status_code=503, detail="cross-platform verification metadata is temporarily unavailable")

    rows.sort(
        key=lambda row: (
            1 if row[2].equivalent_contracts else 0,
            row[2].confidence,
            row[0].score,
        ),
        reverse=True,
    )
    candidate, counterpart, verification = rows[0]
    return MarketCrossPlatformView(
        market_id=market_id,
        generated_at=datetime.now(timezone.utc),
        candidates_checked=len(rows),
        counterpart=counterpart,
        candidate_score=candidate.score,
        title_similarity=candidate.title_similarity,
        verification=verification,
        disclaimer=(
            "A comparison candidate is not an equivalent contract. Consensus and disagreement are shown only after "
            "question, timing and resolution evidence pass the contract-verification gate."
        ),
    )
