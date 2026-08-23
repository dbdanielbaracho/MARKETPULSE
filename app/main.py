from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import html
import json
import os
import re
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from uuid import uuid4
from urllib.parse import urlencode, urlsplit
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from app.adapters.kalshi import KalshiAdapter
from app.adapters.official_rss import TrustedFeedCollector
from app.adapters.openai_drafts import OpenAIDraftProvider
from app.adapters.polymarket import PolymarketAdapter
from app.config.runtime import RuntimeFlags
from app.domain.evidence import EvidenceBundle, EvidenceItem, EvidenceKind
from app.domain.revenue import AttributionRecord, RevenueState
from app.services.content_queue import ContentDecision, ContentPolicy, classify_content_candidate
from app.services.country_policy import resolve_country_policy
from app.services.content_drafts import generate_evidence_brief
from app.services.ingestion import IngestionWorker, RefreshBatch
from app.services.matching import MarketContractFacts, decide_match
from app.services.social_distribution import all_channel_readiness
from app.storage.api_keys import ApiKeyStore, ApiPrincipal
from app.storage.campaigns import CampaignLinkStore
from app.storage.content_queue import ContentQueueStore, PersistenceProbe
from app.storage.maintenance import BackupResult, DatabaseMaintenance
from app.storage.revenue import RevenueStore
from app.storage.snapshots import SnapshotStore

APP_VERSION = "0.43.2"


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
    source_url: str | None = None
    slug: str | None = Field(default=None, min_length=8, max_length=180)


class EvidenceView(BaseModel):
    evidence_id: str
    title: str
    url: str
    publisher: str
    kind: Literal["venue", "news", "official", "research"]
    freshness: Literal["fresh", "stale", "future_dated", "undated"]
    published_at: datetime | None
    retrieved_at: datetime


class MarketEvidenceResponse(BaseModel):
    market_id: str
    generated_at: datetime
    publisher_count: int
    items: list[EvidenceView]


class MarketComparison(BaseModel):
    left_id: str
    right_id: str
    decision: Literal["equivalent", "related", "not_equivalent", "insufficient_evidence"]
    equivalent_contracts: bool
    reasons: list[str]
    warning: str


class RelatedMarketView(BaseModel):
    market: DiscoveryMarket
    relationship: Literal["related", "insufficient_evidence"]
    equivalent_contracts: Literal[False] = False
    reasons: list[str]


class MarketRouteView(BaseModel):
    market_id: str
    venue: Literal["kalshi", "polymarket"]
    available: bool
    mode: Literal["partner", "organic", "unavailable"]
    outbound_url: str | None
    reason: str


class SnapshotPoint(BaseModel):
    probability: float | None
    volume_usd: float | None
    observed_at: datetime


class MarketSignalResponse(BaseModel):
    market_id: str
    label: Literal["rising_fast", "falling_fast", "high_attention", "watching", "insufficient_data"]
    reasons: list[str]
    generated_at: datetime


class CampaignLinkRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=80)
    market_id: str = Field(min_length=1, max_length=200)
    creator_id: str | None = Field(default=None, max_length=100)
    channel: str = Field(min_length=1, max_length=100)


class CampaignLinkView(BaseModel):
    slug: str
    market_id: str
    creator_id: str | None
    channel: str
    active: bool
    public_url: str


class TimelineEvent(BaseModel):
    kind: Literal["probability", "venue", "news", "official", "research"]
    occurred_at: datetime
    title: str
    probability: float | None = None
    volume_usd: float | None = None
    source_url: str | None = None


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    plan: Literal["starter", "pro", "business"] = "starter"
    scopes: list[Literal["markets:read", "history:read"]]
    daily_limit: int = Field(default=1000, ge=1, le=1_000_000)


class ApiKeyCreateResponse(BaseModel):
    key_id: str
    api_key: str
    plan: str
    scopes: list[str]
    daily_limit: int
    notice: str


class ApiKeyView(BaseModel):
    key_id: str
    name: str
    plan: str
    scopes: list[str]
    daily_limit: int
    active: bool
    created_at: datetime
    revoked_at: datetime | None


class PartnerRevenueEvent(BaseModel):
    event_id: str = Field(min_length=3, max_length=200)
    attribution_id: str | None = Field(default=None, max_length=200)
    click_id: str | None = Field(default=None, max_length=200)
    state: Literal["attributed", "qualified", "commission_pending", "approved", "payable", "paid", "rejected", "reversed", "expired", "disputed", "unknown"]
    commission_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class DraftReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=3, max_length=500)


class AdminDraftView(BaseModel):
    draft_id: str
    candidate_id: str
    headline: str
    body: str
    citation_ids: list[str]
    generator: str
    state: Literal["pending_review", "approved", "rejected"]
    created_at: datetime


class PublicationScheduleRequest(BaseModel):
    scheduled_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class PublicationActionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class PublicationView(BaseModel):
    publication_id: str
    draft_id: str
    article_key: str
    slug: str
    version: int
    headline: str
    body: str
    citation_ids: list[str]
    state: Literal["active", "rolled_back"]
    published_at: datetime
    rolled_back_at: datetime | None


_DISCOVERY: list[DiscoveryMarket] = []
_LAST_REFRESH_AT: datetime | None = None
_LAST_REFRESH_ERRORS: tuple[str, ...] = ()
_EXTERNAL_EVIDENCE: dict[str, list[EvidenceItem]] = {}
_LAST_EVIDENCE_REFRESH_AT: datetime | None = None
_LAST_EVIDENCE_ERRORS: tuple[str, ...] = ()
_EVIDENCE_SOURCE_ITEM_COUNTS: dict[str, int] = {}
_EVIDENCE_SOURCE_TOTAL_ITEMS = 0
_CONTENT_QUEUE_COUNTS: dict[str, int] = {}
_CONTENT_DRAFT_COUNTS: dict[str, int] = {}
_AI_DRAFTS_ERROR: str | None = None
_AI_PROVIDER_VERIFIED = False
_AI_DRAFTS_TODAY = 0
_AI_DAILY_LIMIT_REACHED = False
_STORAGE_PROBE: PersistenceProbe | None = None
_PERSISTENT_STORAGE_CONFIGURED = False
_LAST_BACKUP: BackupResult | None = None
_LAST_BACKUP_ERROR: str | None = None


def _evidence_bundle(market: DiscoveryMarket) -> EvidenceBundle:
    items: list[EvidenceItem] = []
    if market.source_url:
        items.append(EvidenceItem(
            title=f"Primary venue contract: {market.title}"[:300].rstrip(),
            url=market.source_url,
            publisher=market.venue.capitalize(),
            kind=EvidenceKind.VENUE,
            published_at=None,
            retrieved_at=market.observed_at,
            summary="Primary contract page supplied by the prediction-market venue.",
        ))
    items.extend(_EXTERNAL_EVIDENCE.get(market.canonical_id, ()))
    return EvidenceBundle(market_id=market.canonical_id, items=items).deduplicated()


