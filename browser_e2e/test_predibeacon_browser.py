from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, Route, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _server():
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "MP_INGESTION_ENABLED": "false",
            "MP_OFFICIAL_EVIDENCE": "false",
            "MP_CONTENT_CANDIDATES": "false",
            "MP_CONTENT_DRAFTS": "false",
            "MP_DATABASE_PATH": str(ROOT / ".browser-test.db"),
            "MP_PUBLIC_BASE_URL": "https://predibeacon.com",
        }
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.entrypoint:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urlopen(base + "/", timeout=1) as r:
                    if r.status < 500:
                        break
            except Exception:
                time.sleep(0.15)
        else:
            raise RuntimeError("local PrediBeacon server did not become ready")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def base_url():
    with _server() as base:
        yield base


def _market(venue: str, idx: int, category: str = "Tech") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "canonical_id": f"{venue}-{idx}",
        "title": f"{venue.title()} sample market {idx}",
        "venue": venue,
        "category": category,
        "probability": 0.61 if idx % 2 else 0.42,
        "probability_change": 0.07 if idx % 2 else -0.03,
        "volume_usd": 250000 + idx * 1000,
        "trend_score": 80 - idx,
        "observed_at": now.isoformat(),
        "closes_at": (now + timedelta(days=2 + idx)).isoformat(),
        "source_url": f"https://example.com/{venue}/{idx}",
        "slug": f"{venue}-sample-market-{idx}-abcdef12",
    }


MARKETS = [
    _market("kalshi", 1, "Economy"),
    _market("kalshi", 2, "Politics"),
    _market("kalshi", 3, "Sports"),
    _market("kalshi", 4, "Tech"),
    _market("polymarket", 5, "Economy"),
    _market("polymarket", 6, "Politics"),
    _market("polymarket", 7, "Sports"),
    _market("polymarket", 8, "Tech"),
]


def _json(route: Route, body, status: int = 200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def _install_api_mock(page: Page, state: str = "normal") -> list[str]:
    seen: list[str] = []

    def handler(route: Route):
        url = route.request.url
        seen.append(url)
        if state == "slow":
            time.sleep(0.35)
        if "/api/v1/status" in url:
            if state == "error":
                return _json(route, {"detail": "down"}, 503)
            return _json(
                route,
                {
                    "freshness": "fresh",
                    "venue_market_counts": {
                        "kalshi": 0 if state == "partial" else 4,
                        "polymarket": 4,
                    },
                },
            )
        if "/api/v1/compare/pairs" in url:
            if state == "error":
                return _json(route, {"detail": "down"}, 503)
            return _json(route, {"pairs": []})
        if "/api/v1/market/cross-platform" in url:
            if state == "error":
                return _json(route, {"detail": "down"}, 503)
            return _json(route, {"counterpart": None, "verification": None})
        if "/api/v1/markets/closing-soon" in url:
            if state == "error":
                return _json(route, {"detail": "down"}, 503)
            selected = [] if state == "empty" else MARKETS[:3]
            return _json(route, selected)
        if "/api/v1/discovery" in url:
            if state == "error":
                return _json(route, {"detail": "down"}, 503)
            if state == "empty":
                return _json(route, [])
            from urllib.parse import parse_qs, urlsplit

            qs = parse_qs(urlsplit(url).query)
            rows = list(MARKETS)
            venue = qs.get("venue", [""])[0]
            category = qs.get("category", [""])[0]
            if state == "partial":
                rows = [x for x in rows if x["venue"] == "polymarket"]
            if venue:
                rows = [x for x in rows if x["venue"] == venue]
            if category:
                rows = [x for x in rows if x["category"] == category]
            return _json(route, rows)
        return route.continue_()

    page.route("**/api/v1/**", handler)
    return seen


def _new_page(browser, base_url: str, state="normal", viewport=None):
    context = browser.new_context(viewport=viewport or {"width": 1440, "height": 900})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    seen = _install_api_mock(page, state=state)
    page.goto(base_url + "/", wait_until="domcontentloaded")
    return context, page, errors, seen


def _set_hidden_select(page: Page, selector: str, value: str):
    page.locator(selector).evaluate(
        "(el, value) => { el.value = value; el.dispatchEvent(new Event('change', {bubbles:true})); }",
        value,
    )


def test_venue_hub_clicks_are_real_navigation_and_real_filters(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url)
        try:
            page.locator("[data-venue-link='kalshi']").first.click()
            page.wait_for_url("**/?venue=kalshi#markets")
            expect(page.locator("#venue")).to_have_value("kalshi")
            page.wait_for_function("document.querySelectorAll('#grid .card').length > 0")
            assert page.locator("#grid .venue-badge.polymarket").count() == 0
            assert page.locator("#grid .venue-badge.kalshi").count() > 0

            page.goto(base_url + "/", wait_until="domcontentloaded")
            page.locator("[data-venue-link='polymarket']").first.click()
            page.wait_for_url("**/?venue=polymarket#markets")
            expect(page.locator("#venue")).to_have_value("polymarket")
            page.wait_for_function("document.querySelectorAll('#grid .card').length > 0")
            assert page.locator("#grid .venue-badge.kalshi").count() == 0
            assert page.locator("#grid .venue-badge.polymarket").count() > 0

            page.goto(base_url + "/?venue=kalshi#markets", wait_until="domcontentloaded")
            page.locator("[data-venue-link='all']").first.click()
            page.wait_for_url("**/?venue=all#markets")
            expect(page.locator("#venue")).to_have_value("")
            page.wait_for_function("document.querySelectorAll('#grid .card').length >= 2")
            assert page.locator("#grid .venue-badge.kalshi").count() > 0
            assert page.locator("#grid .venue-badge.polymarket").count() > 0
            assert not errors
        finally:
            context.close()
            browser.close()


def test_every_platform_sort_category_combination_emits_correct_query(base_url):
    platforms = ["", "kalshi", "polymarket"]
    sorts = ["trending", "movers", "volume"]
    categories = ["", "Economy", "Politics", "Sports", "Tech"]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, seen = _new_page(browser, base_url)
        try:
            from urllib.parse import parse_qs, urlsplit

            def matches(url: str, platform: str, sort: str, category: str) -> bool:
                if "/api/v1/discovery" not in url:
                    return False
                q = parse_qs(urlsplit(url).query)
                return (
                    q.get("sort") == [sort]
                    and q.get("limit") == ["100"]
                    and q.get("venue", [""])[0] == platform
                    and q.get("category", [""])[0] == category
                )

            for platform in platforms:
                _set_hidden_select(page, "#venue", platform)
                for sort in sorts:
                    page.locator("#sort").select_option(sort)
                    for category in categories:
                        selector = f".chip[data-category='{category}']"
                        before = len(seen)
                        page.locator(selector).click()
                        page.wait_for_timeout(70)
                        fresh = seen[before:]
                        assert any(matches(u, platform, sort, category) for u in fresh), (
                            platform,
                            sort,
                            category,
                            fresh,
                        )
                        expect(page.locator(selector)).to_have_attribute("aria-pressed", "true")
                        assert page.locator(".chip[aria-pressed='true']").count() == 1
            assert not errors
        finally:
            context.close()
            browser.close()


def test_all_quick_filter_buttons(base_url):
    expected = {
        "trending": "sort=trending",
        "movers": "sort=movers",
        "volume": "sort=volume",
        "closing": "/api/v1/markets/closing-soon",
    }
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, seen = _new_page(browser, base_url)
        try:
            for mode, marker in expected.items():
                before = len(seen)
                page.locator(f".quick-filter[data-q='{mode}']").click()
                page.wait_for_timeout(40)
                fresh = seen[before:]
                assert any(marker in u for u in fresh), (mode, fresh)
                expect(page.locator(f".quick-filter[data-q='{mode}']")).to_have_attribute("aria-pressed", "true")
                assert page.locator(".quick-filter[aria-pressed='true']").count() == 1
            assert not errors
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("state", ["normal", "empty", "partial", "error", "slow"])
def test_data_states_never_freeze_browser(base_url, state):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url, state=state)
        try:
            page.wait_for_timeout(900)
            assert page.evaluate("1 + 1") == 2
            assert page.locator("body").is_visible()
            if state == "normal":
                page.wait_for_function("document.querySelectorAll('#grid .card').length > 0")
            elif state == "empty":
                expect(page.locator("#state")).to_contain_text("No markets")
            elif state == "error":
                expect(page.locator("#count")).not_to_have_text("Loading…")
            assert not errors
        finally:
            context.close()
            browser.close()


