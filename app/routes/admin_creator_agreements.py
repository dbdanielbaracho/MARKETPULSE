from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import app.main as core
from app.storage.creator_agreements import CreatorAgreementStore


router = APIRouter(prefix="/api/v1/admin/creators", tags=["admin-creator-agreements"])


class CreatorAgreementConfigureRequest(BaseModel):
    agreement_id: str = Field(min_length=3, max_length=120)
    share_basis_points: int = Field(ge=0, le=10000)


class CreatorAgreementApproveRequest(BaseModel):
    agreement_id: str = Field(min_length=3, max_length=120)


@router.post(
    "/{creator_id}/agreement",
    dependencies=[Depends(core._require_admin)],
)
def configure_creator_agreement(
    creator_id: str,
    payload: CreatorAgreementConfigureRequest,
) -> dict[str, object]:
    try:
        agreement = CreatorAgreementStore(core._database_path()).configure(
            creator_id=creator_id,
            agreement_id=payload.agreement_id,
            share_basis_points=payload.share_basis_points,
            approved=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "creator_id": agreement.creator_id,
        "agreement_id": agreement.agreement_id,
        "approved": False,
        "notice": "Configured terms remain inactive until explicit approval.",
    }


@router.post(
    "/{creator_id}/agreement/approve",
    dependencies=[Depends(core._require_admin)],
)
def approve_creator_agreement(
    creator_id: str,
    payload: CreatorAgreementApproveRequest,
) -> dict[str, object]:
    try:
        agreement = CreatorAgreementStore(core._database_path()).approve(
            creator_id,
            payload.agreement_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="creator agreement not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "creator_id": agreement.creator_id,
        "agreement_id": agreement.agreement_id,
        "approved": agreement.approved,
        "approved_at": agreement.approved_at,
    }


@router.post(
    "/{creator_id}/agreement/revoke",
    dependencies=[Depends(core._require_admin)],
)
def revoke_creator_agreement(creator_id: str) -> dict[str, object]:
    try:
        CreatorAgreementStore(core._database_path()).revoke(creator_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"creator_id": creator_id, "approved": False}
