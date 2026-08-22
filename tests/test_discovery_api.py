from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import DiscoveryMarket, app, set_discovery_markets

client = TestClient(app)


def seed() -> None:
    now = datetime(2026, 8, 21, 20, 0, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:a", title="Fed decision", venue="kalshi", category="Economy", probability=.65, probability_change=.12, volume_usd=1000, trend_score=80, observed_at=now),
        DiscoveryMarket(canonical_id="polymarket:b", title="AI launch", venue="polymarket", category="Tech", probability=.40, probability_change=.20, volume_usd=500, trend_score=70, observed_at=now),
        DiscoveryMarket(canonical_id="kalshi:c", title="Inflation report", venue="kalshi", category="Economy", probability=.55, probability_change=None, volume_usd=9000, trend_score=60, observed_at=now),
    ])


def test_trending_sort():
    seed()
    data = client.get("/api/v1/markets?sort=trending").json()
    assert [item["canonical_id"] for item in data] == ["kalshi:a", "polymarket:b", "kalshi:c"]


def test_movers_does_not_fake_missing_change():
    seed()
    data = client.get("/api/v1/markets?sort=movers").json()
    assert data[0]["canonical_id"] == "polymarket:b"
    assert data[-1]["probability_change"] is None


def test_volume_sort_filter_and_search():
    seed()
    data = client.get("/api/v1/markets?sort=volume&category=Economy&q=inflation").json()
    assert len(data) == 1
    assert data[0]["canonical_id"] == "kalshi:c"


def test_limit_is_bounded():
    response = client.get("/api/v1/markets?limit=101")
    assert response.status_code == 422


def test_equal_scores_are_balanced_across_venues():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id=f"kalshi:{index}", title=f"Kalshi {index}", venue="kalshi", probability=.5, volume_usd=100, trend_score=30, observed_at=now)
        for index in range(3)
    ] + [
        DiscoveryMarket(canonical_id=f"polymarket:{index}", title=f"Polymarket {index}", venue="polymarket", probability=.5, volume_usd=100, trend_score=30, observed_at=now)
        for index in range(3)
    ])
    data = client.get("/api/v1/markets?sort=trending&limit=4").json()
    assert [item["venue"] for item in data] == ["kalshi", "polymarket", "kalshi", "polymarket"]


def test_venue_filter_returns_requested_platform_only():
    seed()
    data = client.get("/api/v1/markets?venue=kalshi").json()
    assert len(data) == 2
    assert {item["venue"] for item in data} == {"kalshi"}


def test_invalid_venue_is_rejected():
    assert client.get("/api/v1/markets?venue=unknown").status_code == 422


def test_comparison_never_equates_same_title_with_different_deadline():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:x", title="Will X happen?", venue="kalshi", probability=.5, volume_usd=1, trend_score=1, observed_at=now, closes_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        DiscoveryMarket(canonical_id="polymarket:x", title="Will X happen?", venue="polymarket", probability=.5, volume_usd=1, trend_score=1, observed_at=now, closes_at=datetime(2026, 9, 2, tzinfo=timezone.utc)),
    ])
    result = client.get("/api/v1/compare", params={"left_id": "kalshi:x", "right_id": "polymarket:x"})
    assert result.status_code == 200
    assert result.json()["decision"] == "not_equivalent"
    assert result.json()["equivalent_contracts"] is False


def test_comparison_fails_closed_when_rules_are_unavailable():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:y", title="Will Y happen?", venue="kalshi", probability=.5, volume_usd=1, trend_score=1, observed_at=now),
        DiscoveryMarket(canonical_id="polymarket:y", title="Will Y happen?", venue="polymarket", probability=.5, volume_usd=1, trend_score=1, observed_at=now),
    ])
    data = client.get("/api/v1/compare", params={"left_id": "kalshi:y", "right_id": "polymarket:y"}).json()
    assert data["decision"] == "insufficient_evidence"
    assert data["equivalent_contracts"] is False
    assert "require matching" in data["warning"].lower()


def test_comparison_returns_404_for_unknown_market():
    seed()
    response = client.get("/api/v1/compare", params={"left_id": "kalshi:a", "right_id": "kalshi:missing"})
    assert response.status_code == 404


