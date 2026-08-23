# PrediBeacon Intelligence API

PrediBeacon's B2B product is an intelligence layer over normalized public prediction-market data. The API preserves the same safety rules as the consumer product: related markets are not equivalent contracts, reported volume is not execution quality, and market probability is not a guaranteed outcome.

All commercial endpoints require `X-PrediBeacon-API-Key`. The current Intelligence v1 routes reuse the existing `markets:read` commercial scope and daily quota accounting. Authenticated intelligence responses are `Cache-Control: no-store`.

## Commercial endpoints

### `GET /api/v1/commercial/markets`
Authenticated normalized market discovery. Supports `sort`, `category`, `venue`, `q`, and `limit`.

Scope: `markets:read`

### `GET /api/v1/commercial/history`
Authenticated probability and reported-volume history for a market.

Scope: `history:read`

### `GET /api/v1/commercial/intelligence/market`
Returns PrediBeacon Attention Score, Market Quality and Breaking Signal for one market.

The scores describe observed signal strength, completeness, freshness and recent acceleration. They are not forecasts, expected-return scores or trading advice.

Scope: `markets:read`

### `GET /api/v1/commercial/intelligence/compare`
Returns contract-equivalence status and, only after the equivalence gate passes, verified consensus probability, probability gap and agreement classification.

Lookalike contracts do not receive a consensus value.

Scope: `markets:read`

### `GET /api/v1/commercial/intelligence/execution`
Retrieves a live read-only order book and returns visible top-of-book spread, displayed depth and a bounded Execution Quality score.

Kalshi YES/NO bids are normalized into a YES-side bid/ask book. Polymarket resolves the YES outcome token and reads its CLOB book.

Execution Quality is not a fill guarantee, liquidity guarantee, profitability estimate or best-execution promise.

Scope: `markets:read`

### `GET /api/v1/commercial/intelligence/large-trades`
Reads recent public venue trades and identifies unusually large observed trade values using both an absolute threshold and a multiple of the local sample median.

Kalshi trades are not assigned a trader identity when the venue does not expose one. Polymarket wallet identifiers are retained only when supplied by the public venue feed. A large-trade signal does not imply insider knowledge, manipulation, intent, profitability or future direction.

Scope: `markets:read`

## Public intelligence primitives

- `GET /api/v1/status` — provider health, freshness and venue counts.
- `GET /api/v1/market` — normalized current market state.
- `GET /api/v1/market/history` — bounded market history.
- `GET /api/v1/market/signal` — current signal reasons.
- `GET /api/v1/market/timeline` — probability observations plus evidence events.
- `GET /api/v1/evidence` — evidence bundle metadata.
- `GET /api/v1/compare` — contract-equivalence decision gate.
- `GET /api/v1/market/related` — related markets, explicitly never equivalent.

## Reusable intelligence engine

The product layer includes bounded, testable calculations for Attention Score, Market Quality, Breaking Signal, verified-only Consensus and Verified Disagreement. The execution layer uses observable order-book spread and displayed depth. The large-trade layer uses public trade history and conservative outlier thresholds.

## What remains deliberately gated

Executable-arbitrage labels and automated best-execution routing remain gated. They require validated fees, live executable quotes, settlement/friction assumptions and jurisdiction-aware routing in addition to the data layers already implemented.
