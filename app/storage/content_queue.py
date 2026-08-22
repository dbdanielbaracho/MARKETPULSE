from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_hex
from pathlib import Path
from typing import Literal

from app.domain.evidence import EvidenceBundle, EvidenceItem, EvidenceKind
from app.services.content_queue import ContentCandidate, ContentDecision
from app.services.content_drafts import ContentDraft

CandidateState = Literal["queued", "claimed", "completed", "failed", "rejected"]
PublicationState = Literal["active", "rolled_back"]
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
class StoredDraft:
    draft_id: str
    candidate_id: str
    headline: str
    body: str
    citation_ids: tuple[str, ...]
    generator: str
    state: str
    created_at: datetime


@dataclass(frozen=True)
class StoredPublication:
    publication_id: str
    draft_id: str
    article_key: str
    slug: str
    version: int
    headline: str
    body: str
    citation_ids: tuple[str, ...]
    state: PublicationState
    published_at: datetime
    rolled_back_at: datetime | None


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
                CREATE TABLE IF NOT EXISTS content_candidate_evidence (
                    candidate_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('venue', 'news', 'official', 'research')),
                    published_at TEXT,
                    retrieved_at TEXT NOT NULL,
                    summary TEXT,
                    PRIMARY KEY(candidate_id, evidence_id),
                    FOREIGN KEY(candidate_id) REFERENCES content_candidates(candidate_id)
                );
                CREATE INDEX IF NOT EXISTS idx_content_evidence_candidate
                    ON content_candidate_evidence(candidate_id);
                CREATE TABLE IF NOT EXISTS content_drafts (
                    draft_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL UNIQUE,
                    headline TEXT NOT NULL,
                    body TEXT NOT NULL,
                    citation_ids TEXT NOT NULL,
                    generator TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending_review', 'approved', 'rejected')),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES content_candidates(candidate_id)
                );
                CREATE INDEX IF NOT EXISTS idx_content_draft_state
                    ON content_drafts(state, created_at);
                CREATE TABLE IF NOT EXISTS content_publications (
                    publication_id TEXT PRIMARY KEY,
                    draft_id TEXT NOT NULL UNIQUE,
                    article_key TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    version INTEGER NOT NULL CHECK(version >= 1),
                    headline TEXT NOT NULL,
                    body TEXT NOT NULL,
                    citation_ids TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('active', 'rolled_back')),
                    published_at TEXT NOT NULL,
                    rolled_back_at TEXT,
                    FOREIGN KEY(draft_id) REFERENCES content_drafts(draft_id),
                    UNIQUE(article_key, version)
                );
                CREATE INDEX IF NOT EXISTS idx_content_publication_state
                    ON content_publications(state, published_at);
                CREATE TABLE IF NOT EXISTS content_publication_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    publication_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL CHECK(to_state IN ('active', 'rolled_back')),
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(publication_id) REFERENCES content_publications(publication_id)
                );
                CREATE TABLE IF NOT EXISTS content_draft_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draft_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL CHECK(to_state IN ('pending_review', 'approved', 'rejected')),
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(draft_id) REFERENCES content_drafts(draft_id)
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

    def enqueue(
        self,
        candidate: ContentCandidate,
        evidence_bundle: EvidenceBundle,
        now: datetime | None = None,
    ) -> bool:
        if candidate.decision == ContentDecision.REJECT:
            return False
        if evidence_bundle.market_id != candidate.market_id:
            raise ValueError("evidence bundle market does not match candidate")
        bundle = evidence_bundle.deduplicated()
        by_id = {item.evidence_id: item for item in bundle.items}
        evidence_ids = tuple(sorted(set(candidate.evidence_ids)))
        missing = [identifier for identifier in evidence_ids if identifier not in by_id]
        if missing:
            raise ValueError(f"candidate evidence snapshot is incomplete: {missing}")

        candidate_id, key = self._identity(candidate)
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        evidence = json.dumps(evidence_ids, separators=(",", ":"))
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
                for evidence_id in evidence_ids:
                    item = by_id[evidence_id]
                    connection.execute(
                        """INSERT INTO content_candidate_evidence(
                               candidate_id, evidence_id, title, url, publisher, kind,
                               published_at, retrieved_at, summary
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            candidate_id, evidence_id, item.title, str(item.url),
                            item.publisher, item.kind.value,
                            item.published_at.isoformat() if item.published_at else None,
                            item.retrieved_at.isoformat(), item.summary,
                        ),
                    )
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

    def evidence(self, candidate_id: str) -> tuple[EvidenceItem, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT title, url, publisher, kind, published_at, retrieved_at, summary
                   FROM content_candidate_evidence
                   WHERE candidate_id = ? ORDER BY evidence_id""",
                (candidate_id,),
            ).fetchall()
        return tuple(
            EvidenceItem(
                title=row[0],
                url=row[1],
                publisher=row[2],
                kind=EvidenceKind(row[3]),
                published_at=datetime.fromisoformat(row[4]) if row[4] else None,
                retrieved_at=datetime.fromisoformat(row[5]),
                summary=row[6],
            )
            for row in rows
        )

    def claim_next(self, now: datetime | None = None) -> StoredCandidate | None:
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT candidate_id FROM content_candidates
                   WHERE state = 'queued' ORDER BY created_at, candidate_id LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            candidate_id = row[0]
            connection.execute(
                "UPDATE content_candidates SET state = 'claimed', updated_at = ? WHERE candidate_id = ?",
                (timestamp, candidate_id),
            )
            connection.execute(
                """INSERT INTO content_candidate_audit(
                       candidate_id, from_state, to_state, reason, occurred_at
                   ) VALUES (?, 'queued', 'claimed', 'draft_worker_claimed', ?)""",
                (candidate_id, timestamp),
            )
        return self.get(candidate_id)

    def save_draft(
        self,
        candidate_id: str,
        draft: ContentDraft,
        now: datetime | None = None,
    ) -> StoredDraft:
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        citations = tuple(dict.fromkeys(draft.citation_ids))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM content_candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise KeyError(candidate_id)
            if row[0] != "claimed":
                raise ValueError(f"candidate must be claimed before drafting: {row[0]}")
            allowed = {
                item[0] for item in connection.execute(
                    "SELECT evidence_id FROM content_candidate_evidence WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchall()
            }
            if not citations or any(identifier not in allowed for identifier in citations):
                raise ValueError("draft citations must reference the persisted evidence snapshot")
            digest = sha256(
                json.dumps([candidate_id, draft.generator, citations], separators=(",", ":")).encode()
            ).hexdigest()
            draft_id = f"draft_{digest[:20]}"
            connection.execute(
                """INSERT INTO content_drafts(
                       draft_id, candidate_id, headline, body, citation_ids,
                       generator, state, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, 'pending_review', ?)""",
                (
                    draft_id, candidate_id, draft.headline, draft.body,
                    json.dumps(citations, separators=(",", ":")), draft.generator, timestamp,
                ),
            )
            connection.execute(
                """INSERT INTO content_draft_audit(
                       draft_id, from_state, to_state, reason, occurred_at
                   ) VALUES (?, NULL, 'pending_review', 'draft_created', ?)""",
                (draft_id, timestamp),
            )
            connection.execute(
                "UPDATE content_candidates SET state = 'completed', updated_at = ? WHERE candidate_id = ?",
                (timestamp, candidate_id),
            )
            connection.execute(
                """INSERT INTO content_candidate_audit(
                       candidate_id, from_state, to_state, reason, occurred_at
                   ) VALUES (?, 'claimed', 'completed', 'evidence_draft_created', ?)""",
                (candidate_id, timestamp),
            )
        return StoredDraft(
            draft_id=draft_id,
            candidate_id=candidate_id,
            headline=draft.headline,
            body=draft.body,
            citation_ids=citations,
            generator=draft.generator,
            state="pending_review",
            created_at=datetime.fromisoformat(timestamp),
        )


    def drafts(self, state: str = "pending_review", limit: int = 50) -> list[StoredDraft]:
        if state not in {"pending_review", "approved", "rejected"}:
            raise ValueError("invalid draft state")
        if not 1 <= limit <= 100:
            raise ValueError("draft limit must be between 1 and 100")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT draft_id, candidate_id, headline, body, citation_ids,
                          generator, state, created_at
                   FROM content_drafts WHERE state = ?
                   ORDER BY created_at, draft_id LIMIT ?""",
                (state, limit),
            ).fetchall()
        return [
            StoredDraft(
                draft_id=row[0], candidate_id=row[1], headline=row[2], body=row[3],
                citation_ids=tuple(json.loads(row[4])), generator=row[5], state=row[6],
                created_at=datetime.fromisoformat(row[7]),
            )
            for row in rows
        ]

    def review_draft(
        self,
        draft_id: str,
        to_state: Literal["approved", "rejected"],
        reason: str,
        now: datetime | None = None,
    ) -> StoredDraft:
        if to_state not in {"approved", "rejected"}:
            raise ValueError("draft review must approve or reject")
        if not reason.strip():
            raise ValueError("draft review reason is required")
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM content_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            if row is None:
                raise KeyError(draft_id)
            if row[0] != "pending_review":
                raise ValueError(f"draft is not pending review: {row[0]}")
            connection.execute(
                "UPDATE content_drafts SET state = ? WHERE draft_id = ?",
                (to_state, draft_id),
            )
            connection.execute(
                """INSERT INTO content_draft_audit(
                       draft_id, from_state, to_state, reason, occurred_at
                   ) VALUES (?, 'pending_review', ?, ?, ?)""",
                (draft_id, to_state, reason.strip(), timestamp),
            )
            draft_row = connection.execute(
                """SELECT draft_id, candidate_id, headline, body, citation_ids,
                          generator, state, created_at
                   FROM content_drafts WHERE draft_id = ?""",
                (draft_id,),
            ).fetchone()
        return StoredDraft(
            draft_id=draft_row[0], candidate_id=draft_row[1], headline=draft_row[2],
            body=draft_row[3], citation_ids=tuple(json.loads(draft_row[4])),
            generator=draft_row[5], state=draft_row[6],
            created_at=datetime.fromisoformat(draft_row[7]),
        )

    def draft_audit(self, draft_id: str) -> list[tuple[str | None, str, str]]:
        with self._connect() as connection:
            return connection.execute(
                """SELECT from_state, to_state, reason
                   FROM content_draft_audit WHERE draft_id = ? ORDER BY id""",
                (draft_id,),
            ).fetchall()

    def draft_counts(self) -> dict[str, int]:
        result = {"pending_review": 0, "approved": 0, "rejected": 0}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state, COUNT(*) FROM content_drafts GROUP BY state"
            ).fetchall()
        result.update({state: count for state, count in rows})
        return result

    def drafts_created_since(self, since: datetime) -> int:
        if since.tzinfo is None:
            raise ValueError("draft limit timestamp must be timezone-aware")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM content_drafts WHERE created_at >= ?",
                (since.isoformat(),),
            ).fetchone()
        return int(row[0])

    @staticmethod
    def _publication_from_row(row: tuple) -> StoredPublication:
        return StoredPublication(
            publication_id=row[0],
            draft_id=row[1],
            article_key=row[2],
            slug=row[3],
            version=row[4],
            headline=row[5],
            body=row[6],
            citation_ids=tuple(json.loads(row[7])),
            state=row[8],
            published_at=datetime.fromisoformat(row[9]),
            rolled_back_at=datetime.fromisoformat(row[10]) if row[10] else None,
        )

    @staticmethod
    def _slug(headline: str, publication_id: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", headline.casefold()).strip("-")[:70]
        return f"{base or 'prediction-market-brief'}-{publication_id[-8:]}"

    def publish_draft(
        self,
        draft_id: str,
        reason: str,
        now: datetime | None = None,
    ) -> StoredPublication:
        if not reason.strip():
            raise ValueError("publication reason is required")
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT d.state, d.candidate_id, d.headline, d.body, d.citation_ids,
                          c.market_id
                   FROM content_drafts d
                   JOIN content_candidates c ON c.candidate_id = d.candidate_id
                   WHERE d.draft_id = ?""",
                (draft_id,),
            ).fetchone()
            if row is None:
                raise KeyError(draft_id)
            if row[0] != "approved":
                raise ValueError(f"draft must be approved before publication: {row[0]}")
            existing = connection.execute(
                """SELECT publication_id, draft_id, article_key, slug, version, headline,
                          body, citation_ids, state, published_at, rolled_back_at
                   FROM content_publications WHERE draft_id = ?""",
                (draft_id,),
            ).fetchone()
            if existing is not None:
                return self._publication_from_row(existing)
            article_key = row[5]
            version = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM content_publications WHERE article_key = ?",
                (article_key,),
            ).fetchone()[0]
            publication_id = f"pub_{sha256(draft_id.encode()).hexdigest()[:20]}"
            slug = self._slug(row[2], publication_id)
            connection.execute(
                """INSERT INTO content_publications(
                       publication_id, draft_id, article_key, slug, version, headline, body,
                       citation_ids, state, published_at, rolled_back_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL)""",
                (publication_id, draft_id, article_key, slug, version, row[2], row[3], row[4], timestamp),
            )
            connection.execute(
                """INSERT INTO content_publication_audit(
                       publication_id, from_state, to_state, reason, occurred_at
                   ) VALUES (?, NULL, 'active', ?, ?)""",
                (publication_id, reason.strip(), timestamp),
            )
            stored = connection.execute(
                """SELECT publication_id, draft_id, article_key, slug, version, headline,
                          body, citation_ids, state, published_at, rolled_back_at
                   FROM content_publications WHERE publication_id = ?""",
                (publication_id,),
            ).fetchone()
        return self._publication_from_row(stored)

    def rollback_publication(
        self,
        publication_id: str,
        reason: str,
        now: datetime | None = None,
    ) -> StoredPublication:
        if not reason.strip():
            raise ValueError("rollback reason is required")
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM content_publications WHERE publication_id = ?",
                (publication_id,),
            ).fetchone()
            if row is None:
                raise KeyError(publication_id)
            if row[0] != "active":
                raise ValueError(f"publication is not active: {row[0]}")
            connection.execute(
                """UPDATE content_publications
                   SET state = 'rolled_back', rolled_back_at = ?
                   WHERE publication_id = ?""",
                (timestamp, publication_id),
            )
            connection.execute(
                """INSERT INTO content_publication_audit(
                       publication_id, from_state, to_state, reason, occurred_at
                   ) VALUES (?, 'active', 'rolled_back', ?, ?)""",
                (publication_id, reason.strip(), timestamp),
            )
            stored = connection.execute(
                """SELECT publication_id, draft_id, article_key, slug, version, headline,
                          body, citation_ids, state, published_at, rolled_back_at
                   FROM content_publications WHERE publication_id = ?""",
                (publication_id,),
            ).fetchone()
        return self._publication_from_row(stored)

    def publications(self, state: PublicationState = "active", limit: int = 50) -> list[StoredPublication]:
        if state not in {"active", "rolled_back"}:
            raise ValueError("invalid publication state")
        if not 1 <= limit <= 100:
            raise ValueError("publication limit must be between 1 and 100")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT publication_id, draft_id, article_key, slug, version, headline,
                          body, citation_ids, state, published_at, rolled_back_at
                   FROM content_publications WHERE state = ?
                   ORDER BY published_at DESC, publication_id DESC LIMIT ?""",
                (state, limit),
            ).fetchall()
        return [self._publication_from_row(row) for row in rows]

    def publication(self, slug: str, include_rolled_back: bool = False) -> StoredPublication | None:
        query = """SELECT publication_id, draft_id, article_key, slug, version, headline,
                          body, citation_ids, state, published_at, rolled_back_at
                   FROM content_publications WHERE slug = ?"""
        params: tuple[object, ...] = (slug,)
        if not include_rolled_back:
            query += " AND state = 'active'"
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._publication_from_row(row) if row is not None else None

    def publication_evidence(self, publication_id: str) -> tuple[EvidenceItem, ...]:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT d.candidate_id
                   FROM content_publications p
                   JOIN content_drafts d ON d.draft_id = p.draft_id
                   WHERE p.publication_id = ?""",
                (publication_id,),
            ).fetchone()
        if row is None:
            raise KeyError(publication_id)
        return self.evidence(row[0])

    def publication_audit(self, publication_id: str) -> list[tuple[str | None, str, str]]:
        with self._connect() as connection:
            return connection.execute(
                """SELECT from_state, to_state, reason
                   FROM content_publication_audit WHERE publication_id = ? ORDER BY id""",
                (publication_id,),
            ).fetchall()

    def publication_counts(self) -> dict[str, int]:
        result = {"active": 0, "rolled_back": 0}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state, COUNT(*) FROM content_publications GROUP BY state"
            ).fetchall()
        result.update({state: count for state, count in rows})
        return result

