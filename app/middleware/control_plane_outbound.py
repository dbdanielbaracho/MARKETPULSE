from __future__ import annotations

from secrets import token_urlsafe
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.domain.revenue import AttributionRecord
from app.services.runtime_control import append_tracking, effective_provider, request_country
from app.storage.revenue import RevenueStore


_ALLOWED_HOSTS = {
    "kalshi": {"kalshi.com", "www.kalshi.com"},
    "polymarket": {"polymarket.com", "www.polymarket.com"},
}


def _validated_destination(market, venue: str) -> tuple[str | None, str]:
    if market.venue != venue or not market.source_url:
        return None, "route_unavailable"
    parsed = urlsplit(market.source_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_HOSTS[venue]:
        return None, "unverified_destination"
    return market.source_url, "ok"


def _route_payload(core, market, request: Request) -> dict[str, object]:
    venue = market.venue
    destination, destination_state = _validated_destination(market, venue)
    provider = effective_provider(core._database_path(), venue)
    country = request_country(request.headers)
    if destination is None:
        return {
            "market_id": market.canonical_id,
            "venue": venue,
            "available": False,
            "mode": "unavailable",
            "outbound_url": None,
            "reason": destination_state,
        }
    if not provider.enabled:
        return {
            "market_id": market.canonical_id,
            "venue": venue,
            "available": False,
            "mode": "unavailable",
            "outbound_url": None,
            "reason": "provider_disabled",
        }
    if country is not None and not provider.country_allowed(country):
        return {
            "market_id": market.canonical_id,
            "venue": venue,
            "available": False,
            "mode": "unavailable",
            "outbound_url": None,
            "reason": "jurisdiction_unavailable",
        }
    mode = "partner" if provider.commercial_verified and provider.attribution_id else "organic"
    return {
        "market_id": market.canonical_id,
        "venue": venue,
        "available": True,
        "mode": mode,
        "outbound_url": f"/out/{venue}?{urlencode({'market_id': market.canonical_id})}",
        "reason": "verified_partner_route" if mode == "partner" else "verified_organic_route",
    }


def register_control_plane_outbound_middleware(app) -> None:
    """Make published admin settings authoritative for route discovery and outbound traffic.

    Jurisdiction blocks are enforced whenever the trusted deployment edge supplies a
    country header. Unknown location preserves the pre-control-plane organic route;
    production can later make an edge country header mandatory once that deployment
    invariant is verified end-to-end.
    """

    @app.middleware("http")
    async def control_plane_outbound(request: Request, call_next):
        import app.main as core

        if request.url.path == "/api/v1/market/route":
            market_id = (request.query_params.get("market_id") or "").strip()
            if not market_id:
                return JSONResponse({"detail": "market_id is required"}, status_code=422)
            try:
                market = core._market_by_id(market_id)
            except Exception:
                return JSONResponse({"detail": "market not found"}, status_code=404)
            return JSONResponse(_route_payload(core, market, request), headers={"Cache-Control": "no-store"})

        path = request.url.path
        if not path.startswith("/out/"):
            return await call_next(request)
        venue = path.removeprefix("/out/").strip("/")
        if venue not in _ALLOWED_HOSTS:
            return await call_next(request)

        market_id = (request.query_params.get("market_id") or "").strip()
        if not market_id:
            return JSONResponse({"detail": "market_id is required"}, status_code=422)
        try:
            market = core._market_by_id(market_id)
        except Exception:
            return JSONResponse({"detail": "outbound route unavailable"}, status_code=404)
        destination, destination_state = _validated_destination(market, venue)
        if destination_state == "route_unavailable":
            return JSONResponse({"detail": "outbound route unavailable"}, status_code=404)
        if destination is None:
            return JSONResponse({"detail": "unverified destination"}, status_code=409)

        provider = effective_provider(core._database_path(), venue)
        country = request_country(request.headers)
        if not provider.enabled:
            return JSONResponse(
                {"detail": "provider temporarily unavailable", "venue": venue},
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
        if country is not None and not provider.country_allowed(country):
            return JSONResponse(
                {"detail": "provider unavailable in this jurisdiction", "venue": venue, "country": country},
                status_code=451,
                headers={"Cache-Control": "no-store"},
            )

        click_id = token_urlsafe(18)
        attribution_id = str(uuid4())
        partner_id = provider.attribution_id if provider.commercial_verified and provider.attribution_id else f"{venue}-organic"
        store = RevenueStore(core._database_path())
        store.record_click(AttributionRecord(
            attribution_id=attribution_id,
            click_id=click_id,
            partner_id=partner_id,
            venue=venue,
            country=country or "ZZ",
        ))
        store.record_click_context(
            click_id=click_id,
            market_id=market_id,
            campaign_id=request.query_params.get("campaign_id"),
            creator_id=request.query_params.get("creator_id"),
            channel=request.query_params.get("channel"),
            referrer=request.headers.get("referer"),
        )
        target = append_tracking(destination, provider)
        return RedirectResponse(
            target,
            status_code=302,
            headers={
                "Cache-Control": "no-store",
                "X-PrediBeacon-Click-ID": click_id,
                "X-PrediBeacon-Route-Mode": "partner" if provider.commercial_verified else "organic",
                "X-PrediBeacon-Country-State": country or "unknown",
            },
        )
