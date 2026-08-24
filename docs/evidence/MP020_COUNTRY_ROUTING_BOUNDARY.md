# MP-020 country routing boundary

Date: 2026-08-24

PrediBeacon's outbound boundary is fail-closed at three independent layers:

1. market/venue routing never accepts a caller-supplied redirect destination and requires an exact server-side venue/country route plus an allowlisted HTTPS host;
2. country policy explicitly recognizes every country pack currently present in `config/countries`: US, GB and BR;
3. disabled GB and BR country packs remain informational-only at runtime: commercial outbound and paid social are denied even when a caller claims age, partner-contract and platform-authorization checks are satisfied.

The US country pack remains the only enabled pack. Its commercial action also remains denied until the separately evidenced partner/platform authorization boundary is satisfied; this change does not enable a paid partnership, invent partner economics or activate UK/Brazil distribution.

Regression coverage:

- `tests/test_country_policy.py`
- `tests/test_country_policy_config_alignment.py`
- existing outbound-router tests and market route eligibility tests continue to run in the full suite.

Any future country pack added under `config/countries` must gain an explicit runtime policy or `tests/test_country_policy_config_alignment.py` fails closed.
