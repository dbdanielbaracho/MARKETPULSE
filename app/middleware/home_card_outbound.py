from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response


_SCRIPT = r"""
<script id="predibeacon-home-card-outbound">
(()=>{
  function outboundFor(card){
    const id=card.querySelector('.watch[data-id]')?.dataset.id;
    const badge=card.querySelector('.venue-badge');
    const venue=badge?.classList.contains('kalshi')?'kalshi':badge?.classList.contains('polymarket')?'polymarket':null;
    if(!id||!venue)return null;
    return `/out/${venue}?${new URLSearchParams({market_id:id,channel:'home_card'})}`;
  }
  document.addEventListener('click',event=>{
    const card=event.target.closest?.('.card');
    if(!card||event.target.closest('a,button,input,select,textarea,label'))return;
    const outbound=outboundFor(card);
    if(!outbound)return;
    window.open(outbound,'_blank','noopener,noreferrer');
  });
})();
</script>
"""


def register_home_card_outbound_middleware(app: FastAPI) -> None:
    """Make the non-control area of each discovery card an attributable venue exit.

    The browser never receives or constructs a raw Kalshi/Polymarket destination.
    Every card exit first reaches PrediBeacon's `/out/{venue}` boundary, which
    records attribution and only applies provider commercial identifiers when
    they are explicitly verified/configured. Existing internal analysis/watch
    controls remain internal and do not trigger the external exit.
    """

    @app.middleware("http")
    async def home_card_outbound(request: Request, call_next):
        response = await call_next(request)
        if request.url.path != "/" or response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response

        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8") for chunk in chunks)
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            return Response(
                content=raw,
                status_code=response.status_code,
                headers={key: value for key, value in response.headers.items() if key.lower() != "content-length"},
                media_type=response.media_type,
            )

        if 'id="predibeacon-home-card-outbound"' not in body:
            body = body.replace("</body>", _SCRIPT + "</body>", 1)
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
