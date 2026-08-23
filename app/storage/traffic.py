from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


class TrafficStore:
    """Aggregate first-party page traffic without visitor identifiers, IPs or user agents."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS traffic_daily (
                    day TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    market_id TEXT NOT NULL DEFAULT '',
                    channel TEXT NOT NULL DEFAULT '',
                    views INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(day, surface, market_id, channel)
                );
                CREATE INDEX IF NOT EXISTS idx_traffic_daily_day ON traffic_daily(day);
                CREATE INDEX IF NOT EXISTS idx_traffic_daily_surface ON traffic_daily(surface);
                """
            )

    @staticmethod
    def _clean(value: str | None, *, maximum: int) -> str:
        if not value:
            return ""
        cleaned = "".join(ch for ch in value.strip() if ch.isalnum() or ch in "-_.:")
        return cleaned[:maximum]

    def record_view(
        self,
        *,
        surface: str,
        market_id: str | None = None,
        channel: str | None = None,
        observed_at: datetime | None = None,
    ) -> None:
        safe_surface = self._clean(surface, maximum=40)
        if not safe_surface:
            raise ValueError("surface is required")
        safe_market = self._clean(market_id, maximum=200)
        safe_channel = self._clean(channel, maximum=100)
        current = observed_at or datetime.now(timezone.utc)
        day = current.astimezone(timezone.utc).date().isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO traffic_daily(day, surface, market_id, channel, views)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(day, surface, market_id, channel)
                DO UPDATE SET views = views + 1
                """,
                (day, safe_surface, safe_market, safe_channel),
            )

    def summary(self, *, days: int = 30, top_markets: int = 20) -> dict[str, object]:
        if days < 1 or days > 365:
            raise ValueError("days must be between 1 and 365")
        if top_markets < 1 or top_markets > 100:
            raise ValueError("top_markets must be between 1 and 100")
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        with self._connection() as connection:
            total = connection.execute(
                "SELECT COALESCE(SUM(views), 0) AS total FROM traffic_daily WHERE day >= ?",
                (start,),
            ).fetchone()["total"]
            by_surface = {
                row["surface"]: row["views"]
                for row in connection.execute(
                    """SELECT surface, SUM(views) AS views FROM traffic_daily
                    WHERE day >= ? GROUP BY surface ORDER BY views DESC""",
                    (start,),
                )
            }
            by_channel = {
                (row["channel"] or "direct"): row["views"]
                for row in connection.execute(
                    """SELECT channel, SUM(views) AS views FROM traffic_daily
                    WHERE day >= ? GROUP BY channel ORDER BY views DESC""",
                    (start,),
                )
            }
            market_rows = connection.execute(
                """SELECT market_id, SUM(views) AS views FROM traffic_daily
                WHERE day >= ? AND market_id <> ''
                GROUP BY market_id ORDER BY views DESC LIMIT ?""",
                (start, top_markets),
            ).fetchall()
            daily = [
                {"day": row["day"], "views": row["views"]}
                for row in connection.execute(
                    """SELECT day, SUM(views) AS views FROM traffic_daily
                    WHERE day >= ? GROUP BY day ORDER BY day""",
                    (start,),
                )
            ]
        return {
            "window_days": days,
            "page_views": int(total or 0),
            "views_by_surface": by_surface,
            "views_by_channel": by_channel,
            "top_market_views": [dict(row) for row in market_rows],
            "daily": daily,
            "privacy": "Aggregate counts only; no visitor identifiers, IP addresses or user agents are stored.",
        }
