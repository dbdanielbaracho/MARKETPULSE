# PrediBeacon Pro billing and entitlement decision

Status: accepted architecture; live billing remains fail-closed until owner-controlled provider configuration exists.

## Primary-source review

Reviewed Stripe Billing guidance for subscriptions, Checkout, customer portal, webhooks and Entitlements. Stripe recommends asynchronous subscription lifecycle synchronization through webhooks, product-based access checks, a self-service customer portal, and persisting active entitlements internally for fast access decisions.

## Decision

ADOPT the hosted subscription/customer-management model rather than building card collection or a custom billing portal. ADAPT entitlement handling by keeping PrediBeacon's internal entitlement state authoritative for request-time feature gates while synchronizing it from authenticated provider events. REJECT price/discount/trial invention in source code: commercial prices are business configuration and must not be guessed by engineering.

## Mandatory implementation properties

1. No card data enters PrediBeacon servers; hosted checkout/provider UI handles payment collection.
2. Subscription state is synchronized asynchronously from authenticated, replay-bounded, idempotent provider events; success-page redirects alone never grant Pro access.
3. Feature access is based on explicit entitlements, not merely a plan-name string.
4. Active entitlements are persisted internally for fast, deterministic request-time checks.
5. Customer self-service uses the provider-hosted portal for payment method, invoice, plan and cancellation management.
6. Price IDs, product IDs, webhook secrets and API secrets are environment/configuration values and never committed.
7. Missing provider credentials, product mapping or verified price configuration means billing is unavailable/fail-closed; the product must never fabricate a checkout URL or price.
8. Webhook processing must be idempotent and auditable and must handle activation, renewal failure, cancellation, upgrade/downgrade and entitlement change.
9. Public APIs and UI must never expose partner commissions, revenue-share percentages, partner IDs or unrelated internal commercial economics.
10. Production activation requires provider test-mode evidence first, then owner-controlled live credentials and verified product/price mapping.

## External activation gate

Live PrediBeacon Pro billing cannot be truthfully marked VERIFIED until a billing account, live/test credentials, products/prices and webhook endpoint are configured by an authorized account owner. Until then, implementation must remain safe and non-billable rather than simulate a commercial launch.
