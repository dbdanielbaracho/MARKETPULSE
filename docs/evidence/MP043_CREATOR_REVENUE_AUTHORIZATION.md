# MP-043 creator revenue authorization evidence

Date: 2026-08-24

MP-043 is implemented as a fail-closed chain rather than a public economics surface.

The verified implementation boundary is:

1. public creator pages expose market selections and tracked campaign links, not financial configuration;
2. creator API credentials are opaque high-entropy tokens returned once and persisted only as hashes;
3. creator identity is derived server-side from the credential and cannot be selected by a request parameter;
4. agreement configuration is admin-only and inactive by default;
5. agreement approval is a separate admin action that requires the exact configured agreement identifier;
6. revocation immediately removes approval;
7. creator amount calculation uses exact Decimal arithmetic and only the durable revenue ledger's reconciled `paid` totals;
8. the authenticated creator response uses `Cache-Control: no-store` and does not expose partner identifiers, agreement identifiers, configured share fields/values or other internal economics;
9. the end-to-end regression test drives paid revenue, admin agreement configuration, admin approval, creator credential issuance, creator self-service and revocation through the same application entrypoint.

Relevant regression coverage includes:

- `tests/test_creator_agreements.py`
- `tests/test_creator_revenue_share_decimal.py`
- `tests/test_creator_credentials.py`
- `tests/test_admin_creator_agreements.py`
- `tests/test_creator_revenue_end_to_end.py`

Security/accounting decisions are recorded in:

- `docs/decisions/MP043_CREATOR_AGREEMENT_AUTHORIZATION.md`
- `docs/decisions/MP043_CREATOR_AUTHENTICATION.md`
- `docs/decisions/MP043_CREATOR_REVENUE_DECIMAL.md`

No production partner identifiers, partner commission terms, creator agreement percentage or internal commercial economics are evidence artifacts or public API fields.
