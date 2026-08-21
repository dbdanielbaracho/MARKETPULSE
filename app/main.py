from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

APP_VERSION = "0.1.0"

app = FastAPI(title="MarketPulse", version=APP_VERSION)


@app.get("/health")
def health() -> dict[str, str]:
    """Deterministic readiness endpoint: never depends on external venues."""
    return {
        "status": "ok",
        "service": "marketpulse-web",
        "version": APP_VERSION,
    }


@app.get("/api/v1/status")
def status() -> dict[str, str]:
    return {
        "service": "marketpulse-web",
        "version": APP_VERSION,
        "country": "US",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    template = Path(__file__).parent / "templates" / "index.html"
    return template.read_text(encoding="utf-8")