def test_market_evidence_preserves_primary_venue_provenance():
    now = datetime.now(timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(
            canonical_id="kalshi:evidence",
            title="Will evidence remain attributable?",
            venue="kalshi",
            probability=.5,
            volume_usd=1,
            trend_score=1,
            observed_at=now,
            source_url="https://kalshi.com/markets/evidence",
        )
    ])
    response = client.get("/api/v1/evidence", params={"market_id": "kalshi:evidence"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["publisher_count"] == 1
    assert payload["items"][0]["publisher"] == "Kalshi"
    assert payload["items"][0]["kind"] == "venue"
    assert payload["items"][0]["freshness"] == "undated"
    assert payload["items"][0]["url"] == "https://kalshi.com/markets/evidence"


def test_market_evidence_returns_404_for_unknown_market():
    set_discovery_markets([])
    assert client.get("/api/v1/evidence", params={"market_id": "missing"}).status_code == 404


def test_market_evidence_bounds_long_venue_titles():
    now = datetime.now(timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(
            canonical_id="kalshi:long",
            title="Long combined contract " + ("selection, " * 60),
            venue="kalshi",
            probability=.5,
            volume_usd=1,
            trend_score=1,
            observed_at=now,
            source_url="https://kalshi.com/markets/long",
        )
    ])
    response = client.get("/api/v1/evidence", params={"market_id": "kalshi:long"})
    assert response.status_code == 200
    assert len(response.json()["items"][0]["title"]) <= 300


def test_market_evidence_combines_primary_and_official_sources(monkeypatch):
    import app.main as main
    from app.domain.evidence import EvidenceItem, EvidenceKind

    now = datetime.now(timezone.utc)
    market = DiscoveryMarket(
        canonical_id="kalshi:fed",
        title="Federal Reserve monetary policy decision",
        venue="kalshi",
        probability=.5,
        volume_usd=1,
        trend_score=1,
        observed_at=now,
        source_url="https://kalshi.com/markets/fed",
    )
    official = EvidenceItem(
        title="Federal Reserve issues monetary policy statement",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary.htm",
        publisher="Federal Reserve",
        kind=EvidenceKind.OFFICIAL,
        published_at=now,
        retrieved_at=now,
    )
    set_discovery_markets([market])
    monkeypatch.setattr(main, "_EXTERNAL_EVIDENCE", {market.canonical_id: [official]})
    payload = client.get("/api/v1/evidence", params={"market_id": market.canonical_id}).json()
    assert payload["publisher_count"] == 2
    assert {item["kind"] for item in payload["items"]} == {"venue", "official"}


def test_market_detail_page_and_api_are_internal():
    seed()
    page = client.get("/market", params={"market_id": "kalshi:a"})
    detail = client.get("/api/v1/market", params={"market_id": "kalshi:a"})
    assert page.status_code == 200
    assert "PREDIBEACON" in page.text
    assert "target=\"_blank\"" in page.text
    assert detail.status_code == 200
    assert detail.json()["canonical_id"] == "kalshi:a"


def test_outbound_records_click_and_preserves_internal_journey(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "revenue.db"))
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([DiscoveryMarket(
        canonical_id="kalshi:tracked",
        title="Tracked market",
        venue="kalshi",
        probability=.5,
        trend_score=70,
        observed_at=now,
        source_url="https://kalshi.com/markets/tracked",
    )])
    response = client.get(
        "/out/kalshi",
        params={"market_id": "kalshi:tracked", "campaign_id": "launch", "creator_id": "daniel", "channel": "tiktok"},
        headers={"referer": "https://predibeacon.com/market?market_id=kalshi%3Atracked"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "https://kalshi.com/markets/tracked"
    assert response.headers["x-predibeacon-click-id"]
    from app.storage.revenue import RevenueStore
    summary = RevenueStore(str(tmp_path / "revenue.db")).summary()
    assert summary["state_counts"] == {"clicked": 1}
    assert summary["click_context_count"] == 1
    assert summary["clicks_by_channel"] == {"tiktok": 1}


def test_outbound_rejects_mismatched_or_untrusted_destination(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "revenue.db"))
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    set_discovery_markets([DiscoveryMarket(
        canonical_id="kalshi:unsafe",
        title="Unsafe route",
        venue="kalshi",
        probability=.5,
        trend_score=20,
        observed_at=now,
        source_url="https://example.com/not-a-market",
    )])
    assert client.get("/out/kalshi", params={"market_id": "kalshi:unsafe"}, follow_redirects=False).status_code == 409
    assert client.get("/out/polymarket", params={"market_id": "kalshi:unsafe"}, follow_redirects=False).status_code == 404


def test_history_signal_related_and_watchlist(tmp_path, monkeypatch):
    from datetime import timedelta
    from app.services.intelligence import MarketSnapshot
    from app.storage.snapshots import SnapshotStore

    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "history.db"))
    now = datetime.now(timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:history", title="Will inflation fall this year?", venue="kalshi", category="Economy", probability=.72, probability_change=.15, volume_usd=12000, trend_score=88, observed_at=now),
        DiscoveryMarket(canonical_id="polymarket:related", title="Will inflation fall next year?", venue="polymarket", category="Economy", probability=.61, probability_change=.02, volume_usd=9000, trend_score=70, observed_at=now),
    ])
    store = SnapshotStore(str(tmp_path / "history.db"))
    store.append(MarketSnapshot("kalshi:history", .55, 8000, now - timedelta(hours=2)))
    store.append(MarketSnapshot("kalshi:history", .72, 12000, now - timedelta(hours=1)))

    history = client.get("/api/v1/market/history", params={"market_id": "kalshi:history", "hours": 24})
    signal = client.get("/api/v1/market/signal", params={"market_id": "kalshi:history"})
    related = client.get("/api/v1/market/related", params={"market_id": "kalshi:history"})
    watchlist = client.get("/watchlist")

    assert history.status_code == 200
    assert [point["probability"] for point in history.json()] == [.55, .72]
    assert signal.json()["label"] == "rising_fast"
    assert signal.json()["reasons"]
    assert related.json()[0]["canonical_id"] == "polymarket:related"
    assert watchlist.status_code == 200
    assert "Your watchlist" in watchlist.text


