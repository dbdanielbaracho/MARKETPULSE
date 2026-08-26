from __future__ import annotations

import os

import pytest

from app.middleware.home_client_dedup import CURATION_VERSION, MIN_HOMEPAGE_VOLUME_USD

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production thin-activity regression runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")
RAILWAY = os.getenv(
    "PREDIBEACON_RAILWAY_URL",
    "https://marketpulse-production-aa9f.up.railway.app",
)
ESCAPED_TITLE = "Chicago WS wins by over 9.5 runs?"


def test_real_production_rejects_thin_activity_from_kalshi_discovery():
    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            for label, base in (("custom", CUSTOM), ("railway", RAILWAY)):
                response = request.get(
                    base + "/api/v1/markets?venue=kalshi&sort=movers&limit=100",
                    timeout=30_000,
                )
                assert response.ok, (label, response.status)
                headers = {key.casefold(): value for key, value in response.headers.items()}
                assert headers.get("x-predibeacon-curation") == CURATION_VERSION, (label, headers)

                items = response.json()
                assert isinstance(items, list), (label, type(items))
                for item in items:
                    volume = item.get("volume_usd")
                    assert isinstance(volume, (int, float)) and not isinstance(volume, bool), (label, item)
                    assert volume >= MIN_HOMEPAGE_VOLUME_USD, (label, item.get("canonical_id"), volume)

                escaped = [
                    item
                    for item in items
                    if item.get("title") == ESCAPED_TITLE and (item.get("volume_usd") or 0) < MIN_HOMEPAGE_VOLUME_USD
                ]
                assert not escaped, (label, escaped)
        finally:
            request.dispose()
