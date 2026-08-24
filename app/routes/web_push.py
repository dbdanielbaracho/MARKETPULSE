from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

import app.main as core
from app.routes.public_alert_signals import market_alert_signals
from app.services.push_alert_dispatch import alert_state, dispatch_push_alerts_once
from app.services.web_push import web_push_config
from app.storage.push_subscriptions import PushSubscriptionStore


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=8, max_length=512)
    auth: str = Field(min_length=8, max_length=512)


class PushAlertPreference(BaseModel):
    market_id: str = Field(min_length=1, max_length=200)
    probability_threshold: float | None = Field(default=None, ge=0, le=1)
    breaking: bool = True
    execution: bool = True
    large: bool = True
    gap: bool = True
    evidence: bool = True
    closing_hours: int | None = Field(default=24, ge=1, le=168)


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=12, max_length=2048)
    keys: PushKeys
    alerts: list[PushAlertPreference] = Field(min_length=1, max_length=25)


class PushAlertsUpdate(BaseModel):
    alerts: list[PushAlertPreference] = Field(min_length=1, max_length=25)


class PushSubscriptionCreated(BaseModel):
    subscription_id: str
    management_token: str
    alert_count: int
    notice: str


def _store() -> PushSubscriptionStore:
    return PushSubscriptionStore(core._database_path())


def _preferences(item: PushAlertPreference) -> dict[str, object]:
    return item.model_dump()


async def _prepared_alerts(alerts: list[PushAlertPreference]) -> list[tuple[str, dict[str, object], dict[str, object]]]:
    prepared: list[tuple[str, dict[str, object], dict[str, object]]] = []
    seen: set[str] = set()
    for item in alerts:
        if item.market_id in seen:
            raise HTTPException(status_code=422, detail="duplicate market in push alert preferences")
        seen.add(item.market_id)
        try:
            snapshot = await market_alert_signals(Response(), market_id=item.market_id)
        except HTTPException as exc:
            raise HTTPException(status_code=422, detail=f"invalid push alert market: {item.market_id}") from exc
        prepared.append((item.market_id, _preferences(item), alert_state(snapshot)))
    return prepared


async def _run_dispatcher(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await dispatch_push_alerts_once(_store())
        except Exception:
            # Push delivery must never take down the application runtime.
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=300)
        except TimeoutError:
            pass


@asynccontextmanager
async def _lifespan(_: object):
    stop = asyncio.Event()
    task = None
    if web_push_config().enabled:
        task = asyncio.create_task(_run_dispatcher(stop), name="predibeacon-web-push")
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=3)
            except TimeoutError:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


router = APIRouter(prefix="/api/v1/push", tags=["web-push"], lifespan=_lifespan)


@router.get("/config")
def push_config(response: Response) -> dict[str, object]:
    config = web_push_config()
    response.headers["Cache-Control"] = "no-store"
    return {
        "enabled": config.enabled,
        "public_key": config.public_key if config.enabled else None,
        "reason": config.reason,
    }


@router.post("/subscriptions", response_model=PushSubscriptionCreated)
async def create_push_subscription(payload: PushSubscriptionCreate, response: Response) -> PushSubscriptionCreated:
    config = web_push_config()
    if not config.enabled:
        raise HTTPException(status_code=503, detail="background Web Push is not configured")
    subscription_id = f"push_{uuid4().hex}"
    raw_token = "pb_push_" + token_urlsafe(32)
    store = _store()
    try:
        prepared = await _prepared_alerts(payload.alerts)
        store.create(
            subscription_id=subscription_id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            raw_token=raw_token,
        )
        store.replace_alerts(subscription_id=subscription_id, alerts=prepared)
    except HTTPException:
        store.revoke(subscription_id)
        raise
    except (ValueError, KeyError) as exc:
        store.revoke(subscription_id)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    return PushSubscriptionCreated(
        subscription_id=subscription_id,
        management_token=raw_token,
        alert_count=len(payload.alerts),
        notice="Store this management token in this browser. PrediBeacon retains only its SHA-256 hash.",
    )


@router.put("/subscriptions/{subscription_id}/alerts")
async def replace_push_alerts(
    subscription_id: str,
    payload: PushAlertsUpdate,
    response: Response,
    management_token: str | None = Header(default=None, alias="X-PrediBeacon-Push-Token"),
) -> dict[str, object]:
    store = _store()
    try:
        store.authorize(subscription_id, management_token or "")
        prepared = await _prepared_alerts(payload.alerts)
        count = store.replace_alerts(subscription_id=subscription_id, alerts=prepared)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid push management token") from exc
    except HTTPException:
        raise
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.headers["Cache-Control"] = "no-store"
    return {"subscription_id": subscription_id, "alert_count": count}


@router.delete("/subscriptions/{subscription_id}")
def revoke_push_subscription(
    subscription_id: str,
    response: Response,
    management_token: str | None = Header(default=None, alias="X-PrediBeacon-Push-Token"),
) -> dict[str, object]:
    store = _store()
    try:
        store.authorize(subscription_id, management_token or "")
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid push management token") from exc
    if not store.revoke(subscription_id):
        raise HTTPException(status_code=404, detail="active push subscription not found")
    response.headers["Cache-Control"] = "no-store"
    return {"subscription_id": subscription_id, "active": False}