def _market_slug(title: str, canonical_id: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:120] or "market"
    suffix = hashlib.sha256(canonical_id.encode("utf-8")).hexdigest()[:10]
    return f"{words}-{suffix}"


def set_discovery_markets(markets: list[DiscoveryMarket]) -> None:
    """Replace the current read model atomically and give every market a stable path."""
    global _DISCOVERY
    _DISCOVERY = [
        item if item.slug else item.model_copy(update={"slug": _market_slug(item.title, item.canonical_id)})
        for item in markets
    ]


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
                source_url=str(market.source_url) if market.source_url else None,
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

def _official_evidence_enabled() -> bool:
    value = os.getenv("MP_OFFICIAL_EVIDENCE", "true").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("MP_OFFICIAL_EVIDENCE must be boolean")


def _content_candidates_enabled() -> bool:
    value = os.getenv("MP_CONTENT_CANDIDATES", "true").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("MP_CONTENT_CANDIDATES must be boolean")


def _content_drafts_enabled() -> bool:
    value = os.getenv("MP_CONTENT_DRAFTS", "true").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("MP_CONTENT_DRAFTS must be boolean")


def _ai_drafts_enabled() -> bool:
    value = os.getenv("MP_AI_DRAFTS", "false").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("MP_AI_DRAFTS must be boolean")


def _ai_model() -> str:
    value = os.getenv("MP_OPENAI_MODEL", "gpt-5.6-luna").strip()
    if not value or len(value) > 100:
        raise ValueError("MP_OPENAI_MODEL is invalid")
    return value


def _ai_daily_limit() -> int:
    raw = os.getenv("MP_AI_DAILY_LIMIT", "100").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("MP_AI_DAILY_LIMIT must be an integer") from exc
    if value < 1 or value > 1000:
        raise ValueError("MP_AI_DAILY_LIMIT must be between 1 and 1000")
    return value



def _database_path() -> str:
    return os.getenv("MP_DATABASE_PATH", "/tmp/marketpulse.db")


def _database_backups_enabled() -> bool:
    value = os.getenv("MP_DATABASE_BACKUPS", "true").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("MP_DATABASE_BACKUPS must be boolean")


def _backup_directory() -> str:
    return os.getenv("MP_DATABASE_BACKUP_DIRECTORY", "/data/backups")


def _backup_retention() -> int:
    raw = os.getenv("MP_DATABASE_BACKUP_RETENTION", "7").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("MP_DATABASE_BACKUP_RETENTION must be an integer") from exc
    if value < 1 or value > 90:
        raise ValueError("MP_DATABASE_BACKUP_RETENTION must be between 1 and 90")
    return value


def _admin_review_configured() -> bool:
    return len(os.getenv("MP_ADMIN_TOKEN", "").strip()) >= 32


def _require_admin(
    token: Annotated[str | None, Header(alias="X-MarketPulse-Admin-Token")] = None,
) -> None:
    expected = os.getenv("MP_ADMIN_TOKEN", "").strip()
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="admin review is not configured")
    if token is None or not compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid admin credentials")


def _commercial_principal(token: str | None, scope: str) -> ApiPrincipal:
    try:
        return ApiKeyStore(_database_path()).authorize(token or "", scope)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


def _commercial_markets_key(
    token: Annotated[str | None, Header(alias="X-PrediBeacon-API-Key")] = None,
) -> ApiPrincipal:
    return _commercial_principal(token, "markets:read")


def _commercial_history_key(
    token: Annotated[str | None, Header(alias="X-PrediBeacon-API-Key")] = None,
) -> ApiPrincipal:
    return _commercial_principal(token, "history:read")


def _evidence_refresh_interval() -> float:
    return _bounded_seconds("MP_EVIDENCE_REFRESH_INTERVAL_SECONDS", 900, 300, 86_400)


async def run_external_evidence_forever(stop: asyncio.Event, queue: ContentQueueStore) -> None:
    global _EXTERNAL_EVIDENCE, _LAST_EVIDENCE_REFRESH_AT, _LAST_EVIDENCE_ERRORS, _EVIDENCE_SOURCE_ITEM_COUNTS, _EVIDENCE_SOURCE_TOTAL_ITEMS, _CONTENT_QUEUE_COUNTS
    collector = TrustedFeedCollector()
    while not stop.is_set():
        if _DISCOVERY:
            matched, errors = await collector.collect(list(_DISCOVERY))
            _EXTERNAL_EVIDENCE = matched
            _LAST_EVIDENCE_ERRORS = errors
            _EVIDENCE_SOURCE_ITEM_COUNTS = dict(collector.last_source_item_counts)
            _EVIDENCE_SOURCE_TOTAL_ITEMS = collector.last_total_item_count
            _LAST_EVIDENCE_REFRESH_AT = datetime.now(timezone.utc)
            if _content_candidates_enabled():
                policy = ContentPolicy()
                for market in _DISCOVERY:
                    if market.canonical_id not in matched:
                        continue
                    evidence_bundle = _evidence_bundle(market)
                    candidate = classify_content_candidate(
                        market_id=market.canonical_id,
                        score=market.trend_score,
                        evidence=evidence_bundle,
                        policy=policy,
                    )
                    if candidate.decision != ContentDecision.REJECT:
                        queue.enqueue(candidate, evidence_bundle)
                _CONTENT_QUEUE_COUNTS = queue.counts()
            delay = _evidence_refresh_interval()
        else:
            delay = 10
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            pass


async def run_content_drafts_forever(
    stop: asyncio.Event,
    queue: ContentQueueStore,
    ai_provider: OpenAIDraftProvider | None = None,
    ai_daily_limit: int = 100,
) -> None:
    global _CONTENT_QUEUE_COUNTS, _CONTENT_DRAFT_COUNTS, _AI_DRAFTS_TODAY, _AI_DAILY_LIMIT_REACHED
    while not stop.is_set():
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        _AI_DRAFTS_TODAY = queue.drafts_created_since(today) if ai_provider is not None else 0
        _AI_DAILY_LIMIT_REACHED = ai_provider is not None and _AI_DRAFTS_TODAY >= ai_daily_limit
        if _AI_DAILY_LIMIT_REACHED:
            candidate = None
            delay = 60
        else:
            candidate = queue.claim_next()
            delay = 30 if candidate is None else 0
        if candidate is None:
            _CONTENT_QUEUE_COUNTS = queue.counts()
            _CONTENT_DRAFT_COUNTS = queue.draft_counts()
        else:
            try:
                evidence = queue.evidence(candidate.candidate_id)
                if ai_provider is not None:
                    draft = await ai_provider.generate(
                        market_id=candidate.market_id,
                        evidence=evidence,
                    )
                else:
                    draft = generate_evidence_brief(
                        market_id=candidate.market_id,
                        evidence=evidence,
                    )
                queue.save_draft(candidate.candidate_id, draft)
            except Exception:
                current = queue.get(candidate.candidate_id)
                if current is not None and current.state == "claimed":
                    queue.transition(candidate.candidate_id, "failed", "draft_generation_failed")
            _CONTENT_QUEUE_COUNTS = queue.counts()
            _CONTENT_DRAFT_COUNTS = queue.draft_counts()
            delay = 0
        if delay:
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass


