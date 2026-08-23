# PrediBeacon — Master Test Plan

## Objective

Make production validation automated and repeatable so the owner does not need to manually test every button, browser state, language and data condition after each deploy.

## Quality gates

A change is releasable only when all of these pass:

1. unit/domain tests (`pytest`)
2. API/route tests
3. security secret scan
4. performance smoke
5. browser E2E matrix (Chromium)
6. production quality gate
7. deployment status checks

## Controlled dimensions

The home-page state space is modeled explicitly.

- Platform: `all`, `kalshi`, `polymarket`
- Sort: `trending`, `movers`, `volume`
- Quick mode: `trending`, `movers`, `volume`, `closing`
- Category: `all`, `Economy`, `Politics`, `Sports`, `Tech`
- Data state: `normal`, `empty`, `partial`, `error`, `slow`
- Viewport: desktop 1440x900, laptop 1280x720, tablet 768x1024, mobile 390x844
- Locale: English, Portuguese (Brazil), Spanish
- Input: mouse, keyboard
- Navigation entry: root URL, direct venue URL, back/forward navigation

The complete Cartesian product is intentionally not executed in a browser on every commit because it grows into thousands of slow redundant cases. Instead:

- finite query/filter logic is covered exhaustively in fast tests;
- browser interaction uses pairwise/risk-based coverage plus every critical path;
- all clickable internal navigation is crawled automatically;
- error/empty/slow states are explicitly exercised.

## Home-page browser tests

### Venue hub

- Entire Kalshi card is clickable.
- Kalshi chart area is clickable through the parent card.
- `Explore Kalshi` navigates to `?venue=kalshi#markets`.
- Kalshi direct URL initializes the platform select to Kalshi.
- Only Kalshi cards are rendered when Kalshi is selected.
- Entire Polymarket card behaves equivalently.
- PrediBeacon lighthouse resets to the combined view.
- Keyboard Enter activates Kalshi, PrediBeacon and Polymarket.
- Browser Back/Forward preserves the chosen view.

### Sort and quick filters

- `Most relevant / Para você` => `sort=trending`.
- `Movement / Em movimento` => `sort=movers`.
- `Most active / Mais ativos` => `sort=volume`.
- `Closing soon / Terminando em breve` uses the closing-soon endpoint.
- The active quick filter has exactly one `aria-pressed=true`.
- Sort remains compatible with every platform and category.

### Categories

Every category button is clicked for all three platform states and all three sort states. Expected query parameters and selected visual state are verified.

### Market cards

- Venue badge matches provider.
- Probability accepts known value and unavailable value.
- Movement handles positive, negative and unavailable values.
- Volume handles numeric and unavailable values.
- Deadline handles future, closed and unknown values.
- Analysis button has a valid internal destination.
- Watch button toggles Watch/Watching and persists in localStorage.
- Cross-platform availability panel handles verified equivalent, candidate only, no counterpart and endpoint failure.

### Data resilience

- Normal feed.
- Empty feed.
- One platform unavailable.
- Both platforms unavailable.
- Status endpoint failure.
- Market endpoint failure.
- Comparison endpoint failure.
- Delayed responses: page remains responsive.
- No JavaScript `pageerror` or infinite MutationObserver loop.
- Loading indicators eventually transition to content or an explicit unavailable/error state in bounded-response scenarios.

### Navigation and legal pages

The crawler checks all internal links discovered from the public pages, including at minimum:

- Markets / home
- Disagreements anchor
- Intelligence
- Watchlist
- Alerts
- Briefs / summaries
- Methodology
- Risk
- Privacy
- Terms
- Market detail links

Each internal destination must return a non-5xx response and must not emit an uncaught browser exception during initial render.

## Responsive checks

At each viewport:

- no horizontal overflow greater than two pixels;
- venue hub remains visible and usable;
- no overlapping hero text/cards;
- buttons stay at least 44px high where intended;
- main navigation remains reachable;
- market rows/cards remain readable;
- footer remains reachable.

## Accessibility checks

- skip link is keyboard reachable;
- all actionable hub elements have accessible names;
- select elements have labels;
- active chips use `aria-pressed`;
- status areas use live regions without causing DOM mutation loops;
- keyboard activation works without a mouse;
- focus is not trapped.

## Locale checks

For EN/PT-BR/ES:

- browser locale can initialize the site language;
- manual language override wins over browser default;
- venue/filter state is preserved when language changes;
- customer-facing labels are not mixed between languages on the same component;
- legal/trust text follows the controlled translation/fallback policy.

