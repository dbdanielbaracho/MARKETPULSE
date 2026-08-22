# PrediBeacon Performance and Concurrency Verification — 0.42.0

## Decision

PrediBeacon now enforces three complementary release gates:

1. A full first-party journey proves discovery, campaign routing, internal market detail, allowlisted outbound attribution, creator click accounting, API-key creation and atomic rotation.
2. A 60-writer SQLite test proves quota updates serialize without lost increments under WAL and the five-second busy timeout.
3. A 240-request in-process ASGI smoke test enforces a conservative 250 ms p95 regression budget.

## Why this design

SQLite WAL improves reader/writer concurrency, but concurrent writers still take turns. The test therefore verifies atomic results instead of pretending SQLite supports parallel writes ([SQLite WAL documentation](https://www.sqlite.org/wal.html)).

FastAPI's TestClient calls the application without a real socket, which makes the route journey deterministic and suitable for CI ([FastAPI TestClient](https://fastapi.tiangolo.com/reference/testclient/)). HTTPX documents the corresponding direct ASGI transport model ([HTTPX transports](https://www.python-httpx.org/advanced/transports/)).

The existing backup implementation remains based on SQLite's online backup API, which produces a consistent snapshot while limiting source locking to read intervals ([SQLite Backup API](https://sqlite.org/backup.html)).

## What the performance number means

The budget detects application-level regressions in serialization, routing and middleware. It excludes DNS, TLS, Railway routing, third-party APIs and client rendering. It is not advertised as a public SLA and never sends load to production.

## Verified CI result

GitHub Actions run 603 completed with 166 tests passed. The 240-request smoke gate measured a 3.12 ms median and 4.32 ms p95, comfortably within the 250 ms regression budget. These are in-process CI measurements, not production latency.

## Release evidence

- `tests/test_e2e_release_journey.py`
- `tests/test_sqlite_concurrency.py`
- `scripts/performance_smoke.py`
- CI executes both pytest and the explicit performance smoke gate.
