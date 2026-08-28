from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright


pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production quality assertions run only against deployed production",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")

_THRESHOLD_PATTERNS = (
    re.compile(r"\b(above|below|over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+(?:us\$|\$|€|£|¥)?\s*\d[\d,]*(?:\.\d+)?", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\+\s*(?=(?:hits?|runs?|rbis?|goals?|assists?|rebounds?|points?|bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\b)", re.I),
)


def _family(title: str) -> str:
    value = " ".join(str(title or "").casefold().split())
    value = _THRESHOLD_PATTERNS[0].sub(r"\1 <threshold>", value)
    value = _THRESHOLD_PATTERNS[1].sub("<threshold>+ ", value)
    return " ".join(value.split())


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, value
    return parsed.astimezone(timezone.utc)


def test_real_relevant_feed_contains_only_homepage_quality_markets():
    with sync_playwright() as p:
        request = p.request.new_context(base_url=CUSTOM)
        try:
            response = request.get("/api/v1/markets/relevant?limit=100", timeout=25_000)
            assert response.ok, response.status
            items = response.json()
            assert isinstance(items, list)
            assert items, "production relevant feed unexpectedly returned no markets"

            now = datetime.now(timezone.utc)
            seen_families: set[tuple[str, str]] = set()
            failures: list[tuple[str, str, object]] = []
            for item in items:
                market_id = item.get("canonical_id") or "<missing-id>"
                volume = item.get("volume_usd")
                trend = item.get("trend_score")
                relevance = item.get("relevance_score")
                closes = _parse_dt(item.get("closes_at"))

                if not isinstance(volume, (int, float)) or volume <= 0:
                    failures.append((market_id, "volume_usd must be > 0", volume))
                if not isinstance(trend, (int, float)) or trend <= 0:
                    failures.append((market_id, "trend_score must be > 0", trend))
                if not isinstance(relevance, (int, float)) or relevance <= 0:
                    failures.append((market_id, "relevance_score must be > 0", relevance))
                if closes is not None and closes <= now + timedelta(minutes=55):
                    failures.append((market_id, "market closes too soon for homepage", closes.isoformat()))

                family = (str(item.get("venue") or "").casefold(), _family(str(item.get("title") or "")))
                if family in seen_families:
                    failures.append((market_id, "duplicate threshold/event family", family))
                seen_families.add(family)

            assert not failures, failures[:20]
        finally:
            request.dispose()


def test_real_homepage_visible_cards_never_show_known_bad_quality_patterns():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        try:
            response = page.goto(CUSTOM, wait_until="domcontentloaded", timeout=30_000)
            assert response is not None and response.status < 500

            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                visible = page.locator(".card:visible")
                count_text = page.locator("#count").text_content() or ""
                if visible.count() > 0 and "Loading" not in count_text and "Carregando" not in count_text:
                    break
                page.wait_for_timeout(400)
            else:
                pytest.fail("production homepage did not render visible market cards within 25 seconds")

            # Let lazy cross-platform status and localization observers settle for
            # the cards actually in the viewport before asserting customer copy.
            page.wait_for_timeout(1200)
            cards = page.locator(".card:visible")
            texts = [cards.nth(i).inner_text() for i in range(cards.count())]
            assert texts, "no visible homepage market cards"

            forbidden = []
            for text in texts:
                compact = " ".join(text.split())
                if re.search(r"\bUS\$\s*0(?:\D|$)", compact, re.I):
                    forbidden.append(("zero volume", compact[:240]))
                if re.search(r"(?:Relev[aâ]ncia|Trend)\s*0\s*/\s*100", compact, re.I):
                    forbidden.append(("zero relevance", compact[:240]))
                if re.search(r"(?:Fecha em|Closes in)\s*(?:em\s*)?0\s*(?:h|hora|horas|hour|hours)\b", compact, re.I):
                    forbidden.append(("immediate close", compact[:240]))
                if "Change unavailable" in compact:
                    forbidden.append(("unlocalized change unavailable", compact[:240]))
                if re.search(r"[▲▼]\s*0(?:[.,]0)?\s*pts\b", compact, re.I):
                    forbidden.append(("zero-point movement presented as mover", compact[:240]))
                if "A PrediBeacon classifica este mercado como de alta relevância neste momento." in compact:
                    forbidden.append(("generic high-relevance explanation", compact[:240]))
                if "Nenhum equivalente verificado encontrado" in compact:
                    forbidden.append(("verbose no-equivalent copy", compact[:240]))

            assert not forbidden, forbidden[:20]

            # Source/platform must be visible without opening the card.
            missing_venue_badge = [
                i for i in range(cards.count())
                if cards.nth(i).locator(".venue-badge").count() != 1
                or not cards.nth(i).locator(".venue-badge").inner_text().strip()
            ]
            assert not missing_venue_badge, missing_venue_badge

            titles = [
                cards.nth(i).locator("h3").inner_text().strip()
                for i in range(cards.count())
                if cards.nth(i).locator("h3").count()
            ]
            venues = [
                cards.nth(i).locator(".venue-badge").inner_text().strip().casefold()
                for i in range(cards.count())
                if cards.nth(i).locator(".venue-badge").count()
            ]
            seen: set[tuple[str, str]] = set()
            duplicates = []
            for index, title in enumerate(titles):
                venue = venues[index] if index < len(venues) else ""
                key = (venue, _family(title))
                if key in seen:
                    duplicates.append((venue, title))
                seen.add(key)
            assert not duplicates, duplicates[:20]
        finally:
            context.close()
            browser.close()
