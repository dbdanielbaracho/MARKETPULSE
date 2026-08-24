from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Mapping

_CENT = Decimal("0.01")
_BASIS_POINTS = Decimal("10000")


def creator_amount_due(
    paid_partner_revenue_totals: Mapping[str, object],
    share_basis_points: int,
) -> dict[str, float]:
    """Apply an approved creator share only to already-paid partner revenue.

    Calculation uses decimal arithmetic and explicit banker's rounding to cents.
    The input mapping must already be restricted to reconciled `paid` revenue by
    the durable revenue ledger. This function never estimates partner revenue.
    """
    if isinstance(share_basis_points, bool) or not isinstance(share_basis_points, int):
        raise ValueError("share_basis_points must be an integer")
    if share_basis_points < 0 or share_basis_points > 10000:
        raise ValueError("share_basis_points must be between 0 and 10000")

    rate = Decimal(share_basis_points) / _BASIS_POINTS
    result: dict[str, float] = {}
    for currency, raw_amount in paid_partner_revenue_totals.items():
        code = str(currency).strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("invalid currency in paid partner revenue")
        try:
            amount = Decimal(str(raw_amount))
        except Exception as exc:
            raise ValueError("invalid paid partner revenue amount") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("invalid paid partner revenue amount")
        due = (amount * rate).quantize(_CENT, rounding=ROUND_HALF_EVEN)
        result[code] = float(due)
    return result
