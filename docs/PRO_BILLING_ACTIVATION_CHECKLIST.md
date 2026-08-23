# PrediBeacon Pro activation checklist

This checklist is intentionally fail-closed. No public billing button should be enabled until every item below has evidence.

- [ ] Authorized Stripe account connected by the account owner.
- [ ] Test-mode secret key configured outside the repository.
- [ ] PrediBeacon Pro Product and recurring Price created and commercially verified.
- [ ] Test webhook endpoint configured with a dedicated signing secret.
- [ ] First-party authenticated PrediBeacon customer identity is available.
- [ ] Checkout is bound to the authenticated internal account reference.
- [ ] Customer Portal is bound to the authenticated account's Stripe customer ID.
- [ ] Webhooks persist idempotent subscription/entitlement state.
- [ ] Purchase activation verified in test mode.
- [ ] Renewal verified in test mode.
- [ ] Payment failure does not silently retain unsupported access.
- [ ] Cancellation/end-of-period behavior verified.
- [ ] Upgrade/downgrade behavior verified if multiple products are later introduced.
- [ ] No Stripe secret, webhook secret, Price ID or internal customer/account ID is returned by public package endpoints.
- [ ] Pricing displayed publicly exactly matches owner-approved Stripe configuration.
- [ ] Live-mode credentials are configured only after all test-mode evidence is green.
