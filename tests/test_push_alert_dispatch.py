from datetime import datetime, timezone

from app.services.push_alert_dispatch import transition_reasons
from app.storage.push_subscriptions import PushAlert


def _alert(preferences, last_state):
    return PushAlert(
        subscription_id='push_test_12345678',
        market_id='kalshi:test',
        preferences=preferences,
        last_state=last_state,
        active=True,
        updated_at=datetime.now(timezone.utc),
    )


def test_server_push_triggers_only_on_transitions_not_existing_state():
    alert = _alert(
        {'breaking': True, 'execution': True, 'gap': True, 'large': True, 'evidence': True, 'closing_hours': 24},
        {
            'breaking': True,
            'execution': True,
            'gap': True,
            'large_key': 'large-1',
            'evidence_key': 'evidence-1',
            'closing_hours': 12,
        },
    )
    same = {
        'breaking': True,
        'execution': True,
        'gap': True,
        'large_key': 'large-1',
        'evidence_key': 'evidence-1',
        'closing_hours': 11,
    }
    assert transition_reasons(alert, same) == []


def test_server_push_detects_material_move_evidence_trade_gap_and_closing_crossings():
    alert = _alert(
        {
            'probability_threshold': 0.7,
            'breaking': True,
            'execution': True,
            'gap': True,
            'large': True,
            'evidence': True,
            'closing_hours': 24,
        },
        {
            'probability': 0.65,
            'breaking': False,
            'execution': False,
            'gap': False,
            'large_key': 'large-1',
            'evidence_key': 'evidence-1',
            'closing_hours': 30,
        },
    )
    next_state = {
        'probability': 0.72,
        'breaking': True,
        'execution': True,
        'gap': True,
        'large_key': 'large-2',
        'evidence_key': 'evidence-2',
        'closing_hours': 23.5,
    }
    reasons = transition_reasons(alert, next_state)
    assert len(reasons) == 7
    assert any('70%' in reason for reason in reasons)
    assert any('breaking' in reason for reason in reasons)
    assert any('execution' in reason for reason in reasons)
    assert any('large' in reason for reason in reasons)
    assert any('cross-platform' in reason for reason in reasons)
    assert any('evidence' in reason for reason in reasons)
    assert any('24' in reason for reason in reasons)


def test_missing_data_never_creates_a_transition():
    alert = _alert(
        {'probability_threshold': 0.7, 'breaking': True, 'closing_hours': 24},
        {'probability': None, 'breaking': False, 'closing_hours': None},
    )
    assert transition_reasons(alert, {'probability': None, 'breaking': False, 'closing_hours': None}) == []
