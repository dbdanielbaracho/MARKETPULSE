# MP-033 global locale, currency, timezone and trust-copy boundary

Date: 2026-08-24

PrediBeacon separates presentation localization from source-of-truth economics and legal/trust claims.

Verified technical boundary:

1. public product UI supports EN, ES, PT-BR, FR, DE, IT, JA, KO, ZH-CN and AR with English fallback and RTL handling for Arabic;
2. user-visible reported USD values on discovery and market-detail surfaces are formatted with the selected document locale through `Intl.NumberFormat`; PrediBeacon does not fabricate FX conversion or silently relabel venue-reported currency;
3. home discovery closing-time presentation and market-detail relative time use `Intl.RelativeTimeFormat` instead of English-only `h`/`d` tokens, while absolute market timestamps use `Intl.DateTimeFormat` in the browser's local timezone with a timezone abbreviation;
4. venue contract titles remain canonical source text rather than being machine-translated into a potentially different contract meaning;
5. trust/legal pages (`/methodology`, `/risk`, `/privacy`, `/terms`) may use a non-English presentation language only after that exact page/locale is explicitly recorded as a reviewed complete translation;
6. until such review exists, a non-English request receives the complete canonical English document, `Content-Language: en`, and `X-PrediBeacon-Language-Fallback: canonical-en` rather than a mixed-language legal page;
7. normal non-trust product pages continue to honor the requested supported locale.

Currency identity remains explicit because current discovery volume fields are canonically `volume_usd`; locale-aware presentation changes separators, symbol placement and compact-number conventions, but does not imply an exchange-rate conversion.

This boundary intentionally treats partial legal-string catalogs as insufficient evidence for a legal-language claim. Adding a future reviewed translation is an allowlist operation, not an implicit best-effort substitution.

Regression coverage includes:

- `tests/test_locale_number_time.py`, including the public discovery home surface;
- `tests/test_public_locale_trust.py`;
- `tests/test_trust_locale_policy.py`;
- the complete application, browser E2E and production-quality gates.
