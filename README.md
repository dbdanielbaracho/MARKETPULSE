# MarketPulse

MarketPulse is a global-ready, automation-first prediction-market intelligence and outbound distribution platform. The first active country pack is the United States; UK and Brazil are structurally prepared but disabled until policy/commercial review.

Core loop:

`venues -> ingestion -> normalization -> market intelligence -> content/discovery -> outbound attribution -> partner revenue reconciliation`

## Principles

- Automation-first: routine operation should require no manual site feeding.
- Configuration-first: legitimate variation belongs in versioned policy/configuration, not hardcode.
- Evidence-first: external claims and partner economics require sources/evidence.
- Market-equivalence safety: similar titles are not automatically equivalent contracts.
- Outbound-only in this project: MarketPulse does not custody user funds or execute trades.
- Global by architecture, local by policy.

## Local run

```bash
uvicorn app.main:app --reload
```

## Tests

```bash
pytest
```
