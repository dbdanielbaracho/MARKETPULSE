from app.services.creator_revenue_share import creator_amount_due


def test_creator_share_uses_decimal_arithmetic_and_half_even_cent_rounding():
    assert creator_amount_due({"USD": 0.15}, 1000) == {"USD": 0.02}
    assert creator_amount_due({"USD": 0.05}, 1000) == {"USD": 0.0}
    assert creator_amount_due({"USD": 12.50}, 4000) == {"USD": 5.0}


def test_creator_share_never_accepts_invalid_terms_or_paid_revenue():
    for share in (-1, 10001, True, 1.5):
        try:
            creator_amount_due({"USD": 10}, share)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid share accepted: {share!r}")

    for totals in ({"US": 10}, {"USD": -1}, {"USD": "NaN"}, {"USD": "Infinity"}):
        try:
            creator_amount_due(totals, 1000)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid paid totals accepted: {totals!r}")


def test_zero_share_is_explicit_and_does_not_invent_creator_due():
    assert creator_amount_due({"USD": 100.00}, 0) == {"USD": 0.0}
