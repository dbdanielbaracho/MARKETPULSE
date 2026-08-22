from __future__ import annotations

import asyncio
import html
import json
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.config.runtime import RuntimeFlags
from app.services.ingestion import IngestionWorker, RefreshBatch
from app.services.matching import MarketContractFacts, decide_match
from app.storage.snapshots import SnapshotStore

APP_VERSION = "0.6.0"


class DiscoveryMarket(BaseModel):
    canonical_id: str
    title: str
    venue: Literal["kalshi", "polymarket"]
    category: str | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    probability_change: float | None = None
    volume_usd: float | None = Field(default=None, ge=0)
    trend_score: float = Field(ge=0, le=100)
    observed_at: datetime
    closes_at: datetime | None = None


class MarketComparison(BaseModel):
    left_id: str
    right_id: str
    decision: Literal["equivalent", "related", "not_equivalent", "insufficient_evidence"]
    equivalent_contracts: bool
    reasons: list[str]
    warning: str


_DISCOVERY: list[DiscoveryMarket] = []
_LAST_REFRESH_AT: datetime | None = None
_LAST_REFRESH_ERRORS: tuple[str, ...] = ()


def set_discovery_markets(markets: list[DiscoveryMarket]) -> None:
    """Replace the current read model atomically at process level."""
    global _DISCOVERY
    _DISCOVERY = list(markets)


def publish_refresh_batch(batch: RefreshBatch) -> None:
    """Publish a complete successful/partial batch without erasing good data on total failure."""
    global _LAST_REFRESH_AT, _LAST_REFRESH_ERRORS
    _LAST_REFRESH_AT = datetime.now(timezone.utc)
    _LAST_REFRESH_ERRORS = batch.errors
    if not batch.markets:
        return
    signal_by_id = {item.canonical_id: item for item in batch.signals}
    items = []
    for market in batch.markets:
        item = signal_by_id[market.canonical_id]
        items.append(
            DiscoveryMarket(
                canonical_id=market.canonical_id,
                title=market.title,
                venue=market.venue,
                category=market.category,
                probability=item.probability,
                probability_change=item.probability_change,
                volume_usd=item.volume_usd,
                trend_score=item.trend_score,
                observed_at=market.observed_at,
                closes_at=market.closes_at,
            )
        )
    set_discovery_markets(items)


