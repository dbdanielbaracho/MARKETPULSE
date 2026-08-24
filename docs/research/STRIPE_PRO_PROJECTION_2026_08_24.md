# Stripe subscription projection decision — 2026-08-24

Primary sources reviewed:

- https://docs.stripe.com/billing/subscriptions/webhooks
- https://docs.stripe.com/billing/subscriptions/build-subscriptions?api-integration=checkout&payment-ui=elements
- https://docs.stripe.com/api/subscriptions/object

Adopted:

1. Subscription state is asynchronous and is projected from verified webhook events rather than inferred from a checkout redirect.
2. PrediBeacon handles `customer.subscription.created`, `customer.subscription.updated` and `customer.subscription.deleted` for access lifecycle.
3. Product identity, not a displayed price, is the entitlement allowlist boundary. Price can change without changing the authorized Pro product.
4. Stripe Customer ID is stored only server-side and bound to an authenticated first-party account. Checkout uses an internal `client_reference_id`; the customer binding is accepted only from a verified `checkout.session.completed` subscription event.
5. Subscription ID, status and bounded period-end data are stored in the existing entitlement projection. Non-access statuses remain fail-closed.
6. Provider event IDs are deduplicated only after successful or intentionally ignored processing so malformed/unbound events remain retryable.
7. Because webhook event order is not assumed, a subscription event received before the Customer binding returns non-success and remains retryable.

Rejected:

- trusting query-string account IDs;
- granting Pro access from checkout success-page navigation;
- exposing Stripe customer/product/price IDs through the public Pro package endpoint;
- treating credentials or a configured price as evidence that a subscription is active.

Production activation still requires owner-controlled Stripe product/price/webhook credentials and a real lifecycle test. Those external values are never invented by the codebase.
