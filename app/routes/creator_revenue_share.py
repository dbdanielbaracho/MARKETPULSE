from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import app.main as core
from app.services.creator_revenue_share import creator_amount_due
from app.storage.creator_agreements import CreatorAgreementStore
from app.storage.revenue import RevenueStore


router = APIRouter(prefix="/api/v1/admin/creators", tags=["creator-revenue-share"])


class CreatorAgreementRequest(BaseModel):
    agreement_id: str = Field(min_length=3, max_length=120)
    share_basis_points: int = Field(ge=0, le=10000)


class CreatorAgreementApprovalRequest(BaseModel):
    agreement_id: str = Field(min_length=3, max_length=120)


@router.post(
    "/{creator_id}/revenue-share-agreement",
    dependencies=[Depends(core._require_admin)],
)
def configure_creator_revenue_share_agreement(
    creator_id: str,
    payload: CreatorAgreementRequest,
) -> dict[str, object]:
    """Configure private terms without making them usable."""
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
        "agreement_id": agreement.agreement_id,
        "creator_id": agreement.creator_id,
        "share_basis_points": agreement.share_basis_points,
        "approved": agreement.approved,
        "approved_at": agreement.approved_at,
        "updated_at": agreement.updated_at,
        "notice": "Configured terms remain unusable until the exact agreement is explicitly approved.",
    }


@router.post(
    "/{creator_id}/revenue-share-agreement/approve",
    dependencies=[Depends(core._require_admin)],
)
def approve_creator_revenue_share_agreement(
    creator_id: str,
    payload: CreatorAgreementApprovalRequest,
) -> dict[str, object]:
    try:
        agreement = CreatorAgreementStore(core._database_path()).approve(creator_id, payload.agreement_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="creator agreement not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "agreement_id": agreement.agreement_id,
        "creator_id": agreement.creator_id,
        "approved": agreement.approved,
        "approved_at": agreement.approved_at,
        "notice": "The exact configured creator agreement is now approved for paid-revenue calculation.",
    }


@router.post(
    "/{creator_id}/revenue-share-agreement/revoke",
    dependencies=[Depends(core._require_admin)],
)
def revoke_creator_revenue_share_agreement(creator_id: str) -> dict[str, object]:
    try:
        store = CreatorAgreementStore(core._database_path())
        store.revoke(creator_id)
        approved_after = store.approved_for_creator(creator_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "creator_id": creator_id,
        "approved": approved_after is not None,
        "notice": "Revocation is idempotent; no creator share is usable after this response.",
    }


@router.get(
    "/{creator_id}/revenue-share",
    dependencies=[Depends(core._require_admin)],
)
def creator_revenue_share_snapshot(creator_id: str) -> dict[str, object]:
    base = RevenueStore(core._database_path()).creator_summary(creator_id)
    try:
        agreement = CreatorAgreementStore(core._database_path()).approved_for_creator(creator_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    paid_totals = base.get("paid_partner_revenue_totals") or {}
    if agreement is None:
        return {
            **base,
            "agreement": None,
            "creator_amount_due": None,
            "notice": "No creator amount is calculated without an explicitly approved revenue-share agreement.",
        }

    try:
        amount_due = creator_amount_due(paid_totals, agreement.share_basis_points)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="invalid paid-revenue calculation input") from exc
    return {
        **base,
        "agreement": {
            "agreement_id": agreement.agreement_id,
            "share_basis_points": agreement.share_basis_points,
            "approved": agreement.approved,
            "approved_at": agreement.approved_at,
            "updated_at": agreement.updated_at,
        },
        "creator_amount_due": amount_due,
        "notice": "Creator amount is derived only from reconciled paid partner revenue and the approved agreement share.",
    }
