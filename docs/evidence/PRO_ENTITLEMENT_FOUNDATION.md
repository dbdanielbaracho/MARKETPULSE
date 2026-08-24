# PrediBeacon Pro entitlement foundation

Reviewed 2026-08-24 against current Stripe primary documentation for subscription lifecycle, webhooks, product mapping, customer portal and entitlements.

## Decision

PrediBeacon Pro access is represented by a **server-side persisted entitlement projection**, not by a client-side checkout redirect, displayed price, cookie or unverified request parameter.

The implementation introduced in `app/services/pro_entitlements.py` deliberately separates three concerns:

1. **Product configuration** — `MP_PRO_PRODUCT_ID` identifies the commercial product. No subscription price, commission, partner identifier or internal economics is embedded in code or public output.
2. **Provider state** — an opaque subject, product, subscription status and optional validity boundary are persisted locally under SQLite WAL.
3. **Feature authorization** — advanced PrediBeacon capabilities are granted only when the persisted product matches configured product identity and the subscription status is explicitly access-granting. Unknown, mismatched, expired or malformed states fail closed.

Current allowed Pro capability keys are internal authorization identifiers:

- `advanced_intelligence`
- `advanced_alerts`
- `evidence_digest`
- `data_export`

They do not imply a public price or a promise that every capability is already commercially launched.

## Subscription lifecycle rule

Stripe documents subscription activity as asynchronous and recommends webhooks to react to subscription state changes. It also documents `trialing` and `active` as access-granting states, while states such as `unpaid` and `canceled` require access revocation. PrediBeacon takes the conservative approach of granting access only for `active` or `trialing`; `past_due`, `paused`, `unpaid`, `canceled`, `incomplete` and unknown values fail closed.

Stripe also recommends mapping access from the subscribed **product rather than price**, allowing price/billing-period changes without changing feature authorization. PrediBeacon therefore stores and matches an opaque product identifier and does not use any price value for authorization.

Stripe Entitlements recommends persisting active entitlements internally for fast authorization. The current local projection prepares that boundary without requiring live Stripe credentials.

## Primary sources

- Stripe, Using webhooks with subscriptions: https://docs.stripe.com/billing/subscriptions/webhooks
- Stripe, Build a subscriptions integration: https://docs.stripe.com/billing/subscriptions/build-subscriptions
- Stripe, Entitlements: https://docs.stripe.com/billing/entitlements

## Remaining external/commercial gates

This foundation does **not** claim live subscription billing. Remaining work includes live Stripe product/customer configuration, checkout creation, verified Stripe webhook signature handling, provider event-to-local projection, customer portal, account/subject binding, production credential verification and live lifecycle evidence. Those steps must not be marked verified until real provider configuration and production acceptance exist.