def test_campaign_creator_and_top_journey(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "campaigns.db"))
    token = "a" * 40
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    now = datetime.now(timezone.utc)
    set_discovery_markets([DiscoveryMarket(
        canonical_id="kalshi:creator",
        title="Creator selected market",
        venue="kalshi",
        probability=.64,
        trend_score=84,
        observed_at=now,
        source_url="https://kalshi.com/markets/creator",
    )])
    created = client.post(
        "/api/v1/admin/campaign-links",
        headers={"X-MarketPulse-Admin-Token": token},
        json={"slug": "daniel-launch-01", "market_id": "kalshi:creator", "creator_id": "daniel", "channel": "tiktok"},
    )
    assert created.status_code == 200
    assert created.json()["public_url"].endswith("/go/daniel-launch-01")

    entry = client.get("/go/daniel-launch-01", follow_redirects=False)
    assert entry.status_code == 302
    assert "market_id=kalshi%3Acreator" in entry.headers["location"]
    assert "creator_id=daniel" in entry.headers["location"]
    assert "campaign_id=daniel-launch-01" in entry.headers["location"]

    creator = client.get("/api/v1/creators/daniel/markets")
    assert creator.status_code == 200
    assert creator.json()[0]["market"]["canonical_id"] == "kalshi:creator"
    assert "Creator markets" in client.get("/creator/daniel").text
    assert "Top markets today" in client.get("/top").text


def test_campaign_slug_cannot_be_reassigned(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATABASE_PATH", str(tmp_path / "campaigns.db"))
    token = "b" * 40
    monkeypatch.setenv("MP_ADMIN_TOKEN", token)
    now = datetime.now(timezone.utc)
    set_discovery_markets([
        DiscoveryMarket(canonical_id="kalshi:a", title="A", venue="kalshi", trend_score=1, observed_at=now),
        DiscoveryMarket(canonical_id="kalshi:b", title="B", venue="kalshi", trend_score=1, observed_at=now),
    ])
    headers = {"X-MarketPulse-Admin-Token": token}
    assert client.post("/api/v1/admin/campaign-links", headers=headers, json={"slug":"fixed-link","market_id":"kalshi:a","channel":"x"}).status_code == 200
    assert client.post("/api/v1/admin/campaign-links", headers=headers, json={"slug":"fixed-link","market_id":"kalshi:b","channel":"x"}).status_code == 409


def test_alert_embed_and_installable_surfaces():
    now = datetime.now(timezone.utc)
    set_discovery_markets([DiscoveryMarket(canonical_id="kalshi:widget", title="Widget market", venue="kalshi", probability=.58, trend_score=75, observed_at=now)])
    alerts = client.get("/alerts", params={"market_id": "kalshi:widget"})
    embed = client.get("/embed/market", params={"market_id": "kalshi:widget"})
    manifest = client.get("/manifest.webmanifest")
    worker = client.get("/service-worker.js")
    market = client.get("/market", params={"market_id": "kalshi:widget"})
    home = client.get("/")

    assert alerts.status_code == 200
    assert "Market alerts" in alerts.text
    assert embed.status_code == 200
    assert "POWERED BY PREDIBEACON" in embed.text
    assert "frame-ancestors *" in embed.headers["content-security-policy"]
    assert manifest.status_code == 200
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    assert manifest.json()["name"] == "PrediBeacon"
    assert worker.status_code == 200
    assert worker.headers["service-worker-allowed"] == "/"
    assert "Create alert" in market.text
    assert "Copy embed code" in market.text
    assert 'href="/alerts"' in home.text
