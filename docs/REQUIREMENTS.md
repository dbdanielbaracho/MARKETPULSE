# MarketPulse Requirements Registry

This registry is the scope-control source of truth. A requirement may not disappear silently. Allowed terminal states: VERIFIED, REPLACED_WITH_EVIDENCE, BLOCKED, or REMOVED_WITH_RATIONALE. `DEFERRED` is non-terminal and must retain an owner/reason.

| ID | Requirement | Status | Evidence / gate |
|---|---|---|---|
| MP-001 | Automation-first operation; no routine manual site feeding | IN_PROGRESS | ingestion worker and runtime scheduling implemented; content/distribution workers + E2E pending |
| MP-002 | Configuration-first; avoid legitimate business variation in hardcode | IN_PROGRESS | versioned config + validation; PrediBeacon public brand remains separated from MarketPulse technical identifiers |
| MP-003 | USA first active market | VERIFIED | US country pack |
| MP-004 | Architecture prepared for UK and Brazil | VERIFIED | disabled UK/BR country packs |
| MP-005 | Kalshi public-data ingestion | VERIFIED | current decimal-schema adapter, tests, and live count evidence |
| MP-006 | Polymarket public-data ingestion | VERIFIED | normalized adapter, tests, and live count evidence |
| MP-007 | Normalized market model | VERIFIED | domain model + tests |
| MP-008 | Snapshot history | VERIFIED | SQLite WAL snapshot store + tests |
| MP-009 | Movers/trending discovery | VERIFIED | runtime ranking API/UI and reproducible production evidence in `docs/LIVE_EVIDENCE.md` |
| MP-010 | Market equivalence must not be inferred from title similarity alone | VERIFIED | fail-closed matcher, adversarial tests, comparison API and deployed evidence |
| MP-011 | Market comparison UI with explicit non-equivalence handling | VERIFIED | accessible comparison UI and live `equivalent_contracts=false` evidence |
| MP-012 | News/evidence context engine | IN_PROGRESS | venue provenance, Federal Reserve/SEC official feeds and allowlisted NPR/BBC/ABC News feeds with freshness, per-source telemetry and conservative matching; 3 live official market matches verified, live publisher diversity pending |
| MP-013 | Automated AI content candidates | IN_PROGRESS | evidence-gated classifier, durable audited queue, immutable snapshots, citation-locked drafts and opt-in OpenAI Structured Outputs provider with Luna default, reasoning disabled, output cap and daily draft limit; credential/model verification passed in production, first evidence-diverse AI draft pending |
| MP-014 | Automated website publishing | IN_PROGRESS | fail-closed authenticated review plus manual publication API, immutable version/citations, public article views and audited rollback; production publishing UI, scheduling and automated worker remain pending |
| MP-015 | SEO automation | VERIFIED | canonical, Open Graph, JSON-LD, valid robots.txt and sitemap with tests/live evidence |
| MP-016 | Instagram distribution | IN_PROGRESS | fail-closed credential, authorization, country, contract and editorial readiness gates; provider integration pending |
| MP-017 | TikTok distribution | IN_PROGRESS | fail-closed credential, authorization, country, contract and editorial readiness gates; provider integration pending |
| MP-018 | Telegram distribution | IN_PROGRESS | fail-closed readiness gate; bot/provider integration pending |
| MP-019 | WhatsApp distribution where channel policy permits | IN_PROGRESS | fail-closed readiness gate; policy approval and provider integration pending |
| MP-020 | Outbound router is country/partner/market aware and fail-closed | IN_PROGRESS | first-party market-level outbound endpoint, exact venue/market validation, HTTPS allowlist and new-tab UI implemented; organic clicks work while commercial partner identity remains evidence-gated |
| MP-021 | Partner attribution | IN_PROGRESS | durable click ledger now captures market, campaign, creator, channel and referrer before redirect; partner conversion adapter remains pending |
| MP-022 | Partner revenue states: pending/approved/payable/paid/reversed etc. | IN_PROGRESS | guarded state machine plus durable idempotent partner-event transitions and audit log; live partner reconciliation pending |
| MP-023 | Revenue dashboard; no unnecessary user-funds accounting | VERIFIED | durable ledger plus protected 0.29.0 dashboard; zero-state and tests prove only partner-reported currency amounts are counted and no user-funds ledger exists |
| MP-024 | Mobile-first, simple, accessible website | IN_PROGRESS | discovery cards now open an internal market journey with responsive detail view, local watchlist, sharing and explicit external-new-tab CTA; production usability evidence pending |
| MP-025 | Search and category discovery | VERIFIED | deployed API/UI filters with production evidence in `docs/LIVE_EVIDENCE.md` |
| MP-026 | Freshness displayed honestly; never claim live without evidence | VERIFIED | bounded freshness states, UI banner, tests and live Railway evidence |
| MP-027 | GitHub PR + CI gates | VERIFIED | repository workflow |
| MP-028 | Railway staging with deterministic healthcheck | VERIFIED | Docker deployment + /health |
| MP-029 | Secrets never committed | VERIFIED | pinned Gitleaks CI gate scans full Git history on pushes and PRs |
| MP-030 | Observability, retries, timeouts, rate-limit handling | VERIFIED | bounded retry/timeout behavior, structured telemetry, live protected 0.28.0 operations dashboard, explicit critical/warning checks, fail-closed auth and regression tests |
| MP-031 | Feature flags and kill switches for external venues/publishing | VERIFIED | fail-closed runtime flags + worker enforcement + tests |
| MP-032 | Partner economics never invented; require evidence/config | IN_PROGRESS | router requires commercial_verified, commission absent without evidence, and partner-readiness checklist captures required contract/reconciliation proof; config validation pending |
| MP-033 | Global-ready locale/currency/timezone/policy boundaries | IN_PROGRESS | country packs plus explicit US, Brazil and unknown-country policy boundaries; runtime localization pending |
| MP-034 | Future integration path with broader global platform preserved | VERIFIED | accepted ADR 0001, runtime-checkable MarketFetcher port, normalized domain boundary and regression tests prove new venue adapters require no core rewrite |
| MP-035 | Final evidence audit: requirement -> code -> config -> test -> result | REQUIRED | release checklist |
| MP-036 | Every discoverable market has an internal PrediBeacon detail journey before outbound | IN_PROGRESS | detail API/page and card navigation implemented; canonical slug URLs and history chart pending |
| MP-037 | Preserve PrediBeacon while external venue opens separately | IN_PROGRESS | venue CTA uses a new tab with explicit external-platform notice; live browser evidence pending |
| MP-038 | First-party watchlist without requiring account or custody | IN_PROGRESS | local-browser add/remove implemented; dedicated watchlist view and sync pending |
| MP-039 | Shareable market links preserve campaign, creator and channel context | IN_PROGRESS | detail sharing and outbound context persistence implemented; campaign link builder pending |
| MP-040 | Probability history and event timeline | REQUIRED | snapshot data exists; public chart/timeline pending |
| MP-041 | Explain trend and movement using attributable evidence | REQUIRED | trend/evidence foundations exist; public explanation component pending |
| MP-042 | Alerts for thresholds, material moves, evidence and closing time | REQUIRED | notification preference and delivery workers pending |
| MP-043 | Creator pages, lists, tracked links and paid-revenue-only sharing | REQUIRED | attribution fields exist; creator product pending |
| MP-044 | Embeddable widgets remain visibly Powered by PrediBeacon | REQUIRED | widget API and embed pending |
| MP-045 | PrediBeacon Pro subscriptions for advanced intelligence | REQUIRED | product packaging, entitlements and billing pending |
| MP-046 | Commercial API for normalized data and proprietary signals | REQUIRED | public discovery API exists; authentication, quotas and commercial packaging pending |
| MP-047 | PrediBeacon remains a single public brand; white label is excluded | VERIFIED | explicit product-scope decision; no third-party branded instances or reseller mode |

## Change-control rule

Every PR that materially changes product scope must update this registry. Replacements require a rationale and evidence. A requirement cannot be marked VERIFIED from prose alone: reproducible code/config/test/deployment evidence is required.
