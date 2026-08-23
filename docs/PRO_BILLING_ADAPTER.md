# PrediBeacon Pro billing adapter

## Research decision

Primary-source review used Stripe Billing/Checkout, Customer Portal, Entitlements and the current Stripe Python package. The project **adopts** Stripe-hosted Checkout for subscription payment collection and Stripe-hosted Customer Portal for self-service. It **adapts** provider events into PrediBeacon's own entitlement state and **rejects** any public route that trusts an arbitrary account/customer identifier before a first-party authenticated account boundary exists.

The Python dependency is pinned to the current stable Stripe 15.4.0 release reviewed on 2026-08-23. Dependency upgrades remain normal reviewed changes rather than floating production updates.

## Implemented now

- fail-closed environment validation for secret key, Pro price mapping, webhook secret and HTTPS public origin;
- hosted subscription Checkout session adapter;
- hosted Customer Portal session adapter;
- Stripe webhook signature-verification boundary;
- strict provider redirect host validation;
- internal `client_reference_id` reconciliation boundary;
- no public Checkout/Portal endpoint yet, intentionally, because a public caller must never be able to choose another account/customer identity;
- regression tests proving secrets, price IDs, internal account references and commercial economics are not placed in user-facing redirect URLs.

## Remaining external activation boundary

Live/self-service billing requires all of the following before public billing routes can be enabled:

1. authorized Stripe account connection and test/live credentials;
2. verified PrediBeacon Pro Product/Price configuration (engineering must not invent the price);
3. configured webhook endpoint and secret;
4. authenticated PrediBeacon customer/account identity so checkout and portal sessions are created only for the signed-in account;
5. test-mode lifecycle evidence for purchase, renewal, payment failure, cancellation, upgrade/downgrade and entitlement change.

Until those conditions exist, billing remains intentionally unavailable rather than insecure or simulated.
