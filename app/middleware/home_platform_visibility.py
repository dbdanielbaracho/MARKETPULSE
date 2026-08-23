from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.services.home_card_localization import enhance_home_card_localization
from app.services.home_page_enhancements import enhance_home_template
from app.services.home_experience_v2 import enhance_home_v2
from app.services.home_venue_context import enhance_home_venue_context


def register_home_platform_visibility_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def home_platform_visibility_presentation(request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if request.url.path != "/" or response.status_code != 200 or "text/html" not in content_type:
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

        enhanced = enhance_home_card_localization(
            enhance_home_venue_context(enhance_home_v2(enhance_home_template(body)))
        )
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        return Response(
            content=enhanced,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