def test_watch_button_persists_and_analysis_links_are_valid(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url)
        try:
            page.wait_for_function("document.querySelectorAll('#grid .card').length > 0")
            watch = page.locator("#grid .watch").first
            market_id = watch.get_attribute("data-id")
            watch.click()
            expect(watch).to_contain_text("Watching")
            stored = page.evaluate("JSON.parse(localStorage.getItem('predibeacon-watchlist') || '[]')")
            assert market_id in stored
            href = page.locator("#grid .actions .primary").first.get_attribute("href")
            assert href and href.startswith("/") and "javascript:" not in href.lower()
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("document.querySelectorAll('#grid .watch').length > 0")
            expect(page.locator(f"#grid .watch[data-id='{market_id}']")).to_contain_text("Watching")
            assert not errors
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 1440, "height": 900},
        {"width": 1280, "height": 720},
        {"width": 768, "height": 1024},
        {"width": 390, "height": 844},
    ],
)
def test_responsive_layout_has_no_material_horizontal_overflow(base_url, viewport):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url, viewport=viewport)
        try:
            page.wait_for_timeout(350)
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 2, (viewport, overflow)
            assert page.locator(".venue-hub").is_visible()
            assert page.locator("#markets").is_visible()
            assert not errors
        finally:
            context.close()
            browser.close()


def test_keyboard_can_activate_all_three_venue_choices(base_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context, page, errors, _ = _new_page(browser, base_url)
        try:
            kalshi = page.locator("[data-venue-link='kalshi']").first
            kalshi.focus()
            page.keyboard.press("Enter")
            page.wait_for_url("**/?venue=kalshi#markets")

            page.goto(base_url + "/", wait_until="domcontentloaded")
            poly = page.locator("[data-venue-link='polymarket']").first
            poly.focus()
            page.keyboard.press("Enter")
            page.wait_for_url("**/?venue=polymarket#markets")

            page.goto(base_url + "/?venue=kalshi#markets", wait_until="domcontentloaded")
            beacon = page.locator("[data-venue-link='all']").first
            beacon.focus()
            page.keyboard.press("Enter")
            page.wait_for_url("**/?venue=all#markets")
            assert not errors
        finally:
            context.close()
            browser.close()
