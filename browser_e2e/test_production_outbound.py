from __future__ import annotations

import os
from urllib.parse import quote

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright


pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production smoke runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")


def _find_routable_market(request):
    response = request.get("/api/v1/markets?limit=40", timeout=25_000)
    assert response.ok, response.status
    markets = response.json()
    assert markets, "production discovery returned no markets"
    for market in markets:
        market_id = market.get("canonical_id")
        slug = market.get("slug")
        venue = market.get("venue")
        if not market_id or not slug or venue not in {"kalshi", "polymarket"}:
            continue
        route = request.get(
            "/api/v1/market/route?market_id=" + quote(market_id, safe=""),
            timeout=20_000,
        )
        if route.ok and route.json().get("available") is True:
            return market
    pytest.fail("no routable production market found for outbound browser acceptance")


def test_external_venue_click_opens_separate_safe_context_and_keeps_predibeacon_open():
    """MP-037 live acceptance: venue navigation must not replace PrediBeacon.

    The outbound request itself is intercepted before any third-party page is
    contacted. This verifies the browser semantics we own: a separate browsing
    context, no opener capability, central /out routing, and the original
    PrediBeacon market page remaining in place.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        request = p.request.new_context(base_url=CUSTOM)
        market = _find_routable_market(request)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        context.route(
            "**/out/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<!doctype html><title>Outbound intercepted</title><p>ok</p>",
            ),
        )
        try:
            detail_url = f"{CUSTOM}/markets/{market['slug']}"
            response = page.goto(detail_url, wait_until="domcontentloaded", timeout=30_000)
            assert response is not None and response.status < 500
            expect(page.locator("#market")).to_be_visible(timeout=20_000)
            outbound = page.locator("#outbound")
            expect(outbound).to_be_visible(timeout=15_000)

            href = outbound.get_attribute("href") or ""
            target = outbound.get_attribute("target")
            rel = set((outbound.get_attribute("rel") or "").split())
            assert href.startswith(f"/out/{market['venue']}?"), href
            assert target == "_blank"
            assert "noopener" in rel
            assert "noreferrer" in rel

            original_url = page.url
            with page.expect_popup(timeout=10_000) as popup_info:
                outbound.click()
            popup = popup_info.value
            popup.wait_for_load_state("domcontentloaded")
            assert page.url == original_url
            assert page.evaluate("document.visibilityState") in {"visible", "hidden"}
            assert popup.evaluate("window.opener === null") is True
            assert not errors, errors
        finally:
            context.close()
            request.dispose()
            browser.close()
