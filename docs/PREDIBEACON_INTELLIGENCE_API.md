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

## Intelligence products built from these primitives

### Smart Movers
Ranks movement using probability change, attention, reported activity, freshness and time-to-close. It is more selective than sorting by absolute percentage move alone.

### Breaking Markets
Uses stored history to identify fresh acceleration in probability and reported volume. It deliberately does not claim that a whale caused the move because PrediBeacon does not yet ingest sufficient trade-level identity data to prove that.

### Market Quality
Scores completeness and reliability of the displayed signal using data availability, recency and usable history. Market Quality is not outcome confidence.

### Verified Consensus
Computes a simple mean only after two contracts pass the equivalence gate. The consumer product labels it as a market consensus, not a statistical forecast.

### Verified Disagreement
Ranks the probability gap between verified equivalent contracts. Lookalike contracts never enter this ranking.

### Venue Activity Comparison
Compares reported volume for verified equivalent contracts. This is an activity proxy only and does not assert better price, spread, depth, fees or execution.

## Next data adapters required for higher-order products

The architecture should accept future venue adapters without changing the consumer intelligence model. New providers must normalize to the same canonical market representation and pass equivalent-contract verification before being included in consensus or disagreement products.

Trade-level or order-book adapters are required before PrediBeacon can truthfully expose products such as large-trader detection, spread/depth quality, executable arbitrage, or best-execution routing. Those labels must not be used based on aggregate volume alone.
