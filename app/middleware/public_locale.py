from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.services.public_locale import DEFAULT_LOCALE, localize_public_html, normalize_locale
from app.services.public_locale_extended import extend_public_translation
from app.services.public_locale_trust import translate_trust_page


PUBLIC_LOCALE_PATHS = {
    "/",
    "/top",
    "/watchlist",
    "/alerts",
    "/articles",
    "/methodology",
    "/risk",
    "/privacy",
    "/terms",
    "/market",
}


def _eligible(path: str) -> bool:
    return (
        path in PUBLIC_LOCALE_PATHS
        or path.startswith("/markets/")
        or path.startswith("/articles/")
        or path.startswith("/creator/")
    )


def register_public_locale_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def public_locale_presentation(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        content_type = response.headers.get("content-type", "")
        if not _eligible(path) or response.status_code != 200 or "text/html" not in content_type:
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

        locale = normalize_locale(request.cookies.get("predibeacon_lang") or DEFAULT_LOCALE)
        localized = localize_public_html(path, body, locale)
        localized = extend_public_translation(path, localized, locale)
        localized = translate_trust_page(path, localized, locale)
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        headers["Content-Language"] = locale
        vary = headers.get("Vary", "")
        vary_values = {item.strip() for item in vary.split(",") if item.strip()}
        vary_values.add("Cookie")
        headers["Vary"] = ", ".join(sorted(vary_values))
        return Response(
            content=localized,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
