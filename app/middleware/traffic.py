from __future__ import annotations

import os

from fastapi import FastAPI, Request

from app.storage.traffic import TrafficStore


_STATIC_SURFACES = {
    "/": "home",
    "/top": "intelligence",
    "/watchlist": "watchlist",
    "/alerts": "alerts",
    "/articles": "articles",
    "/methodology": "methodology",
    "/risk": "risk",
    "/privacy": "privacy",
    "/terms": "terms",
}


def _database_path() -> str:
    return os.getenv("MP_DATABASE_PATH", "/tmp/marketpulse.db")


def _surface(path: str) -> tuple[str, str | None] | None:
    if path in _STATIC_SURFACES:
        return _STATIC_SURFACES[path], None
    if path.startswith("/markets/") and len(path) > len("/markets/"):
        return "market", path.removeprefix("/markets/").split("/", 1)[0]
    if path.startswith("/articles/") and len(path) > len("/articles/"):
        return "article", None
    if path.startswith("/creator/"):
        return "creator", None
    return None


def register_traffic_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def aggregate_public_traffic(request: Request, call_next):
        response = await call_next(request)
        if request.method != "GET" or response.status_code != 200:
            return response
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response
        target = _surface(request.url.path)
        if target is None:
            return response
        surface, market_key = target
        channel = request.query_params.get("channel")
        try:
            TrafficStore(_database_path()).record_view(
                surface=surface,
                market_id=market_key,
                channel=channel,
            )
        except (OSError, ValueError, RuntimeError):
            # Telemetry must never make the public product unavailable.
            pass
        return response
