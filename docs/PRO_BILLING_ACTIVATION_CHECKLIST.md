# PrediBeacon Pro activation checklist

This checklist is intentionally fail-closed. Public capability metadata may report checkout available only when both the billing credentials and opaque Pro Product identity are configured. Actual checkout and portal routes additionally require an authenticated PrediBeacon Pro account.

## Implemented and regression-tested controls

- [x] First-party authenticated PrediBeacon Pro identity with one-time bearer token stored only as SHA-256 at rest.
- [x] Checkout derives `client_reference_id` and customer email from the authenticated server-side account; caller-selected account IDs are ignored.
- [x] Customer Portal uses only the Stripe customer ID already bound server-side to the authenticated account.
- [x] Verified `checkout.session.completed` subscription events bind one Stripe Customer to one PrediBeacon Pro account.
- [x] Verified `customer.subscription.created`, `customer.subscription.updated` and `customer.subscription.deleted` events project product/status/period state into the durable entitlement store.
- [x] Subscription events for unbound customers remain retryable rather than being marked processed.
- [x] Provider event IDs are idempotently recorded only after successful or intentional handling.
- [x] Product mismatch and non-access subscription states fail closed.
- [x] No Stripe secret, webhook secret, Price ID, Product ID, customer ID, email or internal commercial economics are returned by the public Pro package endpoint.
- [x] Public `checkout_available` remains false unless both Stripe billing configuration and the opaque Pro Product identity are present.

## External activation evidence still required

- [ ] Authorized Stripe account connected by the account owner.
- [ ] Test-mode secret key configured outside the repository.
- [ ] PrediBeacon Pro Product and recurring Price created and commercially verified by the owner.
- [ ] Test webhook endpoint configured with a dedicated signing secret.
- [ ] Purchase activation verified end to end in Stripe test mode.
- [ ] Renewal verified in test mode.
- [ ] Payment failure behavior verified with real Stripe lifecycle events.
- [ ] Cancellation/end-of-period behavior verified with real Stripe lifecycle events.
- [ ] Upgrade/downgrade behavior verified if multiple products are later introduced.
- [ ] Pricing displayed publicly only after it exactly matches owner-approved Stripe configuration.
- [ ] Live-mode credentials configured only after all test-mode evidence is green.

No repository code may invent the Product, Price, price amount, tax treatment or commercial terms in order to satisfy these external items.
