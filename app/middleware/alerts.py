from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.services.alert_page_enhancements import enhance_alerts_template
from app.services.push_alert_page import enhance_push_alerts_template


def register_alerts_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def smart_alerts_presentation(request: Request, call_next):
        response = await call_next(request)
        if request.url.path != "/alerts" or response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            return response
        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8") for chunk in chunks)
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            body = None
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        if body is None:
            return Response(content=raw, status_code=response.status_code, headers=headers, media_type=response.media_type)
        enhanced = enhance_alerts_template(body)
        enhanced = enhance_push_alerts_template(enhanced)
        return Response(
            content=enhanced,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
