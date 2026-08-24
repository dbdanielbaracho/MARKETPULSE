# MP-024 production mobile full-journey acceptance

This evidence note records the acceptance boundary added for MP-024.

The dedicated production mobile smoke now proves the PrediBeacon-owned mobile journey from the public home page to a real internal market page and then to the safe external CTA. The test selects a currently routable production market from the public API, verifies that its home-card internal link is visible and touch-sized, taps into the canonical PrediBeacon market page, verifies no material horizontal overflow, verifies the external CTA is touch-sized and uses `_blank` with `noopener noreferrer`, intercepts the outbound route before third-party navigation, and proves the original PrediBeacon page remains open with a null opener in the new context.

This acceptance intentionally does not depend on Kalshi or Polymarket page uptime. It verifies only the browser semantics and responsive journey controlled by PrediBeacon.

MP-024 remains IN_PROGRESS until this test has a post-merge production pass. A green in-process or PR-only test is not sufficient for terminal verification.