async def run_scheduled_publications_forever(
    stop: asyncio.Event,
    queue: ContentQueueStore,
) -> None:
    while not stop.is_set():
        queue.publish_due(limit=20)
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except TimeoutError:
            pass


async def run_database_backups_forever(
    stop: asyncio.Event,
    maintenance: DatabaseMaintenance,
) -> None:
    global _LAST_BACKUP, _LAST_BACKUP_ERROR
    while not stop.is_set():
        try:
            _LAST_BACKUP = await asyncio.to_thread(maintenance.backup)
            _LAST_BACKUP_ERROR = None
        except Exception as exc:
            _LAST_BACKUP_ERROR = type(exc).__name__
        try:
            await asyncio.wait_for(stop.wait(), timeout=86_400)
        except TimeoutError:
            pass


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
    global _CONTENT_QUEUE_COUNTS, _CONTENT_DRAFT_COUNTS, _AI_DRAFTS_ERROR, _AI_PROVIDER_VERIFIED, _AI_DRAFTS_TODAY, _AI_DAILY_LIMIT_REACHED, _STORAGE_PROBE, _PERSISTENT_STORAGE_CONFIGURED, _LAST_BACKUP, _LAST_BACKUP_ERROR
    flags = RuntimeFlags.from_env()
    database_path = _database_path()
    store = SnapshotStore(database_path)
    content_queue = ContentQueueStore(database_path)
    _STORAGE_PROBE = content_queue.record_startup()
    _CONTENT_QUEUE_COUNTS = content_queue.counts()
    _CONTENT_DRAFT_COUNTS = content_queue.draft_counts()
    _PERSISTENT_STORAGE_CONFIGURED = Path(database_path).parent == Path("/data")
    worker = IngestionWorker(
        store=store,
        flags=flags,
        kalshi=KalshiAdapter(os.getenv("MP_KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")),
        polymarket=PolymarketAdapter(os.getenv("MP_POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")),
    )
    ai_provider = None
    _AI_DRAFTS_ERROR = None
    _AI_PROVIDER_VERIFIED = False
    _AI_DRAFTS_TODAY = 0
    _AI_DAILY_LIMIT_REACHED = False
    if _ai_drafts_enabled():
        api_key = os.getenv("MP_OPENAI_API_KEY", "").strip()
        if api_key:
            ai_provider = OpenAIDraftProvider(api_key=api_key, model=_ai_model())
            try:
                await ai_provider.verify()
            except Exception:
                _AI_DRAFTS_ERROR = "provider_verification_failed"
                ai_provider = None
            else:
                _AI_PROVIDER_VERIFIED = True
        else:
            _AI_DRAFTS_ERROR = "missing_api_key"

    stop = asyncio.Event()
    tasks = [
        asyncio.create_task(
            worker.run_forever(
                interval_seconds=_refresh_interval(),
                publish=publish_refresh_batch,
                stop=stop,
            ),
            name="marketpulse-ingestion",
        )
    ]
    if _PERSISTENT_STORAGE_CONFIGURED and _database_backups_enabled():
        tasks.append(asyncio.create_task(
            run_database_backups_forever(
                stop,
                DatabaseMaintenance(database_path, _backup_directory(), _backup_retention()),
            ),
            name="marketpulse-database-backups",
        ))
    if flags.automated_publishing:
        tasks.append(asyncio.create_task(
            run_scheduled_publications_forever(stop, content_queue),
            name="marketpulse-scheduled-publishing",
        ))
    if _official_evidence_enabled():
        tasks.append(asyncio.create_task(run_external_evidence_forever(stop, content_queue), name="marketpulse-external-evidence"))
    if _content_drafts_enabled() and (not _ai_drafts_enabled() or ai_provider is not None):
        tasks.append(asyncio.create_task(
            run_content_drafts_forever(stop, content_queue, ai_provider, _ai_daily_limit()),
            name="marketpulse-content-drafts",
        ))
    try:
        yield
    finally:
        stop.set()
        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=3)
            except TimeoutError:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


app = FastAPI(title="PrediBeacon", version=APP_VERSION, lifespan=lifespan)


@app.middleware("http")
async def redirect_www_to_canonical(request: Request, call_next):
    """Keep one public origin so links, analytics, and search signals do not split."""
    hostname = (request.url.hostname or "").lower()
    if hostname == "www.predibeacon.com":
        target = f"{_public_base_url()}{request.url.path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(url=target, status_code=308)
    return await call_next(request)


