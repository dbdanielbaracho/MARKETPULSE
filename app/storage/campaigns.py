from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,99}$")


@dataclass(frozen=True)
class CampaignLink:
    slug: str
    market_id: str
    creator_id: str | None
    channel: str
    active: bool
    created_at: datetime


class CampaignLinkStore:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS campaign_links (
                    slug TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    creator_id TEXT,
                    channel TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_campaign_creator ON campaign_links(creator_id, active)")

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _item(row: sqlite3.Row) -> CampaignLink:
        return CampaignLink(row["slug"], row["market_id"], row["creator_id"], row["channel"], bool(row["active"]), datetime.fromisoformat(row["created_at"]))

    def create(self, *, slug: str, market_id: str, creator_id: str | None, channel: str) -> CampaignLink:
        slug = slug.strip().casefold()
        channel = channel.strip().casefold()
        creator_id = creator_id.strip() if creator_id else None
        if not _SLUG.fullmatch(slug):
            raise ValueError("invalid campaign slug")
        if creator_id and not _ID.fullmatch(creator_id):
            raise ValueError("invalid creator id")
        if not _ID.fullmatch(channel):
            raise ValueError("invalid channel")
        item = CampaignLink(slug, market_id, creator_id, channel, True, datetime.now(timezone.utc))
        with self._connection() as connection:
            existing = connection.execute("SELECT * FROM campaign_links WHERE slug=?", (slug,)).fetchone()
            if existing:
                current = self._item(existing)
                if (current.market_id, current.creator_id, current.channel) != (market_id, creator_id, channel):
                    raise ValueError("campaign slug already belongs to another destination")
                return current
            connection.execute(
                "INSERT INTO campaign_links(slug, market_id, creator_id, channel, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (slug, market_id, creator_id, channel, item.created_at.isoformat()),
            )
        return item

    def get(self, slug: str) -> CampaignLink | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM campaign_links WHERE slug=? AND active=1", (slug.casefold(),)).fetchone()
        return self._item(row) if row else None

    def for_creator(self, creator_id: str, limit: int = 100) -> list[CampaignLink]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM campaign_links WHERE creator_id=? AND active=1 ORDER BY created_at DESC LIMIT ?",
                (creator_id, min(max(limit, 1), 100)),
            ).fetchall()
        return [self._item(row) for row in rows]
