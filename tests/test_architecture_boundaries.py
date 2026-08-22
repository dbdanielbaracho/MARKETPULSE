from app.adapters.kalshi import KalshiAdapter
from app.adapters.polymarket import PolymarketAdapter
from app.services.ingestion import MarketFetcher


def test_current_venues_satisfy_runtime_market_fetcher_port():
    assert isinstance(KalshiAdapter("https://example.com"), MarketFetcher)
    assert isinstance(PolymarketAdapter("https://example.com"), MarketFetcher)


def test_future_adapter_can_implement_port_without_core_changes():
    class FutureVenue:
        async def fetch_markets(self, limit: int = 100):
            return []

    assert isinstance(FutureVenue(), MarketFetcher)
