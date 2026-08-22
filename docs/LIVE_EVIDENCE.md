# Live deployment evidence

Verified at 2026-08-22T03:18:08Z against:

- Public service: https://marketpulse-production-aa9f.up.railway.app
- Git commit: `0dd0431d8a47ff07b9779d95eef25cf12f362ceb`
- Application version: `0.3.3`

## Reproducible checks

```bash
curl --fail --silent --show-error \
  https://marketpulse-production-aa9f.up.railway.app/health

curl --fail --silent --show-error \
  https://marketpulse-production-aa9f.up.railway.app/api/v1/status

curl --fail --silent --show-error \
  "https://marketpulse-production-aa9f.up.railway.app/api/v1/markets?venue=kalshi&limit=50"

curl --fail --silent --show-error \
  "https://marketpulse-production-aa9f.up.railway.app/api/v1/markets?venue=polymarket&limit=50"
```

## Observed results

- `/health`: HTTP 200, version `0.3.3`.
- Refresh errors: none.
- Internal read model: 100 Kalshi markets and 100 Polymarket markets.
- Kalshi-filtered API: 50 of 50 returned records identify `venue=kalshi`; no null probabilities.
- Polymarket-filtered API: 50 of 50 returned records identify `venue=polymarket`; no null probabilities.
- Search, category, sort, limit, and validated venue filters are covered by automated API tests.

This evidence verifies deployed discovery behavior only. It does not close unrelated content, distribution, revenue, or global-localization requirements.


## Safe comparison evidence

Verified at 2026-08-22T03:28Z on application version `0.4.0`.

- The public page renders the heading `Compare contracts safely`.
- A live comparison between a Kalshi market and a Polymarket market returned:
  - `decision: related`
  - `equivalent_contracts: false`
  - reason: `question text differs`
  - warning that equivalence requires matching question, deadline, resolution source, and rules.
- Automated tests also prove that identical titles with different deadlines are `not_equivalent`, while identical titles without sufficient rule evidence return `insufficient_evidence`.

The system therefore fails closed: title similarity alone cannot establish contract equivalence.


## Freshness evidence

Verified at 2026-08-22T03:37Z on application version `0.5.0`.

- `freshness: fresh`
- measured `data_age_seconds`
- configured `stale_after_seconds: 900`
- `last_refresh_errors: null`
- venue counts: 100 Kalshi and 100 Polymarket
- public page contains the accessible freshness status component
- automated tests cover `fresh`, `stale`, `future`, and `unavailable`
- invalid freshness thresholds fail closed during configuration

The interface does not claim live data. It reports only the freshness state supported by the latest successful refresh timestamp.


## SEO evidence

Verified at 2026-08-22T03:42Z on application version `0.6.0`.

- canonical URL matches the configured HTTPS production origin
- Open Graph URL and metadata are rendered
- WebSite JSON-LD is rendered
- `/sitemap.xml` returns valid XML with the canonical home URL
- `/robots.txt` returns three real lines: user agent, allow rule, and sitemap URL
- the public origin validator rejects HTTP, credentials, paths, queries, and fragments
- CI regression tests and full-history secret scanning pass

A live validation initially detected literal newline escapes in `robots.txt`; PR #26 corrected the response and strengthened the exact-line test before MP-015 was marked verified.


## Primary market evidence

Verified at 2026-08-22T03:56Z on application version `0.7.0`.

- public market cards expose attributable evidence controls
- Polymarket evidence returns HTTP 200 with publisher, venue kind, explicit undated state, and primary contract URL
- Kalshi evidence returns HTTP 200 with the same provenance fields
- unknown market IDs return 404
- canonical evidence identifiers and URL deduplication remain enforced
- a live Kalshi combined-contract title initially exceeded the evidence label bound; PR #29 added safe label truncation and regression coverage before evidence was accepted

This verifies primary venue evidence only. MP-012 remains IN_PROGRESS until independent news and official-source collectors are connected and source-diversity gates pass in production.


## AI provider and durable storage evidence

Verified at 2026-08-22T16:49:59Z on application version `0.16.0`.

- OpenAI draft mode: enabled and explicitly configured.
- Provider/model: OpenAI `gpt-5.6-luna`.
- Startup verification: `verified: true`, `error: null`.
- Daily draft limit: 100; drafts generated today: 0.
- Automated publishing: disabled.
- Persistent storage remained writable and retained identity `fcb833b0327b062c3335f8b95e1dd636` across startup counts 9, 10, and 11.
- Market ingestion remained healthy with 100 Kalshi and 100 Polymarket markets and no refresh errors.
- PR #43 added fail-closed credential/model verification before the AI worker starts.
- The first live verification exposed an unsupported reasoning value; PR #44 replaced it with the documented `none` value, passed CI and secret scanning, and the redeploy verified successfully.

This proves provider credentials, model access, fail-closed startup behavior, and volume persistence. It does not complete MP-013: a real AI draft remains blocked until an independent evidence match passes the conservative source-diversity gates.


## Evidence coverage and market selection evidence

Verified at 2026-08-22T17:09:59Z on application version `0.19.0`.

- Market ingestion remained healthy with 100 Kalshi and 100 Polymarket markets.
- Polymarket selection now uses documented descending 24-hour volume ordering; current Fed and geopolitical markets replaced the previous concentration in 2028 nomination contracts.
- Kalshi selection excludes opaque multivariate combo contracts.
- Trusted feeds returned 227 parsed items with no source errors:
  - Federal Reserve: 35
  - U.S. Securities and Exchange Commission: 50
  - NPR: 10
  - BBC News: 82
  - ABC News: 50
- Conservative matching associated 15 official items with 3 live Federal Reserve markets.
- No independent news item passed the final title and semantic overlap gates in this cycle.
- Content queue and pending-review draft counts remained zero; OpenAI was not called for unsupported content.
- AI provider verification remained true and automated publishing remained disabled.

This advances MP-012 with reproducible live official matches and source health telemetry. Publisher diversity and the first evidence-diverse AI draft remain pending; the scheduled collector will continue checking automatically.
