from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen

import pytest

from app.middleware.home_client_dedup import RENDER_CURATION_VERSION

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Route, sync_playwright


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _server():
    port = _free_port()
    env = os.environ.copy()
    env.update({"MP_INGESTION_ENABLED": "false", "MP_OFFICIAL_EVIDENCE": "false"})
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.entrypoint:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urlopen(base + "/", timeout=1) as response:
                    if response.status < 500:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("local server did not become ready")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _market(title: str, market_id: str, *, volume=1000.0, relevance=70.0):
    now = datetime.now(timezone.utc)
    return {
        "canonical_id": market_id,
        "title": title,
        "venue": "polymarket",
        "category": "Economy",
        "probability": 0.5,
        "probability_change": 0.02,
        "volume_usd": volume,
        "trend_score": relevance,
        "observed_at": now.isoformat(),
        "closes_at": (now + timedelta(days=2)).isoformat(),
        "slug": market_id.replace(":", "-"),
    }


def _fulfill_json(route: Route, body):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def test_uncurated_api_payload_can_never_be_observed_as_uncurated_dom():
    payload = [
        _market("Will the price of Bitcoin be above $111,000 on August 25?", "polymarket:btc111"),
        _market("Will the price of Bitcoin be above $109,000 on August 25?", "polymarket:btc109"),
        _market("Zero volume leak", "polymarket:zero", volume=0.0),
        _market("Chicago WS wins by over 9.5 runs?", "kalshi:thin", volume=1.0),
        _market("Low relevance leak", "polymarket:low", relevance=2.0),
        _market("Independent quality market", "polymarket:good"),
    ]

    with _server() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        def handler(route: Route):
            url = route.request.url
            if "/api/v1/status" in url:
                return _fulfill_json(route, {"freshness": "fresh", "venue_market_counts": {"kalshi": 1, "polymarket": 5}})
            if "/api/v1/compare/pairs" in url:
                return _fulfill_json(route, {"pairs": []})
            if "/api/v1/markets" in url:
                return _fulfill_json(route, payload)
            return route.continue_()

        page.route("**/api/v1/**", handler)
        try:
            response = page.goto(base + "/", wait_until="domcontentloaded")
            assert response is not None and response.ok
            assert response.headers.get("x-predibeacon-render-curation") == RENDER_CURATION_VERSION
            assert page.locator(f'script[data-predibeacon-render-curation="{RENDER_CURATION_VERSION}"]').count() == 1
            page.wait_for_function("!document.querySelector('#count').textContent.includes('Loading')")

            visible_titles = page.locator("#grid .card:visible h3").all_text_contents()
            assert len(visible_titles) == 2, visible_titles
            assert "Will the price of Bitcoin be above $111,000 on August 25?" in visible_titles
            assert "Will the price of Bitcoin be above $109,000 on August 25?" not in visible_titles
            assert "Zero volume leak" not in visible_titles
            assert "Chicago WS wins by over 9.5 runs?" not in visible_titles
            assert "Low relevance leak" not in visible_titles
            assert "Independent quality market" in visible_titles
            assert page.locator("#count").text_content() == "2 markets"
            assert not errors, errors
        finally:
            context.close()
            browser.close()
