from __future__ import annotations

import os
from secrets import token_urlsafe
from typing import Annotated, Literal
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

import app.main as core
from app.services.api_billing import (
    ApiBillingConfig,
    ApiBillingConfigurationError,
    active_api_plan,
    api_plan_catalog,
    create_api_checkout,
    create_api_portal,
    process_api_subscription_event,
    verify_api_webhook,
)
from app.storage.api_accounts import ApiCustomerAccount, ApiCustomerStore
from app.storage.api_keys import ApiKeyStore


router = APIRouter(tags=["commercial-api-billing"])


class ApiAccountCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ApiCheckoutRequest(BaseModel):
    plan: Literal["starter", "pro", "business"]


class SubscriberKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


def _accounts() -> ApiCustomerStore:
    return ApiCustomerStore(core._database_path())


def _require_account(token: Annotated[str | None, Header(alias="X-PrediBeacon-API-Account-Token")] = None) -> ApiCustomerAccount:
    try:
        return _accounts().authorize(token or "")
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid Commercial API account credentials") from exc


def _catalog():
    try:
        return api_plan_catalog()
    except ApiBillingConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Commercial API plan configuration is invalid") from exc


def _billing_config() -> ApiBillingConfig:
    secret = os.getenv("MP_STRIPE_SECRET_KEY", "").strip()
    webhook = os.getenv("MP_STRIPE_API_WEBHOOK_SECRET", "").strip()
    origin = os.getenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com").strip().rstrip("/")
    parsed = urlparse(origin)
    if not secret or not webhook or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail="Commercial API billing is not configured")
    return ApiBillingConfig(secret, webhook, origin)


@router.post("/api/v1/admin/api-accounts", dependencies=[Depends(core._require_admin)])
def create_api_account(payload: ApiAccountCreateRequest, response: Response) -> dict[str, str]:
    account_id = "apiacct_" + uuid4().hex
    raw_token = "pb_apiacct_" + token_urlsafe(32)
    try:
        account = _accounts().create(account_id=account_id, email=payload.email, raw_token=raw_token)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid Commercial API account request") from exc
    response.headers["Cache-Control"] = "no-store"
    return {
        "account_id": account.account_id,
        "account_token": raw_token,
        "notice": "Store this account token now. PrediBeacon retains only its SHA-256 hash.",
    }


@router.get("/api/v1/api-account/me")
def api_account_me(response: Response, account: ApiCustomerAccount = Depends(_require_account)) -> dict[str, object]:
    plan = active_api_plan(_accounts(), account.account_id, _catalog())
    response.headers["Cache-Control"] = "no-store"
    return {
        "account_id": account.account_id,
        "billing_customer_bound": account.stripe_customer_id is not None,
        "active_plan": plan.plan if plan else None,
        "api_access_active": plan is not None,
    }


@router.post("/api/v1/api-account/checkout")
def api_account_checkout(payload: ApiCheckoutRequest, response: Response, account: ApiCustomerAccount = Depends(_require_account)) -> dict[str, str]:
    if account.stripe_customer_id is not None:
        raise HTTPException(status_code=409, detail="Commercial API account already has a billing customer; use the customer portal")
    plan = _catalog().get(payload.plan)
    if plan is None:
        raise HTTPException(status_code=503, detail="requested Commercial API plan is not configured")
    try:
        url = create_api_checkout(account_id=account.account_id, email=account.email, plan=plan, config=_billing_config())
    except (ValueError, ApiBillingConfigurationError) as exc:
        raise HTTPException(status_code=502, detail="unable to create hosted Commercial API checkout") from exc
    response.headers["Cache-Control"] = "no-store"
    return {"url": url}


@router.post("/api/v1/api-account/portal")
def api_account_portal(response: Response, account: ApiCustomerAccount = Depends(_require_account)) -> dict[str, str]:
    if account.stripe_customer_id is None:
        raise HTTPException(status_code=409, detail="Commercial API account is not bound to a billing customer")
    try:
        url = create_api_portal(customer_id=account.stripe_customer_id, config=_billing_config())
    except (ValueError, ApiBillingConfigurationError) as exc:
        raise HTTPException(status_code=502, detail="unable to create Commercial API customer portal") from exc
    response.headers["Cache-Control"] = "no-store"
    return {"url": url}


@router.post("/api/v1/api-account/stripe-webhook")
async def api_account_webhook(
    request: Request,
    response: Response,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    catalog = _catalog()
    if not catalog:
        raise HTTPException(status_code=503, detail="Commercial API products are not configured")
    payload = await request.body()
    try:
        event = verify_api_webhook(payload=payload, signature=stripe_signature or "", config=_billing_config())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid Commercial API billing webhook") from exc
    try:
        outcome = process_api_subscription_event(event, store=_accounts(), catalog=catalog)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Commercial API customer binding is not ready") from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail="invalid Commercial API billing event projection") from exc
    response.headers["Cache-Control"] = "no-store"
    return {"status": outcome}


@router.post("/api/v1/api-account/keys")
def issue_subscriber_key(payload: SubscriberKeyRequest, response: Response, account: ApiCustomerAccount = Depends(_require_account)) -> dict[str, object]:
    plan = active_api_plan(_accounts(), account.account_id, _catalog())
    if plan is None:
        raise HTTPException(status_code=403, detail="active Commercial API subscription required")
    key_id = str(uuid4())
    raw_token = "pb_live_" + token_urlsafe(32)
    ApiKeyStore(core._database_path()).create(
        key_id=key_id,
        raw_token=raw_token,
        name=payload.name,
        plan=plan.plan,
        scopes=plan.scopes,
        daily_limit=plan.daily_limit,
        owner_account_id=account.account_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "key_id": key_id,
        "api_key": raw_token,
        "plan": plan.plan,
        "scopes": list(plan.scopes),
        "daily_limit": plan.daily_limit,
        "notice": "Store this key now. PrediBeacon retains only its SHA-256 hash.",
    }


@router.get("/api/v1/api-account/keys")
def list_subscriber_keys(response: Response, account: ApiCustomerAccount = Depends(_require_account)) -> list[dict[str, object]]:
    response.headers["Cache-Control"] = "no-store"
    return [
        {
            "key_id": item.key_id,
            "name": item.name,
            "plan": item.plan,
            "scopes": list(item.scopes),
            "daily_limit": item.daily_limit,
            "active": item.active,
            "created_at": item.created_at,
            "revoked_at": item.revoked_at,
        }
        for item in ApiKeyStore(core._database_path()).list_owner_keys(account.account_id)
    ]


@router.delete("/api/v1/api-account/keys/{key_id}")
def revoke_subscriber_key(key_id: str, response: Response, account: ApiCustomerAccount = Depends(_require_account)) -> dict[str, object]:
    if not ApiKeyStore(core._database_path()).revoke_owned(key_id, account.account_id):
        raise HTTPException(status_code=404, detail="active account-owned API key not found")
    response.headers["Cache-Control"] = "no-store"
    return {"key_id": key_id, "active": False}
