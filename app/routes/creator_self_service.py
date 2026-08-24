from __future__ import annotations

from secrets import token_urlsafe
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field

import app.main as core
from app.storage.creator_credentials import CreatorCredential, CreatorCredentialStore
from app.storage.revenue import RevenueStore


router = APIRouter(tags=["creator-self-service"])


class CreatorCredentialCreateRequest(BaseModel):
    creator_id: str = Field(min_length=2, max_length=100)


class CreatorCredentialCreateResponse(BaseModel):
    credential_id: str
    creator_id: str
    creator_token: str
    notice: str


def _require_creator(
    token: Annotated[str | None, Header(alias="X-PrediBeacon-Creator-Token")] = None,
) -> CreatorCredential:
    try:
        return CreatorCredentialStore(core._database_path()).authorize(token or "")
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid creator credentials") from exc


@router.post(
    "/api/v1/admin/creator-credentials",
    response_model=CreatorCredentialCreateResponse,
    dependencies=[Depends(core._require_admin)],
)
def create_creator_credential(payload: CreatorCredentialCreateRequest) -> CreatorCredentialCreateResponse:
    credential_id = str(uuid4())
    raw_token = f"pc_live_{token_urlsafe(32)}"
    try:
        item = CreatorCredentialStore(core._database_path()).create(
            credential_id=credential_id,
            creator_id=payload.creator_id,
            raw_token=raw_token,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid creator credential request") from exc
    return CreatorCredentialCreateResponse(
        credential_id=item.credential_id,
        creator_id=item.creator_id,
        creator_token=raw_token,
        notice="Store this token now. PrediBeacon retains only its SHA-256 hash.",
    )


@router.delete(
    "/api/v1/admin/creator-credentials/{credential_id}",
    dependencies=[Depends(core._require_admin)],
)
def revoke_creator_credential(credential_id: str) -> dict[str, object]:
    try:
        revoked = CreatorCredentialStore(core._database_path()).revoke(credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid creator credential id") from exc
    if not revoked:
        raise HTTPException(status_code=404, detail="active creator credential not found")
    return {"credential_id": credential_id, "active": False}


@router.get("/api/v1/creator/me/revenue")
def creator_self_revenue(
    response: Response,
    credential: CreatorCredential = Depends(_require_creator),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return RevenueStore(core._database_path()).creator_summary(credential.creator_id)
