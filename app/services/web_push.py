from __future__ import annotations

import json
import os
from dataclasses import dataclass

from pywebpush import WebPushException, webpush

from app.storage.push_alerts import PushSubscriptionRecord


class WebPushConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebPushConfig:
    public_key: str
    private_key: str
    subject: str

    @classmethod
    def from_env(cls) -> "WebPushConfig":
        public_key = os.getenv("MP_WEBPUSH_VAPID_PUBLIC_KEY", "").strip()
        private_key = os.getenv("MP_WEBPUSH_VAPID_PRIVATE_KEY", "").strip()
        subject = os.getenv("MP_WEBPUSH_VAPID_SUBJECT", "").strip()
        if not public_key or not private_key or not subject:
            raise WebPushConfigurationError("Web Push VAPID configuration is incomplete")
        if not (subject.startswith("mailto:") or subject.startswith("https://")):
            raise WebPushConfigurationError("MP_WEBPUSH_VAPID_SUBJECT must be mailto: or https:")
        return cls(public_key=public_key, private_key=private_key, subject=subject)


def send_push(
    *,
    subscription: PushSubscriptionRecord,
    title: str,
    body: str,
    url: str,
    config: WebPushConfig,
) -> None:
    message = json.dumps(
        {"title": title[:120], "body": body[:300], "url": url},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=message,
        vapid_private_key=config.private_key,
        vapid_claims={"sub": config.subject},
        ttl=300,
        timeout=10,
    )


__all__ = ["WebPushConfig", "WebPushConfigurationError", "WebPushException", "send_push"]
