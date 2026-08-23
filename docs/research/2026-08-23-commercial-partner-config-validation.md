# Commercial partner configuration validation — 2026-08-23

## Decision

PrediBeacon treats partner/commercial configuration as evidence-bearing server-side configuration. A venue may remain organic with no partner identity, but any configured partner identity is syntactically validated before runtime starts, and commercial verification remains fail-closed when partner identity is absent.

Partner IDs are opaque internal configuration. They are bounded to 1–200 ASCII characters and allowlisted to letters, digits, dot, underscore, colon and hyphen. Whitespace, path/query delimiters, markup characters, control characters and oversized values are rejected before the routing layer starts.

This validation does **not** authorize a partnership, invent economics, or publish identifiers. Contract verification and venue authorization remain separate gates.

## Primary-source basis

OWASP Input Validation Cheat Sheet, reviewed 2026-08-23: validate input as early as possible, perform both syntactic and semantic validation, use allowlists rather than denylists, enforce length bounds, and enforce security validation server-side.

Source: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html

OWASP Secure Code Review Cheat Sheet, reviewed 2026-08-23: server-side validation, allowlist validation, length limits and non-sensitive error behavior are explicit review checks.

Source: https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html

## Scope

- `app/config/runtime.py`
- `tests/test_commercial_config_validation.py`
- no public rendering of partner identity
- no commission percentage or revenue-share configuration introduced
- no commercial relationship represented as approved
