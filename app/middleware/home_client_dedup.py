from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.services.intelligence import attention_score
from app.services.ranking import activity_confidence

MIN_HOMEPAGE_RELEVANCE = 5.0
MIN_HOMEPAGE_VOLUME_USD = 100.0
MIN_FALLBACK_VOLUME_USD = 1000.0
MIN_TIME_TO_CLOSE = timedelta(hours=1)
MAX_PER_SUBJECT_PER_VENUE = 2
CURATION_VERSION = "quality-v6"
RENDER_CURATION_VERSION = "prerender-v5"
INTELLIGENCE_RANKING_VERSION = "server-ranking-v1"

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
_TOP_ATTENTION_NEEDLE = "function attention(m){let s=Math.max(0,Math.min(70,(m.trend_score||0)*.7));const move=Math.abs((m.probability_change||0)*100),vol=m.volume_usd||0,h=hoursLeft(m);s+=Math.min(15,move*.75);if(vol>=100000)s+=10;else if(vol>=10000)s+=6;else if(vol>0)s+=2;if(h!=null&&h>0&&h<=72)s+=5;return Math.round(Math.min(100,s))}"
_TOP_ATTENTION_REPLACEMENT = "function attention(m){return Number.isFinite(m.attention_score)?m.attention_score:0}"
_TOP_SMART_NEEDLE = "const smart=[...data].sort((a,b)=>(attention(b)+Math.abs(b.probability_change||0)*100)-(attention(a)+Math.abs(a.probability_change||0)*100)).filter(x=>Math.abs(x.probability_change||0)>=.02||attention(x)>=70).slice(0,6);"
_TOP_SMART_REPLACEMENT = "const smart=[...data].sort((a,b)=>attention(b)-attention(a)).filter(x=>attention(x)>=35).slice(0,6);"


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
    current = now or datetime.now(timezone.utc)
    strict = [item for item in items if _is_quality_market(item, now=current)]
    candidates = strict or [item for item in items if _is_fallback_quality_market(item, now=current)]
    return _deduplicate(candidates)


def _enrich_ranking(item: dict[str, object], *, now: datetime) -> dict[str, object]:
    enriched = dict(item)
    volume = _number(item.get("volume_usd"))
    change = _number(item.get("probability_change"))
    trend = _number(item.get("trend_score")) or 0.0
    closes_at = _parse_closes_at(item.get("closes_at"))
    hours_to_close = None if closes_at is None else (closes_at - now).total_seconds() / 3600
    enriched["activity_confidence"] = round(activity_confidence(volume), 4)
    enriched["attention_score"] = attention_score(
        trend_score_value=trend,
        probability_change_value=change,
        volume_usd=volume,
        hours_to_close=hours_to_close,
    )
    return enriched


_SCRIPT = r'''<script data-predibeacon-render-curation="prerender-v5">
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
  const strictQuality = (item, now) => baseQuality(item, now, 100) && item.trend_score >= 5;
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
        is_top = request.url.path == "/top" and response.status_code == 200 and "text/html" in content_type
        if not is_home and not is_top:
            return response
        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8") for chunk in chunks)
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            return Response(content=raw, status_code=response.status_code, headers=headers, media_type=response.media_type)
        if is_top:
            attention_rewritten = _TOP_ATTENTION_NEEDLE in body
            smart_rewritten = _TOP_SMART_NEEDLE in body
            if attention_rewritten:
                body = body.replace(_TOP_ATTENTION_NEEDLE, _TOP_ATTENTION_REPLACEMENT, 1)
            if smart_rewritten:
                body = body.replace(_TOP_SMART_NEEDLE, _TOP_SMART_REPLACEMENT, 1)
            headers["X-PrediBeacon-Intelligence-Ranking"] = INTELLIGENCE_RANKING_VERSION if attention_rewritten and smart_rewritten else "missing"
            return Response(content=body, status_code=response.status_code, headers=headers, media_type=response.media_type)
        rewritten = _RENDER_NEEDLE in body
        if rewritten:
            body = body.replace(_RENDER_NEEDLE, _RENDER_REPLACEMENT, 1)
        injected = "data-predibeacon-render-curation" in body
        if not injected and "<script>" in body:
            body = body.replace("<script>", "<!-- home-prerender-curation -->" + _SCRIPT + "<script>", 1)
            injected = True
        headers["X-PrediBeacon-Render-Curation"] = RENDER_CURATION_VERSION if rewritten and injected else "missing"
        return Response(content=body, status_code=response.status_code, headers=headers, media_type=response.media_type)
