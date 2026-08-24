from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

_SUBSCRIPTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{7,119}$")
_MARKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
_KEY = re.compile(r"^[A-Za-z0-9_-]{8,512}$")
_PUSH_HOSTS = frozenset({
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
})


@dataclass(frozen=True)
class PushSubscription:
    subscription_id: str
    endpoint: str
    p256dh: str
    auth: str
    active: bool
    created_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class PushAlert:
    subscription_id: str
    market_id: str
    preferences: dict[str, object]
    last_state: dict[str, object]
    active: bool
    updated_at: datetime


class PushSubscriptionStore:
    """Durable Web Push subscriptions with one-time management tokens hashed at rest."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    endpoint TEXT NOT NULL UNIQUE,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    active INTEGER NOT NULL CHECK(active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS push_alerts (
                    subscription_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    preferences_json TEXT NOT NULL,
                    last_state_json TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0, 1)),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(subscription_id, market_id),
                    FOREIGN KEY(subscription_id) REFERENCES push_subscriptions(subscription_id)
                );
                CREATE INDEX IF NOT EXISTS idx_push_alerts_active
                    ON push_alerts(active, subscription_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _subscription(row: sqlite3.Row) -> PushSubscription:
        return PushSubscription(
            subscription_id=row["subscription_id"],
            endpoint=row["endpoint"],
            p256dh=row["p256dh"],
            auth=row["auth"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            revoked_at=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
        )

    @staticmethod
    def _alert(row: sqlite3.Row) -> PushAlert:
        return PushAlert(
            subscription_id=row["subscription_id"],
            market_id=row["market_id"],
            preferences=json.loads(row["preferences_json"]),
            last_state=json.loads(row["last_state_json"]),
            active=bool(row["active"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _validate_subscription(subscription_id: str, endpoint: str, p256dh: str, auth: str, raw_token: str) -> None:
        if not _SUBSCRIPTION_ID.fullmatch(subscription_id.strip()):
            raise ValueError("invalid push subscription id")
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "").rstrip(".").lower()
        if parsed.scheme != "https" or host not in _PUSH_HOSTS or len(endpoint) > 2048:
            raise ValueError("push endpoint host is not allowlisted")
        if not _KEY.fullmatch(p256dh) or not _KEY.fullmatch(auth):
            raise ValueError("invalid Web Push key material")
        if len(raw_token) < 32:
            raise ValueError("invalid push management token")

    @staticmethod
    def _serialize_alert(market_id: str, preferences: dict[str, object], last_state: dict[str, object]) -> tuple[str, str, str]:
        market_id = market_id.strip()
        if not _MARKET_ID.fullmatch(market_id):
            raise ValueError("invalid market id")
        preferences_json = json.dumps(preferences, sort_keys=True, separators=(",", ":"))
        last_state_json = json.dumps(last_state, sort_keys=True, separators=(",", ":"))
        if len(preferences_json) > 4096 or len(last_state_json) > 4096:
            raise ValueError("push alert state too large")
        return market_id, preferences_json, last_state_json

    def create(self, *, subscription_id: str, endpoint: str, p256dh: str, auth: str, raw_token: str) -> PushSubscription:
        subscription_id = subscription_id.strip()
        endpoint = endpoint.strip()
        p256dh = p256dh.strip()
        auth = auth.strip()
        self._validate_subscription(subscription_id, endpoint, p256dh, auth, raw_token)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO push_subscriptions
                   (subscription_id, endpoint, p256dh, auth, token_hash, active, created_at, revoked_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, NULL)""",
                (subscription_id, endpoint, p256dh, auth, self._hash(raw_token), now),
            )
            row = connection.execute(
                "SELECT * FROM push_subscriptions WHERE subscription_id=?", (subscription_id,)
            ).fetchone()
        return self._subscription(row)

    def authorize(self, subscription_id: str, raw_token: str) -> PushSubscription:
        if not raw_token:
            raise PermissionError("missing push management token")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM push_subscriptions
                   WHERE subscription_id=? AND token_hash=? AND active=1""",
                (subscription_id.strip(), self._hash(raw_token)),
            ).fetchone()
        if row is None:
            raise PermissionError("invalid push management token")
        return self._subscription(row)

    def upsert_alert(
        self,
        *,
        subscription_id: str,
        market_id: str,
        preferences: dict[str, object],
        last_state: dict[str, object],
    ) -> PushAlert:
        market_id, preferences_json, last_state_json = self._serialize_alert(market_id, preferences, last_state)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM push_subscriptions WHERE subscription_id=? AND active=1", (subscription_id,)
            ).fetchone()
            if exists is None:
                raise KeyError("push subscription not found")
            connection.execute(
                """INSERT INTO push_alerts
                   (subscription_id, market_id, preferences_json, last_state_json, active, updated_at)
                   VALUES (?, ?, ?, ?, 1, ?)
                   ON CONFLICT(subscription_id, market_id) DO UPDATE SET
                       preferences_json=excluded.preferences_json,
                       last_state_json=excluded.last_state_json,
                       active=1,
                       updated_at=excluded.updated_at""",
                (subscription_id, market_id, preferences_json, last_state_json, now),
            )
            row = connection.execute(
                "SELECT * FROM push_alerts WHERE subscription_id=? AND market_id=?",
                (subscription_id, market_id),
            ).fetchone()
        return self._alert(row)

    def replace_alerts(
        self,
        *,
        subscription_id: str,
        alerts: list[tuple[str, dict[str, object], dict[str, object]]],
    ) -> int:
        serialized = [self._serialize_alert(market_id, preferences, last_state) for market_id, preferences, last_state in alerts]
        if len({market_id for market_id, _, _ in serialized}) != len(serialized):
            raise ValueError("duplicate market in push alert preferences")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM push_subscriptions WHERE subscription_id=? AND active=1", (subscription_id,)
            ).fetchone()
            if exists is None:
                raise KeyError("push subscription not found")
            connection.execute(
                "UPDATE push_alerts SET active=0, updated_at=? WHERE subscription_id=? AND active=1",
                (now, subscription_id),
            )
            for market_id, preferences_json, last_state_json in serialized:
                connection.execute(
                    """INSERT INTO push_alerts
                       (subscription_id, market_id, preferences_json, last_state_json, active, updated_at)
                       VALUES (?, ?, ?, ?, 1, ?)
                       ON CONFLICT(subscription_id, market_id) DO UPDATE SET
                           preferences_json=excluded.preferences_json,
                           last_state_json=excluded.last_state_json,
                           active=1,
                           updated_at=excluded.updated_at""",
                    (subscription_id, market_id, preferences_json, last_state_json, now),
                )
        return len(serialized)

    def update_state(self, subscription_id: str, market_id: str, state: dict[str, object]) -> None:
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"))
        if len(payload) > 4096:
            raise ValueError("push alert state too large")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """UPDATE push_alerts SET last_state_json=?, updated_at=?
                   WHERE subscription_id=? AND market_id=? AND active=1""",
                (payload, now, subscription_id, market_id),
            )

    def active_alerts(self, limit: int = 1000) -> list[PushAlert]:
        bounded = min(max(limit, 1), 5000)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT a.* FROM push_alerts a
                   JOIN push_subscriptions s ON s.subscription_id=a.subscription_id
                   WHERE a.active=1 AND s.active=1
                   ORDER BY a.updated_at ASC LIMIT ?""",
                (bounded,),
            ).fetchall()
        return [self._alert(row) for row in rows]

    def get_active(self, subscription_id: str) -> PushSubscription:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM push_subscriptions WHERE subscription_id=? AND active=1", (subscription_id,)
            ).fetchone()
        if row is None:
            raise KeyError("push subscription not found")
        return self._subscription(row)

    def revoke(self, subscription_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE push_subscriptions SET active=0, revoked_at=? WHERE subscription_id=? AND active=1",
                (now, subscription_id.strip()),
            )
            connection.execute(
                "UPDATE push_alerts SET active=0, updated_at=? WHERE subscription_id=?",
                (now, subscription_id.strip()),
            )
        return result.rowcount == 1
