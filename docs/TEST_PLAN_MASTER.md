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

## Manual testing policy

Manual owner testing is a final visual acceptance check, not the primary QA mechanism. Routine functional verification belongs in CI.