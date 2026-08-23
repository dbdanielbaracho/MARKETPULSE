from __future__ import annotations

import os

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production mobile acceptance runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")


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