## Production/domain checks

After merge, deployment automation must verify:

- Railway deployment status is success;
- `https://predibeacon.com` responds;
- `https://www.predibeacon.com` behavior is intentional (serve or redirect);
- canonical domain and Railway origin deliver the same app version;
- custom-domain page does not freeze;
- no permanent loading state under healthy APIs;
- DNS/proxy changes are not required for ordinary application releases.

## Regression policy

Every production incident must add a regression test before or with the fix. In particular, these incidents are permanently covered:

- custom domain loads differently from Railway origin;
- venue cards appear clickable but do not navigate/filter;
- URL changes without applying venue filter;
- localization MutationObserver recursively rewrites DOM and freezes Chrome;
- loading state remains visible after an API error.

## Research-backed quality decisions

Before a material UX, mobile, accessibility, security, performance, SEO, PWA or testing decision is accepted, the implementation must be compared with current primary-source guidance and the project must record whether the practice is adopted, adapted or rejected with rationale. Research must prefer current standards and first-party documentation over blog opinion.

Current baseline decisions:

- Responsive design on one URL is the default. Separate mobile URLs and user-agent-specific HTML are rejected unless a future hard requirement proves they are necessary. This follows Google mobile-first indexing guidance and reduces duplicate implementation paths.
- Browser E2E tests must assert user-visible behavior with isolated state and role/label-based locators where practical. This follows Playwright guidance and avoids brittle implementation-detail tests.
- WCAG 2.2 AA is the minimum accessibility target. Touch controls should normally target at least 44x44 CSS px even though WCAG 2.2 AA allows smaller targets with spacing exceptions; focus must remain visible and unobscured.
- Core Web Vitals field targets are LCP <= 2.5 s, INP <= 200 ms and CLS <= 0.1 at the 75th percentile, segmented by mobile and desktop. Synthetic CI thresholds are supporting regression gates, not substitutes for field data.
- Security verification uses OWASP ASVS 5.0 as the reference checklist for web application controls, supplemented by project-specific threat tests for outbound attribution, admin APIs, partner reconciliation and data leakage.

## Final-project acceptance execution

The project is not considered finished merely because the latest PR is green. At the end of implementation, a dedicated final acceptance run must be executed without waiting for owner prompts.

The final run must include:

1. full `pytest` suite and all deterministic combinatorial tests;
2. browser E2E critical journeys with fresh isolated contexts;
3. mobile/tablet/desktop responsive matrix, including small-phone widths and landscape where layout risk exists;
4. keyboard-only navigation and accessibility checks against the WCAG 2.2 AA target;
5. production-domain crawl of every discoverable public route and every actionable control reachable from those routes;
6. Kalshi-only, Polymarket-only and combined-view journeys, including market absent on the other venue;
7. outbound routing in organic and commercially configured test modes, proving no commission percentage, partner economics or private identifiers leak publicly;
8. locale/browser-language/manual-override combinations for every supported language catalog, with English fallback checks;
9. healthy, empty, partial, stale, slow, timeout, malformed and upstream-failure data states;
10. watchlist, alerts, sharing/campaign attribution, market detail, comparison, related markets, Top 10 and installable PWA flows;
11. SEO checks: canonical, robots, sitemap, structured data, Open Graph and mobile content parity;
12. security checks mapped to applicable OWASP ASVS controls plus secret scan, auth boundaries, HMAC replay protection, input validation, XSS/HTML injection, open redirect, path/query abuse and sensitive-response cache policy;
13. performance regression tests plus production field-metric review when sufficient traffic exists;
14. service-worker/offline tests proving no admin/API/outbound/editorial sensitive responses are cached;
15. deployment verification on `predibeacon.com`, `www` behavior and Railway origin equivalence;
16. partner/revenue tests proving only verified partner data enters revenue accounting and user-facing pages never expose internal commission rates;
17. regression replay for every incident recorded during development;
18. final requirements audit: every registry item must end as VERIFIED, BLOCKED with an external dependency and evidence, REPLACED_WITH_EVIDENCE, or REMOVED_WITH_RATIONALE. No unexplained `IN_PROGRESS` or `REQUIRED` item is allowed at project close.

Failures in this final run are treated as project defects, not manual-owner acceptance tasks. A defect must be fixed, receive a regression test, and the affected final-run segment must be repeated before closure.

## Manual testing policy

Manual owner testing is a final visual/product acceptance check, not the primary QA mechanism. Routine functional verification belongs in CI. The owner is not expected to execute the final test matrix manually.