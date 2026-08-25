from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import FastAPI, Request
from starlette.responses import Response

# Prediction venues often expose one event as a ladder of near-identical
# thresholds (for example platinum > 1908.49, > 1908.99, > 1909.49).  Those
# are distinct contracts, but showing every rung as a homepage card makes the
# product look duplicated.  This middleware groups only obvious threshold
# ladders for the public discovery endpoint; individual contracts remain
# available by their canonical market URLs and IDs.
_CURRENCY_THRESHOLD = re.compile(
    r"(?<![\w])(?:US\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?\s*(?=(?:USD|EUR|GBP|JPY|CAD|AUD|BTC|ETH)(?:\b|/))",
    re.IGNORECASE,
)
_UNIT_THRESHOLD = re.compile(
    r"(?<![\w])\d[\d,]*(?:\.\d+)?\s*(?=(?:%|°[CF]|degrees?\b|ounces?\b|oz\b|barrels?\b|bbl\b))",
    re.IGNORECASE,
)
_SPACE = re.compile(r"\s+")


def _family_title(title: str) -> str:
    normalized = title.casefold()
    normalized = _CURRENCY_THRESHOLD.sub(" <threshold> ", normalized)
    normalized = _UNIT_THRESHOLD.sub(" <threshold> ", normalized)
    return _SPACE.sub(" ", normalized).strip()


def _close_bucket(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    # Same event deadline, allowing harmless feed precision differences.
    return dt.replace(second=0, microsecond=0).isoformat()


def _group(markets: list[dict]) -> list[dict]:
    grouped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for market in markets:
        title = str(market.get("title") or "")
        venue = str(market.get("venue") or "")
        key = (venue, _family_title(title), _close_bucket(market.get("closes_at")))
        if key in seen:
            continue
        seen.add(key)
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
        headers["X-PrediBeacon-Event-Grouping"] = "threshold-ladders"
        return Response(
            content=json.dumps(grouped, separators=(",", ":"), ensure_ascii=False),
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )
