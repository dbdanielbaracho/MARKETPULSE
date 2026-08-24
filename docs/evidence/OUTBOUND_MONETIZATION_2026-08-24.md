# Attributable outbound monetization boundary — 2026-08-24

PrediBeacon's public discovery cards now treat the non-control card body as a venue exit while preserving the internal `View PrediBeacon analysis` and `Watch` controls. A Kalshi card constructs only `/out/kalshi?market_id=...&channel=home_card`; a Polymarket card constructs only `/out/polymarket?market_id=...&channel=home_card`.

The browser does not construct raw Kalshi or Polymarket destinations and does not contain invented affiliate, partner, commission, or revenue-share identifiers. The existing server-side outbound boundary owns destination allowlisting, click attribution, country/market/partner policy and application of provider commercial identifiers only when they are explicitly verified and configured.

Regression coverage in `tests/test_home_card_outbound.py` proves: the home receives the attributable-card behavior; provider identity maps to the matching `/out/{venue}` route; external opening uses a separate browsing context with `noopener,noreferrer`; internal links/buttons do not trigger the card exit; non-home responses are not modified; and public UI sources cannot hardcode direct Kalshi/Polymarket links through `href` or `window.open`.

This change increases the set of attributable outbound entry points. It does not claim that a provider will pay for a click before PrediBeacon has an approved commercial relationship and the provider-issued tracking configuration required by that relationship. Those external commercial activations remain governed by the existing partner blocks/evidence.
