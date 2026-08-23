from __future__ import annotations

import html
import os
import re
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import Response


_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_DESCRIPTION_RE = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']\s*/?>',
    re.IGNORECASE | re.DOTALL,
)


def _public_base_url() -> str:
    value = os.getenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return "https://predibeacon.com"
    return value


def _text(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def _inject_metadata(body: str, canonical: str) -> str:
    if "</head>" not in body.lower():
        return body

    title_match = _TITLE_RE.search(body)
    description_match = _DESCRIPTION_RE.search(body)
    title = _text(title_match.group(1)) if title_match else "PrediBeacon"
    description = (
        _text(description_match.group(1))
        if description_match
        else "PrediBeacon ranks and explains prediction-market signals from Kalshi and Polymarket."
    )
    escaped_title = html.escape(title, quote=True)
    escaped_description = html.escape(description, quote=True)
    escaped_canonical = html.escape(canonical, quote=True)

    tags = (
        f'<link rel="canonical" href="{escaped_canonical}">'
        '<meta property="og:type" content="website">'
        f'<meta property="og:site_name" content="PrediBeacon">'
        f'<meta property="og:title" content="{escaped_title}">'
        f'<meta property="og:description" content="{escaped_description}">'
        f'<meta property="og:url" content="{escaped_canonical}">'
        '<meta name="twitter:card" content="summary">'
        f'<meta name="twitter:title" content="{escaped_title}">'
        f'<meta name="twitter:description" content="{escaped_description}">'
    )
    return re.sub(r"</head>", tags + "</head>", body, count=1, flags=re.IGNORECASE)


def register_public_seo_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def public_seo(request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        path = request.url.path
        if (
            response.status_code != 200
            or "text/html" not in content_type
            or path.startswith("/admin")
            or path.startswith("/embed")
            or path == "/market"
        ):
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

        if 'rel="canonical"' not in body.casefold():
            canonical = _public_base_url() + (path if path != "/" else "/")
            body = _inject_metadata(body, canonical)

        headers = {key: value for key, value in response.headers.items() if key.lower() != "content-length"}
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
