# MarketPulse Requirements Registry

This registry is the scope-control source of truth. A requirement may not disappear silently. Allowed terminal states: VERIFIED, REPLACED_WITH_EVIDENCE, BLOCKED, or REMOVED_WITH_RATIONALE. `DEFERRED` is non-terminal and must retain an owner/reason.

| ID | Requirement | Status | Evidence / gate |
|---|---|---|---|
| MP-001 | Automation-first operation; no routine manual site feeding | IN_PROGRESS | ingestion worker and runtime scheduling implemented; content/distribution workers + E2E pending |
| MP-002 | Configuration-first; avoid legitimate business variation in hardcode | IN_PROGRESS | versioned config + validation |
| MP-003 | USA first active market | VERIFIED | US country pack |
| MP-004 | Architecture prepared for UK and Brazil | VERIFIED | disabled UK/BR country packs |
| MP-005 | Kalshi public-data ingestion | VERIFIED | normalized adapter + tests |
| MP-006 | Polymarket public-data ingestion | VERIFIED | normalized adapter + tests |
| MP-007 | Normalized market model | VERIFIED | domain model + tests |
| MP-008 | Snapshot history | VERIFIED | SQLite WAL snapshot store + tests |
| MP-009 | Movers/trending discovery | IN_PROGRESS | runtime ingestion + snapshots + signal engine + ranking API + dynamic UI; live deployment evidence pending |
| MP-010 | Market equivalence must not be inferred from title similarity alone | IN_PROGRESS | fail-safe contract matcher + adversarial tests; CI/release evidence pending |
| MP-011 | Market comparison UI with explicit non-equivalence handling | REQUIRED | UX + matching gate |
| MP-012 | News/evidence context engine | IN_PROGRESS | provenance model + canonical URL dedupe + explicit freshness states + source diversity gate; collectors/UI pending |
| MP-013 | Automated AI content candidates | IN_PROGRESS | evidence-gated candidate classifier with update/create decisions; generation/queue persistence pending |
| MP-014 | Automated website publishing | REQUIRED | content lifecycle + rollback |
| MP-015 | SEO automation | REQUIRED | metadata/sitemap/canonical/schema validation |
| MP-016 | Instagram distribution | REQUIRED | provider/policy integration |
| MP-017 | TikTok distribution | REQUIRED | provider/policy integration |
| MP-018 | Telegram distribution | REQUIRED | provider integration |
| MP-019 | WhatsApp distribution where channel policy permits | REQUIRED | policy + provider integration |
| MP-020 | Outbound router is country/partner/market aware and fail-closed | IN_PROGRESS | server-side route IDs + HTTPS host allowlist + commercial verification gate; market-level eligibility/UI pending |
| MP-021 | Partner attribution | IN_PROGRESS | attribution/revenue state model exists; click persistence + partner event reconciliation pending |
| MP-022 | Partner revenue states: pending/approved/payable/paid/reversed etc. | IN_PROGRESS | explicit guarded state machine + tests; persistence/reconciliation pending |
| MP-023 | Revenue dashboard; no unnecessary user-funds accounting | REQUIRED | dashboard/reconciliation |
| MP-024 | Mobile-first, simple, accessible website | IN_PROGRESS | dynamic baseline UI; usability/accessibility audit pending |
| MP-025 | Search and category discovery | IN_PROGRESS | runtime read-model now feeds dynamic API/UI; deployed live-data E2E pending |
| MP-026 | Freshness displayed honestly; never claim live without evidence | IN_PROGRESS | timestamp UI + evidence freshness states (fresh/stale/future/undated); E2E stale-state pending |
| MP-027 | GitHub PR + CI gates | VERIFIED | repository workflow |
| MP-028 | Railway staging with deterministic healthcheck | VERIFIED | Docker deployment + /health |
| MP-029 | Secrets never committed | REQUIRED | secret scanning/config gate |
| MP-030 | Observability, retries, timeouts, rate-limit handling | IN_PROGRESS | transient-only retries for 429/5xx/network, bounded timeouts, structured refresh logs/status and failure isolation; metrics dashboard pending |
| MP-031 | Feature flags and kill switches for external venues/publishing | VERIFIED | fail-closed runtime flags + worker enforcement + tests |
| MP-032 | Partner economics never invented; require evidence/config | IN_PROGRESS | router requires commercial_verified; commission amount absent unless supplied by partner evidence; config validation pending |
| MP-033 | Global-ready locale/currency/timezone/policy boundaries | IN_PROGRESS | country packs; runtime localization pending |
| MP-034 | Future integration path with broader global platform preserved | REQUIRED | bounded interfaces/ADR |
| MP-035 | Final evidence audit: requirement -> code -> config -> test -> result | REQUIRED | release checklist |

## Change-control rule

Every PR that materially changes product scope must update this registry. Replacements require a rationale and evidence. A requirement cannot be marked VERIFIED from prose alone: reproducible code/config/test/deployment evidence is required.
