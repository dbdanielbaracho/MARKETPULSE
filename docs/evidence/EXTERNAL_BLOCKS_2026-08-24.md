# PrediBeacon external activation blocks — 2026-08-24

This document separates repository-complete foundations from evidence that cannot be fabricated inside source control.

## Partner attribution and revenue (MP-021 / MP-022)

The repository already contains durable click context, signed reconciliation intake, replay bounds, idempotent partner events, guarded revenue-state transitions and audit logging. Final venue payload mapping and paid/reversed lifecycle evidence require approved Kalshi/Polymarket partner access and genuine provider payloads. Tracked in issue #143.

## PrediBeacon Pro (MP-045)

Authenticated account/customer binding, hosted Checkout/Portal integration, signed webhook verification, durable subscription projection and fail-closed entitlements are implemented. Final evidence requires approved live Stripe Product/Price configuration, production webhook configuration and a genuine subscription/cancel/expiry lifecycle. Tracked in issue #181.

## Legal localization (MP-033)

Locale/currency/timezone boundaries, CLDR/Babel presentation, public UI localization, RTL support and fail-closed legal-language fallback are implemented. Legal pages intentionally remain on reviewed canonical English unless a full locale is explicitly approved. Human legal/content approval is required before additional legal-language catalogs can be treated as reviewed. Tracked in issue #186.

## Background Web Push (MP-042)

The repository contains durable push subscriptions with hashed management tokens, per-market alert preferences, server-side dispatcher lifecycle, VAPID configuration boundary, service-worker push/click handling and explicit browser opt-in. Production delivery still requires externally provisioned VAPID key material; absence of keys fails closed rather than degrading into fake background delivery.

## Social distribution (MP-016–MP-019)

These channels require provider-owned accounts, credentials and/or policy approval. Telegram has a bounded-retry Bot API adapter but needs a real bot/chat configuration and production evidence. Instagram, TikTok and WhatsApp must not be activated from guessed credentials or invented provider approval.

TikTok is additionally policy-gated: the current Content Posting API requires an approved posting scope and user authorization; unaudited clients are restricted to private visibility, and Direct Post requires creator information plus explicit posting UX/consent. PrediBeacon must not implement unattended public posting in a way that bypasses those provider requirements.

## Closure rule

External blocks may be terminalized as `BLOCKED` only when the registry cites the concrete dependency and repository-side safety boundary. They must never be converted to `VERIFIED` using simulated partner IDs, fabricated provider events, machine-only legal approval or fake production credentials.
