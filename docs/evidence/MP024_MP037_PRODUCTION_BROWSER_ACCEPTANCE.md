# MP-024 / MP-037 production browser acceptance evidence

Date: 2026-08-24

Tested production commit: `71028a0e710fab4367f53c1de6ee382251984395`

GitHub Actions run: `32686907239` (`Production browser smoke`)

Observable commit status: `predibeacon/production-browser-smoke = success`.

The production workflow executed against `https://predibeacon.com` after the Railway deployment settle window and completed the real-production test step successfully. The workflow invokes all three production suites in sequence:

- `browser_e2e/test_production_smoke.py`
- `browser_e2e/test_production_mobile.py`
- `browser_e2e/test_production_outbound.py`

This pass occurred only after production smoke had exposed and the project had corrected two discovery defects: a closed contract remaining in active discovery and relevance results being reordered for venue balancing. The fixes were merged through PR #170 and PR #171 with their own CI gates before this successful production run.

MP-024 evidence boundary: the mobile production suite exercises responsive discovery and the internal market journey with small-screen overflow and touch-target checks plus the external CTA path.

MP-037 evidence boundary: the outbound production suite verifies that the external venue is opened separately with the opener isolated, preserving the PrediBeacon page rather than replacing it.

The evidence does not imply availability or correctness of the third-party venue after navigation; it verifies PrediBeacon-controlled browser behavior and the production surfaces under PrediBeacon's control.
