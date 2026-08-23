from __future__ import annotations

import os

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright


pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production smoke runs only in the dedicated workflow",
)

ROOT = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")
WWW = os.getenv("PREDIBEACON_WWW_URL", "https://www.predibeacon.com")


def test_www_is_reachable_and_resolves_to_the_same_product():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        try:
            page = context.new_page()
            response = page.goto(WWW, wait_until="domcontentloaded", timeout=30_000)
            assert response is not None
            assert response.status < 500, response.status
            page.locator(".venue-hub").wait_for(state="visible", timeout=15_000)
            assert "PREDIBEACON" in (page.locator("body").inner_text().upper())
            assert page.evaluate("1 + 1") == 2
        finally:
            context.close()
            browser.close()


def test_production_has_no_debug_traceback_or_server_signature_leakage():
    with sync_playwright() as p:
        request = p.request.new_context(base_url=ROOT)
        try:
            response = request.get("/__predibeacon_missing_route_for_smoke__", timeout=20_000)
            assert 400 <= response.status < 500, response.status
            body = response.text().casefold()
            assert "traceback (most recent call last)" not in body
            assert "uvicorn" not in body
            assert "starlette" not in body
        finally:
            request.dispose()


def test_production_content_type_and_clickjacking_headers_are_sane():
    with sync_playwright() as p:
        request = p.request.new_context(base_url=ROOT)
        try:
            response = request.get("/", timeout=20_000)
            assert response.ok
            headers = {k.casefold(): v for k, v in response.headers.items()}
            assert "text/html" in headers.get("content-type", "").casefold()
            assert headers.get("x-content-type-options", "").casefold() == "nosniff"
            frame = headers.get("x-frame-options", "").casefold()
            csp = headers.get("content-security-policy", "").casefold()
            assert frame in {"deny", "sameorigin"} or "frame-ancestors" in csp
        finally:
            request.dispose()
