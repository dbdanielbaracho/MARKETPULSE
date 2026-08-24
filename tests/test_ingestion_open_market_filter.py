import asyncio
from datetime import datetime, timedelta, timezone

from app.config.runtime import RuntimeFlags
from app.domain.markets import NormalizedMarket
from app.services.ingestion import IngestionWorker
from app.storage.snapshots import SnapshotStore


class FakeFetcher:
    def __init__(self, markets):
        self.markets = markets

    async def fetch_markets(self, limit=100):
        return list(self.markets)[:limit]


def _market(identifier: str, *, closes_at):
    return NormalizedMarket(
        venue="polymarket",
        venue_market_id=identifier,
        title=f"Market {identifier}",
        yes_probability=0.5,
        volume_usd=1000,
        closes_at=closes_at,
        source_url=f"https://polymarket.com/event/{identifier}",
        observed_at=datetime.now(timezone.utc),
    )


def test_refresh_batch_contains_only_open_timezone_valid_contracts(tmp_path):
    now = datetime.now(timezone.utc)
    fetcher = FakeFetcher([
        _market("future", closes_at=now + timedelta(hours=2)),
        _market("closed", closes_at=now - timedelta(minutes=1)),
        _market("naive", closes_at=(now + timedelta(hours=2)).replace(tzinfo=None)),
        _market("undated", closes_at=None),
    ])
    worker = IngestionWorker(
        store=SnapshotStore(tmp_path / "snapshots.db"),
        flags=RuntimeFlags(
            kalshi_ingestion=False,
            polymarket_ingestion=True,
            automated_publishing=False,
            outbound_routing=False,
            social_distribution=False,
        ),
        polymarket=fetcher,
    )

    batch = asyncio.run(worker.refresh_once())

    ids = [market.canonical_id for market in batch.markets]
    assert ids == ["polymarket:future", "polymarket:undated"]
    assert [item.canonical_id for item in batch.signals] == ids
    assert batch.errors == ()

    assert worker.store.history("polymarket:closed") == []
    assert worker.store.history("polymarket:naive") == []
