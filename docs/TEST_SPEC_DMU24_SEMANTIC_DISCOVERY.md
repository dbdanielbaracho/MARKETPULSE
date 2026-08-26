# DMU 2.4 — Semantic Discovery Test Specification

Version: 1.1
Date: 2026-08-26
Applies to: PrediBeacon monitored inventory (`/api/v1/markets`) and public curated Discovery (`/`, `/api/v1/discovery`, `/top`).
Governing controls: DMU-SEM-001, DMU-UXA-001, DMU-TSC-001, DMU-RCG-001, DMU-PROD-001.

## Product promise

Discovery highlights markets that deserve attention now. It is not a dump of every monitored/valid contract.

## Contract separation

`/api/v1/markets` is the monitored/ranked inventory contract. Its responsibility is discovery data retrieval, sorting, filtering, deduplication and provider balance. It is not an editorial endorsement.

`/api/v1/discovery` is the user-facing semantic curation contract. The homepage and `/top` MUST consume it for the "deserves attention now" journey. Its output is allowed to be empty even when monitored inventory is non-empty.

## What MUST happen

1. Monitored inventory remains observable separately from the curated Discovery subset.
2. Discovery only emits markets with reported volume >= USD 1,000 and product `relevance_score >= 20/100`.
3. Every emitted item exposes `semantic_discovery_version`, `relevance_score`, `activity_confidence`, `attention_score` and `attention_reason_code`.
4. Public sorting operates on candidates but weak candidates cannot re-enter the final semantic subset.
5. Dynamic "Why it matters" copy follows the selected page language.
6. When no market qualifies, the page explains that no market currently meets the documented attention criteria.
7. A public metric labeled as relevance renders `relevance_score` when the semantic contract provides it.
8. `/top` and the homepage consume the same semantic Discovery source of truth.

## What MUST NEVER happen

1. A market below USD 1,000 cannot enter Discovery only because a probability move is large.
2. Urgency/closing time cannot override the material-activity floor.
3. A low-quality fallback cannot silently repopulate Discovery merely to avoid zero cards.
4. Technical validity (`HTTP 200`, valid JSON, valid contract, `trend_score >= 5`) cannot be treated as proof that a market deserves attention.
5. A Portuguese card cannot render known English-only dynamic explanation text.
6. A card labeled as relevance cannot display `trend_score` while eligibility is governed by a different `relevance_score` without explicit differentiation.
7. Green CI or smoke cannot override contradictory production evidence from the real user journey.
8. Tightening the curated Discovery contract cannot silently change the raw `/api/v1/markets` inventory contract.

## Context matrix

| Context | Required cases |
|---|---|
| Venue | Kalshi, Polymarket, All |
| Sort | trending, movers, volume |
| Activity | 0, 1, 99, 149, 289, 302, 999.99, 1000, 3000, 10k, 100k |
| Movement | zero, small, meaningful, extreme |
| Deadline | imminent <1h, <=24h, <=72h, long-dated |
| Relevance | below 20, exactly 20, above 20 |
| Result set | many qualifying, one qualifying, zero qualifying while inventory remains non-empty |
| Locale | en plus real pt-BR journey; supported locale runtime dictionary remains bounded |
| Surface | `/api/v1/markets`, `/api/v1/discovery`, `/`, `/top` |
| Environment | deterministic in-process, local browser, deployed production custom domain and Railway origin |

## Exact escaped-production oracle

Input set from the owner-observed Kalshi journey:

- Full Game: over 183.5 points? — ~USD 20.8k, displayed score 37.
- Washington wins the game by over 21.5 points — USD 149, displayed score 13.
- Byron Buxton: 1+ RBIs? — USD 302, displayed score 11.
- Byron Buxton: 2+ total bases? — USD 289, displayed score 9.

Expected curated result: only the materially active Full Game market may remain, assuming its other data stays valid. The three thin contracts must be rejected regardless of move/urgency. They may still exist in monitored inventory if otherwise valid.

## Test layers

### Deterministic

- existing `tests/test_discovery_api.py` protects the monitored inventory contract;
- `tests/test_dmu24_semantic_discovery.py` protects the semantic eligibility oracle;
- `tests/test_public_discovery.py` protects the dedicated curated API contract and the real escaped sample;
- `tests/test_semantic_discovery_middleware.py` protects public surface routing, visible relevance and localized runtime behavior;
- full repository `pytest`;
- performance smoke.

### Browser

- full `browser_e2e` suite;
- public homepage and `/top` use `/api/v1/discovery`;
- localized reason/empty-state behavior;
- visible relevance must match the selected item's `relevance_score`.

### Production truth

`browser_e2e/test_production_semantic_discovery.py` must execute against both public custom domain and Railway origin. It verifies `/api/v1/discovery` semantic headers/fields, volume and relevance invariants across both venues and all three public sorts, verifies `/top` consumes the same contract, and executes the Portuguese Kalshi journey against the rendered DOM.

## Release exit criteria

All tests above green on the merge SHA; deploy of the same SHA green; real production Discovery API and Portuguese rendered journey satisfy this specification; Final Project Acceptance green; Production Browser Smoke green; and an adversarial contradiction review finds no known evidence that refutes the release claim.
