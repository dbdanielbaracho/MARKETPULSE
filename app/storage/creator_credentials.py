from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_CREATOR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,99}$")
_CREDENTIAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{7,119}$")


@dataclass(frozen=True)
class CreatorCredential:
    credential_id: str
    creator_id: str
    active: bool
    created_at: datetime
    revoked_at: datetime | None


class CreatorCredentialStore:
    """Hashed bearer credentials for private creator self-service APIs."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS creator_credentials (
                    credential_id TEXT PRIMARY KEY,
                    creator_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    active INTEGER NOT NULL CHECK(active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_creator_credentials_creator
                    ON creator_credentials(creator_id, active);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _record(row: sqlite3.Row) -> CreatorCredential:
        return CreatorCredential(
            credential_id=row["credential_id"],
            creator_id=row["creator_id"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            revoked_at=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
        )

    @staticmethod
    def _validate_ids(credential_id: str, creator_id: str) -> tuple[str, str]:
        credential_id = credential_id.strip()
        creator_id = creator_id.strip()
        if not _CREDENTIAL_ID.fullmatch(credential_id):
            raise ValueError("invalid creator credential id")
        if not _CREATOR_ID.fullmatch(creator_id):
            raise ValueError("invalid creator id")
        return credential_id, creator_id

    def create(self, *, credential_id: str, creator_id: str, raw_token: str) -> CreatorCredential:
        credential_id, creator_id = self._validate_ids(credential_id, creator_id)
        if not raw_token or len(raw_token) < 32:
            raise ValueError("invalid creator credential")
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO creator_credentials
                (credential_id, creator_id, token_hash, active, created_at, revoked_at)
                VALUES (?, ?, ?, 1, ?, NULL)
                """,
                (credential_id, creator_id, self._hash(raw_token), now.isoformat()),
            )
            row = connection.execute(
                "SELECT * FROM creator_credentials WHERE credential_id=?",
                (credential_id,),
            ).fetchone()
        return self._record(row)

    def authorize(self, raw_token: str) -> CreatorCredential:
        if not raw_token:
            raise PermissionError("missing creator credential")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM creator_credentials WHERE token_hash=? AND active=1",
                (self._hash(raw_token),),
            ).fetchone()
        if row is None:
            raise PermissionError("invalid creator credential")
        return self._record(row)

    def revoke(self, credential_id: str) -> bool:
        credential_id = credential_id.strip()
        if not _CREDENTIAL_ID.fullmatch(credential_id):
            raise ValueError("invalid creator credential id")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE creator_credentials
                SET active=0, revoked_at=?
                WHERE credential_id=? AND active=1
                """,
                (now, credential_id),
            )
        return result.rowcount == 1
