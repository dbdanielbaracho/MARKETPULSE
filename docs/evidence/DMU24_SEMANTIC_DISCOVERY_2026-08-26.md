# DMU 2.4 Semantic Discovery Incident — 2026-08-26

Status: OPEN until merged production evidence closes every gate below.

## Governing baseline

Documento Mestre Universal Consolidado v2.4 is the operational guide for this incident, especially DMU-PROD-001, DMU-SEM-001, DMU-UXA-001, DMU-TSC-001 and DMU-RCG-001.

## Production contradiction

A real owner-observed Kalshi journey contradicted the prior green release claim. The public section promised markets that "deserve attention now" while showing:

- Full Game: over 183.5 points? — reported volume about USD 20.8k, displayed relevance/trend 37/100.
- Washington wins the game by over 21.5 points — reported volume USD 149, displayed relevance/trend 13/100.
- Byron Buxton: 1+ RBIs? — reported volume USD 302, displayed relevance/trend 11/100.
- Byron Buxton: 2+ total bases? — reported volume USD 289, displayed relevance/trend 9/100.

The same Portuguese journey also rendered English dynamic "Why it matters" explanations. Under DMU-RCG-001 the production observation overrides earlier green checks.

## Reproduction and RCA

### Product root cause

`app/middleware/home_client_dedup.py` conflated two different concepts:

1. valid/monitorable market inventory; and
2. editorial eligibility for the Discovery promise.

The old strict gate accepted reported volume >= USD 100 and `trend_score >= 5`. If any strict item existed, it became a Discovery candidate even when its own displayed score communicated very weak relevance. The quiet-market fallback was designed to avoid an empty homepage and therefore also encoded the wrong objective: filling Discovery instead of telling the truth when nothing met the attention promise.

### Test-system root cause

`tests/test_home_market_curation.py` froze the same weak oracle as correct behavior: USD 100 and trend 5 were explicit acceptance boundaries. Production smoke only proved those technical thresholds and therefore could be green while the user-facing meaning was wrong. This is a DMU-TSC-001 failure: the test category existed, but the oracle did not encode the product promise.

### Language root cause

The card `why(m)` function generated dynamic English explanations client-side. Static page localization did not make those runtime explanations locale-aware, allowing mixed-language cards.

## Corrective contract

Discovery is now a curated subset of monitored inventory. A market may remain monitored without being highlighted.

Semantic eligibility requires both:

- reported activity >= USD 1,000; and
- product relevance score >= 20/100.

The USD 1,000 material-activity boundary is not newly invented for this incident: the existing quiet-market fallback already used it as the materially active boundary. The correction promotes that existing stronger materiality concept into the user-facing Discovery contract.

There is deliberately no weak fallback below this semantic gate. If no market qualifies, the correct state is an explicit message saying that no market currently meets PrediBeacon's documented attention criteria for the selected filters. Provider inventory counts remain visible separately.

The API also exposes the semantic policy version, relevance score, activity confidence and a reason code. Dynamic explanations are localized at runtime instead of using an English-only movement heuristic.

## Executable invariants / oracles

DMU24-SEM-01: A valid market with reported volume below USD 1,000 MUST NOT be highlighted in Discovery, even with a very large probability move or imminent close.

DMU24-SEM-02: A Discovery item MUST have `relevance_score >= 20`.

DMU24-SEM-03: If zero items satisfy the semantic gate, the curated response MUST be empty; the system MUST NOT re-admit weak inventory to avoid an empty state.

DMU24-SEM-04: The monitored provider count and curated Discovery count are different concepts and MUST remain explainable.

DMU24-SEM-05: Every production Discovery API item MUST expose `semantic_discovery_version`, `relevance_score`, `activity_confidence` and `attention_reason_code`.

DMU24-SEM-06: A Portuguese public journey MUST NOT show the known English dynamic reason strings inside market cards.

DMU24-SEM-07: The real escaped Kalshi sample above MUST curate to the materially active Full Game market only.

DMU24-RCG-01: Green CI/smoke cannot close this incident unless the post-deploy public journey and real production API satisfy DMU24-SEM-01 through DMU24-SEM-07.

## Evidence map

| Requirement/risk | Code | Deterministic test | Production test | Exit evidence |
|---|---|---|---|---|
| Thin activity mislabeled as attention-worthy | `app/services/discovery_semantics.py` | `tests/test_dmu24_semantic_discovery.py` | `browser_e2e/test_production_semantic_discovery.py` | production API + public Kalshi journey |
| Weak fallback masks honest empty state | semantic curator + middleware | semantic service/middleware tests | Portuguese browser journey | explicit semantic empty state |
| Mixed-language dynamic explanation | semantic middleware runtime reason dictionary | middleware test | Portuguese browser journey | no forbidden English dynamic reasons |
| Prior gate false positive | new semantic oracle fields/headers | middleware tests | production semantic test | Final Acceptance + Production Browser Smoke on deployed merge SHA |

## Closure requirements

Do not mark this incident closed until all of the following are true on the same merged SHA:

1. deterministic suite green;
2. performance gate green;
3. browser E2E green;
4. production quality gate green;
5. deployment status green for the public service;
6. real production API satisfies semantic invariants for Kalshi and Polymarket across trending, movers and volume sorts;
7. real Portuguese Kalshi journey shows either qualifying cards with localized reasons or the truthful semantic empty state;
8. Final Project Acceptance green;
9. Production Browser Smoke green;
10. contradiction review finds no known production evidence that refutes the release claim.
