import pytest

from app.services.categories import classify_market_category


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Eagles vs. Patriots", "Sports"),
        ("Shane Drohan: 4+ strikeouts?", "Sports"),
        ("Grant McCray: 2+ hits + runs + RBIs?", "Sports"),
        ("Drew Gilbert: 1+ stolen bases?", "Sports"),
        ("Texas wins by over 5.5 runs?", "Sports"),
        ("Will Josh Stein win the 2028 Democratic presidential nomination?", "Politics"),
        ("Clarity Act signed into law in 2026?", "Politics"),
        ("Will the Fed decrease interest rates by 25 bps?", "Economy"),
        ("Will Bitcoin reach $100,000 in August?", "Economy"),
        ("Will platinum close above 1900 USD/ounce?", "Economy"),
        ("Will OpenAI release a new AI model?", "Tech"),
        ("Will Elon Musk post 240-259 tweets this week?", "Tech"),
        ("Will Anthropic valuation hit $3T?", "Tech"),
    ],
)
def test_title_fallback_produces_public_filter_categories(title, expected):
    assert classify_market_category(title=title) == expected


def test_provider_category_has_priority():
    assert classify_market_category(
        title="Ambiguous market",
        provider_category="cryptocurrency",
    ) == "Economy"


def test_kalshi_series_category_is_recognized():
    assert classify_market_category(
        title="Ambiguous contract title",
        raw={"_predibeacon_series_category": "Sports"},
    ) == "Sports"


def test_structural_sports_metadata_is_recognized():
    assert classify_market_category(
        title="Team A to win?",
        raw={"sportsMarketType": "moneyline"},
    ) == "Sports"


def test_unknown_market_is_not_forced_into_a_category():
    assert classify_market_category(title="A completely ambiguous contract") is None


def test_strong_title_signal_outranks_noisy_provider_category():
    assert classify_market_category(
        title="Will Elon Musk post 240-259 tweets this week?",
        provider_category="sports",
        raw={"sportsMarketType": "moneyline"},
    ) == "Tech"
