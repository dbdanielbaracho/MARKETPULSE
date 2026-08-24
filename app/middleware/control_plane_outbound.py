from __future__ import annotations

from urllib.parse import urlsplit
from uuid import uuid4
from secrets import token_urlsafe

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.domain.revenue import AttributionRecord
from app.services.runtime_control import append_tracking, effective_provider, request_country
from app.storage.revenue import RevenueStore


_ALLOWED_HOSTS = {
    "kalshi": {"kalshi.com", "www.kalshi.com"},
    "polymarket": {"polymarket.com", "www.polymarket.com"},
}


def _validated_destination(market, venue: str) -> str | None:
    if market.venue != venue or not market.source_url:
        return None
    parsed = urlsplit(market.source_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_HOSTS[venue]:
        return None
    return market.source_url


def register_control_plane_outbound_middleware(app) -> None:
    """Make published admin settings authoritative for public provider routing."""

    @app.middleware("http")
    async def control_plane_outbound(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/out/"):
            return await call_next(request)
        venue = path.removeprefix("/out/").strip("/")
        if venue not in _ALLOWED_HOSTS:
            return await call_next(request)

        import app.main as core

        market_id = (request.query_params.get("market_id") or "").strip()
        if not market_id:
            return JSONResponse({"detail": "market_id is required"}, status_code=422)
        try:
            market = core._market_by_id(market_id)
        except Exception:
            return JSONResponse({"detail": "outbound route unavailable"}, status_code=404)
        destination = _validated_destination(market, venue)
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
        if not provider.country_allowed(country):
            return JSONResponse(
                {"detail": "provider unavailable in this jurisdiction", "venue": venue, "country": country or "ZZ"},
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
            },
        )
