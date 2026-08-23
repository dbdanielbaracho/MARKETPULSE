from pathlib import Path


INDEX_TEMPLATE = Path("app/templates/index.html")


def test_comparisons_are_automatic_and_never_require_market_hunting():
    source = INDEX_TEMPLATE.read_text(encoding="utf-8")

    assert "Cross-platform comparisons" in source
    assert "Customers never need to search market by market." in source
    assert "No verified equivalent contracts are currently available" in source
    assert "renderComparisons(data)" in source
    assert 'id="compare-left"' not in source
    assert 'id="compare-right"' not in source
    assert "FIRST MARKET" not in source
    assert "SECOND MARKET" not in source


def test_discovery_cards_explain_relevance_and_platform():
    source = INDEX_TEMPLATE.read_text(encoding="utf-8")

    assert "venue-badge" in source
    assert "POLYMARKET" in source
    assert "KALSHI" in source
    assert "View PrediBeacon analysis" in source
    assert "Volume reported by venue" in source
    assert "function relevanceReason" in source
    assert "if(pct>0&&pct<1)return '<1%'" in source
