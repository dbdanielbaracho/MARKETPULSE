from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


@dataclass(frozen=True)
class CountryPolicy:
    country: str
    locale: str
    currency: str
    default_timezone: str
    audience: str
    informational_content_allowed: bool
    commercial_outbound_allowed: bool
    paid_social_allowed: bool
    minimum_age: int
    route_mode: str
    reason: str


_UNKNOWN = CountryPolicy(
    country="ZZ",
    locale="en-US",
    currency="USD",
    default_timezone="UTC",
    audience="global_informational",
    informational_content_allowed=True,
    commercial_outbound_allowed=False,
    paid_social_allowed=False,
    minimum_age=18,
    route_mode="informational_only",
    reason="country_or_eligibility_not_verified",
)
_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "countries"
_ROUTE_MODES = frozenset({"contract_required", "informational_only"})
_LOCALE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2}|-[A-Z][a-z]{3})?(?:-[A-Z]{2})?$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _required_text(mapping: Mapping[str, object], key: str, *, max_length: int = 200) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"country policy {key} must be text")
    value = value.strip()
    if not value or len(value) > max_length:
        raise ValueError(f"country policy {key} must be bounded non-empty text")
    return value


def _required_bool(mapping: Mapping[str, object], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"country policy {key} must be boolean")
    return value


def _parse_policy(payload: Mapping[str, object], source: Path) -> CountryPolicy:
    version = payload.get("version")
    if version != 1:
        raise ValueError(f"unsupported country pack version in {source.name}")
    country = _required_text(payload, "country_code", max_length=2).upper()
    if len(country) != 2 or not country.isalpha():
        raise ValueError(f"invalid country_code in {source.name}")
    locale = _required_text(payload, "locale", max_length=35)
    if not _LOCALE_RE.fullmatch(locale):
        raise ValueError(f"invalid BCP 47 locale in {source.name}")
    currency = _required_text(payload, "currency", max_length=3).upper()
    if not _CURRENCY_RE.fullmatch(currency):
        raise ValueError(f"invalid ISO-style currency code in {source.name}")
    default_timezone = _required_text(payload, "default_timezone", max_length=64)
    try:
        ZoneInfo(default_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"invalid IANA timezone in {source.name}") from exc
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError(f"country pack enabled must be boolean in {source.name}")
    policy = payload.get("policy")
    if not isinstance(policy, Mapping):
        raise ValueError(f"country pack policy missing in {source.name}")
    minimum_age = policy.get("minimum_age")
    if not isinstance(minimum_age, int) or isinstance(minimum_age, bool) or minimum_age < 13 or minimum_age > 120:
        raise ValueError(f"country policy minimum_age invalid in {source.name}")
    route_mode = _required_text(policy, "route_mode", max_length=40)
    if route_mode not in _ROUTE_MODES:
        raise ValueError(f"unsupported country policy route_mode in {source.name}")
    commercial_outbound_allowed = _required_bool(policy, "commercial_outbound_allowed")
    paid_social_allowed = _required_bool(policy, "paid_social_allowed")
    if not enabled and (commercial_outbound_allowed or paid_social_allowed):
        raise ValueError(f"disabled country pack cannot enable commercial actions in {source.name}")
    return CountryPolicy(
        country=country,
        locale=locale,
        currency=currency,
        default_timezone=default_timezone,
        audience=_required_text(policy, "audience", max_length=80),
        informational_content_allowed=_required_bool(policy, "informational_content_allowed"),
        commercial_outbound_allowed=commercial_outbound_allowed,
        paid_social_allowed=paid_social_allowed,
        minimum_age=minimum_age,
        route_mode=route_mode,
        reason=_required_text(policy, "reason"),
    )


@lru_cache(maxsize=1)
def configured_country_policies() -> Mapping[str, CountryPolicy]:
    policies: dict[str, CountryPolicy] = {}
    for path in sorted(_CONFIG_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError(f"country pack must be a mapping: {path.name}")
        policy = _parse_policy(raw, path)
        if policy.country in policies:
            raise ValueError(f"duplicate country policy: {policy.country}")
        policies[policy.country] = policy
    if not policies:
        raise ValueError("no country policies configured")
    return policies


def resolve_country_policy(country: str | None) -> CountryPolicy:
    if country is None:
        return _UNKNOWN
    normalized = country.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        return _UNKNOWN
    return configured_country_policies().get(normalized, _UNKNOWN)


def commercial_action_allowed(
    *,
    country: str | None,
    age: int | None,
    partner_contract_verified: bool,
    platform_authorization_verified: bool,
) -> tuple[bool, str]:
    policy = resolve_country_policy(country)
    if age is None or age < policy.minimum_age:
        return False, "age_not_verified"
    if not policy.commercial_outbound_allowed:
        return False, policy.reason
    if not partner_contract_verified:
        return False, "partner_contract_not_verified"
    if not platform_authorization_verified:
        return False, "platform_authorization_not_verified"
    return True, "verified_commercial_action"
