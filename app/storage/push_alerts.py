from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PushSubscriptionRecord:
    subscription_id: str
    endpoint: str
    p256dh: str
    auth: str
    active: bool


class PushAlertStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    manage_token_hash TEXT NOT NULL,
                    endpoint TEXT NOT NULL UNIQUE,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS push_alert_rules (
                    rule_id TEXT PRIMARY KEY,
                    subscription_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    threshold REAL,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(subscription_id) REFERENCES push_subscriptions(subscription_id)
                );
                CREATE INDEX IF NOT EXISTS idx_push_rules_active ON push_alert_rules(active, subscription_id);
                """
            )

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def upsert_subscription(self, *, subscription_id: str, manage_token: str, endpoint: str, p256dh: str, auth: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO push_subscriptions(subscription_id, manage_token_hash, endpoint, p256dh, auth, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(endpoint) DO UPDATE SET
                    subscription_id=excluded.subscription_id,
                    manage_token_hash=excluded.manage_token_hash,
                    p256dh=excluded.p256dh,
                    auth=excluded.auth,
                    active=1,
                    updated_at=excluded.updated_at
                """,
                (subscription_id, self.token_hash(manage_token), endpoint, p256dh, auth, now, now),
            )

    def authorize(self, subscription_id: str, manage_token: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manage_token_hash, active FROM push_subscriptions WHERE subscription_id=?",
                (subscription_id,),
            ).fetchone()
        return bool(row and row[1] and row[0] == self.token_hash(manage_token))

    def add_rule(self, *, rule_id: str, subscription_id: str, market_id: str, rule_type: str, threshold: float | None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO push_alert_rules(rule_id, subscription_id, market_id, rule_type, threshold, state_json, active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, '{}', 1, ?, ?)""",
                (rule_id, subscription_id, market_id, rule_type, threshold, now, now),
            )

    def list_rules(self, subscription_id: str) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT rule_id, market_id, rule_type, threshold, state_json
                   FROM push_alert_rules WHERE subscription_id=? AND active=1 ORDER BY created_at""",
                (subscription_id,),
            ).fetchall()
        return [
            {"rule_id": row[0], "market_id": row[1], "rule_type": row[2], "threshold": row[3], "state": json.loads(row[4] or "{}")}
            for row in rows
        ]

    def update_rule_state(self, rule_id: str, state: dict[str, object]) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE push_alert_rules SET state_json=?, updated_at=? WHERE rule_id=?",
                (json.dumps(state, separators=(",", ":"), sort_keys=True), datetime.now(timezone.utc).isoformat(), rule_id),
            )

    def deactivate_rule(self, *, rule_id: str, subscription_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE push_alert_rules SET active=0, updated_at=? WHERE rule_id=? AND subscription_id=? AND active=1",
                (datetime.now(timezone.utc).isoformat(), rule_id, subscription_id),
            )
            return cursor.rowcount == 1

    def deactivate_subscription(self, subscription_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE push_subscriptions SET active=0, updated_at=? WHERE subscription_id=?", (datetime.now(timezone.utc).isoformat(), subscription_id))
            connection.execute("UPDATE push_alert_rules SET active=0, updated_at=? WHERE subscription_id=?", (datetime.now(timezone.utc).isoformat(), subscription_id))

    def active_rule_targets(self) -> list[tuple[dict[str, object], PushSubscriptionRecord]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT r.rule_id, r.market_id, r.rule_type, r.threshold, r.state_json,
                          s.subscription_id, s.endpoint, s.p256dh, s.auth, s.active
                   FROM push_alert_rules r JOIN push_subscriptions s ON s.subscription_id=r.subscription_id
                   WHERE r.active=1 AND s.active=1"""
            ).fetchall()
        output = []
        for row in rows:
            rule = {"rule_id": row[0], "market_id": row[1], "rule_type": row[2], "threshold": row[3], "state": json.loads(row[4] or "{}")}
            sub = PushSubscriptionRecord(row[5], row[6], row[7], row[8], bool(row[9]))
            output.append((rule, sub))
        return output
