from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.services.public_locale import localize_public_html


PUBLIC_LOCALE_PATHS = {"/alerts", "/market"}


def register_public_locale_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def public_locale_presentation(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        content_type = response.headers.get("content-type", "")
        eligible = path in PUBLIC_LOCALE_PATHS or path.startswith("/markets/")
        if not eligible or response.status_code != 200 or "text/html" not in content_type:
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

        localized = localize_public_html(path, body)
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        return Response(
            content=localized,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
