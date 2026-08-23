from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "if", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "will", "with", "market", "contract",
    "according", "based", "determined", "resolution", "resolve", "resolves", "source", "shall",
}


@dataclass(frozen=True)
class VenueContractFacts:
    canonical_id: str
    venue: str
    question: str
    closes_at: datetime | None
    resolution_source: str | None = None
    resolution_text: str | None = None


@dataclass(frozen=True)
class VerificationResult:
    decision: str
    equivalent_contracts: bool
    confidence: int
    reasons: tuple[str, ...]
    question_similarity: float
    rules_similarity: float | None
    source_match: bool | None
    deadline_delta_hours: float | None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    value = html.unescape(str(text)).casefold()
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^a-z0-9%.$:/+-]+", " ", value)
    return " ".join(value.split())


def _tokens(text: str | None) -> set[str]:
    return {
        token for token in _clean(text).split()
        if len(token) > 1 and token not in _STOPWORDS
    }


def _similarity(left: str | None, right: str | None) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _anchors(text: str | None) -> tuple[str, ...]:
    clean = _clean(text)
    return tuple(sorted(set(re.findall(r"\b(?:19|20)\d{2}\b|\b\d+(?:\.\d+)?%?\b|\$\d+(?:\.\d+)?\b", clean))))


def _source_key(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"https?://[^\s]+", str(value), flags=re.I)
    if match:
        host = (urlsplit(match.group(0)).hostname or "").casefold()
        if host.startswith("www."):
            host = host[4:]
        if host:
            return host
    clean = _clean(value)
    if not clean:
        return None
    tokens = sorted(_tokens(clean))
    return " ".join(tokens) if tokens else None


def _deadline_delta(left: datetime | None, right: datetime | None) -> float | None:
    if left is None or right is None:
        return None
    return abs((left - right).total_seconds()) / 3600


def verify_contracts(left: VenueContractFacts, right: VenueContractFacts) -> VerificationResult:
    """Conservative cross-venue contract verification from structured venue facts.

    Exact or near-exact questions remain necessary but are never sufficient alone.
    A verified pair also needs compatible timing plus either compatible resolution
    sources or substantially overlapping resolution criteria. Missing evidence fails
    closed as `insufficient_evidence`.
    """
    if left.canonical_id == right.canonical_id:
        return VerificationResult("equivalent", True, 100, ("same canonical market",), 1.0, 1.0, True, 0.0)

    reasons: list[str] = []
    question_similarity = _similarity(left.question, right.question)
    deadline_delta = _deadline_delta(left.closes_at, right.closes_at)

    left_anchors = _anchors(left.question)
    right_anchors = _anchors(right.question)
    if left_anchors != right_anchors:
        return VerificationResult(
            "not_equivalent", False, 0,
            ("question contains different numeric/date anchors",),
            round(question_similarity, 4), None, None, deadline_delta,
        )

    if question_similarity < 0.88:
        return VerificationResult(
            "related", False, 0,
            ("question wording is not close enough for equivalence",),
            round(question_similarity, 4), None, None, deadline_delta,
        )
    reasons.append("question meaning is highly similar")

    if deadline_delta is not None:
        if deadline_delta > 24:
            return VerificationResult(
                "not_equivalent", False, 0,
                ("contract deadlines differ by more than 24 hours",),
                round(question_similarity, 4), None, None, round(deadline_delta, 2),
            )
        reasons.append("contract deadlines are compatible")
    else:
        reasons.append("one or both contract deadlines are unavailable")

    left_source = _source_key(left.resolution_source)
    right_source = _source_key(right.resolution_source)
    source_match: bool | None = None
    if left_source and right_source:
        source_match = left_source == right_source or _similarity(left_source, right_source) >= 0.8
        if source_match:
            reasons.append("resolution sources are compatible")
        else:
            return VerificationResult(
                "not_equivalent", False, 10,
                tuple(reasons + ["explicit resolution sources differ"]),
                round(question_similarity, 4), None, False,
                None if deadline_delta is None else round(deadline_delta, 2),
            )

    rules_similarity: float | None = None
    if _tokens(left.resolution_text) and _tokens(right.resolution_text):
        rules_similarity = _similarity(left.resolution_text, right.resolution_text)
        left_rule_anchors = _anchors(left.resolution_text)
        right_rule_anchors = _anchors(right.resolution_text)
        if left_rule_anchors and right_rule_anchors and left_rule_anchors != right_rule_anchors:
            return VerificationResult(
                "not_equivalent", False, 10,
                tuple(reasons + ["resolution criteria contain conflicting numeric/date anchors"]),
                round(question_similarity, 4), round(rules_similarity, 4), source_match,
                None if deadline_delta is None else round(deadline_delta, 2),
            )
        if rules_similarity >= 0.62:
            reasons.append("resolution criteria substantially overlap")
        else:
            reasons.append("resolution criteria overlap is limited")

    confidence = 45
    confidence += min(25, round(max(0.0, question_similarity - 0.88) / 0.12 * 25))
    if deadline_delta is not None:
        confidence += 10
    if source_match is True:
        confidence += 15
    if rules_similarity is not None:
        confidence += 15 if rules_similarity >= 0.72 else 10 if rules_similarity >= 0.62 else 0
    confidence = min(100, confidence)

    enough_resolution_evidence = source_match is True or (rules_similarity is not None and rules_similarity >= 0.62)
    if enough_resolution_evidence and (deadline_delta is None or deadline_delta <= 24):
        return VerificationResult(
            "equivalent", True, confidence, tuple(reasons),
            round(question_similarity, 4),
            None if rules_similarity is None else round(rules_similarity, 4),
            source_match,
            None if deadline_delta is None else round(deadline_delta, 2),
        )

    return VerificationResult(
        "insufficient_evidence", False, min(confidence, 74),
        tuple(reasons + ["resolution evidence is insufficient to prove equivalence"]),
        round(question_similarity, 4),
        None if rules_similarity is None else round(rules_similarity, 4),
        source_match,
        None if deadline_delta is None else round(deadline_delta, 2),
    )


def kalshi_contract_facts(canonical_id: str, raw: dict) -> VenueContractFacts:
    market = raw.get("market") if isinstance(raw.get("market"), dict) else raw
    title = str(market.get("title") or market.get("subtitle") or "")
    close_raw = market.get("close_time") or market.get("expiration_time") or market.get("expected_expiration_time")
    closes_at = datetime.fromisoformat(str(close_raw).replace("Z", "+00:00")) if close_raw else None
    rules = " ".join(
        str(value) for value in (market.get("rules_primary"), market.get("rules_secondary")) if value
    ) or None
    source = market.get("settlement_source") or market.get("resolution_source")
    return VenueContractFacts(canonical_id, "kalshi", title, closes_at, str(source) if source else None, rules)


def polymarket_contract_facts(canonical_id: str, raw: dict) -> VenueContractFacts:
    title = str(raw.get("question") or raw.get("title") or "")
    close_raw = raw.get("endDate") or raw.get("end_date_iso")
    closes_at = datetime.fromisoformat(str(close_raw).replace("Z", "+00:00")) if close_raw else None
    source = raw.get("resolutionSource") or raw.get("resolution_source")
    description = raw.get("description")
    return VenueContractFacts(
        canonical_id, "polymarket", title, closes_at,
        str(source) if source else None,
        str(description) if description else None,
    )