def _bounded_seconds(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def _public_base_url() -> str:
    value = os.getenv(
        "MP_PUBLIC_BASE_URL",
        "https://marketpulse-production-aa9f.up.railway.app",
    ).strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("MP_PUBLIC_BASE_URL must be an origin-only HTTPS URL")
    return value

def _refresh_interval() -> float:
    return _bounded_seconds("MP_REFRESH_INTERVAL_SECONDS", 300, 30, 86_400)


def _stale_after_seconds() -> float:
    return _bounded_seconds("MP_STALE_AFTER_SECONDS", 900, 60, 86_400)


def freshness(now: datetime | None = None) -> tuple[str, float | None]:
    if _LAST_REFRESH_AT is None or not _DISCOVERY:
        return "unavailable", None
    current = now or datetime.now(timezone.utc)
    age = (current - _LAST_REFRESH_AT).total_seconds()
    if age < -5:
        return "future", age
    age = max(age, 0.0)
    return ("stale" if age > _stale_after_seconds() else "fresh"), age


@asynccontextmanager
async def lifespan(_: FastAPI):
    flags = RuntimeFlags.from_env()
    store = SnapshotStore(os.getenv("MP_DATABASE_PATH", "/tmp/marketpulse.db"))
    worker = IngestionWorker(
        store=store,
        flags=flags,
        kalshi=KalshiAdapter(os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")),
        polymarket=PolymarketAdapter(os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")),
    )
    stop = asyncio.Event()
    task = asyncio.create_task(
        worker.run_forever(
            interval_seconds=_refresh_interval(),
            publish=publish_refresh_batch,
            stop=stop,
        ),
        name="marketpulse-ingestion",
    )
    try:
        yield
    finally:
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=3)
        except TimeoutError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="MarketPulse", version=APP_VERSION, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Deterministic readiness endpoint: never depends on external venues."""
    return {"status": "ok", "service": "marketpulse-web", "version": APP_VERSION}


@app.get("/api/v1/status")
def status() -> dict[str, object]:
    freshness_state, age_seconds = freshness()
    venue_counts = {
        venue: sum(1 for item in _DISCOVERY if item.venue == venue)
        for venue in ("kalshi", "polymarket")
    }
    return {
        "service": "marketpulse-web",
        "version": APP_VERSION,
        "country": "US",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_refresh_at": _LAST_REFRESH_AT.isoformat() if _LAST_REFRESH_AT else None,
        "last_refresh_errors": ",".join(_LAST_REFRESH_ERRORS) or None,
        "freshness": freshness_state,
        "data_age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "stale_after_seconds": _stale_after_seconds(),
        "venue_market_counts": venue_counts,
    }


@app.get("/api/v1/markets", response_model=list[DiscoveryMarket])
def markets(
    sort: Literal["trending", "movers", "volume"] = "trending",
    category: str | None = None,
    venue: Literal["kalshi", "polymarket"] | None = None,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DiscoveryMarket]:
    items = _DISCOVERY
    if category:
        items = [item for item in items if (item.category or "").casefold() == category.casefold()]
    if venue:
        items = [item for item in items if item.venue == venue]
    if q:
        needle = q.casefold().strip()
        items = [item for item in items if needle in item.title.casefold()]
    if sort == "movers":
        key = lambda item: abs(item.probability_change or 0.0)
    elif sort == "volume":
        key = lambda item: item.volume_usd or 0.0
    else:
        key = lambda item: item.trend_score
    ranked = sorted(items, key=key, reverse=True)
    balanced: list[DiscoveryMarket] = []
    for _, tied_group in groupby(ranked, key=key):
        buckets = {"kalshi": [], "polymarket": []}
        for item in tied_group:
            buckets[item.venue].append(item)
        while buckets["kalshi"] or buckets["polymarket"]:
            for venue in ("kalshi", "polymarket"):
                if buckets[venue]:
                    balanced.append(buckets[venue].pop(0))
    return balanced[:limit]


@app.get("/api/v1/compare", response_model=MarketComparison)
def compare_markets(
    left_id: str = Query(min_length=1, max_length=200),
    right_id: str = Query(min_length=1, max_length=200),
) -> MarketComparison:
    by_id = {item.canonical_id: item for item in _DISCOVERY}
    missing = [identifier for identifier in (left_id, right_id) if identifier not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail={"missing_market_ids": missing})
    left, right = by_id[left_id], by_id[right_id]
    result = decide_match(
        MarketContractFacts(left.canonical_id, " ".join(left.title.casefold().split()), left.closes_at),
        MarketContractFacts(right.canonical_id, " ".join(right.title.casefold().split()), right.closes_at),
    )
    equivalent = result.decision.value == "equivalent"
    return MarketComparison(
        left_id=left_id,
        right_id=right_id,
        decision=result.decision.value,
        equivalent_contracts=equivalent,
        reasons=list(result.reasons),
        warning=(
            "Equivalent contracts require matching question, deadline, resolution source and rules."
            if not equivalent
            else "Contract facts passed the equivalence gate."
        ),
    )


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    base = _public_base_url()
    return f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"


@app.get("/sitemap.xml")
def sitemap() -> Response:
    base = html.escape(_public_base_url(), quote=True)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{base}/</loc><changefreq>hourly</changefreq></url>"
        "</urlset>"
    )
    return Response(body, media_type="application/xml")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    base = _public_base_url()
    canonical = f"{base}/"
    structured_data = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "MarketPulse",
            "url": canonical,
            "description": "Prediction market intelligence from public market data.",
        },
        separators=(",", ":"),
    )
    seo = (
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">'
        f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">'
        '<meta property="og:type" content="website">'
        '<meta property="og:title" content="MarketPulse — Prediction market intelligence">'
        '<meta property="og:description" content="Discover what public prediction markets are pricing now.">'
        f'<script type="application/ld+json">{structured_data}</script>'
    )
    template = Path(__file__).parent / "templates" / "index.html"
    return template.read_text(encoding="utf-8").replace("</head>", f"{seo}</head>")
