from pathlib import Path


INDEX_TEMPLATE = Path("app/templates/index.html")


def test_comparisons_are_automatic_and_never_require_market_hunting():
    source = INDEX_TEMPLATE.read_text(encoding="utf-8")

    assert "Cross-platform comparisons" in source
    assert "checks both current provider feeds" in source
    assert "No same-question candidate is present on both current feeds" in source
    assert "comparisons()" in source
    assert 'id="compare-left"' not in source
    assert 'id="compare-right"' not in source
    assert 'id="search"' not in source
    assert "FIRST MARKET" not in source
    assert "SECOND MARKET" not in source


def test_discovery_cards_explain_relevance_platform_and_rank():
    source = INDEX_TEMPLATE.read_text(encoding="utf-8")

    assert "venue-badge" in source
    assert "POLYMARKET" in source
    assert "KALSHI" in source
    assert "View analysis" in source
    assert "Why it matters:" in source
    assert "Reported volume" not in source or "Volume" in source
    assert "function why" in source
    assert "Trend" in source
    assert "class=\"rank\"" in source
    assert "Watching" in source
