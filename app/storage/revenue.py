from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.domain.revenue import AttributionRecord, RevenueState


class RevenueStore:
    """Durable, idempotent partner-attribution ledger. It never estimates commission."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS revenue_attributions (
                    attribution_id TEXT PRIMARY KEY,
                    click_id TEXT NOT NULL UNIQUE,
                    partner_id TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    country TEXT NOT NULL,
                    state TEXT NOT NULL,
                    commission_amount REAL,
                    currency TEXT,
                    partner_event_id TEXT UNIQUE,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbound_click_context (
                    click_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    campaign_id TEXT,
                    creator_id TEXT,
                    channel TEXT,
                    referrer TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(click_id) REFERENCES revenue_attributions(click_id)
                );
                CREATE INDEX IF NOT EXISTS idx_outbound_context_market
                    ON outbound_click_context(market_id);
                CREATE INDEX IF NOT EXISTS idx_outbound_context_campaign
                    ON outbound_click_context(campaign_id);
                CREATE TABLE IF NOT EXISTS revenue_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attribution_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    partner_event_id TEXT UNIQUE,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(attribution_id) REFERENCES revenue_attributions(attribution_id)
                );
                """
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> AttributionRecord:
        return AttributionRecord(
            attribution_id=row["attribution_id"],
            click_id=row["click_id"],
            partner_id=row["partner_id"],
            venue=row["venue"],
            country=row["country"],
            state=RevenueState(row["state"]),
            commission_amount=row["commission_amount"],
            currency=row["currency"],
            partner_event_id=row["partner_event_id"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def record_click(self, record: AttributionRecord) -> AttributionRecord:
        if record.state != RevenueState.CLICKED:
            raise ValueError("new attribution must start in clicked state")
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT * FROM revenue_attributions WHERE click_id = ?",
                (record.click_id,),
            ).fetchone()
            if existing:
                return self._record(existing)
            connection.execute(
                """INSERT INTO revenue_attributions
                (attribution_id, click_id, partner_id, venue, country, state,
                 commission_amount, currency, partner_event_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.attribution_id, record.click_id, record.partner_id,
                    record.venue, record.country.upper(), record.state.value,
                    record.commission_amount, record.currency,
                    record.partner_event_id, record.updated_at.isoformat(),
                ),
            )
            connection.execute(
                """INSERT INTO revenue_audit
                (attribution_id, from_state, to_state, partner_event_id, occurred_at)
                VALUES (?, NULL, ?, NULL, ?)""",
                (record.attribution_id, record.state.value, record.updated_at.isoformat()),
            )
            return record

    def record_click_context(
        self,
        *,
        click_id: str,
        market_id: str,
        campaign_id: str | None = None,
        creator_id: str | None = None,
        channel: str | None = None,
        referrer: str | None = None,
    ) -> None:
        """Persist first-party acquisition context without storing user funds."""
        with self._connection() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO outbound_click_context
                (click_id, market_id, campaign_id, creator_id, channel, referrer, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    click_id,
                    market_id,
                    campaign_id or None,
                    creator_id or None,
                    channel or None,
                    (referrer or "")[:500] or None,
                    datetime.now().astimezone().isoformat(),
                ),
            )

    def attribution_id_for_click(self, click_id: str) -> str:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT attribution_id FROM revenue_attributions WHERE click_id=?",
                (click_id,),
            ).fetchone()
        if row is None:
            raise KeyError(click_id)
        return row["attribution_id"]

    def creator_summary(self, creator_id: str) -> dict[str, object]:
        with self._connection() as connection:
            state_counts = {
                row["state"]: row["count"]
                for row in connection.execute(
                    """SELECT a.state, COUNT(*) AS count
                    FROM revenue_attributions a
                    JOIN outbound_click_context c ON c.click_id=a.click_id
                    WHERE c.creator_id=? GROUP BY a.state""",
                    (creator_id,),
                )
            }
            paid_totals = {
                row["currency"]: round(row["amount"], 2)
                for row in connection.execute(
                    """SELECT a.currency, SUM(a.commission_amount) AS amount
                    FROM revenue_attributions a
                    JOIN outbound_click_context c ON c.click_id=a.click_id
                    WHERE c.creator_id=? AND a.state='paid'
                      AND a.commission_amount IS NOT NULL AND a.currency IS NOT NULL
                    GROUP BY a.currency""",
                    (creator_id,),
                )
            }
            row = connection.execute(
                """SELECT COUNT(*) AS clicks, COUNT(DISTINCT c.market_id) AS markets
                FROM outbound_click_context c WHERE c.creator_id=?""",
                (creator_id,),
            ).fetchone()
        return {
            "creator_id": creator_id,
            "click_count": row["clicks"],
            "market_count": row["markets"],
            "state_counts": state_counts,
            "paid_partner_revenue_totals": paid_totals,
            "creator_amount_due": None,
            "notice": "Creator amount is not calculated until an approved revenue-share agreement is configured.",
        }

    def transition(
        self,
        attribution_id: str,
        new_state: RevenueState,
        *,
        commission_amount: float | None = None,
        currency: str | None = None,
        partner_event_id: str,
    ) -> AttributionRecord:
        if not partner_event_id.strip():
            raise ValueError("partner_event_id is required for reconciliation")
        with self._connection() as connection:
            duplicate = connection.execute(
                "SELECT attribution_id FROM revenue_audit WHERE partner_event_id = ?",
                (partner_event_id,),
            ).fetchone()
            if duplicate:
                row = connection.execute(
                    "SELECT * FROM revenue_attributions WHERE attribution_id = ?",
                    (duplicate["attribution_id"],),
                ).fetchone()
                return self._record(row)
            row = connection.execute(
                "SELECT * FROM revenue_attributions WHERE attribution_id = ?",
                (attribution_id,),
            ).fetchone()
            if row is None:
                raise KeyError(attribution_id)
            current = self._record(row)
            updated = current.transition(
                new_state,
                commission_amount=commission_amount,
                currency=currency,
                partner_event_id=partner_event_id,
            )
            connection.execute(
                """UPDATE revenue_attributions SET state=?, commission_amount=?,
                currency=?, partner_event_id=?, updated_at=? WHERE attribution_id=?""",
                (
                    updated.state.value, updated.commission_amount, updated.currency,
                    updated.partner_event_id, updated.updated_at.isoformat(),
                    attribution_id,
                ),
            )
            connection.execute(
                """INSERT INTO revenue_audit
                (attribution_id, from_state, to_state, partner_event_id, occurred_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    attribution_id, current.state.value, updated.state.value,
                    partner_event_id, updated.updated_at.isoformat(),
                ),
            )
            return updated

    def summary(self) -> dict[str, object]:
        with self._connection() as connection:
            states = {
                row["state"]: row["count"]
                for row in connection.execute(
                    "SELECT state, COUNT(*) AS count FROM revenue_attributions GROUP BY state"
                )
            }
            totals = {
                row["currency"]: round(row["amount"], 2)
                for row in connection.execute(
                    """SELECT currency, SUM(commission_amount) AS amount
                    FROM revenue_attributions
                    WHERE commission_amount IS NOT NULL AND currency IS NOT NULL
                    GROUP BY currency"""
                )
            }
            row = connection.execute(
                """SELECT COUNT(*) AS records,
                SUM(CASE WHEN commission_amount IS NULL THEN 1 ELSE 0 END) AS unpriced,
                MAX(updated_at) AS last_updated_at
                FROM revenue_attributions"""
            ).fetchone()
            audit_events = connection.execute(
                "SELECT COUNT(*) AS count FROM revenue_audit"
            ).fetchone()["count"]
            click_context_count = connection.execute(
                "SELECT COUNT(*) AS count FROM outbound_click_context"
            ).fetchone()["count"]
            clicks_by_channel = {
                (item["channel"] or "direct"): item["count"]
                for item in connection.execute(
                    """SELECT channel, COUNT(*) AS count
                    FROM outbound_click_context GROUP BY channel"""
                )
            }
        return {
            "record_count": row["records"],
            "state_counts": states,
            "known_commission_totals": totals,
            "unpriced_record_count": row["unpriced"] or 0,
            "audit_event_count": audit_events,
            "click_context_count": click_context_count,
            "clicks_by_channel": clicks_by_channel,
            "last_updated_at": row["last_updated_at"],
            "commercial_intake_enabled": False,
            "notice": "Only partner-reported amounts are counted; no commission is estimated.",
        }
