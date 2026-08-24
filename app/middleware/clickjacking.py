from __future__ import annotations

from fastapi import FastAPI, Request


_EMBED_PREFIX = "/embed/"


def register_clickjacking_middleware(app: FastAPI) -> None:
    """Deny cross-site framing everywhere except the explicit embed surface.

    PrediBeacon's normal pages are not intended to be framed. The dedicated
    `/embed/` surface is intentionally embeddable and owns its framing policy
    through its route-level Content-Security-Policy (`frame-ancestors *`).
    """

    @app.middleware("http")
    async def clickjacking_boundary(request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith(_EMBED_PREFIX):
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response
