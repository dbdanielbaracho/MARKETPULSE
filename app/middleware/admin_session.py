from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.services.admin_session import COOKIE_NAME, read_session


def register_admin_session_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def admin_session_middleware(request: Request, call_next):
        path = request.url.path
        hostname = (request.url.hostname or "").casefold()

        # Support a dedicated admin.predibeacon.com host as soon as DNS points to
        # this service, without coupling public navigation to the admin surface.
        if hostname == "admin.predibeacon.com" and path == "/":
            return RedirectResponse("/admin", status_code=307)

        session = read_session(request.cookies.get(COOKIE_NAME))

        if path == "/admin":
            destination = "/admin/dashboard" if session else "/admin/login"
            return RedirectResponse(destination, status_code=307)

        if path.startswith("/admin/") and path != "/admin/login" and not session:
            next_path = quote(path, safe="/?:=&")
            return RedirectResponse(f"/admin/login?next={next_path}", status_code=307)

        # Existing APIs continue to use the hardened server-side token dependency.
        # A valid browser session is translated to that credential internally, so
        # the operator never needs to paste the token into the UI.
        if path.startswith("/api/v1/admin/") and path != "/api/v1/admin/session" and session:
            headers = list(request.scope.get("headers", []))
            if not any(name.lower() == b"x-marketpulse-admin-token" for name, _ in headers):
                token = os.getenv("MP_ADMIN_TOKEN", "").strip()
                if token:
                    headers.append((b"x-marketpulse-admin-token", token.encode("utf-8")))
            if not any(name.lower() == b"x-predibeacon-admin-actor" for name, _ in headers):
                headers.append((b"x-predibeacon-admin-actor", str(session["email"]).encode("utf-8")))
            request.scope["headers"] = headers

        return await call_next(request)
