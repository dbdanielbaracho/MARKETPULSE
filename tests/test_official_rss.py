from datetime import datetime, timezone

import asyncio

import httpx
import pytest

from app.adapters.official_rss import FeedSource, OfficialFeedCollector, TrustedFeedCollector, associate, parse_feed
from app.domain.evidence import EvidenceItem, EvidenceKind


FED = FeedSource("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml")


def test_parse_rss_preserves_official_provenance_and_date():
    payload = b"""<rss><channel><item><title>Federal Reserve issues FOMC statement</title><link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20260822a.htm</link><pubDate>Sat, 22 Aug 2026 14:00:00 GMT</pubDate><description>Monetary policy decision and federal funds rate.</description></item></channel></rss>"""
    items = parse_feed(payload, FED, datetime(2026, 8, 22, 15, tzinfo=timezone.utc))
    assert len(items) == 1
    assert items[0].publisher == "Federal Reserve"
    assert items[0].kind == EvidenceKind.OFFICIAL
    assert items[0].published_at == datetime(2026, 8, 22, 14, tzinfo=timezone.utc)


def test_feed_rejects_untrusted_origin():
    with pytest.raises(ValueError):
        OfficialFeedCollector(sources=(FeedSource("Unsafe", "https://example.com/feed.xml"),))


def test_feed_discards_cross_origin_item_links():
    payload = b"""<rss><channel><item><title>Federal Reserve policy decision</title><link>https://evil.example/story</link></item></channel></rss>"""
    assert parse_feed(payload, FED, datetime.now(timezone.utc)) == []


def test_association_requires_two_meaningful_terms():
    now = datetime.now(timezone.utc)
    item = EvidenceItem(
        title="Federal Reserve issues FOMC statement",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary.htm",
        publisher="Federal Reserve",
        kind=EvidenceKind.OFFICIAL,
        published_at=now,
        retrieved_at=now,
        summary="Monetary policy decision on the federal funds rate.",
    )
    class Market:
        def __init__(self, identifier, title):
            self.canonical_id, self.title = identifier, title
    result = associate([
        Market("match", "Fed monetary policy decision"),
        Market("miss", "Who will win the election?"),
        Market("sports", "yes New York M, yes Kansas City"),
    ], [item], (FED,))
    assert list(result) == ["match"]


def test_collector_isolates_source_failures():
    good = b"""<rss><channel><item><title>Federal Reserve monetary policy</title><link>https://www.federalreserve.gov/news/a.htm</link><pubDate>Sat, 22 Aug 2026 14:00:00 GMT</pubDate></item></channel></rss>"""
    def handler(request):
        if request.url.path.endswith("press_all.xml"):
            return httpx.Response(200, content=good)
        return httpx.Response(503)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    collector = OfficialFeedCollector(
        sources=(FED, FeedSource("Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml")),
        client=client,
    )
    class Market:
        canonical_id = "fed"
        title = "Federal Reserve monetary policy"
    matched, errors = asyncio.run(collector.collect([Market()]))
    asyncio.run(client.aclose())
    assert "fed" in matched
    assert errors == ("Federal Reserve:HTTPStatusError",)


def test_news_feed_requires_allowlisted_article_host_and_three_terms():
    now = datetime.now(timezone.utc)
    source = FeedSource(
        "BBC News",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        EvidenceKind.NEWS,
        ("www.bbc.com",),
        3,
    )
    payload = f"""<rss><channel><item><title>Federal Reserve cuts interest rates</title><link>https://www.bbc.com/news/articles/rates</link><pubDate>{now.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate><description>Federal Reserve monetary policy changes.</description></item></channel></rss>""".encode()
    items = parse_feed(payload, source, now)
    class Market:
        def __init__(self, identifier, title):
            self.canonical_id, self.title = identifier, title
    result = associate([
        Market("match", "Will Federal Reserve cut interest rates?"),
        Market("weak", "Will interest rates change?"),
    ], items, (source,))
    assert list(result) == ["match"]
    assert result["match"][0].kind == EvidenceKind.NEWS


def test_stale_news_cannot_be_associated():
    now = datetime.now(timezone.utc)
    source = FeedSource("NPR", "https://feeds.npr.org/1001/rss.xml", EvidenceKind.NEWS, ("www.npr.org",), 3)
    item = EvidenceItem(
        title="Federal Reserve cuts interest rates",
        url="https://www.npr.org/sections/business/rates",
        publisher="NPR",
        kind=EvidenceKind.NEWS,
        published_at=now.replace(year=now.year - 1),
        retrieved_at=now,
        summary="Federal Reserve monetary policy decision.",
    )
    class Market:
        canonical_id = "fed"
        title = "Federal Reserve interest rates"
    assert associate([Market()], [item], (source,)) == {}


def test_news_source_rejects_non_allowlisted_article_link():
    now = datetime.now(timezone.utc)
    source = FeedSource("NPR", "https://feeds.npr.org/1001/rss.xml", EvidenceKind.NEWS, ("www.npr.org",), 3)
    payload = b"""<rss><channel><item><title>Federal Reserve interest rate decision</title><link>https://attacker.example/story</link></item></channel></rss>"""
    assert parse_feed(payload, source, now) == []
