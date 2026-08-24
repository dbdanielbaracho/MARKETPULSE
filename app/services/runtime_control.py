from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.storage.control_plane import ControlPlaneStore


@dataclass(frozen=True)
class EffectiveProvider:
    venue: str
    enabled: bool
    commercial_verified: bool
    partner_id: str
    affiliate_id: str
    referral_code: str
    compensation_model: str
    compensation_rate: float | None
    tracking_parameter: str
    tracking_value: str
    allowed_countries: tuple[str, ...]
    blocked_countries: tuple[str, ...]

    def country_allowed(self, country: str | None) -> bool:
        if country is None:
            return not self.allowed_countries
        code = country.strip().upper()
        if len(code) != 2:
            return False
        if code in self.blocked_countries:
            return False
        if self.allowed_countries and code not in self.allowed_countries:
            return False
        return True

    @property
    def attribution_id(self) -> str:
        return self.partner_id or self.affiliate_id or self.referral_code


def _truthy(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().casefold() in {"1", "true", "yes", "on"}


def effective_provider(database_path: str, venue: str) -> EffectiveProvider:
    if venue not in {"kalshi", "polymarket"}:
        raise ValueError("unsupported venue")
    try:
        item = ControlPlaneStore(database_path).published()["providers"][venue]
    except Exception:
        item = {}
    prefix = f"MP_{venue.upper()}_"
    partner_id = str(item.get("partner_id") or os.getenv(prefix + "PARTNER_ID", "")).strip()
    commercial_verified = bool(item.get("commercial_verified", False)) or _truthy(prefix + "COMMERCIAL_VERIFIED")
    return EffectiveProvider(
        venue=venue,
        enabled=bool(item.get("enabled", True)),
        commercial_verified=commercial_verified,
        partner_id=partner_id,
        affiliate_id=str(item.get("affiliate_id", "")).strip(),
        referral_code=str(item.get("referral_code", "")).strip(),
        compensation_model=str(item.get("compensation_model", "pending")),
        compensation_rate=item.get("compensation_rate"),
        tracking_parameter=str(item.get("tracking_parameter", "")).strip(),
        tracking_value=str(item.get("tracking_value", "")).strip(),
        allowed_countries=tuple(str(value).upper() for value in item.get("allowed_countries", [])),
        blocked_countries=tuple(str(value).upper() for value in item.get("blocked_countries", [])),
    )


def append_tracking(url: str, provider: EffectiveProvider) -> str:
    """Append only a partner-approved query parameter configured by an administrator."""
    if not provider.commercial_verified or not provider.tracking_parameter or not provider.tracking_value:
        return url
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[provider.tracking_parameter] = provider.tracking_value
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def request_country(headers: object) -> str | None:
    """Prefer CDN country metadata; never infer eligibility from IP inside the app."""
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    for name in ("cf-ipcountry", "x-vercel-ip-country", "x-country-code"):
        raw = getter(name)
        if raw:
            value = str(raw).strip().upper()
            if len(value) == 2 and value.isalpha() and value != "XX":
                return value
    return None
