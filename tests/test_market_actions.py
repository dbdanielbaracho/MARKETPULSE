from pathlib import Path


MARKET_TEMPLATE = Path("app/templates/market.html")


def test_market_link_action_is_unambiguous_and_copies_canonical_url():
    source = MARKET_TEMPLATE.read_text(encoding="utf-8")

    assert "Copy market link" in source
    assert "Market link copied" in source
    assert "navigator.clipboard.writeText(location.href)" in source
    assert ">Share market</button>" not in source
