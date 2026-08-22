# Research source: deterministic ASGI and SQLite concurrency testing

Audience: PrediBeacon engineering
Date: 2026-08-22
Scope: reproducible CI tests for the existing FastAPI and SQLite architecture; no production load generation and no new dependency.
Assumptions: one SQLite database on a persistent local volume, WAL enabled per store connection, Python 3.13 CI.

## Direct answer

Use direct in-process ASGI tests for complete route journeys, independent SQLite connections for concurrent writer tests, and a bounded latency smoke budget as a regression signal rather than a production capacity claim.

## Evidence and reconciliation

SQLite documents that WAL permits readers and a writer to proceed concurrently, while writers still serialize. Therefore the consequential invariant is not simultaneous writer throughput; it is absence of lost updates, lock failures within the configured timeout, and correct atomic quota totals. Source: “Write-Ahead Logging,” SQLite, updated 2026, https://www.sqlite.org/wal.html.

SQLite's online backup documentation says the source is locked only during brief read periods and the resulting destination is a snapshot. This supports retaining the online backup mechanism introduced in 0.41.0 while concurrent tests exercise active WAL writes. Source: “SQLite Backup API,” SQLite, updated 2025, https://sqlite.org/backup.html.

FastAPI documents TestClient as a direct application test interface without a real socket, and recommends context-manager usage when lifespan behavior is part of the test. The release journey test intentionally excludes lifespan/external workers and tests the request graph deterministically. Source: “TestClient,” FastAPI, accessed 2026-08-22, https://fastapi.tiangolo.com/reference/testclient/; “Testing Events: lifespan and startup-shutdown,” FastAPI, accessed 2026-08-22, https://fastapi.tiangolo.com/advanced/testing-events/.

HTTPX documents ASGI transport as appropriate for calling an ASGI application directly. This supports in-process route coverage but not claims about network, TLS, Railway edge or venue latency. Source: “Transports — ASGI Transport,” HTTPX, accessed 2026-08-22, https://www.python-httpx.org/advanced/transports/.

## Limits

The 250 ms p95 CI threshold is a regression budget for 240 in-process requests on GitHub-hosted CI. It is not a production SLA, capacity forecast or substitute for authorized external load testing. The test deliberately never contacts Railway, Kalshi or Polymarket.
