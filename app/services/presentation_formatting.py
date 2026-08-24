from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from babel.dates import format_datetime
from babel.numbers import format_currency

from app.services.country_policy import CountryPolicy, resolve_country_policy


def _babel_locale(policy: CountryPolicy) -> str:
    """Convert the validated BCP-47 presentation locale to Babel's locale form."""
    return policy.locale.replace("-", "_")


def format_country_currency(
    amount: Decimal | int | str,
    *,
    country: str | None,
    currency: str | None = None,
) -> str:
    """Format an explicitly identified currency amount for a country's presentation locale.

    Currency identity is never inferred from a bare numeric value. Callers either supply a
    currency code from their domain data or deliberately opt into the country pack currency.
    """
    policy = resolve_country_policy(country)
    currency_code = (currency or policy.currency).strip().upper()
    if len(currency_code) != 3 or not currency_code.isalpha():
        raise ValueError("currency must be a three-letter code")
    return format_currency(Decimal(str(amount)), currency_code, locale=_babel_locale(policy))


def format_country_datetime(
    value: datetime,
    *,
    country: str | None,
    format: str = "medium",
) -> str:
    """Render a timezone-aware instant using the country's validated IANA timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    policy = resolve_country_policy(country)
    return format_datetime(
        value,
        format=format,
        tzinfo=ZoneInfo(policy.default_timezone),
        locale=_babel_locale(policy),
    )
