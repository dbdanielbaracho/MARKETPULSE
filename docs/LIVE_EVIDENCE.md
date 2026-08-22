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
