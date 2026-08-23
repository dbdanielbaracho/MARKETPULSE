# PrediBeacon Partner Launch Packet

Last reviewed: 2026-08-23

This document is an application and operating packet, not evidence that any commercial relationship is approved. PrediBeacon must remain in organic-routing mode until a venue has explicitly approved the relationship and the corresponding commercial configuration is complete.

## Product summary

PrediBeacon is a prediction-market intelligence and discovery product that aggregates and normalizes public market information from Kalshi and Polymarket, ranks what deserves attention, explains market movement and evidence, helps users compare venues without falsely equating non-equivalent contracts, and routes users to the original venue to act.

PrediBeacon does not custody customer funds, hold user trading balances, execute trades, promise returns, or manufacture venue prices. The product is designed around source attribution, contract-equivalence safety, jurisdiction controls, auditability, and external execution at the venue.

Public product: https://predibeacon.com

## What PrediBeacon can offer a venue

- Qualified discovery traffic to individual markets rather than generic home-page traffic.
- Venue branding visible before the user leaves PrediBeacon.
- First-party attribution from discovery channel to market detail to outbound venue click.
- Creator/campaign links with durable click attribution.
- A comparison experience that explicitly refuses to call two contracts equivalent without sufficient evidence.
- Source provenance and freshness controls intended to reduce misleading market presentation.
- No hidden re-routing: partner mode is enabled only after documented commercial verification.

## Kalshi application position

Official entry point reviewed: https://aff.kalshi.com/

The current Kalshi Affiliates dashboard describes partner referral and earnings reporting and notes that it is available to Kalshi accounts and partner accounts that have been granted access.

### Request to Kalshi

PrediBeacon should request:

1. Affiliate/partner account approval for `predibeacon.com`.
2. A stable partner/referral identifier suitable for individual market deep links.
3. Written confirmation of permitted attribution parameters and link format.
4. Access to conversion/revenue reporting and, if available, signed webhook or export reconciliation.
5. Written brand/trademark usage guidance for displaying the Kalshi name/logo in venue labels.
6. Written confirmation of any restrictions on paid social, creator distribution, incentives, geographic targeting, and marketing copy.
7. Clarification of whether any separate data/display permission is required for PrediBeacon's normalized market-intelligence presentation.

### Kalshi production activation rule

Do not enable commercial mode until approval is documented. Required runtime state:

- `MP_KALSHI_COMMERCIAL_VERIFIED=true`
- `MP_KALSHI_PARTNER_ID=<approved partner id>`
- `MP_KALSHI_WEBHOOK_SECRET=<venue-issued/negotiated secret>` only if reconciliation webhooks are actually supported and agreed.

If approval is absent, keep `MP_KALSHI_COMMERCIAL_VERIFIED=false`; PrediBeacon continues to use verified organic routing.

## Polymarket application position

Official resources reviewed:

- Referral program: https://help.polymarket.com/en/articles/14174498-referral-program
- Builders program: https://builders.polymarket.com/
- API information: https://help.polymarket.com/en/articles/13364254-does-polymarket-have-an-api
- Institutional/data notice: https://institutional.polymarket.com/

### Important distinction

Polymarket's current general referral program says referral earnings begin only after the referring Polymarket account reaches the program's stated lifetime trading-volume threshold. PrediBeacon should not create trading volume merely to qualify for a referral program. Its business model should remain independent of proprietary trading.

Polymarket also operates a Builders Program with builder credentials and integration support. Builder Codes are primarily relevant to integrations that attribute orders/volume. PrediBeacon is currently outbound-only and does not execute user orders, so the appropriate application should ask Polymarket which commercial path fits a discovery/intelligence product rather than pretending Builder Code eligibility automatically applies.

### Request to Polymarket

PrediBeacon should request:

