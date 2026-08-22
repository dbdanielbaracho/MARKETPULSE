from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_hex
from pathlib import Path
from typing import Literal

from app.services.content_queue import ContentCandidate, ContentDecision

CandidateState = Literal["queued", "claimed", "completed", "failed", "rejected"]
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"claimed", "rejected"},
    "claimed": {"completed", "failed"},
    "failed": {"queued", "rejected"},
    "completed": set(),
    "rejected": set(),
}


@dataclass(frozen=True)
class PersistenceProbe:
    identity: str
    startup_count: int
    first_started_at: datetime
    last_started_at: datetime


@dataclass(frozen=True)
class StoredCandidate:
    candidate_id: str
    market_id: str
    score: float
    decision: str
    reason: str
    evidence_ids: tuple[str, ...]
    state: CandidateState
    created_at: datetime
    updated_at: datetime


class ContentQueueStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS storage_probe (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    identity TEXT NOT NULL,
                    startup_count INTEGER NOT NULL CHECK(startup_count >= 1),
                    first_started_at TEXT NOT NULL,
                    last_started_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS content_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    market_id TEXT NOT NULL,
                    score REAL NOT NULL CHECK(score >= 0 AND score <= 100),
                    decision TEXT NOT NULL CHECK(decision IN ('update', 'create')),
                    reason TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('queued', 'claimed', 'completed', 'failed', 'rejected')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_content_candidate_state
                    ON content_candidates(state, created_at);
                CREATE TABLE IF NOT EXISTS content_candidate_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES content_candidates(candidate_id)
                );
                """
            )

    def record_startup(self, now: datetime | None = None) -> PersistenceProbe:
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT identity, startup_count, first_started_at
                   FROM storage_probe WHERE singleton = 1"""
            ).fetchone()
            if row is None:
                identity = token_hex(16)
                startup_count = 1
                first_started_at = timestamp
                connection.execute(
                    """INSERT INTO storage_probe(
                           singleton, identity, startup_count, first_started_at, last_started_at
                       ) VALUES (1, ?, ?, ?, ?)""",
                    (identity, startup_count, first_started_at, timestamp),
                )
            else:
                identity, previous_count, first_started_at = row
                startup_count = previous_count + 1
                connection.execute(
                    """UPDATE storage_probe
                       SET startup_count = ?, last_started_at = ?
                       WHERE singleton = 1""",
                    (startup_count, timestamp),
                )
        return PersistenceProbe(
            identity=identity,
            startup_count=startup_count,
            first_started_at=datetime.fromisoformat(first_started_at),
            last_started_at=datetime.fromisoformat(timestamp),
        )

    @staticmethod
    def _identity(candidate: ContentCandidate) -> tuple[str, str]:
        evidence = tuple(sorted(set(candidate.evidence_ids)))
        raw = json.dumps(
            [candidate.market_id, candidate.decision.value, evidence],
            separators=(",", ":"),
        )
        key = sha256(raw.encode()).hexdigest()
        return f"cc_{key[:20]}", key

    def enqueue(self, candidate: ContentCandidate, now: datetime | None = None) -> bool:
        if candidate.decision == ContentDecision.REJECT:
            return False
        candidate_id, key = self._identity(candidate)
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        evidence = json.dumps(sorted(set(candidate.evidence_ids)), separators=(",", ":"))
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO content_candidates(
                       candidate_id, idempotency_key, market_id, score, decision, reason,
                       evidence_ids, state, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)""",
                (
                    candidate_id, key, candidate.market_id, candidate.score,
                    candidate.decision.value, candidate.reason, evidence, timestamp, timestamp,
                ),
            )
            if cursor.rowcount:
                connection.execute(
                    """INSERT INTO content_candidate_audit(
                           candidate_id, from_state, to_state, reason, occurred_at
                       ) VALUES (?, NULL, 'queued', 'candidate_enqueued', ?)""",
                    (candidate_id, timestamp),
                )
                return True
        return False

    def transition(self, candidate_id: str, to_state: CandidateState, reason: str, now: datetime | None = None) -> None:
        if not reason.strip():
            raise ValueError("transition reason is required")
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM content_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise KeyError(candidate_id)
            current = row[0]
            if to_state not in _ALLOWED_TRANSITIONS[current]:
                raise ValueError(f"invalid content candidate transition: {current}->{to_state}")
            connection.execute(
                "UPDATE content_candidates SET state = ?, updated_at = ? WHERE candidate_id = ?",
                (to_state, timestamp, candidate_id),
            )
            connection.execute(
                """INSERT INTO content_candidate_audit(
                       candidate_id, from_state, to_state, reason, occurred_at
                   ) VALUES (?, ?, ?, ?, ?)""",
                (candidate_id, current, to_state, reason.strip(), timestamp),
            )

    def counts(self) -> dict[str, int]:
        result = {state: 0 for state in _ALLOWED_TRANSITIONS}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state, COUNT(*) FROM content_candidates GROUP BY state"
            ).fetchall()
        result.update({state: count for state, count in rows})
        return result

    def get(self, candidate_id: str) -> StoredCandidate | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT candidate_id, market_id, score, decision, reason, evidence_ids,
                          state, created_at, updated_at
                   FROM content_candidates WHERE candidate_id = ?""",
                (candidate_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredCandidate(
            candidate_id=row[0], market_id=row[1], score=row[2], decision=row[3],
            reason=row[4], evidence_ids=tuple(json.loads(row[5])), state=row[6],
            created_at=datetime.fromisoformat(row[7]), updated_at=datetime.fromisoformat(row[8]),
        )

    def audit(self, candidate_id: str) -> list[tuple[str | None, str, str]]:
        with self._connect() as connection:
            return connection.execute(
                """SELECT from_state, to_state, reason
                   FROM content_candidate_audit WHERE candidate_id = ? ORDER BY id""",
                (candidate_id,),
            ).fetchall()
