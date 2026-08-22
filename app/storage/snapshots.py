from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.intelligence import MarketSnapshot


class SnapshotStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_id TEXT NOT NULL,
                    probability REAL,
                    volume_usd REAL,
                    observed_at TEXT NOT NULL,
                    UNIQUE(canonical_id, observed_at)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_market_time ON market_snapshots(canonical_id, observed_at DESC)"
            )

    def append(self, item: MarketSnapshot) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO market_snapshots(canonical_id, probability, volume_usd, observed_at) VALUES (?, ?, ?, ?)",
                (item.canonical_id, item.probability, item.volume_usd, item.observed_at.isoformat()),
            )

    def previous(self, canonical_id: str, before_iso: str) -> MarketSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT canonical_id, probability, volume_usd, observed_at
                   FROM market_snapshots
                   WHERE canonical_id = ? AND observed_at < ?
                   ORDER BY observed_at DESC LIMIT 1""",
                (canonical_id, before_iso),
            ).fetchone()
        if not row:
            return None
        from datetime import datetime
        return MarketSnapshot(row[0], row[1], row[2], datetime.fromisoformat(row[3]))

    def history(self, canonical_id: str, *, hours: int = 168, limit: int = 500) -> list[MarketSnapshot]:
        """Return bounded oldest-to-newest history for public charts."""
        bounded_hours = min(max(hours, 1), 24 * 365)
        bounded_limit = min(max(limit, 2), 2000)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=bounded_hours)).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT canonical_id, probability, volume_usd, observed_at
                   FROM market_snapshots
                   WHERE canonical_id = ? AND observed_at >= ?
                   ORDER BY observed_at DESC LIMIT ?""",
                (canonical_id, cutoff, bounded_limit),
            ).fetchall()
        return [
            MarketSnapshot(row[0], row[1], row[2], datetime.fromisoformat(row[3]))
            for row in reversed(rows)
        ]
