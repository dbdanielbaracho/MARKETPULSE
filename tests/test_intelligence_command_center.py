from pathlib import Path


TOP = Path("app/templates/top.html")
MARKET = Path("app/templates/market.html")


def test_intelligence_command_center_has_core_products():
    source = TOP.read_text(encoding="utf-8")
    for label in (
        "SMART MOVERS",
        "BREAKING MARKETS",
        "FRESH MARKETS",
        "CATALYST MONITOR",
        "RESOLUTION CALENDAR",
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
    assert "never labels lookalike contracts equivalent without verification" in source
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


def test_fresh_markets_are_described_as_newly_observed_not_newly_listed():
    source = TOP.read_text(encoding="utf-8")
    assert "Newly observed by PrediBeacon" in source
    assert "not necessarily a newly listed venue contract" in source
    assert "This does not prove the venue listed it at that time." in source


def test_catalyst_context_never_claims_causation():
    source = TOP.read_text(encoding="utf-8")
    assert "/api/v1/market/timeline" in source
    assert "context, not proof of causation" in source
    assert "does not claim this event caused the price change" in source


def test_venue_comparison_does_not_overclaim_execution_quality():
    source = TOP.read_text(encoding="utf-8")
    assert "Reported volume is an activity proxy, not execution quality." in source
    assert "It does not claim better price, spread, depth, fees or execution." in source


def test_market_detail_has_quality_breaking_and_verified_consensus():
    source = MARKET.read_text(encoding="utf-8")
    assert "MARKET QUALITY" in source
    assert "CROSS-PLATFORM CHECK" in source
    assert "Breaking signal:" in source
    assert "VERIFIED EQUIVALENT" in source
    assert "Consensus is the simple mean of two verified equivalent contracts" in source
    assert "not outcome confidence" in source
