# DMU 2.4 — Semantic Discovery Test Specification

Version: 1.0
Date: 2026-08-26
Applies to: PrediBeacon public Discovery (`/`, `/api/v1/markets`, `/top` consumers)
Governing controls: DMU-SEM-001, DMU-UXA-001, DMU-TSC-001, DMU-RCG-001, DMU-PROD-001.

## Product promise

Discovery highlights markets that deserve attention now. It is not a dump of every monitored/valid contract.

## What MUST happen

1. Monitored inventory remains observable separately from the curated Discovery subset.
2. Discovery only emits markets with reported volume >= USD 1,000 and product relevance >= 20/100.
3. Every emitted item exposes the semantic policy version and its machine-verifiable oracle fields.
4. Ranking sorts operate only on the semantically eligible subset.
5. Dynamic "Why it matters" copy follows the selected page language.
6. When no market qualifies, the page explains that no market currently meets the documented attention criteria.

## What MUST NEVER happen

1. A market below USD 1,000 cannot enter Discovery only because a probability move is large.
2. Urgency/closing time cannot override the material-activity floor.
3. A low-quality fallback cannot silently repopulate Discovery merely to avoid zero cards.
4. Technical validity (`HTTP 200`, valid JSON, valid contract, `trend_score >= 5`) cannot be treated as proof that a market deserves attention.
5. A Portuguese card cannot render known English-only dynamic explanation text.
6. Green CI or smoke cannot override contradictory production evidence from the real user journey.

## Context matrix

| Context | Required cases |
|---|---|
| Venue | Kalshi, Polymarket, All |
| Sort | trending, movers, volume |
| Activity | 0, 1, 99, 149, 289, 302, 999.99, 1000, 3000, 10k, 100k |
| Movement | zero, small, meaningful, extreme |
| Deadline | imminent <1h, <=24h, <=72h, long-dated |
| Relevance | below 20, exactly 20, above 20 |
| Result set | many qualifying, one qualifying, zero qualifying |
| Locale | en plus real pt-BR journey; supported locale runtime dictionary remains bounded |
| Environment | deterministic in-process, local browser, deployed production custom domain and Railway origin |

## Exact escaped-production oracle

Input set from the owner-observed Kalshi journey:

- Full Game: over 183.5 points? — ~USD 20.8k, displayed score 37.
- Washington wins the game by over 21.5 points — USD 149, displayed score 13.
- Byron Buxton: 1+ RBIs? — USD 302, displayed score 11.
- Byron Buxton: 2+ total bases? — USD 289, displayed score 9.

Expected curated result: only the materially active Full Game market may remain, assuming its other data stays valid. The three thin contracts must be rejected regardless of move/urgency.

## Test layers

### Deterministic

- `tests/test_dmu24_semantic_discovery.py`
- `tests/test_semantic_discovery_middleware.py`
- full repository `pytest`
- performance smoke

### Browser

- full `browser_e2e` suite
- localized reason/empty-state behavior

### Production truth

`browser_e2e/test_production_semantic_discovery.py` must execute against both public custom domain and Railway origin. It verifies semantic headers/fields, volume and relevance invariants across both venues and all three public sorts, plus the Portuguese Kalshi journey.

## Release exit criteria

All tests above green on the merge SHA; deploy of the same SHA green; Final Project Acceptance green; Production Browser Smoke green; no known contradictory real journey evidence; production output semantically consistent with this specification.
