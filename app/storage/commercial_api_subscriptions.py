from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_ACCESS_STATUSES = frozenset({"active", "trialing"})
_EVENT_ID = re.compile(r"^evt_[A-Za-z0-9]{6,200}$")


@dataclass(frozen=True)
class CommercialApiSubscription:
    account_id: str
    plan: str
    product_id: str
    subscription_id: str
    status: str
    valid_until: datetime | None
    updated_at: datetime


class CommercialApiSubscriptionStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS commercial_api_subscriptions (
                    account_id TEXT PRIMARY KEY,
                    plan TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    valid_until TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_commercial_api_subscription_id
                    ON commercial_api_subscriptions(subscription_id);
                CREATE TABLE IF NOT EXISTS commercial_api_billing_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> CommercialApiSubscription:
        return CommercialApiSubscription(
            account_id=row["account_id"],
            plan=row["plan"],
            product_id=row["product_id"],
            subscription_id=row["subscription_id"],
            status=row["status"],
            valid_until=datetime.fromisoformat(row["valid_until"]) if row["valid_until"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _event_id(event_id: str) -> str:
        event_id = event_id.strip()
        if not _EVENT_ID.fullmatch(event_id):
            raise ValueError("invalid provider event id")
        return event_id

    def event_seen(self, event_id: str) -> bool:
        event_id = self._event_id(event_id)
        with self._connect() as connection:
            return connection.execute(
                "SELECT 1 FROM commercial_api_billing_events WHERE event_id=?", (event_id,)
            ).fetchone() is not None

    def mark_event_once(self, event_id: str, event_type: str) -> bool:
        event_id = self._event_id(event_id)
        event_type = event_type.strip()
        if not event_type or len(event_type) > 160:
            raise ValueError("invalid provider event type")
        with self._connect() as connection:
            result = connection.execute(
                "INSERT OR IGNORE INTO commercial_api_billing_events(event_id,event_type,processed_at) VALUES (?,?,?)",
                (event_id, event_type, datetime.now(timezone.utc).isoformat()),
            )
        return result.rowcount == 1

    def upsert(
        self,
        *,
        account_id: str,
        plan: str,
        product_id: str,
        subscription_id: str,
        status: str,
        valid_until: datetime | None,
    ) -> CommercialApiSubscription:
        account_id = account_id.strip()
        plan = plan.strip().casefold()
        product_id = product_id.strip()
        subscription_id = subscription_id.strip()
        status = status.strip().casefold()
        if not account_id.startswith("acct_") or not plan or not product_id.startswith("prod_") or not subscription_id.startswith("sub_"):
            raise ValueError("invalid commercial API subscription identity")
        if not status or len(status) > 80:
            raise ValueError("invalid commercial API subscription status")
        if valid_until is not None:
            if valid_until.tzinfo is None or valid_until.utcoffset() is None:
                raise ValueError("commercial API entitlement expiry must be timezone-aware")
            valid_until = valid_until.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            collision = connection.execute(
                "SELECT account_id FROM commercial_api_subscriptions WHERE subscription_id=? AND account_id<>?",
                (subscription_id, account_id),
            ).fetchone()
            if collision is not None:
                raise ValueError("subscription is already bound to another account")
            connection.execute(
                """INSERT INTO commercial_api_subscriptions
                   (account_id,plan,product_id,subscription_id,status,valid_until,updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(account_id) DO UPDATE SET
                     plan=excluded.plan,
                     product_id=excluded.product_id,
                     subscription_id=excluded.subscription_id,
                     status=excluded.status,
                     valid_until=excluded.valid_until,
                     updated_at=excluded.updated_at""",
                (
                    account_id,
                    plan,
                    product_id,
                    subscription_id,
                    status,
                    valid_until.isoformat() if valid_until else None,
                    now.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM commercial_api_subscriptions WHERE account_id=?", (account_id,)
            ).fetchone()
        return self._record(row)

    def active_for_account(self, account_id: str, *, now: datetime | None = None) -> CommercialApiSubscription | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commercial_api_subscriptions WHERE account_id=?", (account_id.strip(),)
            ).fetchone()
        if row is None:
            return None
        item = self._record(row)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        if item.status not in _ACCESS_STATUSES:
            return None
        if item.valid_until is not None and item.valid_until <= current:
            return None
        return item

    def for_account(self, account_id: str) -> CommercialApiSubscription | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commercial_api_subscriptions WHERE account_id=?", (account_id.strip(),)
            ).fetchone()
        return self._record(row) if row else None
