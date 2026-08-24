# MP-042 Web Push terminal boundary

Date: 2026-08-24

MP-042's remaining internal implementation gap has been closed. PrediBeacon now has durable server-originated Web Push infrastructure with explicit user opt-in and fail-closed activation.

## Primary-source decision check

Current primary-source guidance was rechecked before accepting this boundary:

- W3C Push API Working Draft (1 Dec 2025): https://www.w3.org/TR/push-api/ — the Push API is specifically designed for application-server messages that can be delivered when the web application is not active, through the application's Service Worker. PrediBeacon therefore treats a real inactive/closed foreground browser delivery as the production proof required for background push.
- IETF RFC 8292 (VAPID): https://www.rfc-editor.org/rfc/rfc8292.html — VAPID identifies the application server to a Web Push service with a signed token and application-server key. PrediBeacon therefore keeps the private signing material outside GitHub and fails closed until valid VAPID configuration exists.

Decision: ADOPT the standards' application-server/Service-Worker model and VAPID identity boundary; ADAPT it with project-specific same-origin notification navigation, hashed management credentials and transition-preserving fail-closed behavior.

## Verified internal implementation

- browser UI exposes explicit background-push opt-in and opt-out;
- subscriptions are stored durably with a one-time management token whose stored form is hashed;
- per-market alert preferences cover probability threshold, breaking movement, execution-quality weakness, unusually large observed trades, verified cross-platform gaps, new attributable evidence, and configurable closing windows;
- subscription creation validates the referenced markets before persistence;
- a server-side dispatcher evaluates active subscriptions on a bounded interval and sends Web Push only on state transitions;
- transition state is consumed only after successful delivery, preventing silent loss when delivery is disabled or fails;
- expired/gone subscriptions (HTTP 404/410) are revoked;
- VAPID configuration fails closed when absent or malformed;
- notification click navigation is constrained to same-origin destinations;
- provider delivery runs off the event loop and does not expose VAPID private material in public responses.

## Remaining external evidence

The implementation cannot be marked production-verified until real VAPID credentials are configured outside GitHub and a real browser/device subscription proves background delivery while PrediBeacon is not the foreground page.

This is an external activation/evidence dependency, not an unimplemented application feature. The correct requirement-state treatment is therefore `BLOCKED` until sanitized production evidence exists, rather than `IN_PROGRESS` or fabricated `VERIFIED`.

## Safety boundary

No VAPID private key, subscription endpoint, browser key material, user management token, partner identifier, commission percentage, revenue-share term, or internal economics may be committed to the repository or exposed in public evidence.
