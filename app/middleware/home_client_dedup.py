from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.responses import Response

_SCRIPT = r'''<script>
(() => {
  const normalize = (title) => {
    let s = String(title || '').toLowerCase().replace(/\s+/g, ' ').trim();
    // Collapse explicit threshold ladders used by Kalshi/Polymarket.
    s = s.replace(/\b(above|below|over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?/gi, '$1 <threshold>');
    s = s.replace(/(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?\s*(?=(?:usd|eur|gbp|jpy|cad|aud|btc|eth)(?:\b|\/))/gi, '<threshold> ');
    s = s.replace(/\b\d+(?:\.\d+)?\+\s*(?=(?:hits?|runs?|rbis?|rbi|goals?|assists?|rebounds?|points?|stolen\s+bases?|bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\b)/gi, '<threshold>+ ');
    s = s.replace(/\b(?:over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+\d+(?:\.\d+)?\s*(?=(?:runs?|goals?|points?|yards?|sets?|games?|rounds?)\b)/gi, '<threshold> ');
    s = s.replace(/\b\d[\d,]*(?:\.\d+)?\s*(?=(?:%|°[cf]|degrees?\b|ounces?\b|oz\b|barrels?\b|bbl\b))/gi, '<threshold> ');
    return s.replace(/\s+/g, ' ').trim();
  };

  const numericVolume = (card) => {
    const facts = [...card.querySelectorAll('.fact')];
    const fact = facts.find(f => (f.childNodes[0]?.textContent || '').trim().toLowerCase().startsWith('volume'));
    const text = fact?.querySelector('strong')?.textContent?.trim() || '';
    if (!text) return null;
    const compact = text.replace(/\s/g, '').toUpperCase();
    const match = compact.match(/^(?:US\$|\$)?([0-9]+(?:[.,][0-9]+)?)([KMB])?$/);
    if (!match) return null;
    let value = Number(match[1].replace(',', '.'));
    if (!Number.isFinite(value)) return null;
    if (match[2] === 'K') value *= 1_000;
    if (match[2] === 'M') value *= 1_000_000;
    if (match[2] === 'B') value *= 1_000_000_000;
    return value;
  };

  const dedup = () => {
    const grid = document.querySelector('#grid');
    if (!grid) return;
    const cards = [...grid.querySelectorAll('.card')];
    if (!cards.length) return;
    const seenExact = new Set();
    const seenFamily = new Set();
    let visible = 0;
    for (const card of cards) {
      const title = card.querySelector('h3')?.textContent?.trim() || '';
      const venue = card.querySelector('.venue-badge')?.textContent?.trim().toLowerCase() || '';
      const exact = `${venue}|${title.toLowerCase().replace(/\s+/g,' ')}`;
      const family = `${venue}|${normalize(title)}`;
      const volume = numericVolume(card);
      const inactive = volume !== null && volume <= 0;
      const duplicate = seenExact.has(exact) || seenFamily.has(family);
      const hidden = inactive || duplicate;
      if (card.hidden !== hidden) card.hidden = hidden;
      if (!hidden) {
        seenExact.add(exact);
        seenFamily.add(family);
        visible += 1;
      }
    }
    const count = document.querySelector('#count');
    const desiredCount = visible + (visible === 1 ? ' market' : ' markets');
    if (count && count.textContent !== desiredCount) count.textContent = desiredCount;
    const state = document.querySelector('#state');
    if (state && visible === 0) {
      state.hidden = false;
      state.textContent = 'No actively traded markets match these filters.';
    }
  };

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; dedup(); });
  };

  const boot = () => {
    const grid = document.querySelector('#grid');
    if (!grid) return;
    new MutationObserver(schedule).observe(grid, {childList: true, subtree: true, characterData: true});
    schedule();
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
</script>'''


def register_home_client_dedup_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def home_client_dedup(request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if request.url.path != "/" or response.status_code != 200 or "text/html" not in content_type:
            return response
        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8") for chunk in chunks)
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            return Response(content=raw, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
        if "</body>" in body and "home-client-dedup" not in body:
            body = body.replace("</body>", "<!-- home-client-dedup -->" + _SCRIPT + "</body>")
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(content=body, status_code=response.status_code, headers=headers, media_type=response.media_type)
