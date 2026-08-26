from app.services.ranking import (
    FULL_SIGNAL_CONFIDENCE_USD,
    MIN_SIGNAL_ACTIVITY_USD,
    activity_confidence,
    movement_component,
)


def test_activity_confidence_is_continuous_and_monotonic_across_orders_of_magnitude():
    volumes = [0, 1, 10, 99.99, 100, 275, 1000, 10000, 100000, 1000000]
    values = [activity_confidence(value) for value in volumes]
    assert values == sorted(values)
    assert values[0] == 0
    assert activity_confidence(MIN_SIGNAL_ACTIVITY_USD) < activity_confidence(1000)
    assert activity_confidence(1000) < activity_confidence(10000)
    assert activity_confidence(FULL_SIGNAL_CONFIDENCE_USD) == 1
    assert values[-1] == 1


def test_same_probability_move_gets_more_credit_with_more_reported_activity():
    scores = [
        movement_component(0.12, volume, max_points=70)
        for volume in (1, 100, 275, 1000, 10000, 100000)
    ]
    assert scores == sorted(scores)
    assert scores[0] < scores[-1]


def test_baltimore_class_regression_cannot_receive_full_movement_credit_at_275_dollars():
    thin = movement_component(-0.12, 275, max_points=70)
    full = movement_component(-0.12, 100000, max_points=70)
    assert thin < full * 0.4
