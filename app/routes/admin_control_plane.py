from __future__ import annotations

from pathlib import Path
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import app.main as core
from app.storage.control_plane import ControlPlaneStore


router = APIRouter(tags=["admin-control-plane"])


class ControlPlanePayload(BaseModel):
    version: int
    providers: dict[str, dict[str, object]]
    acquisition: dict[str, object]
    publishing: dict[str, object]


def _actor(value: str | None) -> str:
    text = (value or "admin").strip()
    return text[:120] or "admin"


def _redact(payload: dict[str, object]) -> dict[str, object]:
    result = {**payload}
    providers = {}
    for venue, raw in payload.get("providers", {}).items():
        item = dict(raw)
        for key in ("partner_id", "affiliate_id", "referral_code", "tracking_value"):
            value = str(item.get(key, ""))
            if value:
                item[key + "_configured"] = True
                item[key + "_masked"] = ("•" * max(4, len(value) - 4)) + value[-4:]
            else:
                item[key + "_configured"] = False
                item[key + "_masked"] = ""
        providers[venue] = item
    result["providers"] = providers
    return result


@router.get("/api/v1/admin/control-plane", dependencies=[Depends(core._require_admin)])
def control_plane_snapshot() -> dict[str, object]:
    snapshot = ControlPlaneStore(core._database_path()).snapshot()
    return {
        **snapshot,
        "draft_redacted": _redact(snapshot["draft"]),
        "published_redacted": _redact(snapshot["published"]),
    }


@router.put("/api/v1/admin/control-plane/draft", dependencies=[Depends(core._require_admin)])
def save_control_plane_draft(
    payload: ControlPlanePayload,
    actor: str | None = Header(default=None, alias="X-PrediBeacon-Admin-Actor"),
) -> dict[str, object]:
    try:
        return ControlPlaneStore(core._database_path()).save_draft(payload.model_dump(), _actor(actor))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/v1/admin/control-plane/publish", dependencies=[Depends(core._require_admin)])
def publish_control_plane(
    actor: str | None = Header(default=None, alias="X-PrediBeacon-Admin-Actor"),
) -> dict[str, object]:
    try:
        return ControlPlaneStore(core._database_path()).publish(_actor(actor))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/v1/admin/control-plane/rollback/{version}", dependencies=[Depends(core._require_admin)])
def rollback_control_plane(
    version: int,
    actor: str | None = Header(default=None, alias="X-PrediBeacon-Admin-Actor"),
) -> dict[str, object]:
    try:
        return ControlPlaneStore(core._database_path()).rollback(version, _actor(actor))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="control-plane revision not found") from exc


@router.get("/api/v1/admin/control-plane/audit", dependencies=[Depends(core._require_admin)])
def control_plane_audit(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
    return ControlPlaneStore(core._database_path()).audit(limit)


@router.get("/admin/control-plane", response_class=HTMLResponse, include_in_schema=False)
def control_plane_page() -> HTMLResponse:
    nonce = token_urlsafe(18)
    template = Path(__file__).resolve().parents[1] / "templates" / "control_plane.html"
    body = template.read_text(encoding="utf-8").replace("__CSP_NONCE__", nonce)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )
