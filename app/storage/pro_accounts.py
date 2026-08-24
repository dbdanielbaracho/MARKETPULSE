from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_ACCOUNT_ID = re.compile(r"^acct_[A-Za-z0-9_-]{16,96}$")
_STRIPE_CUSTOMER = re.compile(r"^cus_[A-Za-z0-9]{6,200}$")
_EVENT_ID = re.compile(r"^evt_[A-Za-z0-9]{6,200}$")


@dataclass(frozen=True)
class ProAccount:
    account_id: str
    email: str
    stripe_customer_id: str | None
    active: bool
    created_at: datetime
    revoked_at: datetime | None


class ProAccountStore:
    """First-party Pro identity boundary with bearer credentials hashed at rest."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pro_accounts (
                    account_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    stripe_customer_id TEXT UNIQUE,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_pro_accounts_customer
                    ON pro_accounts(stripe_customer_id, active);
                CREATE TABLE IF NOT EXISTS pro_billing_events (
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
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _email(value: str) -> str:
        value = value.strip().casefold()
        if not value or len(value) > 254 or value.count("@") != 1 or any(ch.isspace() for ch in value):
            raise ValueError("invalid Pro account email")
        local, domain = value.split("@", 1)
        if not local or not domain or "." not in domain:
            raise ValueError("invalid Pro account email")
        return value

    @staticmethod
    def _account(row: sqlite3.Row) -> ProAccount:
        return ProAccount(
            account_id=row["account_id"],
            email=row["email"],
            stripe_customer_id=row["stripe_customer_id"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            revoked_at=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
        )

    @staticmethod
    def _validate_event(event_id: str, event_type: str | None = None) -> tuple[str, str | None]:
        event_id = event_id.strip()
        if not _EVENT_ID.fullmatch(event_id):
            raise ValueError("invalid Stripe event identity")
        if event_type is not None:
            event_type = event_type.strip()
            if not event_type or len(event_type) > 160:
                raise ValueError("invalid Stripe event identity")
        return event_id, event_type

    def create(self, *, account_id: str, email: str, raw_token: str) -> ProAccount:
        account_id = account_id.strip()
        if not _ACCOUNT_ID.fullmatch(account_id):
            raise ValueError("invalid Pro account id")
        email = self._email(email)
        if len(raw_token) < 32:
            raise ValueError("invalid Pro account token")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO pro_accounts
                   (account_id,email,token_hash,stripe_customer_id,active,created_at,revoked_at)
                   VALUES (?,?,?,NULL,1,?,NULL)""",
                (account_id, email, self._hash(raw_token), now),
            )
            row = connection.execute("SELECT * FROM pro_accounts WHERE account_id=?", (account_id,)).fetchone()
        return self._account(row)

    def authorize(self, raw_token: str) -> ProAccount:
        if not raw_token:
            raise PermissionError("missing Pro account token")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pro_accounts WHERE token_hash=? AND active=1",
                (self._hash(raw_token),),
            ).fetchone()
        if row is None:
            raise PermissionError("invalid Pro account token")
        return self._account(row)

    def by_id(self, account_id: str) -> ProAccount | None:
        account_id = account_id.strip()
        if not _ACCOUNT_ID.fullmatch(account_id):
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM pro_accounts WHERE account_id=? AND active=1", (account_id,)).fetchone()
        return self._account(row) if row else None

    def by_customer(self, stripe_customer_id: str) -> ProAccount | None:
        stripe_customer_id = stripe_customer_id.strip()
        if not _STRIPE_CUSTOMER.fullmatch(stripe_customer_id):
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pro_accounts WHERE stripe_customer_id=? AND active=1",
                (stripe_customer_id,),
            ).fetchone()
        return self._account(row) if row else None

    def bind_customer(self, account_id: str, stripe_customer_id: str) -> ProAccount:
        account_id = account_id.strip()
        stripe_customer_id = stripe_customer_id.strip()
        if not _ACCOUNT_ID.fullmatch(account_id) or not _STRIPE_CUSTOMER.fullmatch(stripe_customer_id):
            raise ValueError("invalid Pro account/customer binding")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM pro_accounts WHERE account_id=? AND active=1", (account_id,)).fetchone()
            if row is None:
                raise KeyError("active Pro account not found")
            existing = row["stripe_customer_id"]
            if existing and existing != stripe_customer_id:
                raise ValueError("Pro account is already bound to a different customer")
            collision = connection.execute(
                "SELECT account_id FROM pro_accounts WHERE stripe_customer_id=? AND account_id<>?",
                (stripe_customer_id, account_id),
            ).fetchone()
            if collision is not None:
                raise ValueError("Stripe customer is already bound to another Pro account")
            connection.execute(
                "UPDATE pro_accounts SET stripe_customer_id=? WHERE account_id=?",
                (stripe_customer_id, account_id),
            )
            updated = connection.execute("SELECT * FROM pro_accounts WHERE account_id=?", (account_id,)).fetchone()
        return self._account(updated)

    def event_seen(self, event_id: str) -> bool:
        event_id, _ = self._validate_event(event_id)
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM pro_billing_events WHERE event_id=?", (event_id,)).fetchone() is not None

    def mark_event_once(self, event_id: str, event_type: str) -> bool:
        event_id, event_type = self._validate_event(event_id, event_type)
        with self._connect() as connection:
            result = connection.execute(
                "INSERT OR IGNORE INTO pro_billing_events(event_id,event_type,processed_at) VALUES (?,?,?)",
                (event_id, event_type, datetime.now(timezone.utc).isoformat()),
            )
        return result.rowcount == 1

    def revoke(self, account_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE pro_accounts SET active=0, revoked_at=? WHERE account_id=? AND active=1",
                (now, account_id.strip()),
            )
        return result.rowcount == 1
