# Production evidence: secure editorial review

Validated against the Railway production service on 2026-08-22 after deployment of version 0.21.0.

## Public service

- Base URL: `https://marketpulse-production-aa9f.up.railway.app`
- `GET /health`: HTTP 200, service `marketpulse-web`, version `0.21.0`
- Market ingestion: 100 Kalshi and 100 Polymarket markets
- Automated publishing: disabled

## Administrative review boundary

- `GET /admin`: HTTP 200
- `GET /api/v1/admin/drafts` without `X-MarketPulse-Admin-Token`: HTTP 401 with `invalid admin credentials`
- `admin_review_configured`: `true`
- The page sends `Cache-Control: no-store`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`.
- CSP uses a fresh nonce and denies every source by default; `frame-ancestors`, `base-uri`, and `form-action` are `none`.
- Browser code uses `credentials: 'omit'` and `cache: 'no-store'`.
- The administrative token remains in page memory for the current tab only. The page contains no use of cookies, `localStorage`, or `sessionStorage`.
- Approval or rejection requires an editorial reason and changes only the audited draft state. Approval does not publish content.

## Provider and persistence

- OpenAI draft configuration: enabled, configured, and startup-verified
- Model: `gpt-5.6-luna`
- Daily draft ceiling: 100
- Drafts generated on validation date: 0
- Persistent database: writable and volume-backed
- Storage identity: `fcb833b0327b062c3335f8b95e1dd636`
- Startup count: 19
- First recorded startup: `2026-08-22T15:17:34.679090+00:00`
- Latest recorded startup: `2026-08-22T17:25:25.811999+00:00`

The unchanged storage identity across deployments is the persistence check. No secret value is recorded in this document.

## Evidence refresh after deployment

The post-startup feed refresh completed without an error:

| Source | Items |
|---|---:|
| Federal Reserve | 35 |
| U.S. Securities and Exchange Commission | 50 |
| NPR | 10 |
| BBC News | 82 |
| ABC News | 50 |
| **Total** | **227** |

- Official evidence items associated: 15
- News evidence items associated: 0
- Markets with external evidence: 3

Zero news associations is an accepted conservative outcome: it must not create a draft from weak or unrelated evidence.
