from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.domain.evidence import EvidenceItem, EvidenceKind

MAX_FEED_BYTES = 1_000_000
MAX_ITEMS_PER_FEED = 50
_ALLOWED_HOSTS = {"www.federalreserve.gov", "www.sec.gov"}
_TAG_RE = re.compile(r"<[^>]+>")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "the", "to", "will", "with",
    "yes", "no", "happen", "market",
}
_ALIASES = {
    "fed": {"federal", "reserve"},
    "fomc": {"federal", "reserve", "monetary", "policy"},
    "sec": {"securities", "exchange", "commission"},
}


class MarketLike(Protocol):
    canonical_id: str
    title: str


@dataclass(frozen=True)
class FeedSource:
    publisher: str
    url: str


DEFAULT_OFFICIAL_FEEDS = (
    FeedSource("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    FeedSource("Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    FeedSource("U.S. Securities and Exchange Commission", "https://www.sec.gov/news/pressreleases.rss"),
    FeedSource("U.S. Securities and Exchange Commission", "https://www.sec.gov/news/speeches-statements.rss"),
)


def _validate_source(source: FeedSource) -> None:
    parsed = urlsplit(source.url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _ALLOWED_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("official feed URL must use an allowlisted HTTPS origin")


def _text(node: ET.Element, names: tuple[str, ...]) -> str | None:
    for child in node.iter():
        name = child.tag.rsplit("}", 1)[-1].casefold()
        if name in names and child.text and child.text.strip():
            return child.text.strip()
    return None


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    cleaned = " ".join(unescape(_TAG_RE.sub(" ", value)).split())
    return cleaned[:limit].rstrip() or None


def parse_feed(payload: bytes, source: FeedSource, retrieved_at: datetime) -> list[EvidenceItem]:
    _validate_source(source)
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("official feed exceeds size limit")
    root = ET.fromstring(payload)
    entries = [
        node for node in root.iter()
        if node.tag.rsplit("}", 1)[-1].casefold() in {"item", "entry"}
    ][:MAX_ITEMS_PER_FEED]
    items: list[EvidenceItem] = []
    for entry in entries:
        title = _clean(_text(entry, ("title",)), 300)
        url = _text(entry, ("link",))
        if url is None:
            link = next((node for node in entry.iter() if node.tag.rsplit("}", 1)[-1].casefold() == "link"), None)
            url = link.attrib.get("href") if link is not None else None
        if not title or not url:
            continue
        parsed_url = urlsplit(url)
        if parsed_url.scheme != "https" or parsed_url.hostname != urlsplit(source.url).hostname:
            continue
        published = _date(_text(entry, ("pubdate", "published", "updated", "date")))
        summary = _clean(_text(entry, ("description", "summary", "content")), 1200)
        items.append(EvidenceItem(
            title=title,
            url=url,
            publisher=source.publisher,
            kind=EvidenceKind.OFFICIAL,
            published_at=published,
            retrieved_at=retrieved_at,
            summary=summary,
        ))
    return items


def _tokens(value: str) -> set[str]:
    tokens = {token for token in _TOKEN_RE.findall(value.casefold()) if len(token) >= 3 and token not in _STOPWORDS}
    for token in tuple(tokens):
        tokens.update(_ALIASES.get(token, set()))
    return tokens


def associate(markets: list[MarketLike], evidence: list[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
    result: dict[str, list[EvidenceItem]] = {}
    for market in markets:
        market_tokens = _tokens(market.title)
        matches = []
        for item in evidence:
            candidate_tokens = _tokens(f"{item.title} {item.summary or ''}")
            if len(market_tokens & candidate_tokens) >= 2:
                matches.append(item)
        if matches:
            result[market.canonical_id] = matches[:5]
    return result


class OfficialFeedCollector:
    def __init__(self, *, sources: tuple[FeedSource, ...] = DEFAULT_OFFICIAL_FEEDS, client: httpx.AsyncClient | None = None):
        for source in sources:
            _validate_source(source)
        self.sources = sources
        self.client = client

    async def collect(self, markets: list[MarketLike]) -> tuple[dict[str, list[EvidenceItem]], tuple[str, ...]]:
        evidence: list[EvidenceItem] = []
        errors: list[str] = []
        retrieved_at = datetime.now(timezone.utc)
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=8, follow_redirects=False, headers={"User-Agent": "MarketPulse/0.8 evidence collector"})
        try:
            for source in self.sources:
                try:
                    response = await client.get(source.url)
                    response.raise_for_status()
                    content_length = int(response.headers.get("content-length", "0"))
                    if content_length > MAX_FEED_BYTES:
                        raise ValueError("official feed exceeds size limit")
                    evidence.extend(parse_feed(response.content, source, retrieved_at))
                except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
                    errors.append(f"{source.publisher}:{type(exc).__name__}")
        finally:
            if owns_client:
                await client.aclose()
        return associate(markets, evidence), tuple(errors)
