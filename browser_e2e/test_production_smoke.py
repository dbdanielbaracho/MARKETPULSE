from __future__ import annotations

import os
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

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


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, value
    return parsed.astimezone(timezone.utc)


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
        "/robots.txt",
        "/sitemap.xml",
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


def test_live_market_payload_has_strict_provenance_and_valid_values():
    with sync_playwright() as p:
        request = p.request.new_context(base_url=CUSTOM)
        try:
            response = request.get("/api/v1/markets?limit=100", timeout=25_000)
            assert response.ok, response.status
            items = response.json()
            assert isinstance(items, list)

            ids: set[str] = set()
            now = datetime.now(timezone.utc)
            for item in items:
                market_id = item["canonical_id"]
                venue = item["venue"]
                assert market_id not in ids, market_id
                ids.add(market_id)
                assert venue in {"kalshi", "polymarket"}
                assert market_id.startswith(f"{venue}:"), (market_id, venue)

                probability = item.get("probability")
                if probability is not None:
                    assert 0 <= probability <= 1, (market_id, probability)
                volume = item.get("volume_usd")
                if volume is not None:
                    assert volume >= 0, (market_id, volume)
                trend = item.get("trend_score")
                assert 0 <= trend <= 100, (market_id, trend)

                observed = _parse_dt(item.get("observed_at"))
                assert observed is not None
                assert observed <= now + timedelta(minutes=5), (market_id, observed)

                closes = _parse_dt(item.get("closes_at"))
                if closes is not None:
                    assert closes > now - timedelta(minutes=5), (
                        market_id,
                        "closed contract still exposed as active discovery market",
                        closes,
                    )

                source = item.get("source_url")
                if source:
                    host = (urlsplit(source).hostname or "").casefold()
                    expected = "kalshi.com" if venue == "kalshi" else "polymarket.com"
                    assert host == expected or host.endswith("." + expected), (
                        market_id,
                        venue,
                        source,
                    )
        finally:
            request.dispose()


def test_live_venue_filters_never_leak_the_other_platform():
    with sync_playwright() as p:
        request = p.request.new_context(base_url=CUSTOM)
        try:
            for venue in ("kalshi", "polymarket"):
                response = request.get(f"/api/v1/markets?venue={venue}&limit=100", timeout=25_000)
                assert response.ok, (venue, response.status)
                items = response.json()
                assert all(item["venue"] == venue for item in items), (venue, items[:3])
        finally:
            request.dispose()


def test_live_relevance_ranking_is_ordered_deduplicated_and_open():
    with sync_playwright() as p:
        request = p.request.new_context(base_url=CUSTOM)
        try:
            response = request.get("/api/v1/markets/relevant?limit=100", timeout=25_000)
            assert response.ok, response.status
            items = response.json()
            scores = [item["relevance_score"] for item in items]
            assert all(0 <= score <= 100 for score in scores)
            assert scores == sorted(scores, reverse=True), scores

            seen: set[tuple[str, str]] = set()
            now = datetime.now(timezone.utc)
            for item in items:
                identity = (
                    " ".join(item["title"].casefold().split()),
                    item.get("closes_at") or "",
                )
                assert identity not in seen, identity
                seen.add(identity)
                closes = _parse_dt(item.get("closes_at"))
                if closes is not None:
                    assert closes > now - timedelta(minutes=5), (
                        item["canonical_id"],
                        closes,
                    )
        finally:
            request.dispose()


def test_public_seo_points_to_custom_domain_not_railway_origin():
    with sync_playwright() as p:
        request = p.request.new_context(base_url=CUSTOM)
        try:
            robots = request.get("/robots.txt", timeout=20_000)
            sitemap = request.get("/sitemap.xml", timeout=20_000)
            assert robots.ok
            assert sitemap.ok
            robots_text = robots.text()
            sitemap_text = sitemap.text()
            assert "https://predibeacon.com/sitemap.xml" in robots_text
            assert "https://predibeacon.com/" in sitemap_text
            assert "up.railway.app" not in robots_text
            assert "up.railway.app" not in sitemap_text
        finally:
            request.dispose()