@app.middleware("http")
async def public_security_headers(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_request_id if re.fullmatch(r"[A-Za-z0-9._-]{8,64}", supplied_request_id) else str(uuid4())
    declared_size = request.headers.get("content-length")
    if request.method in {"POST", "PUT", "PATCH"} and declared_size:
        try:
            too_large = int(declared_size) > 1_048_576
        except ValueError:
            too_large = True
        if too_large:
            return Response(
                json.dumps({"detail": "request body too large", "request_id": request_id}),
                status_code=413,
                media_type="application/json",
                headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
            )
    started = time.perf_counter()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f'app;dur={(time.perf_counter() - started) * 1000:.1f}'
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith(("/api/v1/admin", "/api/v1/partners")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Deterministic readiness endpoint: never depends on external venues."""
    return {"status": "ok", "service": "predibeacon-web", "version": APP_VERSION}


@app.get("/api/v1/status")
def status() -> dict[str, object]:
    freshness_state, age_seconds = freshness()
    venue_counts = {
        venue: sum(1 for item in _DISCOVERY if item.venue == venue)
        for venue in ("kalshi", "polymarket")
    }
    return {
        "service": "predibeacon-web",
        "version": APP_VERSION,
        "country": "US",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_refresh_at": _LAST_REFRESH_AT.isoformat() if _LAST_REFRESH_AT else None,
        "last_refresh_errors": ",".join(_LAST_REFRESH_ERRORS) or None,
        "freshness": freshness_state,
        "data_age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "stale_after_seconds": _stale_after_seconds(),
        "venue_market_counts": venue_counts,
        "official_evidence_enabled": _official_evidence_enabled(),
        "official_evidence_last_refresh_at": _LAST_EVIDENCE_REFRESH_AT.isoformat() if _LAST_EVIDENCE_REFRESH_AT else None,
        "official_evidence_errors": ",".join(_LAST_EVIDENCE_ERRORS) or None,
        "official_evidence_market_count": len(_EXTERNAL_EVIDENCE),
        "evidence_source_item_counts": _EVIDENCE_SOURCE_ITEM_COUNTS,
        "evidence_source_total_item_count": _EVIDENCE_SOURCE_TOTAL_ITEMS,
        "official_evidence_item_count": sum(
            1 for items in _EXTERNAL_EVIDENCE.values() for item in items
            if item.kind == EvidenceKind.OFFICIAL
        ),
        "news_evidence_item_count": sum(
            1 for items in _EXTERNAL_EVIDENCE.values() for item in items
            if item.kind == EvidenceKind.NEWS
        ),
        "external_evidence_market_count": len(_EXTERNAL_EVIDENCE),
        "content_candidates_enabled": _content_candidates_enabled(),
        "content_queue_counts": _CONTENT_QUEUE_COUNTS,
        "content_drafts_enabled": _content_drafts_enabled(),
        "content_draft_counts": _CONTENT_DRAFT_COUNTS,
        "ai_drafts": {
            "enabled": _ai_drafts_enabled(),
            "provider": "openai" if _ai_drafts_enabled() else None,
            "model": _ai_model() if _ai_drafts_enabled() else None,
            "configured": bool(os.getenv("MP_OPENAI_API_KEY", "").strip()),
            "verified": _AI_PROVIDER_VERIFIED,
            "error": _AI_DRAFTS_ERROR,
            "daily_limit": _ai_daily_limit(),
            "drafts_today": _AI_DRAFTS_TODAY,
            "daily_limit_reached": _AI_DAILY_LIMIT_REACHED,
        },
        "storage": {
            "writable": _STORAGE_PROBE is not None,
            "persistent_volume_configured": _PERSISTENT_STORAGE_CONFIGURED,
            "identity": _STORAGE_PROBE.identity if _STORAGE_PROBE else None,
            "startup_count": _STORAGE_PROBE.startup_count if _STORAGE_PROBE else None,
            "first_started_at": _STORAGE_PROBE.first_started_at.isoformat() if _STORAGE_PROBE else None,
            "last_started_at": _STORAGE_PROBE.last_started_at.isoformat() if _STORAGE_PROBE else None,
        },
        "database_backup": {
            "enabled": _database_backups_enabled(),
            "last_created_at": _LAST_BACKUP.created_at.isoformat() if _LAST_BACKUP else None,
            "last_size_bytes": _LAST_BACKUP.size_bytes if _LAST_BACKUP else None,
            "last_integrity": _LAST_BACKUP.integrity if _LAST_BACKUP else None,
            "retained": _LAST_BACKUP.retained if _LAST_BACKUP else 0,
            "error": _LAST_BACKUP_ERROR,
        },
        "admin_review_configured": _admin_review_configured(),
        "content_publication_counts": ContentQueueStore(_database_path()).publication_counts(),
        "content_publication_schedule_counts": ContentQueueStore(_database_path()).schedule_counts(),
        "automated_publishing_enabled": RuntimeFlags.from_env().automated_publishing,
        "social_distribution_enabled": RuntimeFlags.from_env().social_distribution,
    }


@app.get("/api/v1/admin/operations", dependencies=[Depends(_require_admin)])
def operations_snapshot() -> dict[str, object]:
    snapshot = status()
    venue_counts = snapshot["venue_market_counts"]
    storage = snapshot["storage"]
    ai = snapshot["ai_drafts"]
    queue_counts = snapshot["content_queue_counts"]
    backup = snapshot["database_backup"]
    checks = [
        {"name": "Market freshness", "ok": snapshot["freshness"] == "fresh", "severity": "critical" if snapshot["freshness"] in {"unavailable", "future"} else "warning", "detail": f'Data state is {snapshot["freshness"]}; age={snapshot["data_age_seconds"]}s.'},
        {"name": "Venue ingestion", "ok": venue_counts["kalshi"] > 0 and venue_counts["polymarket"] > 0, "severity": "critical", "detail": f'Kalshi={venue_counts["kalshi"]}; Polymarket={venue_counts["polymarket"]}.'},
        {"name": "Refresh errors", "ok": snapshot["last_refresh_errors"] is None, "severity": "critical", "detail": snapshot["last_refresh_errors"] or "No venue refresh errors."},
        {"name": "Evidence sources", "ok": snapshot["official_evidence_errors"] is None, "severity": "warning", "detail": snapshot["official_evidence_errors"] or f'{snapshot["evidence_source_total_item_count"]} source items available.'},
        {"name": "Persistent storage", "ok": bool(storage["writable"] and storage["persistent_volume_configured"]), "severity": "critical", "detail": "Persistent volume is writable." if storage["writable"] else "Storage is not writable."},
        {"name": "Database backup", "ok": not backup["enabled"] or (backup["error"] is None and backup["last_integrity"] in {None, "ok"}), "severity": "warning", "detail": backup["error"] or (f'{backup["retained"]} verified backups retained.' if backup["last_created_at"] else "Initial backup pending.")},
        {"name": "AI draft provider", "ok": not ai["enabled"] or bool(ai["configured"] and ai["verified"] and not ai["error"]), "severity": "warning", "detail": ai["error"] or ("Provider verified." if ai["enabled"] else "AI drafts disabled.")},
        {"name": "Failed content jobs", "ok": queue_counts.get("failed", 0) == 0, "severity": "warning", "detail": f'{queue_counts.get("failed", 0)} failed queue items.'},
        {"name": "Distribution safety", "ok": not snapshot["automated_publishing_enabled"] and not snapshot["social_distribution_enabled"], "severity": "critical", "detail": "Automated publishing and social distribution are disabled." if not snapshot["automated_publishing_enabled"] and not snapshot["social_distribution_enabled"] else "A distribution switch is enabled."},
    ]
    failing = [item for item in checks if not item["ok"]]
    overall = "critical" if any(item["severity"] == "critical" for item in failing) else ("warning" if failing else "healthy")
    return {"overall": overall, "generated_at": snapshot["generated_at"], "checks": checks, "status": snapshot}


@app.get("/api/v1/admin/database/integrity", dependencies=[Depends(_require_admin)])
def database_integrity() -> dict[str, str]:
    try:
        result = DatabaseMaintenance.integrity(_database_path())
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"integrity": result}


@app.post("/api/v1/admin/database/backups", dependencies=[Depends(_require_admin)])
def create_database_backup() -> dict[str, object]:
    global _LAST_BACKUP, _LAST_BACKUP_ERROR
    try:
        result = DatabaseMaintenance(
            _database_path(),
            _backup_directory(),
            _backup_retention(),
        ).backup()
    except Exception as exc:
        _LAST_BACKUP_ERROR = type(exc).__name__
        raise HTTPException(status_code=503, detail="database backup failed") from exc
    _LAST_BACKUP = result
    _LAST_BACKUP_ERROR = None
    return {
        "created_at": result.created_at,
        "size_bytes": result.size_bytes,
        "integrity": result.integrity,
        "retained": result.retained,
    }


@app.get("/api/v1/admin/revenue", dependencies=[Depends(_require_admin)])
def revenue_snapshot() -> dict[str, object]:
    return RevenueStore(_database_path()).summary()


@app.get(
    "/api/v1/admin/creators/{creator_id}/revenue",
    dependencies=[Depends(_require_admin)],
)
def creator_revenue_snapshot(creator_id: str) -> dict[str, object]:
    return RevenueStore(_database_path()).creator_summary(creator_id)


@app.post("/api/v1/partners/{venue}/events")
async def reconcile_partner_event(
    venue: Literal["kalshi", "polymarket"],
    request: Request,
    timestamp: Annotated[str | None, Header(alias="X-PrediBeacon-Partner-Timestamp")] = None,
    signature: Annotated[str | None, Header(alias="X-PrediBeacon-Partner-Signature")] = None,
) -> dict[str, object]:
    secret = os.getenv(f"MP_{venue.upper()}_WEBHOOK_SECRET", "").strip()
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="partner reconciliation is not configured")
    try:
        timestamp_value = int(timestamp or "")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid partner timestamp") from exc
    if abs(int(time.time()) - timestamp_value) > 300:
        raise HTTPException(status_code=401, detail="stale partner event")
    body = await request.body()
    expected = hmac.new(
        secret.encode("utf-8"),
        (str(timestamp_value) + ".").encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()
    provided = (signature or "").removeprefix("sha256=")
    if not provided or not compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid partner signature")
    try:
        event = PartnerRevenueEvent.model_validate_json(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid partner event") from exc
    if bool(event.attribution_id) == bool(event.click_id):
        raise HTTPException(status_code=422, detail="provide exactly one attribution_id or click_id")
    store = RevenueStore(_database_path())
    try:
        attribution_id = event.attribution_id or store.attribution_id_for_click(event.click_id or "")
        existing = store.get(attribution_id)
        if existing.venue != venue:
            raise ValueError("venue mismatch")
        current = store.transition(
            attribution_id,
            RevenueState(event.state),
            commission_amount=event.commission_amount,
            currency=event.currency,
            partner_event_id=f"{venue}:{event.event_id}",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="attribution not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "attribution_id": current.attribution_id,
        "click_id": current.click_id,
        "venue": current.venue,
        "state": current.state.value,
        "commission_amount": current.commission_amount,
        "currency": current.currency,
        "partner_event_id": current.partner_event_id,
    }


@app.get("/api/v1/policy")
def country_policy(country: str | None = Query(default=None, min_length=2, max_length=2)) -> dict[str, object]:
    policy = resolve_country_policy(country)
    return {
        "country": policy.country,
        "audience": policy.audience,
        "informational_content_allowed": policy.informational_content_allowed,
        "commercial_outbound_allowed": policy.commercial_outbound_allowed,
        "paid_social_allowed": policy.paid_social_allowed,
        "minimum_age": policy.minimum_age,
        "route_mode": policy.route_mode,
        "reason": policy.reason,
    }


@app.get("/api/v1/social/readiness")
def social_readiness(
    country: str | None = Query(default=None, min_length=2, max_length=2),
) -> list[dict[str, object]]:
    return [
        {
            "channel": item.channel,
            "ready": item.ready,
            "reasons": list(item.reasons),
            "credential_configured": item.credential_configured,
            "platform_authorized": item.platform_authorized,
            "country": item.country,
            "audience": item.audience,
        }
        for item in all_channel_readiness(country)
    ]


@app.get("/admin/revenue", response_class=HTMLResponse, include_in_schema=False)
def revenue_page() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "revenue.html"
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; "
                f"style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


@app.get("/admin/operations", response_class=HTMLResponse, include_in_schema=False)
def operations_page() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "operations.html"
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; "
                f"style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "admin.html"
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; "
                f"style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


@app.get("/api/v1/admin/drafts", response_model=list[AdminDraftView], dependencies=[Depends(_require_admin)])
def admin_drafts(
    state: Literal["pending_review", "approved", "rejected"] = "pending_review",
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AdminDraftView]:
    drafts = ContentQueueStore(_database_path()).drafts(state, limit)
    return [
        AdminDraftView(
            draft_id=item.draft_id,
            candidate_id=item.candidate_id,
            headline=item.headline,
            body=item.body,
            citation_ids=list(item.citation_ids),
            generator=item.generator,
            state=item.state,
            created_at=item.created_at,
        )
        for item in drafts
    ]


@app.post("/api/v1/admin/drafts/{draft_id}/review", response_model=AdminDraftView, dependencies=[Depends(_require_admin)])
def review_admin_draft(draft_id: str, request: DraftReviewRequest) -> AdminDraftView:
    try:
        item = ContentQueueStore(_database_path()).review_draft(
            draft_id,
            request.decision,
            request.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="draft not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AdminDraftView(
        draft_id=item.draft_id,
        candidate_id=item.candidate_id,
        headline=item.headline,
        body=item.body,
        citation_ids=list(item.citation_ids),
        generator=item.generator,
        state=item.state,
        created_at=item.created_at,
    )


def _publication_view(item) -> PublicationView:
    return PublicationView(
        publication_id=item.publication_id,
        draft_id=item.draft_id,
        article_key=item.article_key,
        slug=item.slug,
        version=item.version,
        headline=item.headline,
        body=item.body,
        citation_ids=list(item.citation_ids),
        state=item.state,
        published_at=item.published_at,
        rolled_back_at=item.rolled_back_at,
    )


@app.get(
    "/api/v1/admin/publications",
    response_model=list[PublicationView],
    dependencies=[Depends(_require_admin)],
)
def admin_publications(
    state: Literal["active", "rolled_back"] = "active",
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PublicationView]:
    return [
        _publication_view(item)
        for item in ContentQueueStore(_database_path()).publications(state, limit)
    ]


@app.post(
    "/api/v1/admin/drafts/{draft_id}/schedule",
    dependencies=[Depends(_require_admin)],
)
def schedule_admin_draft(
    draft_id: str,
    request: PublicationScheduleRequest,
) -> dict[str, object]:
    try:
        return ContentQueueStore(_database_path()).schedule_publication(
            draft_id,
            request.scheduled_at,
            request.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="draft not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/v1/admin/drafts/{draft_id}/publish",
    response_model=PublicationView,
    dependencies=[Depends(_require_admin)],
)
def publish_admin_draft(draft_id: str, request: PublicationActionRequest) -> PublicationView:
    try:
        item = ContentQueueStore(_database_path()).publish_draft(draft_id, request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="draft not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _publication_view(item)


@app.post(
    "/api/v1/admin/publications/{publication_id}/rollback",
    response_model=PublicationView,
    dependencies=[Depends(_require_admin)],
)
def rollback_admin_publication(
    publication_id: str,
    request: PublicationActionRequest,
) -> PublicationView:
    try:
        item = ContentQueueStore(_database_path()).rollback_publication(
            publication_id,
            request.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="publication not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _publication_view(item)


@app.get("/api/v1/articles", response_model=list[PublicationView])
def published_articles(limit: int = Query(default=20, ge=1, le=100)) -> list[PublicationView]:
    return [
        _publication_view(item)
        for item in ContentQueueStore(_database_path()).publications("active", limit)
    ]


@app.get("/articles", response_class=HTMLResponse)
def article_index() -> HTMLResponse:
    items = ContentQueueStore(_database_path()).publications("active", 100)
    cards = "".join(
        f'<article><h2><a href="/articles/{html.escape(item.slug, quote=True)}">'
        f'{html.escape(item.headline)}</a></h2>'
        f'<p>Published {html.escape(item.published_at.isoformat())} · version {item.version}</p></article>'
        for item in items
    ) or "<p>No editorial briefs have been published yet.</p>"
    return HTMLResponse(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>PrediBeacon — Editorial briefs</title></head><body>"
        "<main><p><a href=\"/\">PrediBeacon</a></p><h1>Editorial briefs</h1>"
        f"{cards}</main></body></html>",
        headers={"Cache-Control": "public, max-age=60"},
    )


@app.get("/articles/{slug}", response_class=HTMLResponse)
def article_page(slug: str) -> HTMLResponse:
    store = ContentQueueStore(_database_path())
    item = store.publication(slug)
    if item is None:
        raise HTTPException(status_code=404, detail="article not found")
    evidence = {source.evidence_id: source for source in store.publication_evidence(item.publication_id)}
    citations = "".join(
        f'<li><a href="{html.escape(str(evidence[identifier].url), quote=True)}" '
        'rel="noopener noreferrer">'
        f'{html.escape(evidence[identifier].publisher)} — '
        f'{html.escape(evidence[identifier].title)}</a></li>'
        for identifier in item.citation_ids
        if identifier in evidence
    )
    body = "<br>".join(html.escape(item.body).splitlines())
    return HTMLResponse(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{html.escape(item.headline)} — PrediBeacon</title></head><body>"
        "<main><p><a href=\"/articles\">Editorial briefs</a></p>"
        f"<article><h1>{html.escape(item.headline)}</h1>"
        f"<p>Version {item.version} · Published {html.escape(item.published_at.isoformat())}</p>"
        f"<div>{body}</div><h2>Sources</h2><ol>{citations}</ol>"
        "<p>Prediction-market prices can change and are not financial advice.</p>"
        "</article></main></body></html>",
        headers={"Cache-Control": "public, max-age=60"},
    )


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


@app.get("/api/v1/commercial/markets", response_model=list[DiscoveryMarket])
def commercial_markets(
    sort: Literal["trending", "movers", "volume"] = "trending",
    category: str | None = None,
    venue: Literal["kalshi", "polymarket"] | None = None,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=100),
    principal: ApiPrincipal = Depends(_commercial_markets_key),
) -> list[DiscoveryMarket]:
    return markets(sort=sort, category=category, venue=venue, q=q, limit=limit)


@app.get("/api/v1/commercial/history", response_model=list[SnapshotPoint])
def commercial_history(
    market_id: str = Query(min_length=1, max_length=200),
    hours: int = Query(default=168, ge=1, le=8760),
    principal: ApiPrincipal = Depends(_commercial_history_key),
) -> list[SnapshotPoint]:
    return market_history(market_id=market_id, hours=hours)


@app.get("/api/v1/market/timeline", response_model=list[TimelineEvent])
def market_timeline(
    market_id: str = Query(min_length=1, max_length=200),
    hours: int = Query(default=168, ge=1, le=8760),
) -> list[TimelineEvent]:
    market = _market_by_id(market_id)
    events = [
        TimelineEvent(
            kind="probability",
            occurred_at=item.observed_at,
            title="Recorded market probability",
            probability=item.probability,
            volume_usd=item.volume_usd,
        )
        for item in SnapshotStore(_database_path()).history(market_id, hours=hours, limit=100)
    ]
    for item in _evidence_bundle(market).items:
        events.append(TimelineEvent(
            kind=item.kind.value,
            occurred_at=item.published_at or item.retrieved_at,
            title=item.title,
            source_url=str(item.url),
        ))
    events.sort(key=lambda item: item.occurred_at, reverse=True)
    return events[:150]


@app.get("/api/v1/evidence", response_model=MarketEvidenceResponse)
def market_evidence(
    market_id: str = Query(min_length=1, max_length=200),
) -> MarketEvidenceResponse:
    market = next((item for item in _DISCOVERY if item.canonical_id == market_id), None)
    if market is None:
        raise HTTPException(status_code=404, detail={"missing_market_id": market_id})
    bundle = _evidence_bundle(market)
    max_age = timedelta(hours=72)
    return MarketEvidenceResponse(
        market_id=market_id,
        generated_at=bundle.generated_at,
        publisher_count=bundle.publisher_count,
        items=[
            EvidenceView(
                evidence_id=item.evidence_id,
                title=item.title,
                url=str(item.url),
                publisher=item.publisher,
                kind=item.kind.value,
                freshness=item.freshness(max_age=max_age).value,
                published_at=item.published_at,
                retrieved_at=item.retrieved_at,
            )
            for item in bundle.items
        ],
    )


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


def _market_by_id(market_id: str) -> DiscoveryMarket:
    market = next((item for item in _DISCOVERY if item.canonical_id == market_id), None)
    if market is None:
        raise HTTPException(status_code=404, detail="market not found")
    return market


@app.get("/api/v1/market", response_model=DiscoveryMarket)
def market_detail(market_id: str = Query(min_length=1, max_length=200)) -> DiscoveryMarket:
    return _market_by_id(market_id)


def _market_route(market: DiscoveryMarket) -> MarketRouteView:
    if not market.source_url:
        return MarketRouteView(market_id=market.canonical_id, venue=market.venue, available=False, mode="unavailable", outbound_url=None, reason="missing_destination")
    parsed = urlsplit(market.source_url)
    allowed_hosts = {
        "kalshi": {"kalshi.com", "www.kalshi.com"},
        "polymarket": {"polymarket.com", "www.polymarket.com"},
    }
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed_hosts[market.venue]:
        return MarketRouteView(market_id=market.canonical_id, venue=market.venue, available=False, mode="unavailable", outbound_url=None, reason="unverified_destination")
    verified = os.getenv(f"MP_{market.venue.upper()}_COMMERCIAL_VERIFIED", "false").strip().casefold() in {"1", "true", "yes", "on"}
    partner_id = os.getenv(f"MP_{market.venue.upper()}_PARTNER_ID", "").strip()
    mode = "partner" if verified and partner_id else "organic"
    return MarketRouteView(
        market_id=market.canonical_id,
        venue=market.venue,
        available=True,
        mode=mode,
        outbound_url=f"/out/{market.venue}?{urlencode({'market_id': market.canonical_id})}",
        reason="verified_partner_route" if mode == "partner" else "verified_organic_route",
    )


@app.get("/api/v1/market/route", response_model=MarketRouteView)
def market_route(market_id: str = Query(min_length=1, max_length=200)) -> MarketRouteView:
    return _market_route(_market_by_id(market_id))


@app.post(
    "/api/v1/admin/api-keys",
    response_model=ApiKeyCreateResponse,
    dependencies=[Depends(_require_admin)],
)
def create_commercial_api_key(payload: ApiKeyCreateRequest) -> ApiKeyCreateResponse:
    key_id = str(uuid4())
    raw_token = f"pb_live_{token_urlsafe(32)}"
    ApiKeyStore(_database_path()).create(
        key_id=key_id,
        raw_token=raw_token,
        name=payload.name,
        plan=payload.plan,
        scopes=tuple(payload.scopes),
        daily_limit=payload.daily_limit,
    )
    return ApiKeyCreateResponse(
        key_id=key_id,
        api_key=raw_token,
        plan=payload.plan,
        scopes=list(payload.scopes),
        daily_limit=payload.daily_limit,
        notice="Store this key now. PrediBeacon retains only its SHA-256 hash.",
    )


@app.get(
    "/api/v1/admin/api-keys",
    response_model=list[ApiKeyView],
    dependencies=[Depends(_require_admin)],
)
def list_commercial_api_keys(
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ApiKeyView]:
    return [
        ApiKeyView(
            key_id=item.key_id,
            name=item.name,
            plan=item.plan,
            scopes=list(item.scopes),
            daily_limit=item.daily_limit,
            active=item.active,
            created_at=item.created_at,
            revoked_at=item.revoked_at,
        )
        for item in ApiKeyStore(_database_path()).list_keys(limit)
    ]


@app.delete(
    "/api/v1/admin/api-keys/{key_id}",
    dependencies=[Depends(_require_admin)],
)
def revoke_commercial_api_key(key_id: str) -> dict[str, object]:
    if not ApiKeyStore(_database_path()).revoke(key_id):
        raise HTTPException(status_code=404, detail="active API key not found")
    return {"key_id": key_id, "active": False}


@app.post(
    "/api/v1/admin/api-keys/{key_id}/rotate",
    response_model=ApiKeyCreateResponse,
    dependencies=[Depends(_require_admin)],
)
def rotate_commercial_api_key(key_id: str) -> ApiKeyCreateResponse:
    new_key_id = str(uuid4())
    raw_token = f"pb_live_{token_urlsafe(32)}"
    try:
        item = ApiKeyStore(_database_path()).rotate(
            old_key_id=key_id,
            new_key_id=new_key_id,
            raw_token=raw_token,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="active API key not found") from exc
    return ApiKeyCreateResponse(
        key_id=item.key_id,
        api_key=raw_token,
        plan=item.plan,
        scopes=list(item.scopes),
        daily_limit=item.daily_limit,
        notice="The previous key was revoked atomically. Store this replacement now; only its SHA-256 hash is retained.",
    )


@app.post(
    "/api/v1/admin/campaign-links",
    response_model=CampaignLinkView,
    dependencies=[Depends(_require_admin)],
)
def create_campaign_link(payload: CampaignLinkRequest) -> CampaignLinkView:
    _market_by_id(payload.market_id)
    try:
        item = CampaignLinkStore(_database_path()).create(
            slug=payload.slug,
            market_id=payload.market_id,
            creator_id=payload.creator_id,
            channel=payload.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CampaignLinkView(
        slug=item.slug,
        market_id=item.market_id,
        creator_id=item.creator_id,
        channel=item.channel,
        active=item.active,
        public_url=f"{_public_base_url()}/go/{item.slug}",
    )


@app.get("/go/{slug}")
def campaign_entry(slug: str) -> RedirectResponse:
    item = CampaignLinkStore(_database_path()).get(slug)
    if item is None:
        raise HTTPException(status_code=404, detail="campaign link not found")
    query = {"market_id": item.market_id, "campaign_id": item.slug, "channel": item.channel}
    if item.creator_id:
        query["creator_id"] = item.creator_id
    market = _market_by_id(item.market_id)
    return RedirectResponse(url=f"/markets/{market.slug}?{urlencode({key: value for key, value in query.items() if key != 'market_id'})}", status_code=302)


@app.get("/api/v1/creators/{creator_id}/markets")
def creator_markets(creator_id: str, limit: int = Query(default=50, ge=1, le=100)) -> list[dict[str, object]]:
    links = CampaignLinkStore(_database_path()).for_creator(creator_id, limit)
    by_id = {market.canonical_id: market for market in _DISCOVERY}
    return [
        {
            "campaign": CampaignLinkView(
                slug=item.slug,
                market_id=item.market_id,
                creator_id=item.creator_id,
                channel=item.channel,
                active=item.active,
                public_url=f"{_public_base_url()}/go/{item.slug}",
            ),
            "market": by_id[item.market_id],
        }
        for item in links
        if item.market_id in by_id
    ]


@app.get("/api/v1/market/history", response_model=list[SnapshotPoint])
def market_history(
    market_id: str = Query(min_length=1, max_length=200),
    hours: int = Query(default=168, ge=1, le=8760),
) -> list[SnapshotPoint]:
    _market_by_id(market_id)
    return [
        SnapshotPoint(probability=item.probability, volume_usd=item.volume_usd, observed_at=item.observed_at)
        for item in SnapshotStore(_database_path()).history(market_id, hours=hours)
    ]


@app.get("/api/v1/market/signal", response_model=MarketSignalResponse)
def market_signal(market_id: str = Query(min_length=1, max_length=200)) -> MarketSignalResponse:
    market = _market_by_id(market_id)
    reasons: list[str] = []
    change = market.probability_change
    if change is not None and abs(change) >= .10:
        reasons.append(f"Probability moved {abs(change) * 100:.1f} points in the latest comparison window.")
        label = "rising_fast" if change > 0 else "falling_fast"
    elif market.trend_score >= 75:
        reasons.append(f"PrediBeacon Trend Score is {market.trend_score:.0f}/100.")
        label = "high_attention"
    elif change is None:
        reasons.append("A reliable recent probability comparison is not available yet.")
        label = "insufficient_data"
    else:
        reasons.append(f"Recent probability movement is {abs(change) * 100:.1f} points.")
        label = "watching"
    if market.volume_usd is not None:
        reasons.append(f"Reported venue volume is USD {market.volume_usd:,.0f}.")
    if market.closes_at is not None:
        remaining = (market.closes_at - datetime.now(timezone.utc)).total_seconds()
        if 0 < remaining <= 72 * 3600:
            reasons.append("This market is scheduled to close within 72 hours.")
    return MarketSignalResponse(
        market_id=market_id,
        label=label,
        reasons=reasons,
        generated_at=datetime.now(timezone.utc),
    )


@app.get("/api/v1/market/related", response_model=list[RelatedMarketView])
def related_markets(
    market_id: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=6, ge=1, le=12),
) -> list[RelatedMarketView]:
    market = _market_by_id(market_id)
    title_terms = {term for term in market.title.casefold().split() if len(term) >= 5}
    candidates = []
    for item in _DISCOVERY:
        if item.canonical_id == market_id:
            continue
        overlap = len(title_terms & set(item.title.casefold().split()))
        same_category = bool(market.category and item.category == market.category)
        if overlap or same_category:
            candidates.append((same_category, overlap, item.trend_score, item))
    candidates.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
    results: list[RelatedMarketView] = []
    for same_category, overlap, _, item in candidates[:limit]:
        match = decide_match(
            MarketContractFacts(market.canonical_id, " ".join(market.title.casefold().split()), market.closes_at),
            MarketContractFacts(item.canonical_id, " ".join(item.title.casefold().split()), item.closes_at),
        )
        reasons = list(match.reasons)
        if same_category:
            reasons.append("Markets share a discovery category.")
        if overlap:
            reasons.append(f"Titles share {overlap} meaningful term{'s' if overlap != 1 else ''}.")
        relationship = "related" if same_category or overlap >= 2 else "insufficient_evidence"
        results.append(RelatedMarketView(
            market=item,
            relationship=relationship,
            equivalent_contracts=False,
            reasons=reasons,
        ))
    return results


@app.get("/alerts", response_class=HTMLResponse)
def alerts_page() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "alerts.html"
    return HTMLResponse(
        template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce),
        headers={
            "Cache-Control": "public, max-age=60",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'self'; manifest-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
        },
    )


@app.get("/embed/market", response_class=HTMLResponse)
def market_embed() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "embed.html"
    return HTMLResponse(
        template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce),
        headers={
            "Cache-Control": "public, max-age=60",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; frame-ancestors *; base-uri 'none'; form-action 'none'"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
        },
    )


@app.get("/manifest.webmanifest")
def web_manifest() -> Response:
    body = (Path(__file__).parent / "static" / "manifest.webmanifest").read_text(encoding="utf-8")
    return Response(body, media_type="application/manifest+json", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/icons/predibeacon.svg")
def pwa_icon() -> Response:
    body = (Path(__file__).parent / "static" / "predibeacon-icon.svg").read_text(encoding="utf-8")
    return Response(body, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/service-worker.js")
def service_worker() -> Response:
    body = (Path(__file__).parent / "static" / "service-worker.js").read_text(encoding="utf-8")
    return Response(body, media_type="application/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/top", response_class=HTMLResponse)
def top_markets_page() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "top.html"
    return HTMLResponse(
        template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce),
        headers={
            "Cache-Control": "public, max-age=60",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
        },
    )


@app.get("/creator/{creator_id}", response_class=HTMLResponse)
def creator_page(creator_id: str) -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "creator.html"
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "public, max-age=60",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
        },
    )


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "watchlist.html"
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "public, max-age=60",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


def _render_market_page(market_id: str | None, canonical_path: str | None = None) -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).parent / "templates" / "market.html"
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    body = body.replace("__MARKET_ID__", html.escape(market_id or "", quote=True))
    if market_id:
        market = _market_by_id(market_id)
        canonical = f"{_public_base_url()}{canonical_path or f'/markets/{market.slug}'}"
        seo = (
            f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">'
            f'<meta property="og:type" content="article">'
            f'<meta property="og:title" content="{html.escape(market.title, quote=True)} — PrediBeacon">'
            f'<meta property="og:description" content="Probability, movement, evidence and related prediction markets.">'
            f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">'
        )
        body = body.replace("</head>", f"{seo}</head>")
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "public, max-age=60",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/market", response_class=HTMLResponse)
def market_page(market_id: str | None = Query(default=None, max_length=200)) -> HTMLResponse:
    return _render_market_page(market_id)


@app.get("/markets/{slug}", response_class=HTMLResponse)
def canonical_market_page(slug: str) -> HTMLResponse:
    market = next((item for item in _DISCOVERY if item.slug == slug), None)
    if market is None:
        raise HTTPException(status_code=404, detail="market not found")
    return _render_market_page(market.canonical_id, f"/markets/{slug}")


@app.get("/out/{venue}")
def outbound_redirect(
    venue: Literal["kalshi", "polymarket"],
    request: Request,
    market_id: str = Query(min_length=1, max_length=200),
    campaign_id: str | None = Query(default=None, max_length=100),
    creator_id: str | None = Query(default=None, max_length=100),
    channel: str | None = Query(default=None, max_length=50),
) -> RedirectResponse:
    """Record an owned first-party click before sending the visitor to a venue.

    Commission remains unknown until a partner reports and reconciles it.
    Destination URLs come only from the ingested server-side market record.
    """
    market = _market_by_id(market_id)
    if market.venue != venue or not market.source_url:
        raise HTTPException(status_code=404, detail="outbound route unavailable")
    parsed = urlsplit(market.source_url)
    allowed_hosts = {
        "kalshi": {"kalshi.com", "www.kalshi.com"},
        "polymarket": {"polymarket.com", "www.polymarket.com"},
    }
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed_hosts[venue]:
        raise HTTPException(status_code=409, detail="unverified destination")

    click_id = token_urlsafe(18)
    attribution_id = str(uuid4())
    commercial_verified = os.getenv(
        f"MP_{venue.upper()}_COMMERCIAL_VERIFIED", "false"
    ).strip().casefold() in {"1", "true", "yes", "on"}
    configured_partner = os.getenv(f"MP_{venue.upper()}_PARTNER_ID", "").strip()
    partner_id = configured_partner if commercial_verified and configured_partner else f"{venue}-organic"
    store = RevenueStore(_database_path())
    store.record_click(AttributionRecord(
        attribution_id=attribution_id,
        click_id=click_id,
        partner_id=partner_id,
        venue=venue,
        country="US",
    ))
    store.record_click_context(
        click_id=click_id,
        market_id=market_id,
        campaign_id=campaign_id,
        creator_id=creator_id,
        channel=channel,
        referrer=request.headers.get("referer"),
    )
    return RedirectResponse(
        market.source_url,
        status_code=302,
        headers={"Cache-Control": "no-store", "X-PrediBeacon-Click-ID": click_id},
    )


def _public_static_page(name: str) -> HTMLResponse:
    allowed = {"methodology", "risk", "privacy", "terms"}
    if name not in allowed:
        raise HTTPException(status_code=404, detail="page not found")
    template = Path(__file__).parent / "templates" / f"{name}.html"
    return HTMLResponse(
        template.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "public, max-age=300",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


@app.get("/methodology", response_class=HTMLResponse)
def methodology_page() -> HTMLResponse:
    return _public_static_page("methodology")


@app.get("/risk", response_class=HTMLResponse)
def risk_page() -> HTMLResponse:
    return _public_static_page("risk")


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page() -> HTMLResponse:
    return _public_static_page("privacy")


@app.get("/terms", response_class=HTMLResponse)
def terms_page() -> HTMLResponse:
    return _public_static_page("terms")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    base = _public_base_url()
    return f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"


@app.get("/sitemap.xml")
def sitemap() -> Response:
    base = html.escape(_public_base_url(), quote=True)
    market_urls = "".join(
        f"<url><loc>{base}/markets/{html.escape(item.slug or '', quote=True)}</loc><changefreq>hourly</changefreq></url>"
        for item in _DISCOVERY
        if item.slug
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{base}/</loc><changefreq>hourly</changefreq></url>"
        f"{market_urls}</urlset>"
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
            "name": "PrediBeacon",
            "url": canonical,
            "description": "Prediction market intelligence from public market data.",
        },
        separators=(",", ":"),
    )
    seo = (
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">'
        f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">'
        '<meta property="og:type" content="website">'
        '<meta property="og:title" content="PrediBeacon — Prediction market intelligence">'
        '<meta property="og:description" content="Discover what public prediction markets are pricing now.">'
        f'<script type="application/ld+json">{structured_data}</script>'
    )
    template = Path(__file__).parent / "templates" / "index.html"
    return template.read_text(encoding="utf-8").replace("</head>", f"{seo}</head>")
