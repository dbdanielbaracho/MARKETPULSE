# Browser notification delivery — 2026-08-23

## Decision

PrediBeacon keeps alert creation tied to an explicit user action, stores current alert preferences locally, and uses `ServiceWorkerRegistration.showNotification()` when a service worker is available. The Notification constructor remains only a guarded desktop fallback.

The active-session checker now re-evaluates when the document becomes visible because background tabs may throttle timers. This is deliberately **not** represented as durable background push: server-originated Web Push infrastructure is not enabled yet.

Smart alerts add two observable, fail-closed signal families:

- new attributable evidence, triggered only when a previously established evidence key changes;
- a user-configurable closing window (1–168 hours), triggered only when a known future close time crosses the chosen boundary.

Missing closing data or evidence never triggers an alert.

## Primary-source basis

MDN Notifications API / Using the Notifications API, reviewed 2026-08-23: notification permission should be requested in response to user interaction and notifications require a secure context.

- https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
- https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API

MDN `Notification()` constructor, reviewed 2026-08-23: on most mobile browsers the constructor throws and `ServiceWorkerRegistration.showNotification()` should be used instead.

- https://developer.mozilla.org/en-US/docs/Web/API/Notification/Notification

MDN Page Visibility API, reviewed 2026-08-23: background tabs are subject to timer throttling; visibility changes provide a reliable opportunity to refresh application state when the page becomes active again.

- https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API

## Rejected claims

- No claim that a five-minute timer executes reliably while a page is hidden.
- No claim that local browser preferences provide durable background push.
- No notification from missing or inferred data.
