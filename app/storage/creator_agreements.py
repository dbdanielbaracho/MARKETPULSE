from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_CREATOR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,99}$")
_AGREEMENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,119}$")


@dataclass(frozen=True)
class CreatorAgreement:
    creator_id: str
    agreement_id: str
    share_basis_points: int
    approved: bool
    approved_at: datetime | None
    updated_at: datetime


class CreatorAgreementStore:
    """Private creator revenue-share configuration.

    No default agreement exists. Callers must explicitly configure and approve an
    agreement before any share may be used. This store is not a public API and
    does not contain partner commission economics.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS creator_agreements (
                    creator_id TEXT PRIMARY KEY,
                    agreement_id TEXT NOT NULL UNIQUE,
                    share_basis_points INTEGER NOT NULL CHECK(share_basis_points BETWEEN 0 AND 10000),
                    approved INTEGER NOT NULL CHECK(approved IN (0, 1)),
                    approved_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _item(row: sqlite3.Row) -> CreatorAgreement:
        return CreatorAgreement(
            creator_id=row["creator_id"],
            agreement_id=row["agreement_id"],
            share_basis_points=int(row["share_basis_points"]),
            approved=bool(row["approved"]),
            approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _validate(creator_id: str, agreement_id: str, share_basis_points: int) -> tuple[str, str, int]:
        creator_id = creator_id.strip()
        agreement_id = agreement_id.strip()
        if not _CREATOR_ID.fullmatch(creator_id):
            raise ValueError("invalid creator id")
        if not _AGREEMENT_ID.fullmatch(agreement_id):
            raise ValueError("invalid agreement id")
        if isinstance(share_basis_points, bool) or not isinstance(share_basis_points, int):
            raise ValueError("share_basis_points must be an integer")
        if share_basis_points < 0 or share_basis_points > 10000:
            raise ValueError("share_basis_points must be between 0 and 10000")
        return creator_id, agreement_id, share_basis_points

    def configure(
        self,
        *,
        creator_id: str,
        agreement_id: str,
        share_basis_points: int,
        approved: bool = False,
    ) -> CreatorAgreement:
        creator_id, agreement_id, share_basis_points = self._validate(
            creator_id, agreement_id, share_basis_points
        )
        now = datetime.now(timezone.utc)
        approved_at = now if approved else None
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT agreement_id FROM creator_agreements WHERE creator_id=?",
                (creator_id,),
            ).fetchone()
            if existing and existing["agreement_id"] != agreement_id:
                raise ValueError("creator already belongs to another agreement")
            connection.execute(
                """
                INSERT INTO creator_agreements
                (creator_id, agreement_id, share_basis_points, approved, approved_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(creator_id) DO UPDATE SET
                    share_basis_points=excluded.share_basis_points,
                    approved=excluded.approved,
                    approved_at=excluded.approved_at,
                    updated_at=excluded.updated_at
                """,
                (
                    creator_id,
                    agreement_id,
                    share_basis_points,
                    int(approved),
                    approved_at.isoformat() if approved_at else None,
                    now.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM creator_agreements WHERE creator_id=?", (creator_id,)
            ).fetchone()
        return self._item(row)

    def approved_for_creator(self, creator_id: str) -> CreatorAgreement | None:
        creator_id = creator_id.strip()
        if not _CREATOR_ID.fullmatch(creator_id):
            raise ValueError("invalid creator id")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM creator_agreements WHERE creator_id=? AND approved=1",
                (creator_id,),
            ).fetchone()
        return self._item(row) if row else None

    def revoke(self, creator_id: str) -> None:
        creator_id = creator_id.strip()
        if not _CREATOR_ID.fullmatch(creator_id):
            raise ValueError("invalid creator id")
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute(
                "UPDATE creator_agreements SET approved=0, approved_at=NULL, updated_at=? WHERE creator_id=?",
                (now, creator_id),
            )
