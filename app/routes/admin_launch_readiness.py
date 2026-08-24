from __future__ import annotations

from fastapi import APIRouter, Depends

import app.main as core
from app.services.runtime_control import effective_provider
from app.storage.traffic import TrafficStore


router = APIRouter(prefix="/api/v1/admin", tags=["admin-launch-readiness"])


def _partner_mode(venue: str) -> str:
    provider = effective_provider(core._database_path(), venue)
    return "partner" if provider.enabled and provider.commercial_verified and provider.attribution_id else "organic"


def _venue_route_available(venue: str) -> bool:
    market = next((item for item in core._DISCOVERY if item.venue == venue), None)
    provider = effective_provider(core._database_path(), venue)
    return bool(provider.enabled and market and core._market_route(market).available)


@router.get("/launch-readiness", dependencies=[Depends(core._require_admin)])
def launch_readiness() -> dict[str, object]:
    status = core.status()
    counts = status["venue_market_counts"]
    origin = core._public_base_url()
    try:
        TrafficStore(core._database_path()).summary(days=1, top_markets=1)
        analytics_ok = True
    except Exception:
        analytics_ok = False

    routes = {venue: _venue_route_available(venue) for venue in ("kalshi", "polymarket")}
    partner_modes = {venue: _partner_mode(venue) for venue in ("kalshi", "polymarket")}
    checks = [
        {
            "name": "Canonical public origin",
            "ok": origin == "https://predibeacon.com",
            "severity": "critical",
            "detail": origin,
        },
        {
            "name": "Current market feeds",
            "ok": counts.get("kalshi", 0) > 0 and counts.get("polymarket", 0) > 0,
            "severity": "critical",
            "detail": f"Kalshi={counts.get('kalshi', 0)}; Polymarket={counts.get('polymarket', 0)}",
        },
        {
            "name": "Market freshness",
            "ok": status["freshness"] == "fresh",
            "severity": "critical",
            "detail": f"state={status['freshness']}; age={status['data_age_seconds']}s",
        },
        {
            "name": "Outbound route safety",
            "ok": all(routes.values()),
            "severity": "critical",
            "detail": routes,
        },
        {
            "name": "Persistent storage",
            "ok": bool(status["storage"]["writable"] and status["storage"]["persistent_volume_configured"]),
            "severity": "critical",
            "detail": status["storage"],
        },
        {
            "name": "First-party analytics",
            "ok": analytics_ok,
            "severity": "warning",
            "detail": "Aggregate traffic store is writable/readable." if analytics_ok else "Traffic aggregate store is unavailable.",
        },
        {
            "name": "Admin operations",
            "ok": bool(status["admin_review_configured"]),
            "severity": "warning",
            "detail": "Admin token is configured." if status["admin_review_configured"] else "Admin token is not configured.",
        },
        {
            "name": "Automated distribution safety",
            "ok": not status["automated_publishing_enabled"] and not status["social_distribution_enabled"],
            "severity": "critical",
            "detail": "Automated publishing/social distribution remain disabled pending explicit launch authorization.",
        },
    ]
    critical_failures = [item for item in checks if item["severity"] == "critical" and not item["ok"]]
    warnings = [item for item in checks if item["severity"] == "warning" and not item["ok"]]
    partner_active = [venue for venue, mode in partner_modes.items() if mode == "partner"]
    partner_pending = [venue for venue, mode in partner_modes.items() if mode != "partner"]

    return {
        "decision": "GO" if not critical_failures else "NO_GO",
        "product_ready": not critical_failures,
        "generated_at": status["generated_at"],
        "checks": checks,
        "warning_count": len(warnings),
        "partner_monetization": {
            "modes": partner_modes,
            "active_partner_venues": partner_active,
            "organic_or_pending_venues": partner_pending,
            "blocks_product_launch": False,
            "notice": "Published Control Plane settings govern live outbound routing; partner revenue activates only with verified commercial configuration.",
        },
    }
