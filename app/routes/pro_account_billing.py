from __future__ import annotations

from secrets import token_urlsafe
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

import app.main as core
from app.services.pro_billing import (
    BillingConfig,
    BillingConfigurationError,
    create_checkout_session,
    create_customer_portal_session,
    verify_webhook,
)
from app.services.pro_entitlements import ProEntitlementStore, ProProductConfig
from app.services.pro_stripe_projection import process_verified_subscription_event
from app.storage.pro_accounts import ProAccount, ProAccountStore


router = APIRouter(tags=["pro-account-billing"])


class ProAccountCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ProAccountCreateResponse(BaseModel):
    account_id: str
    pro_token: str
    notice: str


def _accounts() -> ProAccountStore:
    return ProAccountStore(core._database_path())


def _require_pro_account(
    token: Annotated[str | None, Header(alias="X-PrediBeacon-Pro-Token")] = None,
) -> ProAccount:
    try:
        return _accounts().authorize(token or "")
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid Pro account credentials") from exc


def _billing_config() -> BillingConfig:
    try:
        return BillingConfig.from_env()
    except BillingConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Pro billing is not configured") from exc


@router.post(
    "/api/v1/admin/pro-accounts",
    response_model=ProAccountCreateResponse,
    dependencies=[Depends(core._require_admin)],
)
def create_pro_account(payload: ProAccountCreateRequest, response: Response) -> ProAccountCreateResponse:
    account_id = "acct_" + uuid4().hex
    raw_token = "pp_live_" + token_urlsafe(32)
    try:
        account = _accounts().create(account_id=account_id, email=payload.email, raw_token=raw_token)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid Pro account request") from exc
    response.headers["Cache-Control"] = "no-store"
    return ProAccountCreateResponse(
        account_id=account.account_id,
        pro_token=raw_token,
        notice="Store this token now. PrediBeacon retains only its SHA-256 hash.",
    )


@router.delete(
    "/api/v1/admin/pro-accounts/{account_id}",
    dependencies=[Depends(core._require_admin)],
)
def revoke_pro_account(account_id: str, response: Response) -> dict[str, object]:
    if not _accounts().revoke(account_id):
        raise HTTPException(status_code=404, detail="active Pro account not found")
    response.headers["Cache-Control"] = "no-store"
    return {"account_id": account_id, "active": False}


@router.get("/api/v1/pro/me")
def pro_me(response: Response, account: ProAccount = Depends(_require_pro_account)) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    try:
        product = ProProductConfig.from_env()
    except ValueError:
        product = None
    features = ProEntitlementStore(core._database_path()).active_features(account.account_id, product)
    return {
        "account_id": account.account_id,
        "billing_customer_bound": account.stripe_customer_id is not None,
        "active_features": sorted(features),
    }


@router.post("/api/v1/pro/checkout")
def pro_checkout(response: Response, account: ProAccount = Depends(_require_pro_account)) -> dict[str, str]:
    if account.stripe_customer_id is not None:
        raise HTTPException(status_code=409, detail="Pro account already has a billing customer; use the customer portal")
    try:
        redirect = create_checkout_session(
            account_ref=account.account_id,
            customer_email=account.email,
            config=_billing_config(),
        )
    except (ValueError, BillingConfigurationError) as exc:
        raise HTTPException(status_code=502, detail="unable to create hosted Pro checkout") from exc
    response.headers["Cache-Control"] = "no-store"
    return {"url": redirect.url}


@router.post("/api/v1/pro/portal")
def pro_portal(response: Response, account: ProAccount = Depends(_require_pro_account)) -> dict[str, str]:
    if account.stripe_customer_id is None:
        raise HTTPException(status_code=409, detail="Pro account is not bound to a billing customer")
    try:
        redirect = create_customer_portal_session(
            stripe_customer_id=account.stripe_customer_id,
            config=_billing_config(),
        )
    except (ValueError, BillingConfigurationError) as exc:
        raise HTTPException(status_code=502, detail="unable to create hosted Pro customer portal") from exc
    response.headers["Cache-Control"] = "no-store"
    return {"url": redirect.url}


@router.post("/api/v1/pro/stripe-webhook")
async def pro_stripe_webhook(
    request: Request,
    response: Response,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    config = _billing_config()
    try:
        product = ProProductConfig.from_env()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Pro product configuration is invalid") from exc
    if product is None:
        raise HTTPException(status_code=503, detail="Pro product is not configured")
    payload = await request.body()
    try:
        event = verify_webhook(payload=payload, signature=stripe_signature or "", config=config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid billing webhook signature or payload") from exc
    try:
        outcome = process_verified_subscription_event(
            event,
            accounts=_accounts(),
            entitlements=ProEntitlementStore(core._database_path()),
            product=product,
        )
    except LookupError as exc:
        # Stripe doesn't guarantee event ordering; non-2xx keeps an unbound subscription event retryable.
        raise HTTPException(status_code=409, detail="billing customer binding is not ready") from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail="invalid billing event projection") from exc
    response.headers["Cache-Control"] = "no-store"
    return {"status": outcome}
