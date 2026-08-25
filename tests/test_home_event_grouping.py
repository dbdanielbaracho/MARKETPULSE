from app.middleware.home_event_grouping import _family_title, _group


def test_plus_stat_ladders_share_family():
    assert _family_title("Grant McCray: 2+ hits + runs + RBIs?") == _family_title(
        "Grant McCray: 4+ hits + runs + RBIs?"
    )
    assert _family_title("Eugenio Suárez: 1+ hits + runs + RBIs?") == _family_title(
        "Eugenio Suárez: 5+ hits + runs + RBIs?"
    )


def test_different_stat_families_stay_distinct():
    assert _family_title("Drew Gilbert: 1+ RBIs?") != _family_title(
        "Drew Gilbert: 1+ stolen bases?"
    )
    assert _family_title("Drew Gilbert: 1+ stolen bases?") != _family_title(
        "Drew Gilbert: 1+ hits + runs + RBIs?"
    )


def test_margin_ladders_share_family():
    assert _family_title("Texas wins by over 4.5 runs?") == _family_title(
        "Texas wins by over 5.5 runs?"
    )
    assert _family_title("Everton wins by more than 3.5 goals?") == _family_title(
        "Everton wins by more than 4.5 goals?"
    )


def test_group_keeps_highest_ranked_first_card_per_family():
    rows = [
        {
            "venue": "kalshi",
            "title": "Grant McCray: 2+ hits + runs + RBIs?",
            "closes_at": "2026-08-28T19:00:15Z",
            "trend_score": 47,
        },
        {
            "venue": "kalshi",
            "title": "Grant McCray: 3+ hits + runs + RBIs?",
            "closes_at": "2026-08-28T19:00:40Z",
            "trend_score": 28,
        },
        {
            "venue": "kalshi",
            "title": "Grant McCray: 1+ stolen bases?",
            "closes_at": "2026-08-28T19:00:30Z",
            "trend_score": 1,
        },
    ]
    grouped = _group(rows)
    assert len(grouped) == 2
    assert grouped[0]["title"] == "Grant McCray: 2+ hits + runs + RBIs?"
    assert grouped[1]["title"] == "Grant McCray: 1+ stolen bases?"
