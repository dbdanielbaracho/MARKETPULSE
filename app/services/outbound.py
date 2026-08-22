from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


@dataclass(frozen=True)
class PartnerRoute:
    partner_id: str
    venue: str
    country: str
    destination_url: str
    enabled: bool = False
    commercial_verified: bool = False
    allowed_hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class OutboundDecision:
    allowed: bool
    reason: str
    partner_id: str | None = None
    destination_url: str | None = None


def _host_allowed(url: str, allowed_hosts: Iterable[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"https"} or not parsed.hostname:
        return False
    host = parsed.hostname.rstrip(".").lower()
    allow = {item.rstrip(".").lower() for item in allowed_hosts}
    return host in allow


def resolve_outbound(*, venue: str, country: str, routes: Iterable[PartnerRoute]) -> OutboundDecision:
    """Fail-closed partner router.

    The caller provides server-side routes. User input never supplies a redirect URL.
    """
    candidates = [
        route
        for route in routes
        if route.venue == venue and route.country.upper() == country.upper()
    ]
    if not candidates:
        return OutboundDecision(False, "no_route")

    for route in candidates:
        if not route.enabled:
            continue
        if not route.commercial_verified:
            continue
        if not _host_allowed(route.destination_url, route.allowed_hosts):
            continue
        return OutboundDecision(True, "verified_route", route.partner_id, route.destination_url)

    return OutboundDecision(False, "no_verified_route")
