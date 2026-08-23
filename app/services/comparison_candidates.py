from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


_STOPWORDS = {
    "a", "an", "and", "are", "be", "by", "for", "from", "in", "is", "of", "on", "or",
    "the", "to", "will", "would", "this", "that", "before", "after", "during", "at",
}


class CandidateMarket(Protocol):
    canonical_id: str
    title: str
    venue: str
    category: str | None
    closes_at: datetime | None


@dataclass(frozen=True)
class ComparisonCandidate:
    left_id: str
    right_id: str
    title_similarity: float
    deadline_delta_hours: float | None
    category_match: bool | None
    score: float
    reasons: tuple[str, ...]


def _tokens(title: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9%$.-]+", " ", title.casefold())
    return {
        token for token in normalized.split()
        if len(token) > 1 and token not in _STOPWORDS
    }


def _anchors(title: str) -> tuple[str, ...]:
    normalized = title.casefold()
    return tuple(sorted(set(re.findall(
        r"\b(?:19|20)\d{2}\b|\b\d+(?:\.\d+)?%?\b|\$\d+(?:\.\d+)?\b",
        normalized,
    ))))


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _deadline_delta(left: datetime | None, right: datetime | None) -> float | None:
    if left is None or right is None:
        return None
    return abs((left - right).total_seconds()) / 3600


def comparison_candidates(
    markets: Iterable[CandidateMarket],
    *,
    min_title_similarity: float = 0.72,
    max_deadline_delta_hours: float = 24.0,
    limit: int = 40,
) -> list[ComparisonCandidate]:
    """Find plausible cross-platform pairs without calling them equivalent.

    Candidate discovery is deliberately broader than contract verification, but it
    still rejects conflicting numeric/date anchors and obviously incompatible close
    times. Every returned pair must still pass the separate verification gate before
    it can enter consensus or disagreement products.
    """
    if not 0 < min_title_similarity <= 1:
        raise ValueError("min_title_similarity must be in (0, 1]")
    if max_deadline_delta_hours < 0 or limit < 1:
        raise ValueError("invalid candidate discovery bounds")

    items = list(markets)
    kalshi = [item for item in items if item.venue == "kalshi"]
    polymarket = [item for item in items if item.venue == "polymarket"]
    candidates: list[ComparisonCandidate] = []

    for left in kalshi:
        left_anchors = _anchors(left.title)
        for right in polymarket:
            if left_anchors != _anchors(right.title):
                continue
            similarity = _similarity(left.title, right.title)
            if similarity < min_title_similarity:
                continue
            deadline_delta = _deadline_delta(left.closes_at, right.closes_at)
            if deadline_delta is not None and deadline_delta > max_deadline_delta_hours:
                continue
            category_match: bool | None = None
            if left.category and right.category:
                category_match = left.category.casefold() == right.category.casefold()
            score = similarity * 100
            reasons = [f"title token similarity {similarity:.0%}"]
            if deadline_delta is not None:
                score += max(0.0, 10.0 - min(10.0, deadline_delta / max(max_deadline_delta_hours, 1) * 10.0))
                reasons.append(f"deadlines {deadline_delta:.1f}h apart")
            else:
                reasons.append("one or both deadlines unavailable")
            if category_match is True:
                score += 5
                reasons.append("categories match")
            elif category_match is False:
                score -= 5
                reasons.append("categories differ")
            candidates.append(ComparisonCandidate(
                left_id=left.canonical_id,
                right_id=right.canonical_id,
                title_similarity=round(similarity, 4),
                deadline_delta_hours=None if deadline_delta is None else round(deadline_delta, 2),
                category_match=category_match,
                score=round(max(0.0, min(115.0, score)), 2),
                reasons=tuple(reasons),
            ))

    candidates.sort(key=lambda item: (item.score, item.title_similarity), reverse=True)
    return candidates[:limit]
