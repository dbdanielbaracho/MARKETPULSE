# PrediBeacon Internal Readiness Audit — 0.38.0

Date: 2026-08-22

## Verified internally

| Area | Code/configuration | Test or evidence | Result |
|---|---|---|---|
| Public identity | FastAPI metadata, health/status payloads, templates and public headers | public runtime identity regression test | PrediBeacon only on public product surfaces |
| Discovery journey | rankings, stable market slugs, detail, evidence, history and timeline | existing API/UI suites and production smoke checks | complete internal-to-outbound journey |
| Related markets | conservative discovery plus explicit relationship and non-equivalence fields | adversarial related-market test | no related result claims contract equivalence |
| Outbound safety | server-side destination allowlist and organic/partner modes | route and attribution suites | external destinations fail closed |
| Editorial | approval, manual release, durable scheduling, rollback and citations | queue/scheduling suites | auditable and idempotent |
| Revenue | signed, replay-bounded partner intake and guarded state transitions | reconciliation adversarial tests | no invented commission |
| Installability | manifest identity, branded maskable SVG, service worker and offline trust pages | manifest/static route checks | installable shell complete |
| Public disclosures | methodology, risk, privacy and terms | static-page regression coverage | current organic click behavior disclosed |
| Recovery | persistent SQLite probes and documented backup/restore/rollback | storage tests plus runbook | recovery procedure defined |

## Deliberately inactive external gates

- Instagram, TikTok and X publishing: waiting for developer accounts, OAuth grants and platform review.
- Kalshi and Polymarket paid referrals: waiting for signed commercial terms, partner identifiers, webhook secrets and real payload mappings.
- PrediBeacon Pro and paid API billing: deferred by product decision.
- Creator revenue splits: waiting for agreements and authenticated creator identities.
- Background web push: waiting for push credentials and notification-provider configuration.

These inactive gates are not represented as completed or revenue-producing.
