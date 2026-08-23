from __future__ import annotations

from threading import RLock
from typing import Iterable

from app.domain.markets import NormalizedMarket
from app.services.contract_verification import (
    VenueContractFacts,
    kalshi_contract_facts,
    polymarket_contract_facts,
)


_LOCK = RLock()
_FACTS: dict[str, VenueContractFacts] = {}


def _facts_for_market(market: NormalizedMarket) -> VenueContractFacts:
    if market.venue == "kalshi":
        return kalshi_contract_facts(market.canonical_id, market.raw or {})
    return polymarket_contract_facts(market.canonical_id, market.raw or {})


def publish_contract_facts(markets: Iterable[NormalizedMarket]) -> int:
    """Atomically publish private verification facts from the latest venue refresh."""
    next_facts: dict[str, VenueContractFacts] = {}
    for market in markets:
        try:
            facts = _facts_for_market(market)
        except (TypeError, ValueError):
            continue
        if facts.question:
            next_facts[market.canonical_id] = facts
    with _LOCK:
        _FACTS.clear()
        _FACTS.update(next_facts)
    return len(next_facts)


def contract_facts(market_id: str) -> VenueContractFacts | None:
    with _LOCK:
        return _FACTS.get(market_id)


def contract_facts_snapshot() -> dict[str, VenueContractFacts]:
    with _LOCK:
        return dict(_FACTS)


def clear_contract_facts() -> None:
    with _LOCK:
        _FACTS.clear()
