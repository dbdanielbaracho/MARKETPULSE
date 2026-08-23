from pathlib import Path


TOP = Path("app/templates/top.html")


def test_intelligence_command_center_has_core_products():
    source = TOP.read_text(encoding="utf-8")
    for label in (
        "SMART MOVERS",
        "BREAKING MARKETS",
        "MARKET QUALITY",
        "CATEGORY HEAT",
        "VERIFIED CONSENSUS",
        "VERIFIED DISAGREEMENTS",
        "VENUE COMPARISON",
    ):
        assert label in source


def test_consensus_and_disagreement_fail_closed_on_contract_equivalence():
    source = TOP.read_text(encoding="utf-8")
    assert "if(v.equivalent_contracts)" in source
    assert "Simple mean of two verified equivalent contracts" in source
    assert "Similar titles are excluded" in source
    assert "not a statistical forecast" in source


def test_market_quality_is_not_presented_as_outcome_confidence():
    source = TOP.read_text(encoding="utf-8")
    assert "They are not forecasts, trading advice, liquidity guarantees or outcome confidence." in source
    assert "How much can you trust the displayed signal?" in source
    assert "Completeness, freshness, activity and usable history" in source


def test_breaking_markets_uses_recorded_history_not_whale_claims():
    source = TOP.read_text(encoding="utf-8")
    assert "/api/v1/market/history" in source
    assert "6h acceleration" in source
    assert "reported-volume change" in source
    assert "WHALE" not in source
    assert "ARBITRAGE" not in source


def test_venue_comparison_does_not_overclaim_execution_quality():
    source = TOP.read_text(encoding="utf-8")
    assert "Reported volume is an activity proxy, not execution quality." in source
    assert "It does not claim better price, spread, depth, fees or execution." in source
