from __future__ import annotations

import os
from urllib.parse import quote

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production mobile acceptance runs only in the dedicated workflow",
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
    pytest.fail("no routable production market found for mobile acceptance")


def _find_visible_routable_market(page, request):
    """Choose the journey target from the cards the customer can actually see.

    The homepage is a ranked discovery view and is intentionally not identical to
    the generic /api/v1/markets ordering. Selecting a market from that unrelated
    endpoint made this acceptance test fail whenever ranking changed even though
    the real mobile journey was healthy.
    """
    hrefs = page.locator("#grid a[href^='/markets/']").evaluate_all(
        "els => [...new Set(els.map(el => el.getAttribute('href')).filter(Boolean))]"
    )
    assert hrefs, "production homepage rendered no internal market links"
    visible_slugs = {href.removeprefix("/markets/") for href in hrefs}

    response = request.get("/api/v1/markets?limit=100", timeout=25_000)
    assert response.ok, response.status
    markets = response.json()
    assert markets, "production discovery returned no markets"
    markets_by_slug = {market.get("slug"): market for market in markets if market.get("slug")}

    for slug in visible_slugs:
        market = markets_by_slug.get(slug)
        if not market:
            continue
        market_id = market.get("canonical_id")
        venue = market.get("venue")
        if not market_id or venue not in {"kalshi", "polymarket"}:
            continue
        route = request.get(
            "/api/v1/market/route?market_id=" + quote(market_id, safe=""),
            timeout=20_000,
        )
        if route.ok and route.json().get("available") is True:
            return market
    pytest.fail("no visible routable production market found for mobile acceptance")


def test_mobile_home_is_single_column_touch_ready_and_responsive():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            response = page.goto(CUSTOM, wait_until="domcontentloaded", timeout=30_000)
            assert response is not None and response.status < 500
            expect(page.locator(".venue-hub")).to_be_visible(timeout=15_000)
            expect(page.locator("[data-venue-link='all']").first).to_be_visible()
            expect(page.locator("[data-venue-link='kalshi']").first).to_be_visible()
            expect(page.locator("[data-venue-link='polymarket']").first).to_be_visible()
            expect(page.locator(".pb-mobile-nav")).to_be_visible()

            geometry = page.evaluate(
                """() => ({
                  scrollWidth: document.documentElement.scrollWidth,
                  clientWidth: document.documentElement.clientWidth,
                  navHeight: document.querySelector('.pb-mobile-nav')?.getBoundingClientRect().height || 0,
                  controls: [...document.querySelectorAll('.quick-filter')].map(x => x.getBoundingClientRect().height),
                  venues: [...document.querySelectorAll('[data-venue-link]')].map(x => x.getBoundingClientRect().width),
                })"""
            )
            assert geometry["scrollWidth"] <= geometry["clientWidth"] + 2, geometry
            assert geometry["navHeight"] >= 48, geometry
            assert geometry["controls"] and all(h >= 44 for h in geometry["controls"]), geometry
            assert all(w >= 300 for w in geometry["venues"]), geometry
            assert not errors, errors
        finally:
            context.close()
            browser.close()


def test_mobile_venue_navigation_filters_without_freezing():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            page.goto(CUSTOM, wait_until="domcontentloaded", timeout=30_000)
            page.locator("[data-venue-link='kalshi']").first.tap()
            page.wait_for_url("**/?venue=kalshi#markets", timeout=15_000)
            expect(page.locator("#venue")).to_have_value("kalshi")
            assert page.evaluate("1 + 1") == 2

            page.goto(CUSTOM, wait_until="domcontentloaded", timeout=30_000)
            page.locator("[data-venue-link='polymarket']").first.tap()
            page.wait_for_url("**/?venue=polymarket#markets", timeout=15_000)
            expect(page.locator("#venue")).to_have_value("polymarket")
            assert page.evaluate("1 + 1") == 2
            assert not errors, errors
        finally:
            context.close()
            browser.close()


def test_small_phone_keeps_primary_content_and_navigation_usable():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 320, "height": 640}, is_mobile=True, has_touch=True)
        page = context.new_page()
        try:
            page.goto(CUSTOM, wait_until="domcontentloaded", timeout=30_000)
            expect(page.locator(".venue-hub")).to_be_visible(timeout=15_000)
            expect(page.locator(".pb-mobile-nav")).to_be_visible()
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 2, overflow
        finally:
            context.close()
            browser.close()


def test_mobile_full_journey_home_to_internal_market_then_safe_external_cta():
    """MP-024 acceptance: the primary mobile journey stays usable end to end.

    The third-party destination is intercepted. This verifies the production
    experience owned by PrediBeacon without depending on external venue uptime.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        request = p.request.new_context(base_url=CUSTOM)
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
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
            response = page.goto(CUSTOM, wait_until="domcontentloaded", timeout=30_000)
            assert response is not None and response.status < 500
            page.wait_for_function("document.querySelectorAll('#grid .card').length > 0", timeout=20_000)
            market = _find_visible_routable_market(page, request)

            detail_path = f"/markets/{market['slug']}"
            detail_link = page.locator(f"#grid a[href='{detail_path}']").first
            expect(detail_link).to_be_visible(timeout=15_000)
            detail_box = detail_link.bounding_box()
            assert detail_box and detail_box["height"] >= 44, detail_box
            detail_link.tap()
            page.wait_for_url(f"**{detail_path}", timeout=15_000)

            expect(page.locator("#market")).to_be_visible(timeout=20_000)
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 2, overflow

            outbound = page.locator("#outbound")
            expect(outbound).to_be_visible(timeout=15_000)
            outbound_box = outbound.bounding_box()
            assert outbound_box and outbound_box["height"] >= 44, outbound_box
            assert outbound.get_attribute("target") == "_blank"
            rel = set((outbound.get_attribute("rel") or "").split())
            assert {"noopener", "noreferrer"}.issubset(rel)

            original_url = page.url
            with page.expect_popup(timeout=10_000) as popup_info:
                outbound.tap()
            popup = popup_info.value
            popup.wait_for_load_state("domcontentloaded")
            assert page.url == original_url
            assert popup.evaluate("window.opener === null") is True
            assert not errors, errors
        finally:
            context.close()
            request.dispose()
            browser.close()
