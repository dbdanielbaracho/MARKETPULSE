from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Literal

from app.storage.push_subscriptions import PushSubscription

_VAPID_PUBLIC = re.compile(r"^[A-Za-z0-9_-]{40,256}$")


@dataclass(frozen=True)
class WebPushConfig:
    enabled: bool
    public_key: str | None
    private_key: str | None
    subject: str | None
    reason: str


@dataclass(frozen=True)
class PushDeliveryResult:
    state: Literal["sent", "gone", "failed", "disabled"]
    reason: str


def web_push_config() -> WebPushConfig:
    public_key = os.getenv("MP_WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
    private_key = os.getenv("MP_WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
    subject = os.getenv("MP_WEB_PUSH_VAPID_SUBJECT", "").strip()
    if not public_key and not private_key and not subject:
        return WebPushConfig(False, None, None, None, "vapid_not_configured")
    if not _VAPID_PUBLIC.fullmatch(public_key):
        return WebPushConfig(False, None, None, None, "invalid_vapid_public_key")
    if len(private_key) < 32:
        return WebPushConfig(False, None, None, None, "invalid_vapid_private_key")
    if not (subject.startswith("mailto:") or subject.startswith("https://")) or len(subject) > 320:
        return WebPushConfig(False, None, None, None, "invalid_vapid_subject")
    return WebPushConfig(True, public_key, private_key, subject, "configured")


async def send_web_push(
    subscription: PushSubscription,
    *,
    title: str,
    body: str,
    url: str,
) -> PushDeliveryResult:
    config = web_push_config()
    if not config.enabled or not config.private_key or not config.subject:
        return PushDeliveryResult("disabled", config.reason)
    payload = json.dumps(
        {"title": title[:120], "body": body[:240], "url": url[:500]},
        separators=(",", ":"),
    )

    def _send() -> PushDeliveryResult:
        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            return PushDeliveryResult("failed", "pywebpush_unavailable")
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=config.private_key,
                vapid_claims={"sub": config.subject},
                ttl=300,
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in {404, 410}:
                return PushDeliveryResult("gone", "subscription_gone")
            return PushDeliveryResult("failed", f"web_push_http_{status or 'error'}")
        except Exception:
            return PushDeliveryResult("failed", "web_push_error")
        return PushDeliveryResult("sent", "delivered")

    return await asyncio.to_thread(_send)
