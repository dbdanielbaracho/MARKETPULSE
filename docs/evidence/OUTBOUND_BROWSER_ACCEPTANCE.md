# Outbound browser acceptance decision

Reviewed 2026-08-23 against current MDN guidance for `target`, `noopener`, and `Window.opener`.

Decision: **ADOPT with explicit defense in depth**.

PrediBeacon keeps the intelligence page open while a venue opens in a separate browsing context. The venue CTA uses `target="_blank"` and explicit `rel="noopener noreferrer"`. Modern browsers already give `_blank` implicit opener isolation, but keeping `noopener` is deliberate, visible security intent and protects compatibility assumptions. `noreferrer` additionally avoids leaking the PrediBeacon market URL to the external venue through the Referer header.

The production acceptance test does not contact or automate a third-party venue. It selects a currently routable real PrediBeacon market, verifies the live CTA and central `/out/{venue}` route, intercepts the outbound request locally in the browser, clicks the live CTA, and proves:

- PrediBeacon remains on the original market URL;
- a separate browsing context is created;
- the new context has `window.opener === null`;
- the CTA still goes through the centralized PrediBeacon outbound/attribution layer;
- no direct venue URL bypass is introduced by the mobile or market-detail UI.

Primary guidance reviewed:
- MDN `rel=noopener`: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/rel/noopener
- MDN anchor element security/privacy guidance: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/a
- MDN `Window.opener`: https://developer.mozilla.org/en-US/docs/Web/API/Window/opener
