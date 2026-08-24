from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from app.config.runtime import RuntimeFlags
from app.services.country_policy import resolve_country_policy

SocialChannel = Literal["instagram", "tiktok", "youtube", "telegram", "whatsapp", "x"]

_CHANNELS: tuple[SocialChannel, ...] = (
    "instagram",
    "tiktok",
    "youtube",
    "telegram",
    "whatsapp",
    "x",
)
_CREDENTIAL_ENV = {
    "instagram": "MP_INSTAGRAM_ACCESS_TOKEN",
    "tiktok": "MP_TIKTOK_ACCESS_TOKEN",
    "youtube": "MP_YOUTUBE_REFRESH_TOKEN",
    "telegram": "MP_TELEGRAM_BOT_TOKEN",
    "whatsapp": "MP_WHATSAPP_ACCESS_TOKEN",
    "x": "MP_X_ACCESS_TOKEN",
}
_AUTHORIZATION_ENV = {
    channel: f"MP_{channel.upper()}_AUTHORIZED"
    for channel in _CHANNELS
}


@dataclass(frozen=True)
class ChannelReadiness:
    channel: SocialChannel
    ready: bool
    reasons: tuple[str, ...]
    credential_configured: bool
    platform_authorized: bool
    country: str
    audience: str


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _provider_configuration_present(channel: SocialChannel) -> bool:
    primary = bool(os.getenv(_CREDENTIAL_ENV[channel], "").strip())
    if channel == "telegram":
        return primary and bool(os.getenv("MP_TELEGRAM_CHAT_ID", "").strip())
    if channel == "instagram":
        return primary and bool(os.getenv("MP_INSTAGRAM_USER_ID", "").strip()) and bool(os.getenv("MP_META_GRAPH_VERSION", "").strip())
    if channel == "whatsapp":
        return primary and bool(os.getenv("MP_WHATSAPP_PHONE_NUMBER_ID", "").strip()) and bool(os.getenv("MP_META_GRAPH_VERSION", "").strip())
    return primary


def channel_readiness(
    channel: SocialChannel,
    *,
    country: str | None,
    editorial_approved: bool,
    partner_contract_verified: bool,
    paid_or_commercial: bool,
) -> ChannelReadiness:
    if channel not in _CHANNELS:
        raise ValueError("unsupported social channel")
    policy = resolve_country_policy(country)
    flags = RuntimeFlags.from_env()
    credential = _provider_configuration_present(channel)
    authorized = _enabled(_AUTHORIZATION_ENV[channel])
    reasons: list[str] = []
    if not flags.social_distribution:
        reasons.append("global_social_kill_switch_off")
    if not credential:
        reasons.append("credential_not_configured")
    if not authorized:
        reasons.append("platform_authorization_not_verified")
    if not editorial_approved:
        reasons.append("editorial_approval_required")
    if paid_or_commercial:
        if not partner_contract_verified:
            reasons.append("partner_contract_not_verified")
        if not policy.paid_social_allowed:
            reasons.append(policy.reason)
    return ChannelReadiness(
        channel=channel,
        ready=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        credential_configured=credential,
        platform_authorized=authorized,
        country=policy.country,
        audience=policy.audience,
    )


def all_channel_readiness(country: str | None = None) -> tuple[ChannelReadiness, ...]:
    return tuple(
        channel_readiness(
            channel,
            country=country,
            editorial_approved=False,
            partner_contract_verified=False,
            paid_or_commercial=False,
        )
        for channel in _CHANNELS
    )