1. A direct referral, builder, distribution, or commercial partner path appropriate for an outbound intelligence/discovery site.
2. Written permission and technical method for stable attribution on individual market links.
3. Clarification whether referral eligibility can be granted to an approved partner independently of personal/proprietary trading-volume qualification.
4. Written brand/trademark guidance.
5. Clarification of permitted use, normalization, caching, and redistribution of Polymarket market data for retail users.
6. Explicit data-licensing guidance before offering PrediBeacon data to professional/capital-markets entities. Polymarket's institutional notice says capital-markets entities consuming Polymarket data/content must do so in consultation with Polymarket and ICE.
7. Reporting/reconciliation support for partner conversions and commissions, if approved.

### Polymarket production activation rule

Do not enable commercial mode until approval is documented. Required runtime state:

- `MP_POLYMARKET_COMMERCIAL_VERIFIED=true`
- `MP_POLYMARKET_PARTNER_ID=<approved partner id>`
- `MP_POLYMARKET_WEBHOOK_SECRET=<venue-issued/negotiated secret>` only if reconciliation webhooks are actually supported and agreed.

If approval is absent, keep `MP_POLYMARKET_COMMERCIAL_VERIFIED=false`; PrediBeacon continues to use verified organic routing.

## Application dossier

Use the following information in both applications. Do not invent missing metrics.

### Company/product description

> PrediBeacon is an independent prediction-market intelligence and discovery platform. We aggregate and normalize public market information from multiple venues, rank relevant markets, provide evidence and contract-comparison context, and send users to the original venue for execution. PrediBeacon does not custody funds or execute trades. Our goal is to help users discover the right market and understand which venue they are entering before they leave our site.

### Safety and trust controls

- Venue identity is visible before outbound navigation.
- Organic routing is the default.
- Partner mode requires both a verified commercial flag and a partner identity; incomplete configuration fails closed.
- Outbound clicks are durably attributed for reconciliation.
- Commission amounts are never estimated; only partner-reported amounts enter revenue totals.
- Similar market titles are not treated as equivalent contracts automatically.
- Stale/expired/invalid market data is checked by automated production gates.
- Automated social publishing remains disabled until separately authorized.
- No raw IP address or user-agent is stored by first-party launch analytics.

### Metrics to attach after traffic exists

Pull these from the protected PrediBeacon admin endpoints rather than estimating them:

- 30-day page views.
- Home-to-market-detail rate.
- Market-detail-to-outbound-click rate.
- Outbound clicks by venue/channel.
- Top market-detail pages.
- Campaign/creator attributed clicks.
- Partner-reported conversion/revenue states once a partner feed is active.

Never submit fabricated audience, conversion, AUM, trading-volume, or revenue numbers.

## Suggested outreach message

Subject: PrediBeacon — prediction-market discovery and qualified market traffic partnership

Hello,

PrediBeacon (https://predibeacon.com) is an independent prediction-market intelligence and discovery platform. We normalize and rank public markets, explain market signals and evidence, compare venue availability carefully, and route users to the original venue for execution. We do not custody funds or execute trades.

We are preparing our public launch and would like to discuss the correct commercial/partner structure for sending qualified, market-level traffic to your platform. We already support organic deep linking and durable first-party attribution, but we intentionally do not activate commercial attribution until a venue has explicitly approved the relationship and issued the required partner identity.

We would like guidance on partner/referral eligibility, permitted deep-link attribution, reporting/reconciliation, brand usage, marketing restrictions, and any data/display licensing requirements relevant to our use case.

We can provide product screenshots, architecture/safety controls, and verified traffic/funnel metrics as they accumulate.

Thank you.

## External actions still required

These cannot be completed from the PrediBeacon codebase itself:

- Sign in/create the appropriate Kalshi account and request affiliate/partner access.
- Contact/apply to Polymarket for the appropriate referral/builder/commercial path.
- Accept any venue-specific contractual terms only after human/legal review.
- Receive actual partner IDs, referral formats, webhook secrets, or written data/brand permissions.
- Add those secrets/identifiers to the production environment after approval.

Until those actions are complete, the correct production state is organic routing with zero assumed partner revenue.
