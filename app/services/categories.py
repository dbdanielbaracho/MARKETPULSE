from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping


CATEGORY_LABELS = ("Economy", "Politics", "Sports", "Tech")

_PROVIDER_ALIASES = {
    "Economy": {
        "business", "crypto", "cryptocurrency", "economics", "economy",
        "finance", "financials", "markets",
    },
    "Politics": {
        "election", "elections", "geopolitics", "politics", "world politics",
    },
    "Sports": {
        "baseball", "basketball", "esports", "football", "golf", "hockey",
        "mma", "soccer", "sports", "tennis",
    },
    "Tech": {
        "ai", "artificial intelligence", "science and technology", "tech",
        "technology",
    },
}

_POLITICS_PATTERNS = (
    r"\belection\b", r"\bpresidential\b", r"\bpresident\b",
    r"\bnomination\b", r"\bdemocratic\b", r"\brepublican\b",
    r"\bsenate\b", r"\bsenator\b", r"\bcongress\b", r"\bgovernor\b",
    r"\bprime minister\b", r"\bparliament\b", r"\bceasefire\b",
    r"\bsigned into law\b", r"\binvade\b", r"\bleadership change\b",
    r"\bmilitary control\b", r"\bwhite house\b", r"\bmayor\b",
)

_ECONOMY_PATTERNS = (
    r"\bfed\b", r"\bfederal reserve\b", r"\binterest rates?\b",
    r"\binflation\b", r"\bcpi\b", r"\bgdp\b", r"\bunemployment\b",
    r"\brecession\b", r"\btariffs?\b", r"\bbitcoin\b", r"\bethereum\b",
    r"\bcrypto\b", r"\bcrude oil\b", r"\bwti\b", r"\bnasdaq\b",
    r"\bs&p\b", r"\bstock market\b", r"\btreasur(?:y|ies)\b",
    r"\bcentral bank\b", r"\bmortgage\b", r"\bexchange rate\b",
)

_TECH_PATTERNS = (
    r"\bartificial intelligence\b", r"\bopenai\b", r"\bchatgpt\b",
    r"\bnvidia\b", r"\bspacex\b", r"\btesla\b", r"\bapple\b",
    r"\bmicrosoft\b", r"\bgoogle\b", r"\bquantum\b", r"\brobot(?:s|ics)?\b",
    r"\bsemiconductor\b", r"\bsoftware\b", r"\btechnology\b",
    r"\belon musk\b", r"\bai model\b",
)

_SPORTS_PATTERNS = (
    r"\bvs\.?\b", r"\bo/u\b", r"\bover/under\b", r"\bspread:\s",
    r"\bstrikeouts?\b", r"\bouts recorded\b", r"\bfull game\b",
    r"\binnings?\b", r"\btouchdowns?\b", r"\bgoals?\b",
    r"\bpoints\?\b", r"\bufc\b", r"\bballon d'or\b",
    r"\bchampionship\b", r"\bgame \d+ winner\b", r"\bbo[1357]\b",
    r"\bnba\b", r"\bwnba\b", r"\bnfl\b", r"\bmlb\b", r"\bnhl\b",
    r"\bepl\b", r"\buefa\b", r"\blcs\b", r"\blck\b", r"\blpl\b",
    r"\bvct\b", r"\bdota 2\b", r"\bvalorant\b", r"\bwin on 20\d{2}-",
)


def _normalized_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.casefold().split())


def _provider_label(value: object) -> str | None:
    normalized = _normalized_text(value)
    if not normalized:
        return None
    for label, aliases in _PROVIDER_ALIASES.items():
        if normalized in aliases:
            return label
    return None


def _metadata_text(raw: Mapping[str, Any] | None) -> str:
    if not raw:
        return ""
    values: list[object] = []
    for key in (
        "category", "subcategory", "sport", "league", "series_ticker",
        "event_ticker", "sportsMarketType", "sports_market_type",
    ):
        value = raw.get(key)
        if value:
            values.append(value)
    for collection_key in ("events", "tags"):
        collection = raw.get(collection_key)
        if isinstance(collection, list):
            for item in collection[:10]:
                if isinstance(item, Mapping):
                    for key in ("category", "title", "label", "name", "slug", "ticker"):
                        value = item.get(key)
                        if value:
                            values.append(value)
                elif item:
                    values.append(item)
    return " ".join(_normalized_text(value) for value in values)


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def classify_market_category(
    *,
    title: str,
    provider_category: object = None,
    raw: Mapping[str, Any] | None = None,
) -> str | None:
    """Return the stable PrediBeacon category used by public filters."""
    title_text = _normalized_text(title)

    # Strong signals in the public title outrank noisy provider metadata. Some
    # venue payloads attach sports tags to non-sports events in shared groups.
    for label, patterns in (
        ("Politics", _POLITICS_PATTERNS),
        ("Economy", _ECONOMY_PATTERNS),
        ("Tech", _TECH_PATTERNS),
        ("Sports", _SPORTS_PATTERNS),
    ):
        if _matches(title_text, patterns):
            return label

    explicit = _provider_label(provider_category)
    if explicit:
        return explicit

    if raw and any(raw.get(key) for key in (
        "gameStartTime", "game_start_time", "gameId", "game_id",
        "sportsMarketType", "sports_market_type",
    )):
        return "Sports"

    text = " ".join(part for part in (title_text, _metadata_text(raw)) if part)
    for label, patterns in (
        ("Politics", _POLITICS_PATTERNS),
        ("Economy", _ECONOMY_PATTERNS),
        ("Tech", _TECH_PATTERNS),
        ("Sports", _SPORTS_PATTERNS),
    ):
        if _matches(text, patterns):
            return label
    return None
