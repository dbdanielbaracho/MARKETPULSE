from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.services.public_locale import DEFAULT_LOCALE, normalize_locale


router = APIRouter()


def _request_is_https(request: Request) -> bool:
    if request.url.scheme.casefold() == "https":
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return forwarded_proto.split(",", 1)[0].strip().casefold() == "https"


@router.get("/set-language", include_in_schema=False)
def set_language(
    request: Request,
    lang: str = Query(default=DEFAULT_LOCALE, max_length=16),
    next: str = Query(default="/", max_length=500),
) -> RedirectResponse:
    locale = normalize_locale(lang)
    destination = next if next.startswith("/") and not next.startswith("//") else "/"
    response = RedirectResponse(destination, status_code=303)
    response.set_cookie(
        "predibeacon_lang",
        locale,
        max_age=365 * 24 * 60 * 60,
        samesite="lax",
        httponly=True,
        secure=_request_is_https(request),
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response
