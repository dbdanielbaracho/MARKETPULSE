# MP-043 exact creator revenue calculation

Date: 2026-08-24

## Decision

Creator amounts are calculated only after an explicit creator agreement has been approved and only from the revenue ledger's already-reconciled `paid` partner totals. The calculation uses Python `Decimal`, converts persisted numeric values through their decimal string representation, and quantizes the result to two currency decimal places with `ROUND_HALF_EVEN`.

No partner revenue is estimated, no default creator share exists, and a configured-but-unapproved or revoked agreement is not usable for creator amount calculation.

## Primary-source basis

Python's current `decimal` documentation states that decimal values can be represented exactly, that decimal arithmetic is preferred in accounting applications with strict equality invariants, and that rounding is explicitly controllable. The default decimal context uses `ROUND_HALF_EVEN`.

Source reviewed: https://docs.python.org/3/library/decimal.html

## Security and exposure boundary

The calculation helper is server-side only. It does not expose the configured agreement share, partner identifiers, partner commission terms or internal commercial configuration to public pages. Any future creator-facing response may expose the creator's own derived amount only after creator authentication and must not disclose the underlying internal share configuration unless a separate product/legal decision explicitly requires it.
