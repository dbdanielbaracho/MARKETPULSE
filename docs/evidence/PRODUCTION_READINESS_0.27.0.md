# Production readiness audit — 0.27.0

Validated at 2026-08-22 18:30 UTC against `https://marketpulse-production-aa9f.up.railway.app`.

This is a technical readiness checkpoint, not a statement that the commercial launch is legally complete.

## Public service

| Check | Result |
|---|---|
| `GET /health` | HTTP 200, version 0.27.0 |
| `GET /api/v1/status` | HTTP 200, freshness `fresh` |
| Kalshi ingestion | 100 markets |
| Polymarket ingestion | 100 markets |
| refresh errors | none |
| OpenAI provider | configured and verified, model `gpt-5.6-luna` |
| AI daily cap | 100 drafts; 0 used at validation |
| persistent storage | writable and volume configured |
| storage identity | `fcb833b0327b062c3335f8b95e1dd636` |
| automated publishing | disabled |
| social distribution | disabled |

## Country policy

- US: informational content allowed; commercial outbound and paid social blocked pending partner contract and platform authorization.
- Brazil: informational content allowed; direct commercial outbound and paid social blocked.
- Minimum configured audience age is 18, but partner/platform/local rules may require a higher threshold.

## Social readiness

`GET /api/v1/social/readiness?country=US` returned every configured channel as `ready: false`. Each channel is independently blocked by the global kill switch, missing production credential, unverified platform authorization, and required editorial approval. No posting attempt was made.

## Public trust and editorial surfaces

The following returned HTTP 200:

- `/methodology`
- `/risk`
- `/privacy`
- `/terms`
- `/admin`
- `/articles`

The admin interface includes controlled publish and rollback actions. Public article output is empty until a draft is approved and manually published; no test article was inserted into production.

## Repository gates

PR #59 passed both required jobs before merge:

- `test`: success
- `secret-scan`: success

## Items intentionally still blocked

1. Exact domain and role-based email addresses.
2. Formal US/Brazil trademark clearance for PrediBeacon.
3. Final legal entity, responsible operator, jurisdiction, and address.
4. Written partner contracts and territory/channel authorization.
5. Social account ownership, business verification, credentials, and platform approval.
6. Counsel-approved final terms, privacy notice, disclosures, age/geo rules, and marketing claims.
7. A controlled editorial dry run using a real evidence-qualified candidate.

These blockers require owner, partner, platform, or professional decisions. They must not be bypassed by configuration defaults.


## Official domain validation — 0.27.1

Validated at 2026-08-22 19:15 UTC.

- `https://predibeacon.com/`: HTTP 200 over HTTPS.
- `/health`: version 0.27.1, status `ok`.
- canonical: `https://predibeacon.com/`.
- `robots.txt`: sitemap points to `https://predibeacon.com/sitemap.xml`.
- sitemap locations use the official apex origin.
- `https://www.predibeacon.com/api/v1/markets?limit=1`: HTTP 308 to the identical path and query at `https://predibeacon.com`.
- Kalshi: 100 markets; Polymarket: 100 markets; freshness: `fresh`.
- persistent storage remained writable and retained identity `fcb833b0327b062c3335f8b95e1dd636` across the domain deploy.
- automated publishing and social distribution remained disabled.

The Railway technical domain remains available for infrastructure purposes but is not the configured public canonical origin.
