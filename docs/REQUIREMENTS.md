# MarketPulse Requirements Registry

This registry is the scope-control source of truth. A requirement may not disappear silently. Allowed terminal states: VERIFIED, REPLACED_WITH_EVIDENCE, BLOCKED, or REMOVED_WITH_RATIONALE. `DEFERRED` is non-terminal and must retain an owner/reason.

| ID | Requirement | Status | Evidence / gate |
|---|---|---|---|
| MP-001 | Automation-first operation; no routine manual site feeding | IN_PROGRESS | ingestion/content/distribution workers + E2E |
| MP-002 | Configuration-first; avoid legitimate business variation in hardcode | IN_PROGRESS | versioned config + validation |
| MP-003 | USA first active market | VERIFIED | US country pack |
| MP-004 | Architecture prepared for UK and Brazil | VERIFIED | disabled UK/BR country packs |
| MP-005 | Kalshi public-data ingestion | VERIFIED | normalized adapter + tests |
| MP-006 | Polymarket public-data ingestion | VERIFIED | normalized adapter + tests |
| MP-007 | Normalized market model | VERIFIED | domain model + tests |
| MP-008 | Snapshot history | VERIFIED | SQLite WAL snapshot store + tests |
| MP-009 | Movers/trending discovery | IN_PROGRESS | signal engine exists; ranking/API/UI pending |
| MP-010 | Market equivalence must not be inferred from title similarity alone | REQUIRED | contract-aware matching tests required |
| MP-011 | Market comparison UI with explicit non-equivalence handling | REQUIRED | UX + matching gate |
| MP-012 | News/evidence context engine | REQUIRED | source provenance + freshness gate |
| MP-013 | Automated AI content candidates | REQUIRED | score/policy/queue tests |
| MP-014 | Automated website publishing | REQUIRED | content lifecycle + rollback |
| MP-015 | SEO automation | REQUIRED | metadata/sitemap/canonical/schema validation |
| MP-016 | Instagram distribution | REQUIRED | provider/policy integration |
| MP-017 | TikTok distribution | REQUIRED | provider/policy integration |
| MP-018 | Telegram distribution | REQUIRED | provider integration |
| MP-019 | WhatsApp distribution where channel policy permits | REQUIRED | policy + provider integration |
| MP-020 | Outbound router is country/partner/market aware and fail-closed | IN_PROGRESS | policy exists; runtime/tests pending |
| MP-021 | Partner attribution | REQUIRED | click/event state machine |
| MP-022 | Partner revenue states: pending/approved/payable/paid/reversed etc. | REQUIRED | reconciliation model/tests |
| MP-023 | Revenue dashboard; no unnecessary user-funds accounting | REQUIRED | dashboard/reconciliation |
| MP-024 | Mobile-first, simple, accessible website | IN_PROGRESS | baseline UI; usability/accessibility audit pending |
| MP-025 | Search and category discovery | IN_PROGRESS | baseline UI; dynamic data pending |
| MP-026 | Freshness displayed honestly; never claim live without evidence | REQUIRED | freshness contract/tests |
| MP-027 | GitHub PR + CI gates | VERIFIED | repository workflow |
| MP-028 | Railway staging with deterministic healthcheck | VERIFIED | Docker deployment + /health |
| MP-029 | Secrets never committed | REQUIRED | secret scanning/config gate |
| MP-030 | Observability, retries, timeouts, rate-limit handling | REQUIRED | metrics/logs/backoff tests |
| MP-031 | Feature flags and kill switches for external venues/publishing | REQUIRED | runtime policy tests |
| MP-032 | Partner economics never invented; require evidence/config | REQUIRED | partner config validation |
| MP-033 | Global-ready locale/currency/timezone/policy boundaries | IN_PROGRESS | country packs; runtime localization pending |
| MP-034 | Future integration path with broader global platform preserved | REQUIRED | bounded interfaces/ADR |
| MP-035 | Final evidence audit: requirement -> code -> config -> test -> result | REQUIRED | release checklist |

## Change-control rule

Every PR that materially changes product scope must update this registry. Replacements require a rationale and evidence. A requirement cannot be marked VERIFIED from prose alone: reproducible code/config/test/deployment evidence is required.
