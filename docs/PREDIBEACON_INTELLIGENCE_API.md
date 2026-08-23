# PrediBeacon Intelligence API

PrediBeacon's B2B product is an intelligence layer over normalized public prediction-market data. The API must preserve the same safety rules as the consumer product: related markets are not equivalent contracts, reported volume is not execution quality, and market probability is not a guaranteed outcome.

## Existing commercial endpoints

### `GET /api/v1/commercial/markets`
Authenticated normalized market discovery. Supports `sort`, `category`, `venue`, `q`, and `limit`.

Scope: `markets:read`

### `GET /api/v1/commercial/history`
Authenticated probability and reported-volume history for a market.

Scope: `history:read`

## Existing public intelligence primitives

- `GET /api/v1/status` — provider health, freshness and venue counts.
- `GET /api/v1/market` — normalized current market state.
- `GET /api/v1/market/history` — public bounded market history.
- `GET /api/v1/market/signal` — current PrediBeacon signal reasons.
- `GET /api/v1/market/timeline` — probability observations plus evidence events.
- `GET /api/v1/evidence` — evidence bundle metadata.
- `GET /api/v1/compare` — contract-equivalence decision gate.
- `GET /api/v1/market/related` — related markets, explicitly never equivalent.

## Reusable intelligence engine

The product layer now includes bounded, testable calculations for:

- Attention Score — strength of current market attention, not a forecast.
- Market Quality — completeness, freshness and usable history, not outcome confidence.
- Breaking Signal — recent acceleration from recorded probability/volume history without causal claims.
- Verified Consensus — mean probability only after the contract-equivalence gate passes.
- Verified Disagreement — probability gap classification for verified equivalent contracts.

## Execution-quality data layer

PrediBeacon now has read-only order-book adapters and a venue-neutral execution-quality model.

- Kalshi order books normalize YES bids and NO bids into a comparable YES-side bid/ask book.
- Polymarket uses the public CLOB book for an outcome token.
- Execution Quality uses observable spread and displayed depth only.
- It is not a fill guarantee, liquidity guarantee, expected-return score, or best-execution claim.

This layer is intentionally separate from aggregate reported volume.

## Large-trade data layer

PrediBeacon now has public trade-history adapters for both supported venues and a conservative large-trade detector.

- A signal must clear both an absolute observed-value threshold and a multiple of the local sample median.
- Kalshi data is not assigned a trader identity when the venue does not expose one.
- A Polymarket wallet identifier is retained only when the public venue feed supplies it.
- Large-trade signals do not imply insider knowledge, manipulation, causation, profitability or future direction.

## Consumer intelligence products

### Smart Movers
Ranks movement using probability change, attention, reported activity, freshness and time-to-close. It is more selective than sorting by absolute percentage move alone.

### Breaking Markets
Uses stored history to identify fresh acceleration in probability and reported volume.

### Market Quality
Scores completeness and reliability of the displayed signal using data availability, recency and usable history.

### Verified Consensus
Computes a simple mean only after two contracts pass the equivalence gate. The consumer product labels it as a market consensus, not a statistical forecast.

### Verified Disagreement
Ranks the probability gap between verified equivalent contracts. Lookalike contracts never enter this ranking.

### Venue Activity Comparison
Compares reported volume for verified equivalent contracts. This remains an activity proxy and is separate from the new execution-quality layer.

## Next product wiring

The next commercial and consumer surfaces should expose the reusable intelligence engine, execution-quality snapshots and large-trade signals behind the existing API-key/rate-limit infrastructure. These features should be wired only after their data is available for the selected market and should fail closed when an order book, trade sample, or verified equivalent contract is unavailable.

Executable-arbitrage labels and automated best-execution routing remain gated. They require validated fees, venue-specific settlement/friction assumptions, live executable quotes and jurisdiction-aware routing in addition to the data layers above.
