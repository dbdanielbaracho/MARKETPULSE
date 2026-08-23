import pytest

from app.adapters.polymarket import PolymarketAdapter
from app.services.execution_quality import (
    BookLevel,
    execution_quality,
    kalshi_levels,
    polymarket_levels,
)


def test_execution_quality_rewards_tight_two_sided_book():
    result = execution_quality(
        [BookLevel(.49, 2_000), BookLevel(.48, 2_000)],
        [BookLevel(.50, 2_500), BookLevel(.51, 2_500)],
    )
    assert result.two_sided is True
    assert result.best_bid == .49
    assert result.best_ask == .50
    assert result.spread_points == pytest.approx(1.0)
    assert result.score >= 85
    assert result.grade == "excellent"


def test_execution_quality_fails_closed_on_one_sided_book():
    result = execution_quality([BookLevel(.40, 50)], [])
    assert result.two_sided is False
    assert result.midpoint is None
    assert result.spread_points is None
    assert result.grade == "weak"


def test_kalshi_no_bid_becomes_yes_ask():
    bids, asks = kalshi_levels({
        "orderbook_fp": {
            "yes_dollars": [["0.44", "100"]],
            "no_dollars": [["0.54", "200"]],
        }
    })
    assert bids == [BookLevel(.44, 100)]
    assert asks[0].price == pytest.approx(.46)
    assert asks[0].size == 200


def test_polymarket_book_normalization():
    bids, asks = polymarket_levels({
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [{"price": "0.47", "size": "150"}],
    })
    assert bids == [BookLevel(.45, 100)]
    assert asks == [BookLevel(.47, 150)]


def test_polymarket_yes_token_id_respects_outcome_order():
    raw = {
        "outcomes": '["No", "Yes"]',
        "clobTokenIds": '["no-token", "yes-token"]',
    }
    assert PolymarketAdapter.yes_token_id(raw) == "yes-token"


def test_depth_levels_must_be_positive():
    with pytest.raises(ValueError):
        execution_quality([], [], depth_levels=0)
