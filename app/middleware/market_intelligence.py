from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.services.market_page_enhancements import enhance_market_template


def register_market_intelligence_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def market_intelligence_presentation(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        is_market_page = path == "/market" or path.startswith("/markets/")
        content_type = response.headers.get("content-type", "")
        if not is_market_page or response.status_code != 200 or "text/html" not in content_type:
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

        enhanced = enhance_market_template(body)
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        return Response(
            content=enhanced,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
