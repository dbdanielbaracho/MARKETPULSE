from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_ACCOUNT_ID = re.compile(r"^apiacct_[a-f0-9]{32}$")
_CUSTOMER_ID = re.compile(r"^cus_[A-Za-z0-9]{6,200}$")
_EVENT_ID = re.compile(r"^evt_[A-Za-z0-9]{6,200}$")
_ACCESS_STATUSES = frozenset({"active", "trialing"})


@dataclass(frozen=True)
class ApiCustomerAccount:
    account_id: str
    email: str
    stripe_customer_id: str | None
    active: bool


@dataclass(frozen=True)
class ApiSubscriptionEntitlement:
    account_id: str
    plan: str
    product_id: str
    subscription_id: str
    status: str
    valid_until: datetime | None

    def grants_access(self, now: datetime | None = None) -> bool:
        if self.status.casefold() not in _ACCESS_STATUSES:
            return False
        if self.valid_until is None:
            return True
        if self.valid_until.tzinfo is None:
            return False
        return self.valid_until > (now or datetime.now(timezone.utc))


class ApiCustomerStore:
    """First-party identity and entitlement projection for Commercial API subscribers."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS commercial_api_accounts (
                    account_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    stripe_customer_id TEXT UNIQUE,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_commercial_api_accounts_customer
                    ON commercial_api_accounts(stripe_customer_id, active);
                CREATE TABLE IF NOT EXISTS commercial_api_billing_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS commercial_api_entitlements (
                    account_id TEXT PRIMARY KEY,
                    plan TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    valid_until TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES commercial_api_accounts(account_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _email(value: str) -> str:
        value = value.strip().casefold()
        if not value or len(value) > 254 or value.count("@") != 1 or any(ch.isspace() for ch in value):
            raise ValueError("invalid Commercial API account email")
        local, domain = value.split("@", 1)
        if not local or not domain or "." not in domain:
            raise ValueError("invalid Commercial API account email")
        return value

    @staticmethod
    def _account(row: sqlite3.Row) -> ApiCustomerAccount:
        return ApiCustomerAccount(row["account_id"], row["email"], row["stripe_customer_id"], bool(row["active"]))

    def create(self, *, account_id: str, email: str, raw_token: str) -> ApiCustomerAccount:
        if not _ACCOUNT_ID.fullmatch(account_id.strip()) or len(raw_token) < 32:
            raise ValueError("invalid Commercial API account credential")
        email = self._email(email)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO commercial_api_accounts(account_id,email,token_hash,stripe_customer_id,active,created_at,revoked_at) VALUES (?,?,?,NULL,1,?,NULL)",
                (account_id, email, self._hash(raw_token), datetime.now(timezone.utc).isoformat()),
            )
            row = connection.execute("SELECT * FROM commercial_api_accounts WHERE account_id=?", (account_id,)).fetchone()
        return self._account(row)

    def authorize(self, raw_token: str) -> ApiCustomerAccount:
        if not raw_token:
            raise PermissionError("missing Commercial API account token")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commercial_api_accounts WHERE token_hash=? AND active=1",
                (self._hash(raw_token),),
            ).fetchone()
        if row is None:
            raise PermissionError("invalid Commercial API account token")
        return self._account(row)

    def by_customer(self, customer_id: str) -> ApiCustomerAccount | None:
        if not _CUSTOMER_ID.fullmatch(customer_id.strip()):
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commercial_api_accounts WHERE stripe_customer_id=? AND active=1",
                (customer_id,),
            ).fetchone()
        return self._account(row) if row else None

    def bind_customer(self, account_id: str, customer_id: str) -> ApiCustomerAccount:
        account_id, customer_id = account_id.strip(), customer_id.strip()
        if not _ACCOUNT_ID.fullmatch(account_id) or not _CUSTOMER_ID.fullmatch(customer_id):
            raise ValueError("invalid Commercial API account/customer binding")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM commercial_api_accounts WHERE account_id=? AND active=1", (account_id,)).fetchone()
            if row is None:
                raise KeyError("active Commercial API account not found")
            if row["stripe_customer_id"] and row["stripe_customer_id"] != customer_id:
                raise ValueError("Commercial API account is already bound to another customer")
            collision = connection.execute(
                "SELECT account_id FROM commercial_api_accounts WHERE stripe_customer_id=? AND account_id<>?",
                (customer_id, account_id),
            ).fetchone()
            if collision:
                raise ValueError("Stripe customer is already bound to another Commercial API account")
            connection.execute("UPDATE commercial_api_accounts SET stripe_customer_id=? WHERE account_id=?", (customer_id, account_id))
            updated = connection.execute("SELECT * FROM commercial_api_accounts WHERE account_id=?", (account_id,)).fetchone()
        return self._account(updated)

    def entitlement(self, account_id: str) -> ApiSubscriptionEntitlement | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM commercial_api_entitlements WHERE account_id=?", (account_id.strip(),)).fetchone()
        if not row:
            return None
        valid_until = datetime.fromisoformat(row["valid_until"]) if row["valid_until"] else None
        return ApiSubscriptionEntitlement(row["account_id"], row["plan"], row["product_id"], row["subscription_id"], row["status"], valid_until)

    def upsert_entitlement(self, entitlement: ApiSubscriptionEntitlement) -> None:
        if not _ACCOUNT_ID.fullmatch(entitlement.account_id) or entitlement.plan not in {"starter", "pro", "business"}:
            raise ValueError("invalid Commercial API entitlement")
        if not entitlement.product_id or not entitlement.subscription_id or len(entitlement.product_id) > 255 or len(entitlement.subscription_id) > 255:
            raise ValueError("invalid Commercial API provider entitlement")
        if entitlement.valid_until is not None and entitlement.valid_until.tzinfo is None:
            raise ValueError("valid_until must be timezone-aware")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM commercial_api_accounts WHERE account_id=? AND active=1", (entitlement.account_id,)).fetchone() is None:
                raise KeyError("active Commercial API account not found")
            connection.execute(
                """INSERT INTO commercial_api_entitlements(account_id,plan,product_id,subscription_id,status,valid_until,updated_at)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET
                plan=excluded.plan,product_id=excluded.product_id,subscription_id=excluded.subscription_id,
                status=excluded.status,valid_until=excluded.valid_until,updated_at=excluded.updated_at""",
                (
                    entitlement.account_id,
                    entitlement.plan,
                    entitlement.product_id,
                    entitlement.subscription_id,
                    entitlement.status.casefold(),
                    entitlement.valid_until.isoformat() if entitlement.valid_until else None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def event_seen(self, event_id: str) -> bool:
        if not _EVENT_ID.fullmatch(event_id.strip()):
            raise ValueError("invalid Stripe event identity")
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM commercial_api_billing_events WHERE event_id=?", (event_id,)).fetchone() is not None

    def mark_event_once(self, event_id: str, event_type: str) -> bool:
        if not _EVENT_ID.fullmatch(event_id.strip()) or not event_type.strip() or len(event_type) > 160:
            raise ValueError("invalid Stripe event identity")
        with self._connect() as connection:
            result = connection.execute(
                "INSERT OR IGNORE INTO commercial_api_billing_events(event_id,event_type,processed_at) VALUES (?,?,?)",
                (event_id, event_type, datetime.now(timezone.utc).isoformat()),
            )
        return result.rowcount == 1

    def revoke(self, account_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE commercial_api_accounts SET active=0, revoked_at=? WHERE account_id=? AND active=1",
                (datetime.now(timezone.utc).isoformat(), account_id.strip()),
            )
        return result.rowcount == 1
