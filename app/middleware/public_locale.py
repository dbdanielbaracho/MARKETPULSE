from __future__ import annotations

from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.services.locale_number_time import localize_market_formatting
from app.services.public_locale import DEFAULT_LOCALE, localize_public_html, normalize_locale
from app.services.public_locale_extended import extend_public_translation
from app.services.public_locale_legal import translate_legal_page
from app.services.public_locale_trust import translate_trust_page
from app.services.public_locale_content import translate_content_shell


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


def _preserve_selector_query(localized: str, request: Request) -> str:
    if not request.url.query or 'class="pb-lang"' not in localized:
        return localized
    safe = "/?=&%:-"
    plain_next = quote(request.url.path, safe=safe)
    full_next = quote(f"{request.url.path}?{request.url.query}", safe=safe)
    return localized.replace(f"&next={plain_next}\"", f"&next={full_next}\"")


def _map_browser_language(tag: str) -> str | None:
    normalized = tag.strip().replace("_", "-").casefold()
    if not normalized or normalized == "*":
        return None
    if normalized.startswith("pt"):
        return "pt-BR"
    if normalized.startswith("es"):
        return "es"
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("fr"):
        return "fr"
    if normalized.startswith("de"):
        return "de"
    if normalized.startswith("it"):
        return "it"
    if normalized.startswith("ja"):
        return "ja"
    if normalized.startswith("ko"):
        return "ko"
    if normalized.startswith("ar"):
        return "ar"
    if normalized.startswith("zh"):
        return "zh-CN"
    return None


def _locale_from_accept_language(header: str | None) -> str:
    if not header:
        return DEFAULT_LOCALE

    ranked: list[tuple[float, int, str]] = []
    for index, item in enumerate(header.split(",")):
        parts = [part.strip() for part in item.split(";") if part.strip()]
        if not parts:
            continue
        language = parts[0]
        quality = 1.0
        for parameter in parts[1:]:
            if not parameter.lower().startswith("q="):
                continue
            try:
                quality = float(parameter.split("=", 1)[1])
            except ValueError:
                quality = 0.0
        if quality <= 0:
            continue
        mapped = _map_browser_language(language)
        if mapped:
            ranked.append((quality, -index, mapped))

    if not ranked:
        return DEFAULT_LOCALE
    ranked.sort(reverse=True)
    return ranked[0][2]


def _resolve_locale(cookie_locale: str | None, accept_language: str | None) -> str:
    if cookie_locale:
        return normalize_locale(cookie_locale)
    return _locale_from_accept_language(accept_language)


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

        locale = _resolve_locale(
            request.cookies.get("predibeacon_lang"),
            request.headers.get("accept-language"),
        )
        localized = localize_public_html(path, body, locale)
        localized = extend_public_translation(path, localized, locale)
        localized = translate_legal_page(path, localized, locale)
        localized = translate_trust_page(path, localized, locale)
        localized = translate_content_shell(path, localized, locale)
        localized = localize_market_formatting(path, localized)
        localized = _preserve_selector_query(localized, request)
        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        headers["Content-Language"] = locale
        vary = headers.get("Vary", "")
        vary_values = {item.strip() for item in vary.split(",") if item.strip()}
        vary_values.add("Cookie")
        vary_values.add("Accept-Language")
        headers["Vary"] = ", ".join(sorted(vary_values))
        return Response(
            content=localized,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
