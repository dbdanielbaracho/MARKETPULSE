from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable

from app.domain.markets import NormalizedMarket


class MatchDecision(str, Enum):
    EQUIVALENT = "equivalent"
    RELATED = "related"
    NOT_EQUIVALENT = "not_equivalent"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class MarketContractFacts:
    canonical_id: str
    normalized_question: str
    closes_at: datetime | None
    resolution_source: str | None = None
    resolution_rules_hash: str | None = None


@dataclass(frozen=True)
class MatchResult:
    decision: MatchDecision
    reasons: tuple[str, ...]


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def contract_facts(market: NormalizedMarket) -> MarketContractFacts:
    raw = market.raw or {}
    return MarketContractFacts(
        canonical_id=market.canonical_id,
        normalized_question=_norm(market.title),
        closes_at=market.closes_at,
        resolution_source=raw.get("resolution_source") or raw.get("resolutionSource"),
        resolution_rules_hash=raw.get("resolution_rules_hash") or raw.get("rules_hash"),
    )


def decide_match(left: MarketContractFacts, right: MarketContractFacts) -> MatchResult:
    if left.canonical_id == right.canonical_id:
        return MatchResult(MatchDecision.EQUIVALENT, ("same canonical market",))

    if left.normalized_question != right.normalized_question:
        return MatchResult(MatchDecision.RELATED, ("question text differs",))

    if left.closes_at and right.closes_at and left.closes_at != right.closes_at:
        return MatchResult(MatchDecision.NOT_EQUIVALENT, ("different close/deadline",))

    if left.resolution_source and right.resolution_source and _norm(left.resolution_source) != _norm(right.resolution_source):
        return MatchResult(MatchDecision.NOT_EQUIVALENT, ("different resolution source",))

    if left.resolution_rules_hash and right.resolution_rules_hash:
        if left.resolution_rules_hash == right.resolution_rules_hash:
            return MatchResult(MatchDecision.EQUIVALENT, ("question, deadline and resolution rules agree",))
        return MatchResult(MatchDecision.NOT_EQUIVALENT, ("different resolution rules",))

    return MatchResult(
        MatchDecision.INSUFFICIENT_EVIDENCE,
        ("similar title is not enough to establish contract equivalence",),
    )


def find_candidates(target: MarketContractFacts, candidates: Iterable[MarketContractFacts]) -> list[tuple[MarketContractFacts, MatchResult]]:
    results: list[tuple[MarketContractFacts, MatchResult]] = []
    for candidate in candidates:
        if candidate.canonical_id == target.canonical_id:
            continue
        result = decide_match(target, candidate)
        if result.decision is not MatchDecision.NOT_EQUIVALENT:
            results.append((candidate, result))
    return results
