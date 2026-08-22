from __future__ import annotations

import sqlite3
from pathlib import Path


class AttributionStore:
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
                CREATE TABLE IF NOT EXISTS partner_events (
                    partner_event_id TEXT PRIMARY KEY,
                    attribution_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_partner_events_attribution ON partner_events(attribution_id, received_at DESC)"
            )

    def record_partner_event(self, partner_event_id: str, attribution_id: str, event_type: str, payload_json: str) -> bool:
        """Return True for a new event, False for an exact retry; reject ID collisions."""
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT attribution_id, event_type, payload_json FROM partner_events WHERE partner_event_id = ?",
                (partner_event_id,),
            ).fetchone()
            if existing:
                if existing == (attribution_id, event_type, payload_json):
                    return False
                raise ValueError("partner_event_id collision with different payload")
            connection.execute(
                "INSERT INTO partner_events(partner_event_id, attribution_id, event_type, payload_json) VALUES (?, ?, ?, ?)",
                (partner_event_id, attribution_id, event_type, payload_json),
            )
            return True
