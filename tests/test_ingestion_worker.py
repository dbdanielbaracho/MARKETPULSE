import asyncio
from datetime import datetime, timedelta, timezone

from app.config.runtime import RuntimeFlags
from app.domain.markets import NormalizedMarket
from app.services.ingestion import IngestionWorker
from app.services.retry import RetryPolicy
from app.storage.snapshots import SnapshotStore


class FakeAdapter:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = 0

    async def fetch_markets(self, limit=100):
        self.calls += 1
        value = self.batches.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def market(probability, observed_at):
    return NormalizedMarket(
        venue="kalshi",
        venue_market_id="TEST",
        title="Will the test pass?",
        yes_probability=probability,
        volume_usd=1000,
        observed_at=observed_at,
    )


def flags(kalshi=True, polymarket=False):
    return RuntimeFlags(kalshi, polymarket, False, False, False)


def test_refresh_persists_snapshots_and_computes_change(tmp_path):
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    adapter = FakeAdapter([[market(0.4, now)], [market(0.7, now + timedelta(minutes=1))]])
    worker = IngestionWorker(
        store=SnapshotStore(tmp_path / "snapshots.db"),
        flags=flags(),
        kalshi=adapter,
        retry_policy=RetryPolicy(attempts=1),
    )

    first = asyncio.run(worker.refresh_once())
    second = asyncio.run(worker.refresh_once())

    assert first.signals[0].probability_change is None
    assert second.signals[0].probability_change == 0.3
    assert second.errors == ()


def test_disabled_venue_is_not_called(tmp_path):
    adapter = FakeAdapter([[market(0.4, datetime.now(timezone.utc))]])
    worker = IngestionWorker(
        store=SnapshotStore(tmp_path / "snapshots.db"),
        flags=flags(kalshi=False),
        kalshi=adapter,
    )

    batch = asyncio.run(worker.refresh_once())

    assert adapter.calls == 0
    assert batch.markets == ()


def test_one_venue_failure_does_not_discard_other_venue(tmp_path):
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    kalshi = FakeAdapter([RuntimeError("temporary")])
    polymarket_market = NormalizedMarket(
        venue="polymarket",
        venue_market_id="P1",
        title="Independent venue",
        yes_probability=0.5,
        observed_at=now,
    )
    polymarket = FakeAdapter([[polymarket_market]])
    worker = IngestionWorker(
        store=SnapshotStore(tmp_path / "snapshots.db"),
        flags=flags(kalshi=True, polymarket=True),
        kalshi=kalshi,
        polymarket=polymarket,
        retry_policy=RetryPolicy(attempts=1),
    )

    batch = asyncio.run(worker.refresh_once())

    assert [item.canonical_id for item in batch.markets] == ["polymarket:P1"]
    assert batch.errors == ("kalshi:RuntimeError",)
