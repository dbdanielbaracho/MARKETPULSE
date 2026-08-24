# PrediBeacon external activation blocks — 2026-08-24

This document separates repository-complete foundations from evidence that cannot be fabricated inside source control.

## Partner attribution and revenue (MP-021 / MP-022)

The repository already contains durable click context, signed reconciliation intake, replay bounds, idempotent partner events, guarded revenue-state transitions and audit logging. Final venue payload mapping and paid/reversed lifecycle evidence require approved Kalshi/Polymarket partner access and genuine provider payloads. Tracked in issue #143.

## PrediBeacon Pro (MP-045)

Authenticated account/customer binding, hosted Checkout/Portal integration, signed webhook verification, durable subscription projection and fail-closed entitlements are implemented. Final evidence requires approved live Stripe Product/Price configuration, production webhook configuration and a genuine subscription/cancel/expiry lifecycle. Tracked in issue #181.

## Commercial API subscriptions (MP-046)

The repository contains Commercial API subscriber identity with hashed account tokens, explicitly configured starter/pro/business catalog boundaries, hosted Stripe Checkout/Customer Portal integration, signed webhook projection, account/customer binding, persistent subscription entitlement, subscriber key issuance/list/revocation and authorization-time entitlement enforcement. Product identifiers, Price identifiers, scopes and daily quotas are configuration rather than invented code constants. Final activation requires approved Stripe Product/Price configuration, a dedicated production webhook secret and genuine checkout/subscription/cancel/expiry evidence. No live provider identifiers or commercial economics belong in GitHub.

## Legal localization (MP-033)

Locale/currency/timezone boundaries, CLDR/Babel presentation, public UI localization, RTL support and fail-closed legal-language fallback are implemented. Legal pages intentionally remain on reviewed canonical English unless a full locale is explicitly approved. Human legal/content approval is required before additional legal-language catalogs can be treated as reviewed. Tracked in issue #186.

## Background Web Push (MP-042)

The repository contains durable push subscriptions with hashed management tokens, per-market alert preferences, server-side dispatcher lifecycle, VAPID configuration boundary, service-worker push/click handling and explicit browser opt-in. Production delivery still requires externally provisioned VAPID key material; absence of keys fails closed rather than degrading into fake background delivery.

## Social distribution (MP-016–MP-019)

Repository-side provider foundations are implemented for all three previously missing channels: Instagram uses the two-step media-container/media-publish boundary with an explicitly configured Meta Graph version and Instagram user ID; WhatsApp supports approved template-message delivery only and requires an explicitly configured phone-number ID and Graph version; TikTok uses the official user-mediated Content Posting API `video.upload` inbox flow, so the user must review and complete posting inside TikTok. Telegram already has its bounded-retry Bot API adapter. All channels remain behind credential, provider-authorization, editorial, country/contract and global kill-switch gates.

Production proof still requires provider-owned accounts, credentials and approvals. TikTok is additionally policy-gated: public Direct Post requires the appropriate approved posting scope, user authorization, creator-information UX and explicit consent; unaudited clients are restricted by TikTok policy. PrediBeacon deliberately does not bypass those requirements with unattended public posting.

## Closure rule

External blocks may be terminalized as `BLOCKED` only when the registry cites the concrete dependency and repository-side safety boundary. They must never be converted to `VERIFIED` using simulated partner IDs, fabricated provider events, machine-only legal approval or fake production credentials.
