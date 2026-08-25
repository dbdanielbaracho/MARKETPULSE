from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("PREDIBEACON_PRODUCTION_SMOKE") != "1",
    reason="production quality audit runs only in the dedicated workflow",
)

CUSTOM = os.getenv("PREDIBEACON_CUSTOM_URL", "https://predibeacon.com")
RAILWAY = os.getenv(
    "PREDIBEACON_RAILWAY_URL",
    "https://marketpulse-production-aa9f.up.railway.app",
)
EXPECTED_CURATION = "quality-v2"
MIN_RELEVANCE = 5.0
MAX_PER_SUBJECT_PER_VENUE = 2


def _text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _family(title: str) -> str:
    value = _text(title)
    value = re.sub(
        r"\b(above|below|over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?",
        r"\1 <threshold>",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"(?:us\$|\$|€|£)?\s*\d[\d,]*(?:\.\d+)?\s*(?=(?:usd|eur|gbp|jpy|cad|aud|btc|eth)(?:\b|/))",
        "<threshold> ",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\b\d+(?:\.\d+)?\+\s*(?=(?:hits?|runs?|rbis?|rbi|goals?|assists?|rebounds?|points?|stolen\s+bases?|bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\b)",
        "<threshold>+ ",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\b(?:over|under|more\s+than|less\s+than|at\s+least|at\s+most)\s+\d+(?:\.\d+)?\s*(?=(?:runs?|goals?|points?|yards?|sets?|games?|rounds?)\b)",
        "<threshold> ",
        value,
        flags=re.I,
    )
    return " ".join(value.split())


def _subject(title: str) -> str:
    value = _text(title)
    stripped = re.sub(
        r"\s*:\s*(?:\d+(?:\.\d+)?\+?\s*)?(?:points?|assists?|rebounds?|threes?|three-pointers?|hits?|runs?|rbis?|goals?|stolen\s+bases?|strikeouts?|saves?|shots?|tackles?|receptions?|yards?)\??$",
        "",
        value,
        flags=re.I,
    ).strip()
    return stripped or value


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert_curated_payload(response, *, label: str) -> None:
    assert response.ok, (label, response.status)
    headers = {key.casefold(): value for key, value in response.headers.items()}
    assert headers.get("x-predibeacon-curation") == EXPECTED_CURATION, (label, headers)
    assert "x-predibeacon-curation-input" in headers, (label, headers)
    assert "x-predibeacon-curation-output" in headers, (label, headers)

    items = response.json()
    assert isinstance(items, list), (label, type(items))
    assert int(headers["x-predibeacon-curation-output"]) == len(items), (label, headers, len(items))
    assert int(headers["x-predibeacon-curation-input"]) >= len(items), (label, headers)

    now = datetime.now(timezone.utc)
    exact_seen: set[tuple[str, str]] = set()
    family_seen: set[tuple[str, str]] = set()
    subjects: Counter[tuple[str, str]] = Counter()

    for item in items:
        market_id = item.get("canonical_id")
        title = item.get("title")
        venue = item.get("venue")
        volume = item.get("volume_usd")
        relevance = item.get("trend_score")

        assert isinstance(market_id, str) and market_id, (label, item)
        assert isinstance(title, str) and title.strip(), (label, market_id)
        assert venue in {"kalshi", "polymarket"}, (label, market_id, venue)
        assert isinstance(volume, (int, float)) and not isinstance(volume, bool) and volume > 0, (
            label,
            market_id,
            volume,
        )
        assert isinstance(relevance, (int, float)) and not isinstance(relevance, bool) and relevance >= MIN_RELEVANCE, (
            label,
            market_id,
            relevance,
        )

        probability = item.get("probability")
        if probability is not None:
            assert isinstance(probability, (int, float)) and not isinstance(probability, bool)
            assert 0 <= probability <= 1, (label, market_id, probability)

        closes = _parse_dt(item.get("closes_at"))
        if closes is not None:
            assert closes > now + timedelta(minutes=55), (label, market_id, closes)

        exact = (venue, _text(title))
        family = (venue, _family(title))
        subject = (venue, _subject(title))
        assert exact not in exact_seen, (label, "exact duplicate", exact)
        assert family not in family_seen, (label, "family duplicate", family)
        exact_seen.add(exact)
        family_seen.add(family)
        subjects[subject] += 1
        assert subjects[subject] <= MAX_PER_SUBJECT_PER_VENUE, (
            label,
            "subject monopolization",
            subject,
            subjects[subject],
        )


def test_custom_and_railway_origins_execute_same_quality_gate():
    with sync_playwright() as p:
        request = p.request.new_context()
        try:
            for label, base in (("custom", CUSTOM), ("railway", RAILWAY)):
                for query in ("?limit=100", "?venue=kalshi&limit=100", "?venue=polymarket&limit=100"):
                    response = request.get(base + "/api/v1/markets" + query, timeout=30_000)
                    _assert_curated_payload(response, label=f"{label}:{query}")
        finally:
            request.dispose()


def test_browser_never_renders_zero_volume_or_subthreshold_relevance_cards():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            response = page.goto(CUSTOM, wait_until="domcontentloaded", timeout=30_000)
            assert response is not None and response.ok
            page.wait_for_function(
                """() => {
                    const count = document.querySelector('#count')?.textContent || '';
                    const state = document.querySelector('#state')?.textContent || '';
                    return !count.includes('Loading') && !state.includes('Loading');
                }""",
                timeout=25_000,
            )
            visible = page.locator("#grid .card:visible")
            cards = visible.evaluate_all(
                """cards => cards.map(card => ({
                    title: card.querySelector('h3')?.textContent?.trim() || '',
                    venue: card.querySelector('.venue-badge')?.textContent?.trim().toLowerCase() || '',
                    text: card.textContent || ''
                }))"""
            )
            family_seen: set[tuple[str, str]] = set()
            for card in cards:
                compact = re.sub(r"\s+", " ", card["text"])
                assert not re.search(r"Volume\s*US\$\s*0(?:\D|$)", compact, re.I), card
                relevance = re.search(r"(?:Relevance|Relevância|Trend)\s*([0-9]+(?:[.,][0-9]+)?)\s*/?100", compact, re.I)
                if relevance:
                    score = float(relevance.group(1).replace(",", "."))
                    assert score >= MIN_RELEVANCE, card
                family = (card["venue"], _family(card["title"]))
                assert family not in family_seen, ("visible family duplicate", family, cards)
                family_seen.add(family)
            assert not errors, errors
        finally:
            context.close()
            browser.close()
