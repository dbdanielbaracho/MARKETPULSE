from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from starlette.responses import Response

MIN_HOMEPAGE_RELEVANCE = 5.0
MIN_HOMEPAGE_VOLUME_USD = 0.01
MIN_FALLBACK_VOLUME_USD = 1000.0
MIN_TIME_TO_CLOSE = timedelta(hours=1)
MAX_PER_SUBJECT_PER_VENUE = 2
CURATION_VERSION = "quality-v4"
RENDER_CURATION_VERSION = "prerender-v3"

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

_RENDER_NEEDLE = (
    "const data=await r.json();"
    "if(seq!==discoveryLoadSeq)return;"
    "grid.innerHTML=data.map(card).join('');"
)
_RENDER_REPLACEMENT = (
    "const rawData=await r.json();"
    "if(seq!==discoveryLoadSeq)return;"
    "const data=window.PrediBeaconHomepageCurate(rawData);"
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


def _base_quality_market(item: dict[str, object], *, now: datetime, min_volume: float) -> bool:
    title = _normalized_text(item.get("title"))
    venue = _normalized_text(item.get("venue"))
    canonical_id = _normalized_text(item.get("canonical_id"))
    if not title or venue not in {"kalshi", "polymarket"} or not canonical_id:
        return False
    volume = _number(item.get("volume_usd"))
    trend = _number(item.get("trend_score"))
    if volume is None or volume < min_volume or trend is None or trend < 0:
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


def _is_quality_market(item: dict[str, object], *, now: datetime) -> bool:
    if not _base_quality_market(item, now=now, min_volume=MIN_HOMEPAGE_VOLUME_USD):
        return False
    trend = _number(item.get("trend_score"))
    return trend is not None and trend >= MIN_HOMEPAGE_RELEVANCE


def _is_fallback_quality_market(item: dict[str, object], *, now: datetime) -> bool:
    """Keep the default discovery useful during quiet snapshots without re-admitting noise.

    trend_score measures recent movement/activity, not contract validity. A refresh can
    legitimately make every trend score zero. Only when the strict pool is exhausted,
    allow materially active (>= $1k reported volume), valid, non-imminent contracts.
    """
    return _base_quality_market(item, now=now, min_volume=MIN_FALLBACK_VOLUME_USD)


def _deduplicate(items: list[dict[str, object]]) -> list[dict[str, object]]:
    curated: list[dict[str, object]] = []
    seen_exact: set[tuple[str, str]] = set()
    seen_family: set[tuple[str, str]] = set()
    subject_counts: Counter[tuple[str, str]] = Counter()
    for item in items:
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


def _curate_market_payload(items: list[dict[str, object]], *, now: datetime | None = None) -> list[dict[str, object]]:
    """Fail closed on noise, but never confuse a quiet snapshot with invalid markets."""
    current = now or datetime.now(timezone.utc)
    strict = [item for item in items if _is_quality_market(item, now=current)]
    candidates = strict or [item for item in items if _is_fallback_quality_market(item, now=current)]
    return _deduplicate(candidates)


_SCRIPT = r'''<script data-predibeacon-render-curation="prerender-v3">
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
  const baseQuality = (item, now, minVolume) => {
    if (!item || typeof item !== 'object') return false;
    const title = text(item.title), venue = text(item.venue), id = text(item.canonical_id);
    if (!title || !id || !['kalshi','polymarket'].includes(venue)) return false;
    const volume = finiteNumber(item.volume_usd), trend = finiteNumber(item.trend_score);
    if (volume === null || volume < minVolume || trend === null || trend < 0) return false;
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
  const strictQuality = (item, now) => baseQuality(item, now, 0.01) && item.trend_score >= 5;
  const fallbackQuality = (item, now) => baseQuality(item, now, 1000);
  const dedup = (items) => {
    const exactSeen = new Set(), familySeen = new Set(), subjectCounts = new Map(), out = [];
    for (const item of items) {
      const venue = text(item.venue), title = text(item.title);
      const exact = venue + '|' + title, familyKey = venue + '|' + family(title), subjectKey = venue + '|' + subject(title);
      if (exactSeen.has(exact) || familySeen.has(familyKey)) continue;
      if ((subjectCounts.get(subjectKey) || 0) >= 2) continue;
      exactSeen.add(exact); familySeen.add(familyKey);
      subjectCounts.set(subjectKey, (subjectCounts.get(subjectKey) || 0) + 1);
      out.push(item);
    }
    return out;
  };
  window.PrediBeaconHomepageCurate = (items) => {
    if (!Array.isArray(items)) return [];
    const now = Date.now();
    const strict = items.filter(item => strictQuality(item, now));
    return dedup(strict.length ? strict : items.filter(item => fallbackQuality(item, now)));
  };
  const auditDom = () => {
    const grid = document.querySelector('#grid');
    if (!grid) return;
    const cards = [...grid.querySelectorAll('.card')], seen = new Set();
    for (const card of cards) {
      const title = card.querySelector('h3')?.textContent || '';
      const venue = card.querySelector('.venue-badge')?.textContent?.trim().toLowerCase() || '';
      const key = venue + '|' + family(title);
      if (seen.has(key)) card.hidden = true; else if (!card.hidden) seen.add(key);
    }
    const visible = cards.filter(card => !card.hidden).length;
    if (cards.length && visible !== cards.length) {
      const count = document.querySelector('#count');
      if (count) count.textContent = visible + (visible === 1 ? ' market' : ' markets');
      const state = document.querySelector('#state');
      if (state) {
        state.hidden = visible > 0;
        if (!visible) {
          const pt = (document.documentElement.lang || '').toLowerCase().startsWith('pt');
          state.textContent = pt ? 'Nenhum mercado elegível corresponde a estes filtros.' : 'No quality-eligible markets match these filters.';
        }
      }
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
                    strict_count = sum(_is_quality_market(item, now=datetime.now(timezone.utc)) for item in payload)
                    curated = _curate_market_payload(payload)
                    raw = json.dumps(curated, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                    headers["X-PrediBeacon-Curation"] = CURATION_VERSION
                    headers["X-PrediBeacon-Curation-Input"] = str(input_count)
                    headers["X-PrediBeacon-Curation-Output"] = str(len(curated))
                    headers["X-PrediBeacon-Curation-Mode"] = "strict" if strict_count else "quiet-market-fallback"
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
        headers["X-PrediBeacon-Render-Curation"] = RENDER_CURATION_VERSION if rewritten and injected else "missing"
        return Response(content=body, status_code=response.status_code, headers=headers, media_type=response.media_type)
