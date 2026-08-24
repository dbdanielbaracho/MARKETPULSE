from __future__ import annotations

from pathlib import Path
from secrets import token_urlsafe

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.services.admin_session import (
    COOKIE_NAME,
    admin_config_status,
    admin_email,
    issue_session,
    read_session,
    two_factor_enabled,
    verify_credentials,
)

router = APIRouter()


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=512)
    totp_code: str | None = Field(default=None, max_length=12)


def _secure_html(filename: str) -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).resolve().parents[1] / "templates" / filename
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'self' data:; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


@router.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
def admin_login_page() -> HTMLResponse:
    return _secure_html("admin_login.html")


@router.get("/admin/dashboard", response_class=HTMLResponse, include_in_schema=False)
def admin_dashboard_page() -> HTMLResponse:
    return _secure_html("admin_dashboard.html")


@router.get("/admin/editorial", response_class=HTMLResponse, include_in_schema=False)
def admin_editorial_page() -> HTMLResponse:
    return _secure_html("admin.html")


@router.get("/admin/insights", response_class=HTMLResponse, include_in_schema=False)
def admin_insights_page() -> HTMLResponse:
    return _secure_html("admin_insights.html")


@router.get("/api/v1/admin/session")
def admin_session_status(request: Request) -> dict[str, object]:
    session = read_session(request.cookies.get(COOKIE_NAME))
    config = admin_config_status()
    return {
        "authenticated": bool(session),
        "email": session.get("email") if session else config["configured_email"],
        "two_factor_enabled": config["two_factor_enabled"],
        "configuration": {
            "password_configured": config["password_configured"],
            "password_valid_length": config["password_valid_length"],
            "session_signing_configured": config["session_signing_configured"],
        },
    }


@router.post("/api/v1/admin/session")
def create_admin_session(payload: AdminLoginRequest) -> JSONResponse:
    if not verify_credentials(payload.email, payload.password, payload.totp_code):
        return JSONResponse({"detail": "Invalid administrator credentials"}, status_code=401)
    try:
        signed = issue_session(payload.email)
    except RuntimeError:
        return JSONResponse({"detail": "Administrator session is not configured"}, status_code=503)
    response = JSONResponse({
        "authenticated": True,
        "email": payload.email.strip().casefold(),
        "two_factor_enabled": two_factor_enabled(),
    })
    response.set_cookie(
        COOKIE_NAME,
        signed,
        max_age=8 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return response


@router.delete("/api/v1/admin/session")
def delete_admin_session() -> JSONResponse:
    response = JSONResponse({"authenticated": False, "email": admin_email()})
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return response
