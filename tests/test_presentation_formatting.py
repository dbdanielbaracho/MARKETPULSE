from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.presentation_formatting import (
    format_country_currency,
    format_country_datetime,
)


def test_currency_uses_country_locale_and_explicit_currency_identity() -> None:
    us = format_country_currency(Decimal("1234.50"), country="US", currency="USD")
    gb = format_country_currency(Decimal("1234.50"), country="GB", currency="GBP")
    br = format_country_currency(Decimal("1234.50"), country="BR", currency="BRL")

    assert us == "$1,234.50"
    assert gb == "£1,234.50"
    assert "1.234,50" in br
    assert "R$" in br


def test_currency_defaults_only_to_validated_country_pack_currency() -> None:
    assert format_country_currency("10", country="US") == "$10.00"
    assert format_country_currency("10", country="GB") == "£10.00"
    assert "R$" in format_country_currency("10", country="BR")


def test_currency_rejects_malformed_identity() -> None:
    with pytest.raises(ValueError, match="three-letter"):
        format_country_currency("10", country="US", currency="$")


def test_datetime_converts_same_instant_to_country_timezone() -> None:
    instant = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)

    us = format_country_datetime(instant, country="US", format="HH:mm z")
    gb = format_country_datetime(instant, country="GB", format="HH:mm z")
    br = format_country_datetime(instant, country="BR", format="HH:mm z")

    assert us.startswith("08:00")
    assert gb.startswith("13:00")
    assert br.startswith("09:00")


def test_datetime_rejects_naive_values() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        format_country_datetime(datetime(2026, 8, 24, 12, 0), country="US")


def test_unknown_country_remains_safe_utc_usd_fallback() -> None:
    instant = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)

    assert format_country_currency("10", country="ZZ") == "$10.00"
    assert format_country_datetime(instant, country="ZZ", format="HH:mm z").startswith("12:00")
