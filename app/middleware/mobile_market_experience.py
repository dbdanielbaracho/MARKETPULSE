from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.responses import Response


_MOBILE_CSS = """
<style>
@media (max-width:720px){
  body{padding-bottom:76px}
  main.wrap{padding-top:1.25rem}
  h1{font-size:clamp(1.8rem,9vw,2.65rem);overflow-wrap:anywhere}
  .panel{border-radius:14px;padding:1rem;margin:.85rem 0}
  .prob{font-size:clamp(2.8rem,16vw,4.25rem)}
  .stats,.crossgrid{grid-template-columns:1fr 1fr}
  .actions{display:grid;grid-template-columns:1fr;gap:.6rem}
  .button{width:100%;min-height:52px;justify-content:center}
  #outbound{position:sticky;bottom:84px;z-index:20;box-shadow:0 8px 28px rgba(0,0,0,.35)}
  .pb-mobile-nav{position:fixed;left:0;right:0;bottom:0;z-index:50;display:grid;grid-template-columns:repeat(4,1fr);background:#090d14f2;border-top:1px solid #273244;padding:max(.45rem,env(safe-area-inset-bottom)) .4rem .45rem;backdrop-filter:blur(14px)}
  .pb-mobile-nav a{display:flex;min-height:48px;align-items:center;justify-content:center;text-align:center;text-decoration:none;font-size:.78rem;font-weight:800;color:#d6deea;border-radius:10px}
  .pb-mobile-nav a:focus-visible{outline:3px solid #8be9c7;outline-offset:2px}
  .pb-partner-note{font-size:.78rem;line-height:1.45;color:#aab4c3;margin:.75rem 0 0}
}
@media (min-width:721px){.pb-mobile-nav{display:none}.pb-partner-note{font-size:.8rem;color:#aab4c3}}
@media (max-width:420px){.stats,.crossgrid{grid-template-columns:1fr}}
</style>
"""

_MOBILE_NAV = """
<nav class="pb-mobile-nav" aria-label="Mobile navigation">
<a href="/">Home</a><a href="/#markets">Explore</a><a href="/watchlist">Watchlist</a><a href="/alerts">Alerts</a>
</nav>
"""

_DISCLOSURE = (
    '<p class="pb-partner-note">PrediBeacon may receive compensation from approved partners when you use an external-platform link. '
    'Market probabilities, ranking and comparison are not adjusted based on partner compensation.</p>'
)


def register_mobile_market_experience_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def mobile_market_experience(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if response.status_code != 200 or not (path == "/market" or path.startswith("/markets/")):
            return response
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response
        body = b"".join([chunk async for chunk in response.body_iterator]).decode("utf-8")
        if "pb-mobile-nav" not in body:
            body = body.replace("</head>", _MOBILE_CSS + "</head>")
            body = body.replace(
                '<p class="notice">PrediBeacon provides intelligence and routing. Trades occur only on the external platform.</p>',
                '<p class="notice">PrediBeacon provides intelligence and routing. Trades occur only on the external platform.</p>' + _DISCLOSURE,
            )
            body = body.replace("</body>", _MOBILE_NAV + "</body>")
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(content=body, status_code=response.status_code, headers=headers, media_type="text/html")
