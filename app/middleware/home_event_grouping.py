from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import FastAPI, Request
from starlette.responses import Response

# Prediction venues often expose one event as a ladder of near-identical
# thresholds. Those are distinct contracts, but showing every rung as a
# homepage card makes the product look duplicated. This middleware groups
# obvious ladders for the public discovery endpoint only; every individual
# contract remains available by its canonical market URL and ID.
_COMPARATIVE_THRESHOLD = re.compile(
    r"\b(above|below|over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+(?:US\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?",
    re.IGNORECASE,
)
_CURRENCY_THRESHOLD = re.compile(
    r"(?<![\w])(?:US\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?\s*(?=(?:USD|EUR|GBP|JPY|CAD|AUD|BTC|ETH)(?:\b|/))",
    re.IGNORECASE,
)
_UNIT_THRESHOLD = re.compile(
    r"(?<![\w])\d[\d,]*(?:\.\d+)?\s*(?=(?:%|°[CF]|degrees?\b|ounces?\b|oz\b|barrels?\b|bbl\b))",
    re.IGNORECASE,
)

# Sports feeds commonly publish one athlete/event with 1+, 2+, 3+, 4+, 5+
# versions. The noun after the threshold is kept, so different stat families
# (RBIs vs stolen bases vs hits+runs+RBIs) do not collapse into each other.
_PLUS_STAT_THRESHOLD = re.compile(
    r"\b\d+(?:\.\d+)?\+\s*(?=(?:hits?|runs?|rbis?|rbi|goals?|assists?|rebounds?|points?|stolen\s+bases?|bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\b)",
    re.IGNORECASE,
)

# Team/event margin ladders such as "wins by over 4.5 runs" or
# "wins by more than 4.5 goals" are the same discovery family.
_MARGIN_THRESHOLD = re.compile(
    r"\b(?:over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+\d+(?:\.\d+)?\s*(?=(?:runs?|goals?|points?|yards?|sets?|games?|rounds?)\b)",
    re.IGNORECASE,
)

_SPACE = re.compile(r"\s+")


def _normalized_title(title: str) -> str:
    return _SPACE.sub(" ", title.casefold()).strip()


def _family_title(title: str) -> str:
    normalized = title.casefold()
    # Comparative price ladders often omit an explicit currency code, e.g.
    # "Bitcoin above $111,000". Normalize the comparator+number first so
    # public relevance, discovery, and production audits share one family.
    normalized = _COMPARATIVE_THRESHOLD.sub(r"\1 <threshold>", normalized)
    normalized = _CURRENCY_THRESHOLD.sub(" <threshold> ", normalized)
    normalized = _UNIT_THRESHOLD.sub(" <threshold> ", normalized)
    normalized = _PLUS_STAT_THRESHOLD.sub("<threshold>+ ", normalized)
    normalized = _MARGIN_THRESHOLD.sub("<threshold> ", normalized)
    return _SPACE.sub(" ", normalized).strip()


def _close_day(value: str | None) -> str:
    """Use the event day, not exact feed timestamp, for discovery grouping.

    Providers can publish sibling contracts from the same event with slightly
    different close timestamps. Minute-level bucketing therefore leaked
    duplicates. A date-level bucket is stable enough for homepage discovery;
    the normalized title/family still prevents unrelated events from merging.
    """
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:10]
    return dt.date().isoformat()


def _group(markets: list[dict]) -> list[dict]:
    grouped: list[dict] = []
    exact_seen: set[tuple[str, str]] = set()
    family_seen: set[tuple[str, str, str]] = set()

    # Input is already ranked. Keeping the first contract preserves the most
    # relevant representative while suppressing duplicate/sibling cards.
    for market in markets:
        title = str(market.get("title") or "")
        venue = str(market.get("venue") or "")

        # Exact duplicate titles from a provider should never render twice,
        # even if the upstream feed reports different closing timestamps.
        exact_key = (venue, _normalized_title(title))
        if exact_key in exact_seen:
            continue
        exact_seen.add(exact_key)

        family_key = (venue, _family_title(title), _close_day(market.get("closes_at")))
        if family_key in family_seen:
            continue
        family_seen.add(family_key)
        grouped.append(market)
    return grouped


def register_home_event_grouping_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def group_home_event_ladders(request: Request, call_next):
        response = await call_next(request)
        if request.url.path != "/api/v1/markets" or response.status_code != 200:
            return response
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            payload = json.loads(body)
        except (TypeError, ValueError):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        if not isinstance(payload, list):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        grouped = _group(payload)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["X-PrediBeacon-Event-Grouping"] = "event-family-v3"
        return Response(
            content=json.dumps(grouped, separators=(",", ":"), ensure_ascii=False),
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )
