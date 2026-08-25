from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from starlette.responses import Response

MIN_HOMEPAGE_RELEVANCE = 5.0
MIN_HOMEPAGE_VOLUME_USD = 0.01
MIN_TIME_TO_CLOSE = timedelta(hours=1)
MAX_PER_SUBJECT_PER_VENUE = 2
CURATION_VERSION = "quality-v3"
RENDER_CURATION_VERSION = "prerender-v1"

_THRESHOLD_PATTERNS = (
    re.compile(r"\b(above|below|over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?", re.I),
    re.compile(r"(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?\s*(?=(?:usd|eur|gbp|jpy|cad|aud|btc|eth)(?:\b|/))", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\+\s*(?=(?:hits?|runs?|rbis?|rbi|goals?|assists?|rebounds?|points?|stolen\s+bases?|bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\b)", re.I),
    re.compile(r"\b(?:over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+\d+(?:\.\d+)?\s*(?=(?:runs?|goals?|points?|yards?|sets?|games?|rounds?)\b)", re.I),
    re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*(?=(?:%|°[cf]|degrees?\b|ounces?\b|oz\b|barrels?\b|bbl\b))", re.I),
)
_SUBJECT_SUFFIX = re.compile(
    r"\s*:\s*(?:\d+(?:\.\d+)?\+?\s*)?(?:points?|assists?|rebounds?|threes?|three-pointers?|hits?|runs?|rbis?|goals?|stolen\s+bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\??$",
    re.I,
)

_RENDER_NEEDLE = "const data=await r.json();grid.innerHTML=data.map(card).join('');"
_RENDER_REPLACEMENT = (
    "const rawData=await r.json(),data=window.PrediBeaconHomepageCurate(rawData);"
    "grid.innerHTML=data.map(card).join('');"
)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _family_title(title: str) -> str:
    value = _normalized_text(title)
    value = _THRESHOLD_PATTERNS[0].sub(r"\1 <threshold>", value)
    for pattern in _THRESHOLD_PATTERNS[1:]:
        value = pattern.sub("<threshold> ", value)
    return " ".join(value.split())


def _subject_title(title: str) -> str:
    value = _normalized_text(title)
    stripped = _SUBJECT_SUFFIX.sub("", value).strip()
    return stripped or value


def _parse_closes_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _is_quality_market(item: dict[str, object], *, now: datetime) -> bool:
    title = _normalized_text(item.get("title"))
    venue = _normalized_text(item.get("venue"))
    canonical_id = _normalized_text(item.get("canonical_id"))
    if not title or venue not in {"kalshi", "polymarket"} or not canonical_id:
        return False

    volume = _number(item.get("volume_usd"))
    relevance = _number(item.get("trend_score"))
    if volume is None or volume < MIN_HOMEPAGE_VOLUME_USD:
        return False
    if relevance is None or relevance < MIN_HOMEPAGE_RELEVANCE:
        return False

    probability = item.get("probability")
    if probability is not None:
        parsed_probability = _number(probability)
        if parsed_probability is None or not 0 <= parsed_probability <= 1:
            return False

    closes_at = _parse_closes_at(item.get("closes_at"))
    if closes_at is not None and closes_at <= now + MIN_TIME_TO_CLOSE:
        return False
    return True


def _curate_market_payload(items: list[dict[str, object]], *, now: datetime | None = None) -> list[dict[str, object]]:
    """Fail closed on homepage noise before the browser receives market cards."""
    current = now or datetime.now(timezone.utc)
    curated: list[dict[str, object]] = []
    seen_exact: set[tuple[str, str]] = set()
    seen_family: set[tuple[str, str]] = set()
    subject_counts: Counter[tuple[str, str]] = Counter()

    for item in items:
        if not _is_quality_market(item, now=current):
            continue

        venue = _normalized_text(item.get("venue"))
        title = _normalized_text(item.get("title"))
        exact = (venue, title)
        family = (venue, _family_title(title))
        subject = (venue, _subject_title(title))
        if exact in seen_exact or family in seen_family:
            continue
        if subject_counts[subject] >= MAX_PER_SUBJECT_PER_VENUE:
            continue

        seen_exact.add(exact)
        seen_family.add(family)
        subject_counts[subject] += 1
        curated.append(item)

    return curated


_SCRIPT = r'''<script data-predibeacon-render-curation="prerender-v1">
(() => {
  const text = (value) => String(value || '').toLowerCase().replace(/\s+/g, ' ').trim();
  const family = (title) => {
    let s = text(title);
    s = s.replace(/\b(above|below|over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?/gi, '$1 <threshold>');
    s = s.replace(/(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?\s*(?=(?:usd|eur|gbp|jpy|cad|aud|btc|eth)(?:\b|\/))/gi, '<threshold> ');
    s = s.replace(/\b\d+(?:\.\d+)?\+\s*(?=(?:hits?|runs?|rbis?|rbi|goals?|assists?|rebounds?|points?|stolen\s+bases?|bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\b)/gi, '<threshold>+ ');
    s = s.replace(/\b(?:over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+\d+(?:\.\d+)?\s*(?=(?:runs?|goals?|points?|yards?|sets?|games?|rounds?)\b)/gi, '<threshold> ');
    s = s.replace(/\b\d[\d,]*(?:\.\d+)?\s*(?=(?:%|°[cf]|degrees?\b|ounces?\b|oz\b|barrels?\b|bbl\b))/gi, '<threshold> ');
    return s.replace(/\s+/g, ' ').trim();
  };
  const subject = (title) => {
    const s = text(title);
    return s.replace(/\s*:\s*(?:\d+(?:\.\d+)?\+?\s*)?(?:points?|assists?|rebounds?|threes?|three-pointers?|hits?|runs?|rbis?|goals?|stolen\s+bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\??$/i, '').trim() || s;
  };
  const finiteNumber = (value) => typeof value === 'number' && Number.isFinite(value) ? value : null;
  const quality = (item, now) => {
    if (!item || typeof item !== 'object') return false;
    const title = text(item.title), venue = text(item.venue), id = text(item.canonical_id);
    if (!title || !id || !['kalshi','polymarket'].includes(venue)) return false;
    const volume = finiteNumber(item.volume_usd), relevance = finiteNumber(item.trend_score);
    if (volume === null || volume < 0.01 || relevance === null || relevance < 5) return false;
    if (item.probability != null) {
      const p = finiteNumber(item.probability);
      if (p === null || p < 0 || p > 1) return false;
    }
    if (typeof item.closes_at === 'string' && item.closes_at.trim()) {
      const closes = Date.parse(item.closes_at);
      if (Number.isFinite(closes) && closes <= now + 3600000) return false;
    }
    return true;
  };

  window.PrediBeaconHomepageCurate = (items) => {
    if (!Array.isArray(items)) return [];
    const now = Date.now(), exactSeen = new Set(), familySeen = new Set(), subjectCounts = new Map(), out = [];
    for (const item of items) {
      if (!quality(item, now)) continue;
      const venue = text(item.venue), title = text(item.title);
      const exact = venue + '|' + title, familyKey = venue + '|' + family(title), subjectKey = venue + '|' + subject(title);
      if (exactSeen.has(exact) || familySeen.has(familyKey)) continue;
      if ((subjectCounts.get(subjectKey) || 0) >= 2) continue;
      exactSeen.add(exact);
      familySeen.add(familyKey);
      subjectCounts.set(subjectKey, (subjectCounts.get(subjectKey) || 0) + 1);
      out.push(item);
    }
    return out;
  };

  // Defense in depth only. Primary enforcement happens before grid.innerHTML via
  // PrediBeaconHomepageCurate. This catches future DOM writers that bypass load().
  const auditDom = () => {
    const grid = document.querySelector('#grid');
    if (!grid) return;
    const seen = new Set();
    for (const card of grid.querySelectorAll('.card')) {
      const title = card.querySelector('h3')?.textContent || '';
      const venue = card.querySelector('.venue-badge')?.textContent?.trim().toLowerCase() || '';
      const key = venue + '|' + family(title);
      if (seen.has(key)) card.hidden = true;
      else if (!card.hidden) seen.add(key);
    }
  };
  const grid = document.querySelector('#grid');
  if (grid) new MutationObserver(auditDom).observe(grid, {childList:true, subtree:true});
})();
</script>'''


def register_home_client_dedup_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def home_client_dedup(request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        is_home = request.url.path == "/" and response.status_code == 200 and "text/html" in content_type
        is_market_api = request.url.path == "/api/v1/markets" and response.status_code == 200 and "application/json" in content_type
        if not is_home and not is_market_api:
            return response

        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8") for chunk in chunks)
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}

        if is_market_api:
            try:
                payload = json.loads(raw)
                if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
                    input_count = len(payload)
                    curated = _curate_market_payload(payload)
                    raw = json.dumps(curated, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                    headers["X-PrediBeacon-Curation"] = CURATION_VERSION
                    headers["X-PrediBeacon-Curation-Input"] = str(input_count)
                    headers["X-PrediBeacon-Curation-Output"] = str(len(curated))
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            return Response(content=raw, status_code=response.status_code, headers=headers, media_type=response.media_type)

        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            return Response(content=raw, status_code=response.status_code, headers=headers, media_type=response.media_type)

        rewritten = _RENDER_NEEDLE in body
        if rewritten:
            body = body.replace(_RENDER_NEEDLE, _RENDER_REPLACEMENT, 1)
        injected = "data-predibeacon-render-curation" in body
        if not injected and "<script>" in body:
            body = body.replace("<script>", "<!-- home-prerender-curation -->" + _SCRIPT + "<script>", 1)
            injected = True

        headers["X-PrediBeacon-Render-Curation"] = (
            RENDER_CURATION_VERSION if rewritten and injected else "missing"
        )
        return Response(content=body, status_code=response.status_code, headers=headers, media_type=response.media_type)
