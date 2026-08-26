from __future__ import annotations

import os

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production availability invariant runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")


def test_default_all_cannot_be_empty_when_provider_inventory_exists() -> None:
    """UEA360 production invariant derived from the real escaped defect.

    A user-visible zero result in the default All view is acceptable only when the
    underlying provider inventory is genuinely empty. If status reports inventory,
    discovery must return at least one quality-eligible market or expose a diagnosed
    service failure instead of a false 'no filters match' state.
    """
    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            status_response = request.get(CUSTOM + "/api/v1/status", timeout=30_000)
            assert status_response.ok, status_response.status
            status = status_response.json()
            counts = status.get("venue_market_counts") or {}
            provider_inventory = int(counts.get("kalshi") or 0) + int(counts.get("polymarket") or 0)

            discovery_response = request.get(CUSTOM + "/api/v1/markets?sort=trending&limit=100", timeout=30_000)
            assert discovery_response.ok, discovery_response.status
            markets = discovery_response.json()
            assert isinstance(markets, list)

            if provider_inventory > 0:
                assert markets, {
                    "defect": "provider inventory exists but default discovery collapsed to zero",
                    "provider_inventory": provider_inventory,
                    "provider_counts": counts,
                    "curation_input": discovery_response.headers.get("x-predibeacon-curation-input"),
                    "curation_output": discovery_response.headers.get("x-predibeacon-curation-output"),
                    "curation_mode": discovery_response.headers.get("x-predibeacon-curation-mode"),
                }
        finally:
            request.dispose()
