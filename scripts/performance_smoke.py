"""Bounded in-process ASGI performance smoke test; never targets production."""
from __future__ import annotations

import statistics
import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import DiscoveryMarket, app, set_discovery_markets


def main() -> None:
    set_discovery_markets([
        DiscoveryMarket(
            canonical_id=f"kalshi:perf:{index}",
            title=f"Will controlled performance market {index} resolve yes?",
            venue="kalshi" if index % 2 == 0 else "polymarket",
            category="Performance",
            probability=0.5,
            probability_change=0.01,
            volume_usd=1000 + index,
            trend_score=50 + index % 50,
            observed_at=datetime.now(timezone.utc),
        )
        for index in range(100)
    ])
    client = TestClient(app)
    samples: list[float] = []
    try:
        for index in range(240):
            path = "/api/v1/status" if index % 3 == 0 else "/api/v1/markets?limit=100"
            started = time.perf_counter()
            response = client.get(path)
            samples.append((time.perf_counter() - started) * 1000)
            if response.status_code != 200:
                raise SystemExit(f"performance smoke request failed: {response.status_code}")
    finally:
        set_discovery_markets([])
    ordered = sorted(samples)
    p95 = ordered[max(0, int(len(ordered) * .95) - 1)]
    median = statistics.median(samples)
    print(f"requests={len(samples)} median_ms={median:.2f} p95_ms={p95:.2f}")
    if p95 > 250:
        raise SystemExit(f"in-process p95 budget exceeded: {p95:.2f}ms > 250ms")


if __name__ == "__main__":
    main()
