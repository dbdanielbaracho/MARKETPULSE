# Partner economics validation evidence

## Decision

**ADOPT** server-side, fail-closed validation for evidence-bearing commercial configuration. A venue may remain available in organic mode with no partner identity, but the runtime must reject a configuration that claims a venue is commercially verified while the required partner identity is absent.

This is the best fit for PrediBeacon because partner economics are business/security decisions and must not be inferred from UI state, client-side values, or incomplete environment configuration.

## Current primary-source baseline

OWASP ASVS 5.0.0 is the current stable ASVS baseline. Its input-validation requirements include validating input against business expectations at a trusted service layer and checking combinations of related data for reasonableness (V2.2.1–V2.2.3). PrediBeacon applies that guidance to commercial partner configuration.

Primary sources reviewed:

- https://owasp.org/www-project-application-security-verification-standard/
- https://cornucopia.owasp.org/taxonomy/asvs-5.0/02-validation-and-business-logic/02-input-validation

## Implementation evidence

`app/config/runtime.py::validate_commercial_partner_config`:

- allows only the supported venues `KALSHI` and `POLYMARKET`;
- reads the commercial-verification claim from server environment only;
- rejects `COMMERCIAL_VERIFIED=true` when the corresponding server-side partner identity is missing;
- runs for both venues before `RuntimeFlags` is constructed;
- keeps external side-effect flags off by default.

This means public/organic routing remains possible without inventing commercial status, while commercial claims fail closed unless the server has explicit evidence-bearing configuration.

## Regression evidence

`tests/test_commercial_config_validation.py` verifies:

1. a verified Kalshi configuration without partner identity is rejected;
2. an organic Polymarket configuration does not require partner identity;
3. a verified partner configuration with identity is accepted;
4. runtime startup validates both partner claims;
5. unsupported venues are rejected.

Existing public-surface privacy tests and routing behavior additionally ensure commercial internals are not required for public organic discovery.

## Requirement conclusion

MP-032 can be marked `VERIFIED`: commercial economics are not invented; the runtime validates evidence-bearing partner configuration at a trusted server layer and fails closed when that evidence is incomplete. Live commission amounts or partner credentials are intentionally not required to verify this requirement, because the requirement is about preventing unsupported economics from being asserted, not proving that a commercial contract already exists.
