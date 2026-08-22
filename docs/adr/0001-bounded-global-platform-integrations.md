# ADR 0001: Preserve bounded integration paths

- Status: Accepted
- Date: 2026-08-22
- Decision owners: PrediBeacon engineering
- Scope: MarketPulse technical core / PrediBeacon public product

## Context

PrediBeacon currently reads public Kalshi and Polymarket data. Future growth may add venues, licensed partner feeds, localized products, content providers, social providers, or a broader global platform. The core must not become dependent on one venue, social network, commercial agreement, or jurisdiction.

## Decision

1. Normalized market data is the core boundary. Venue-specific payloads remain inside adapters.
2. Ingestion consumes the structural `MarketFetcher` protocol, not concrete Kalshi or Polymarket classes.
3. A new venue must normalize into `NormalizedMarket`, use bounded timeout/retry behavior, and be controlled by a fail-closed feature flag and country policy.
4. AI generation remains behind provider adapters and cannot publish directly.
5. Social providers remain downstream of editorial approval, platform authorization, credentials, country policy, partner contract, and a global kill switch.
6. Partner reconciliation imports externally assigned events into the idempotent revenue ledger; it never estimates commission.
7. Storage interfaces remain local to the application boundary. A future database migration must preserve idempotency keys, audit history, immutable citations, publication versions, and rollback semantics.
8. Market Core remains operational when social, commercial routing, AI, or any single venue is unavailable.

## Required adapter acceptance tests

Every future adapter must prove:

- normalized output validation;
- timeout, retry, and bounded response behavior;
- idempotency where writes/events exist;
- no secret leakage;
- fail-closed feature flags and country rules;
- isolation: one provider failure does not erase other valid data;
- attribution and commercial values come only from written configuration or partner events.

## Consequences

This permits incremental integration without a rewrite, but intentionally rejects direct provider calls from templates, domain models, or publication code. A broader global platform may replace deployment/storage components while retaining these ports and invariants.

## Evidence

- `app/services/ingestion.py::MarketFetcher`
- `app/domain/markets.py::NormalizedMarket`
- `app/adapters/kalshi.py`
- `app/adapters/polymarket.py`
- `app/config/runtime.py::RuntimeFlags`
- `app/domain/revenue.py`
- `app/storage/revenue.py`
- architecture boundary regression tests
