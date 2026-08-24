# MarketPulse Requirements Registry

This registry is the scope-control source of truth. A requirement may not disappear silently. Allowed terminal states: VERIFIED, REPLACED_WITH_EVIDENCE, BLOCKED, or REMOVED_WITH_RATIONALE. `DEFERRED` is non-terminal and must retain an owner/reason.

| ID | Requirement | Status | Evidence / gate |
|---|---|---|---|
| MP-001 | Automation-first operation; no routine manual site feeding | IN_PROGRESS | ingestion and scheduled editorial publication workers implemented; external distribution providers and end-to-end production evidence pending |
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
| MP-014 | Automated website publishing | IN_PROGRESS | fail-closed authenticated review UI, manual release, durable UTC scheduling, automated due-publication worker, immutable version/citations and audited rollback implemented; production enablement evidence pending |
| MP-015 | SEO automation | VERIFIED | canonical, Open Graph, JSON-LD, valid robots.txt and sitemap with tests/live evidence |
| MP-016 | Instagram distribution | IN_PROGRESS | fail-closed credential, authorization, country, contract and editorial readiness gates; provider integration pending |
| MP-017 | TikTok distribution | IN_PROGRESS | fail-closed credential, authorization, country, contract and editorial readiness gates; provider integration pending |
| MP-018 | Telegram distribution | IN_PROGRESS | fail-closed readiness gate; bot/provider integration pending |
| MP-019 | WhatsApp distribution where channel policy permits | IN_PROGRESS | fail-closed readiness gate; policy approval and provider integration pending |
| MP-020 | Outbound router is country/partner/market aware and fail-closed | IN_PROGRESS | public market-level route eligibility, exact venue/host validation, organic/partner modes and hidden unavailable CTA implemented for US; additional country runtime routing pending |
| MP-021 | Partner attribution | IN_PROGRESS | durable click context plus signed venue-specific reconciliation intake, click lookup, idempotent partner events and creator aggregation implemented; live partner payload mapping pending |
| MP-022 | Partner revenue states: pending/approved/payable/paid/reversed etc. | IN_PROGRESS | guarded state machine, HMAC-authenticated webhook, timestamp replay window, idempotent transitions and audit log implemented; live partner credentials/events pending |
| MP-023 | Revenue dashboard; no unnecessary user-funds accounting | VERIFIED | durable ledger plus protected 0.29.0 dashboard; zero-state and tests prove only partner-reported currency amounts are counted and no user-funds ledger exists |
| MP-024 | Mobile-first, simple, accessible website | VERIFIED | production browser acceptance on commit `71028a0e710fab4367f53c1de6ee382251984395` passed responsive mobile discovery, internal market journey, touch-target/overflow checks and external CTA flow in run `32686907239` |
| MP-025 | Search and category discovery | VERIFIED | deployed API/UI filters with production evidence in `docs/LIVE_EVIDENCE.md` |
| MP-026 | Freshness displayed honestly; never claim live without evidence | VERIFIED | bounded freshness states, UI banner, tests and live Railway evidence |
| MP-027 | GitHub PR + CI gates | VERIFIED | repository workflow |
| MP-028 | Railway staging with deterministic healthcheck | VERIFIED | Docker deployment + /health |
| MP-029 | Secrets never committed | VERIFIED | pinned Gitleaks CI gate scans full Git history on pushes and PRs |
| MP-030 | Observability, retries, timeouts, rate-limit handling | VERIFIED | bounded retry/timeout behavior, structured telemetry, live protected 0.28.0 operations dashboard, explicit critical/warning checks, fail-closed auth and regression tests |
| MP-031 | Feature flags and kill switches for external venues/publishing | VERIFIED | fail-closed runtime flags + worker enforcement + tests |
| MP-032 | Partner economics never invented; require evidence/config | VERIFIED | startup validation fails closed on missing or malformed partner identity, commercial verification remains evidence-gated, commission stays absent without evidence, partner-readiness checklist requires contract/reconciliation proof, and adversarial regression tests enforce bounded allowlisted configuration |
| MP-033 | Global-ready locale/currency/timezone/policy boundaries | IN_PROGRESS | English-default runtime i18n with persistent EN/ES/PT-BR/FR/DE/IT/JA/KO/ZH-CN/AR selector, controlled translation catalogs, RTL Arabic, cookie-separated caching, safe same-site language redirects and English fallback implemented; provider contract titles remain canonical; broader locale-specific currency/timezone formatting and full legal-copy translation coverage remain pending |
| MP-034 | Future integration path with broader global platform preserved | VERIFIED | accepted ADR 0001, runtime-checkable MarketFetcher port, normalized domain boundary and regression tests prove new venue adapters require no core rewrite |
| MP-035 | Final evidence audit: requirement -> code -> config -> test -> result | VERIFIED | `docs/evidence/READINESS_AUDIT_0.38.0.md` maps internal release areas to implementation, tests and explicit external gates |
| MP-036 | Every discoverable market has an internal PrediBeacon detail journey before outbound | VERIFIED | stable hash-backed canonical slugs, detail page/API, charts, signals, timeline, related markets and explicit outbound choice implemented |
| MP-037 | Preserve PrediBeacon while external venue opens separately | VERIFIED | production browser acceptance run `32686907239` passed the dedicated outbound test after deploy of commit `71028a0e710fab4367f53c1de6ee382251984395`, validating a separate target with noopener/noreferrer while the internal PrediBeacon journey remains open |
| MP-038 | First-party watchlist without requiring account or custody | VERIFIED | local-browser add/remove and dedicated responsive watchlist implemented; no account or custody required |
| MP-039 | Shareable market links preserve campaign, creator and channel context | VERIFIED | durable admin-created short links preserve campaign, creator and channel through internal market journey and outbound attribution |
| MP-040 | Probability history and event timeline | VERIFIED | bounded snapshot history and combined probability/evidence timeline API/UI implemented with timestamps, source links and public chart periods |
| MP-041 | Explain trend and movement using attributable evidence | VERIFIED | observational signal explanations plus timestamped venue/news/official/research evidence timeline implemented without unsupported causal claims |
| MP-042 | Alerts for thresholds, material moves, evidence and closing time | IN_PROGRESS | local probability, breaking, execution, large-trade, verified-gap, new-evidence and user-configurable closing-window alerts implemented fail-closed; permission remains user-gesture-bound, mobile notification presentation prefers service-worker showNotification, and visibility return triggers recheck; durable server-originated background push remains pending |
| MP-043 | Creator pages, lists, tracked links and paid-revenue-only sharing | VERIFIED | public creator selections and tracked campaign links plus hashed creator authentication, admin-only pending/approve/revoke agreement lifecycle, Decimal calculation restricted to reconciled paid partner revenue, authenticated no-store creator summary, and end-to-end regression proving partner/agreement economics are not exposed |
| MP-044 | Embeddable widgets remain visibly Powered by PrediBeacon | VERIFIED | responsive iframe widget, visible Powered by PrediBeacon attribution, internal campaign routing and copy-embed action implemented |
| MP-045 | PrediBeacon Pro subscriptions for advanced intelligence | REQUIRED | product packaging, entitlements and billing pending |
| MP-046 | Commercial API for normalized data and proprietary signals | IN_PROGRESS | hashed one-time API keys, scoped markets/history access, atomic daily quotas and starter/pro/business plan metadata implemented; billing and customer portal pending |
| MP-047 | PrediBeacon remains a single public brand; white label is excluded | VERIFIED | explicit product-scope decision; no third-party branded instances or reseller mode |
| MP-048 | Related-market discovery retains users inside PrediBeacon | VERIFIED | related-market API returns explicit related/insufficient-evidence labels, reasons and `equivalent_contracts=false`; UI repeats the non-equivalence warning |
| MP-049 | Daily Top 10 discovery surfaces trending, movers and volume rankings | VERIFIED | responsive public Top 10 view uses live normalized ranking API and preserves onsite campaign attribution |
| MP-050 | Installable mobile web experience | VERIFIED | complete manifest identity, branded any/maskable SVG icon, standalone metadata and versioned same-origin service-worker shell with cached trust pages |
| MP-051 | Commercial API credentials are never stored in plaintext | VERIFIED | one-time pb_live secret issuance, SHA-256 at-rest hashing, protected admin creation, scope checks and quota tests implemented |
| MP-052 | Partner reconciliation events are authenticated and replay-bounded | VERIFIED | venue-specific HMAC-SHA256 signatures, five-minute timestamp window, exact venue validation, idempotent event IDs and adversarial tests implemented |
| MP-053 | Every active market is represented in the dynamic sitemap | VERIFIED | canonical market URLs are emitted from the current normalized discovery set with hourly change frequency |
| MP-054 | Scheduled editorial publication is durable, explicit and auditable | VERIFIED | approved-only schedule records, timezone-aware validation, idempotent due worker, admin controls and store regression tests implemented |
| MP-055 | Offline caching never persists administrative, API, outbound or editorial responses | VERIFIED | versioned allowlisted service worker excludes sensitive prefixes and has regression coverage |
| MP-056 | Public responses receive baseline browser security protections | VERIFIED | global nosniff, referrer, permissions, opener and HSTS headers; protected APIs force `no-store`; regression tests implemented |
| MP-057 | Commercial API keys support auditable revocation and atomic rotation | VERIFIED | metadata-only listing, immediate revocation, transactional replacement, preserved scopes/limits and adversarial tests implemented |
| MP-058 | Requests are traceable without trusting arbitrary caller identifiers | VERIFIED | bounded validated/generated request IDs, response timing, 1 MiB declared write limit and regression tests implemented |
| MP-059 | Persistent SQLite data has verified online backups and bounded retention | VERIFIED | startup/daily online backup worker on `/data`, integrity-checked copies, 1–90 retention bounds, protected manual controls and restore regression tests implemented |
| MP-060 | Critical release journeys have deterministic end-to-end regression coverage | VERIFIED | discovery → campaign → internal detail → outbound attribution → creator accounting and API key creation/rotation are tested without external network access |
| MP-061 | SQLite write concurrency cannot silently lose commercial API quota increments | VERIFIED | 60 concurrent independent authorizations produce exactly usage counts 1–60 under WAL and atomic `BEGIN IMMEDIATE` accounting |
| MP-062 | CI detects material in-process API performance regressions without loading production | VERIFIED | 240-request direct-ASGI smoke gate enforces a 250 ms p95 regression budget and explicitly excludes network/SLA claims |
| MP-063 | Final project closure requires research-backed best-practice review and execution of the complete master acceptance plan without owner prompting | REQUIRED | `docs/TEST_PLAN_MASTER.md` defines source-of-truth decisions and final execution; may be VERIFIED only after all project requirements are terminal and the full final acceptance run passes or external blocks are evidenced |

## Change-control rule

Every PR that materially changes product scope must update this registry. Replacements require a rationale and evidence. A requirement cannot be marked VERIFIED from prose alone: reproducible code/config/test/deployment evidence is required.
