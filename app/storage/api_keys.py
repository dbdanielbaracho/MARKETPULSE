from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ApiPrincipal:
    key_id: str
    name: str
    plan: str
    scopes: tuple[str, ...]
    daily_limit: int
    usage_today: int
    owner_account_id: str | None = None


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    name: str
    plan: str
    scopes: tuple[str, ...]
    daily_limit: int
    active: bool
    created_at: datetime
    revoked_at: datetime | None
    owner_account_id: str | None = None


class ApiKeyStore:
    """Hashed commercial API credentials with atomic daily quota accounting."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS commercial_api_keys (
                    key_id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    daily_limit INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT,
                    owner_account_id TEXT
                );
                CREATE TABLE IF NOT EXISTS commercial_api_usage (
                    key_id TEXT NOT NULL,
                    usage_date TEXT NOT NULL,
                    request_count INTEGER NOT NULL,
                    PRIMARY KEY(key_id, usage_date),
                    FOREIGN KEY(key_id) REFERENCES commercial_api_keys(key_id)
                );
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(commercial_api_keys)")}
            if "revoked_at" not in columns:
                connection.execute("ALTER TABLE commercial_api_keys ADD COLUMN revoked_at TEXT")
            if "owner_account_id" not in columns:
                connection.execute("ALTER TABLE commercial_api_keys ADD COLUMN owner_account_id TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_commercial_api_keys_owner ON commercial_api_keys(owner_account_id, active)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(
        self,
        *,
        key_id: str,
        raw_token: str,
        name: str,
        plan: str,
        scopes: tuple[str, ...],
        daily_limit: int,
        owner_account_id: str | None = None,
    ) -> None:
        if not key_id or not raw_token or len(raw_token) < 32:
            raise ValueError("invalid API credential")
        if not scopes or any(scope not in {"markets:read", "history:read"} for scope in scopes):
            raise ValueError("invalid API scope")
        if daily_limit < 1 or daily_limit > 1_000_000:
            raise ValueError("daily limit out of bounds")
        if owner_account_id is not None and (not owner_account_id.startswith("apiacct_") or len(owner_account_id) > 100):
            raise ValueError("invalid API key owner")
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO commercial_api_keys
                (key_id, token_hash, name, plan, scopes, daily_limit, active, created_at, owner_account_id)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (key_id, self._hash(raw_token), name[:100], plan[:50], ",".join(sorted(set(scopes))), daily_limit, datetime.now(timezone.utc).isoformat(), owner_account_id),
            )

    @staticmethod
    def _owned_entitlement_allows(connection: sqlite3.Connection, row: sqlite3.Row) -> bool:
        owner = row["owner_account_id"]
        if not owner:
            return True
        entitlement = connection.execute(
            """SELECT e.plan,e.product_id,e.status,e.valid_until
            FROM commercial_api_entitlements e
            JOIN commercial_api_accounts a ON a.account_id=e.account_id
            WHERE e.account_id=? AND a.active=1""",
            (owner,),
        ).fetchone()
        if entitlement is None or entitlement["plan"] != row["plan"] or entitlement["status"].casefold() not in {"active", "trialing"}:
            return False
        configured_product = os.getenv(f"MP_API_{row['plan'].upper()}_PRODUCT_ID", "").strip()
        if not configured_product or configured_product != entitlement["product_id"]:
            return False
        if entitlement["valid_until"]:
            try:
                valid_until = datetime.fromisoformat(entitlement["valid_until"])
            except ValueError:
                return False
            if valid_until.tzinfo is None or valid_until <= datetime.now(timezone.utc):
                return False
        return True

    def authorize(self, raw_token: str, required_scope: str) -> ApiPrincipal:
        if not raw_token:
            raise PermissionError("missing API key")
        today = datetime.now(timezone.utc).date().isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM commercial_api_keys WHERE token_hash=? AND active=1",
                (self._hash(raw_token),),
            ).fetchone()
            if row is None:
                raise PermissionError("invalid API key")
            if not self._owned_entitlement_allows(connection, row):
                raise PermissionError("Commercial API subscription is not active")
            scopes = tuple(filter(None, row["scopes"].split(",")))
            if required_scope not in scopes:
                raise PermissionError("scope not granted")
            usage = connection.execute(
                "SELECT request_count FROM commercial_api_usage WHERE key_id=? AND usage_date=?",
                (row["key_id"], today),
            ).fetchone()
            count = usage["request_count"] if usage else 0
            if count >= row["daily_limit"]:
                raise OverflowError("daily API quota exceeded")
            next_count = count + 1
            connection.execute(
                """INSERT INTO commercial_api_usage(key_id, usage_date, request_count)
                VALUES (?, ?, ?)
                ON CONFLICT(key_id, usage_date) DO UPDATE SET request_count=excluded.request_count""",
                (row["key_id"], today, next_count),
            )
        return ApiPrincipal(row["key_id"], row["name"], row["plan"], scopes, row["daily_limit"], next_count, row["owner_account_id"])

    @staticmethod
    def _record(row: sqlite3.Row) -> ApiKeyRecord:
        return ApiKeyRecord(
            key_id=row["key_id"],
            name=row["name"],
            plan=row["plan"],
            scopes=tuple(filter(None, row["scopes"].split(","))),
            daily_limit=row["daily_limit"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            revoked_at=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
            owner_account_id=row["owner_account_id"],
        )

    def list_keys(self, limit: int = 100) -> list[ApiKeyRecord]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit out of bounds")
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM commercial_api_keys ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._record(row) for row in rows]

    def list_owner_keys(self, owner_account_id: str, limit: int = 100) -> list[ApiKeyRecord]:
        if limit < 1 or limit > 100 or not owner_account_id.startswith("apiacct_"):
            raise ValueError("invalid owner key query")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM commercial_api_keys WHERE owner_account_id=? ORDER BY created_at DESC LIMIT ?",
                (owner_account_id, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def revoke(self, key_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            result = connection.execute("UPDATE commercial_api_keys SET active=0, revoked_at=? WHERE key_id=? AND active=1", (now, key_id))
        return result.rowcount == 1

    def revoke_owned(self, key_id: str, owner_account_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE commercial_api_keys SET active=0, revoked_at=? WHERE key_id=? AND owner_account_id=? AND active=1",
                (now, key_id, owner_account_id),
            )
        return result.rowcount == 1

    def rotate(self, *, old_key_id: str, new_key_id: str, raw_token: str) -> ApiKeyRecord:
        if not new_key_id or not raw_token or len(raw_token) < 32:
            raise ValueError("invalid API credential")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute("SELECT * FROM commercial_api_keys WHERE key_id=? AND active=1", (old_key_id,)).fetchone()
            if old is None:
                raise KeyError("active API key not found")
            connection.execute(
                """INSERT INTO commercial_api_keys
                (key_id, token_hash, name, plan, scopes, daily_limit, active, created_at, revoked_at, owner_account_id)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, NULL, ?)""",
                (new_key_id, self._hash(raw_token), old["name"], old["plan"], old["scopes"], old["daily_limit"], now, old["owner_account_id"]),
            )
            connection.execute("UPDATE commercial_api_keys SET active=0, revoked_at=? WHERE key_id=?", (now, old_key_id))
            current = connection.execute("SELECT * FROM commercial_api_keys WHERE key_id=?", (new_key_id,)).fetchone()
        return self._record(current)
