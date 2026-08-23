from __future__ import annotations

import os
import time

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright


pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production smoke runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")
RAILWAY = os.getenv(
    "PREDIBEACON_RAILWAY_URL",
    "https://marketpulse-production-aa9f.up.railway.app",
)


def _open(page, url: str):
    response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    assert response is not None
    assert response.status < 500, (url, response.status)
    expect(page.locator("body")).to_be_visible()
    expect(page.locator(".venue-hub")).to_be_visible(timeout=15_000)
    assert page.evaluate("1 + 1") == 2


def test_custom_domain_and_railway_origin_render_same_product_shell():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            snapshots = {}
            for label, url in (("custom", CUSTOM), ("railway", RAILWAY)):
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                _open(page, url)
                snapshots[label] = page.evaluate(
                    """() => {
                      const hero = document.querySelector('.hero-v2')?.getBoundingClientRect();
                      const hub = document.querySelector('.venue-hub')?.getBoundingClientRect();
                      return {
                        title: document.title,
                        heroWidth: Math.round(hero?.width || 0),
                        hubWidth: Math.round(hub?.width || 0),
                        hasKalshi: !!document.querySelector('[data-venue-link="kalshi"]'),
                        hasAll: !!document.querySelector('[data-venue-link="all"]'),
                        hasPolymarket: !!document.querySelector('[data-venue-link="polymarket"]'),
                      };
                    }"""
                )
                assert snapshots[label]["hasKalshi"]
                assert snapshots[label]["hasAll"]
                assert snapshots[label]["hasPolymarket"]
                assert not errors, (label, errors)
                context.close()

            assert snapshots["custom"]["title"] == snapshots["railway"]["title"]
            assert abs(snapshots["custom"]["heroWidth"] - snapshots["railway"]["heroWidth"]) <= 4
            assert abs(snapshots["custom"]["hubWidth"] - snapshots["railway"]["hubWidth"]) <= 4
        finally:
            browser.close()


def test_custom_domain_venue_buttons_navigate_and_browser_stays_responsive():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            _open(page, CUSTOM)

            page.locator("[data-venue-link='kalshi']").first.click()
            page.wait_for_url("**/?venue=kalshi#markets", timeout=15_000)
            assert page.evaluate("1 + 1") == 2
            expect(page.locator("#venue")).to_have_value("kalshi")

            page.goto(CUSTOM, wait_until="domcontentloaded")
            page.locator("[data-venue-link='polymarket']").first.click()
            page.wait_for_url("**/?venue=polymarket#markets", timeout=15_000)
            assert page.evaluate("1 + 1") == 2
            expect(page.locator("#venue")).to_have_value("polymarket")

            page.goto(CUSTOM + "/?venue=kalshi#markets", wait_until="domcontentloaded")
            page.locator("[data-venue-link='all']").first.click()
            page.wait_for_url("**/?venue=all#markets", timeout=15_000)
            assert page.evaluate("1 + 1") == 2
            expect(page.locator("#venue")).to_have_value("")
            assert not errors, errors
        finally:
            context.close()
            browser.close()


def test_production_loading_state_is_bounded_and_page_never_freezes():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            _open(page, CUSTOM)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                assert page.evaluate("1 + 1") == 2
                count = page.locator("#count").text_content() or ""
                state = page.locator("#state").text_content() or ""
                if "Loading" not in count and "Loading" not in state:
                    break
                page.wait_for_timeout(400)
            else:
                pytest.fail("production remained in Loading state for more than 20 seconds")
            assert not errors, errors
        finally:
            context.close()
            browser.close()


def test_public_internal_routes_do_not_return_server_errors():
    paths = [
        "/",
        "/top",
        "/watchlist",
        "/alerts",
        "/articles",
        "/methodology",
        "/risk",
        "/privacy",
        "/terms",
    ]
    with sync_playwright() as p:
        request = p.request.new_context(base_url=CUSTOM)
        try:
            failures = []
            for path in paths:
                response = request.get(path, timeout=20_000)
                if response.status >= 500:
                    failures.append((path, response.status))
            assert not failures, failures
        finally:
            request.dispose()
