from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BookLevel:
    price: float
    size: float


@dataclass(frozen=True)
class ExecutionQuality:
    best_bid: float | None
    best_ask: float | None
    midpoint: float | None
    spread_points: float | None
    bid_depth_units: float
    ask_depth_units: float
    two_sided: bool
    score: int
    grade: str
    reasons: tuple[str, ...]


def _valid_levels(levels: Iterable[BookLevel]) -> list[BookLevel]:
    return [
        level
        for level in levels
        if 0 <= level.price <= 1 and level.size > 0
    ]


def execution_quality(
    bids: Iterable[BookLevel],
    asks: Iterable[BookLevel],
    *,
    depth_levels: int = 5,
) -> ExecutionQuality:
    """Describe observable book quality without claiming guaranteed execution.

    The score is intentionally bounded and uses only visible top-of-book spread and
    displayed depth. It is not a liquidity guarantee, fill probability, or expected
    return estimate.
    """
    if depth_levels < 1:
        raise ValueError("depth_levels must be positive")

    clean_bids = sorted(_valid_levels(bids), key=lambda level: level.price, reverse=True)
    clean_asks = sorted(_valid_levels(asks), key=lambda level: level.price)
    best_bid = clean_bids[0].price if clean_bids else None
    best_ask = clean_asks[0].price if clean_asks else None
    two_sided = best_bid is not None and best_ask is not None and best_ask >= best_bid

    midpoint = None
    spread_points = None
    reasons: list[str] = []
    score = 0

    if two_sided:
        midpoint = (best_bid + best_ask) / 2
        spread_points = (best_ask - best_bid) * 100
        score += 45
        reasons.append("two-sided order book")
        if spread_points <= 1:
            score += 30
            reasons.append("spread at or below 1 point")
        elif spread_points <= 2:
            score += 24
            reasons.append("spread at or below 2 points")
        elif spread_points <= 5:
            score += 15
            reasons.append("spread at or below 5 points")
        elif spread_points <= 10:
            score += 7
            reasons.append("spread at or below 10 points")
        else:
            reasons.append("wide displayed spread")
    else:
        reasons.append("one-sided or unavailable top of book")

    bid_depth = sum(level.size for level in clean_bids[:depth_levels])
    ask_depth = sum(level.size for level in clean_asks[:depth_levels])
    minimum_depth = min(bid_depth, ask_depth) if two_sided else 0
    if minimum_depth >= 10_000:
        score += 25
        reasons.append("deep displayed book")
    elif minimum_depth >= 1_000:
        score += 18
        reasons.append("substantial displayed book")
    elif minimum_depth >= 100:
        score += 10
        reasons.append("usable displayed book")
    elif minimum_depth > 0:
        score += 4
        reasons.append("thin displayed book")

    score = min(100, score)
    grade = "excellent" if score >= 85 else "good" if score >= 70 else "limited" if score >= 45 else "weak"
    return ExecutionQuality(
        best_bid=best_bid,
        best_ask=best_ask,
        midpoint=midpoint,
        spread_points=spread_points,
        bid_depth_units=round(bid_depth, 4),
        ask_depth_units=round(ask_depth, 4),
        two_sided=two_sided,
        score=score,
        grade=grade,
        reasons=tuple(reasons),
    )


def kalshi_levels(payload: dict) -> tuple[list[BookLevel], list[BookLevel]]:
    """Normalize Kalshi YES/NO bids into a YES-side bid/ask book."""
    book = payload.get("orderbook_fp") or payload.get("orderbook") or {}
    yes = book.get("yes_dollars") or book.get("yes") or []
    no = book.get("no_dollars") or book.get("no") or []

    bids: list[BookLevel] = []
    asks: list[BookLevel] = []
    for row in yes:
        try:
            price, size = float(row[0]), float(row[1])
        except (TypeError, ValueError, IndexError):
            continue
        if price > 1:
            price /= 100
        bids.append(BookLevel(price=price, size=size))

    # A NO bid at p is a YES ask at 1-p in a binary market.
    for row in no:
        try:
            no_price, size = float(row[0]), float(row[1])
        except (TypeError, ValueError, IndexError):
            continue
        if no_price > 1:
            no_price /= 100
        asks.append(BookLevel(price=1 - no_price, size=size))
    return bids, asks


def polymarket_levels(payload: dict) -> tuple[list[BookLevel], list[BookLevel]]:
    """Normalize a Polymarket CLOB book response."""
    bids: list[BookLevel] = []
    asks: list[BookLevel] = []
    for row in payload.get("bids") or []:
        try:
            bids.append(BookLevel(price=float(row["price"]), size=float(row["size"])))
        except (KeyError, TypeError, ValueError):
            continue
    for row in payload.get("asks") or []:
        try:
            asks.append(BookLevel(price=float(row["price"]), size=float(row["size"])))
        except (KeyError, TypeError, ValueError):
            continue
    return bids, asks
