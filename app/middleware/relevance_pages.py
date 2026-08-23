from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.services.relevance_page_enhancements import enhance_relevance_pages


def register_relevance_pages_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def relevance_pages_presentation(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        content_type = response.headers.get("content-type", "")
        if path not in {"/", "/top"} or response.status_code != 200 or "text/html" not in content_type:
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

        enhanced = enhance_relevance_pages(body, path=path)
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        return Response(
            content=enhanced,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
