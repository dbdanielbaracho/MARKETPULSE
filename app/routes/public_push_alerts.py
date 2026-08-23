from __future__ import annotations

import ipaddress
import os
from secrets import token_urlsafe
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl

import app.main as core
from app.services.web_push import WebPushConfig, WebPushConfigurationError
from app.storage.push_alerts import PushAlertStore

router = APIRouter(prefix="/api/v1/push", tags=["push-alerts"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=512)
    auth: str = Field(min_length=8, max_length=256)


class PushSubscriptionIn(BaseModel):
    endpoint: HttpUrl
    keys: PushKeys


class PushSubscriptionCreated(BaseModel):
    subscription_id: str
    manage_token: str
    notice: str


class PushRuleIn(BaseModel):
    market_id: str = Field(min_length=1, max_length=200)
    rule_type: str = Field(pattern="^(probability_above|probability_below|breaking|execution_weak|large_trade|verified_gap|closing_hours)$")
    threshold: float | None = None


class PushRuleView(BaseModel):
    rule_id: str
    market_id: str
    rule_type: str
    threshold: float | None


def _store() -> PushAlertStore:
    return PushAlertStore(core._database_path())


def _public_origin() -> str:
    value = os.getenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=503, detail="push registration unavailable")
    return f"{parsed.scheme}://{parsed.netloc}"


def _require_same_origin(origin: str | None) -> None:
    if not origin or origin.rstrip("/") != _public_origin():
        raise HTTPException(status_code=403, detail="same-origin request required")


def _validate_push_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=422, detail="push endpoint must be an absolute https URL")
    host = parsed.hostname.casefold()
    if host in {"localhost", "localhost.localdomain"}:
        raise HTTPException(status_code=422, detail="invalid push endpoint")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise HTTPException(status_code=422, detail="invalid push endpoint")


def _manage_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="push management token required")
    token = authorization.removeprefix("Bearer ").strip()
    if len(token) < 24 or len(token) > 200:
        raise HTTPException(status_code=401, detail="invalid push management token")
    return token


def _authorized(subscription_id: str, authorization: str | None) -> PushAlertStore:
    store = _store()
    if not store.authorize(subscription_id, _manage_token(authorization)):
        raise HTTPException(status_code=403, detail="invalid push management token")
    return store


@router.get("/config")
def push_config() -> dict[str, object]:
    try:
        config = WebPushConfig.from_env()
    except WebPushConfigurationError:
        return {"available": False, "vapid_public_key": None}
    return {"available": True, "vapid_public_key": config.public_key}


@router.post("/subscriptions", response_model=PushSubscriptionCreated, status_code=201)
def create_push_subscription(
    payload: PushSubscriptionIn,
    origin: str | None = Header(default=None),
) -> PushSubscriptionCreated:
    _require_same_origin(origin)
    try:
        WebPushConfig.from_env()
    except WebPushConfigurationError as exc:
        raise HTTPException(status_code=503, detail="background alerts unavailable") from exc
    endpoint = str(payload.endpoint)
    _validate_push_endpoint(endpoint)
    subscription_id = str(uuid4())
    manage_token = token_urlsafe(32)
    _store().upsert_subscription(
        subscription_id=subscription_id,
        manage_token=manage_token,
        endpoint=endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
    )
    return PushSubscriptionCreated(
        subscription_id=subscription_id,
        manage_token=manage_token,
        notice="Store this token in this browser. PrediBeacon stores only its SHA-256 hash.",
    )


@router.get("/subscriptions/{subscription_id}/rules", response_model=list[PushRuleView])
def list_push_rules(
    subscription_id: str,
    authorization: str | None = Header(default=None),
) -> list[PushRuleView]:
    store = _authorized(subscription_id, authorization)
    return [
        PushRuleView(
            rule_id=str(item["rule_id"]),
            market_id=str(item["market_id"]),
            rule_type=str(item["rule_type"]),
            threshold=item["threshold"],
        )
        for item in store.list_rules(subscription_id)
    ]


@router.post("/subscriptions/{subscription_id}/rules", response_model=PushRuleView, status_code=201)
def create_push_rule(
    subscription_id: str,
    payload: PushRuleIn,
    authorization: str | None = Header(default=None),
    origin: str | None = Header(default=None),
) -> PushRuleView:
    _require_same_origin(origin)
    store = _authorized(subscription_id, authorization)
    core._market_by_id(payload.market_id)
    threshold = payload.threshold
    if payload.rule_type in {"probability_above", "probability_below"}:
        if threshold is None or not 0 <= threshold <= 100:
            raise HTTPException(status_code=422, detail="probability threshold must be 0..100")
    elif payload.rule_type == "verified_gap":
        if threshold is None:
            threshold = 5.0
        if not 0 < threshold <= 100:
            raise HTTPException(status_code=422, detail="gap threshold must be >0 and <=100")
    elif payload.rule_type == "closing_hours":
        if threshold is None:
            threshold = 24.0
        if not 0 < threshold <= 24 * 30:
            raise HTTPException(status_code=422, detail="closing-hours threshold is out of bounds")
    elif threshold is not None:
        raise HTTPException(status_code=422, detail="threshold is not valid for this signal type")

    rule_id = str(uuid4())
    store.add_rule(
        rule_id=rule_id,
        subscription_id=subscription_id,
        market_id=payload.market_id,
        rule_type=payload.rule_type,
        threshold=threshold,
    )
    return PushRuleView(rule_id=rule_id, market_id=payload.market_id, rule_type=payload.rule_type, threshold=threshold)


@router.delete("/subscriptions/{subscription_id}/rules/{rule_id}", status_code=204)
def delete_push_rule(
    subscription_id: str,
    rule_id: str,
    authorization: str | None = Header(default=None),
    origin: str | None = Header(default=None),
):
    _require_same_origin(origin)
    store = _authorized(subscription_id, authorization)
    if not store.deactivate_rule(rule_id=rule_id, subscription_id=subscription_id):
        raise HTTPException(status_code=404, detail="active push rule not found")
    return None


@router.delete("/subscriptions/{subscription_id}", status_code=204)
def delete_push_subscription(
    subscription_id: str,
    authorization: str | None = Header(default=None),
    origin: str | None = Header(default=None),
):
    _require_same_origin(origin)
    store = _authorized(subscription_id, authorization)
    store.deactivate_subscription(subscription_id)
    return None
