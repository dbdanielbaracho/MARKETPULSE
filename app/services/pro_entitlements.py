from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable


PRO_FEATURE_ADVANCED_INTELLIGENCE = "advanced_intelligence"
PRO_FEATURE_ADVANCED_ALERTS = "advanced_alerts"
PRO_FEATURE_EVIDENCE_DIGEST = "evidence_digest"
PRO_FEATURE_DATA_EXPORT = "data_export"

ALLOWED_PRO_FEATURES = frozenset(
    {
        PRO_FEATURE_ADVANCED_INTELLIGENCE,
        PRO_FEATURE_ADVANCED_ALERTS,
        PRO_FEATURE_EVIDENCE_DIGEST,
        PRO_FEATURE_DATA_EXPORT,
    }
)

_ACCESS_STATUSES = frozenset({"active", "trialing"})


@dataclass(frozen=True)
class ProProductConfig:
    """Commercial product mapping without embedding prices or partner economics."""

    provider: str
    product_id: str
    features: frozenset[str]

    @classmethod
    def from_env(cls) -> "ProProductConfig | None":
        product_id = os.getenv("MP_PRO_PRODUCT_ID", "").strip()
        if not product_id:
            return None
        provider = os.getenv("MP_PRO_BILLING_PROVIDER", "stripe").strip().casefold()
        if provider != "stripe":
            raise ValueError("MP_PRO_BILLING_PROVIDER must be stripe when Pro billing is configured")
        raw_features = os.getenv(
            "MP_PRO_FEATURES",
            ",".join(sorted(ALLOWED_PRO_FEATURES)),
        )
        features = frozenset(part.strip() for part in raw_features.split(",") if part.strip())
        if not features:
            raise ValueError("MP_PRO_FEATURES must contain at least one feature")
        unsupported = features - ALLOWED_PRO_FEATURES
        if unsupported:
            raise ValueError(f"unsupported Pro feature(s): {','.join(sorted(unsupported))}")
        if len(product_id) > 255 or any(ch.isspace() for ch in product_id):
            raise ValueError("MP_PRO_PRODUCT_ID must be a bounded opaque identifier without whitespace")
        return cls(provider=provider, product_id=product_id, features=features)


@dataclass(frozen=True)
class ProviderEntitlementState:
    subject_id: str
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
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return self.valid_until > current


@runtime_checkable
class ProBillingProvider(Protocol):
    async def fetch_state(self, subject_id: str) -> ProviderEntitlementState | None: ...


class ProEntitlementStore:
    """Durable local projection of provider-backed subscription entitlements.

    Provider/customer identifiers remain server-side. Access is granted only from a
    persisted provider state that maps to the configured product and an access-granting
    subscription status. Unknown, stale, malformed or mismatched states fail closed.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pro_entitlements (
                    subject_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    valid_until TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _validate_subject(subject_id: str) -> str:
        normalized = subject_id.strip()
        if not normalized or len(normalized) > 200:
            raise ValueError("subject_id must be 1-200 characters")
        return normalized

    def upsert_provider_state(self, state: ProviderEntitlementState) -> None:
        subject_id = self._validate_subject(state.subject_id)
        if not state.product_id or len(state.product_id) > 255:
            raise ValueError("product_id must be a bounded opaque identifier")
        if not state.subscription_id or len(state.subscription_id) > 255:
            raise ValueError("subscription_id must be a bounded opaque identifier")
        if state.valid_until is not None and state.valid_until.tzinfo is None:
            raise ValueError("valid_until must be timezone-aware")
        updated_at = datetime.now(timezone.utc).isoformat()
        valid_until = state.valid_until.isoformat() if state.valid_until else None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO pro_entitlements(subject_id, product_id, subscription_id, status, valid_until, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject_id) DO UPDATE SET
                    product_id=excluded.product_id,
                    subscription_id=excluded.subscription_id,
                    status=excluded.status,
                    valid_until=excluded.valid_until,
                    updated_at=excluded.updated_at
                """,
                (subject_id, state.product_id, state.subscription_id, state.status.casefold(), valid_until, updated_at),
            )

    def state_for(self, subject_id: str) -> ProviderEntitlementState | None:
        subject_id = self._validate_subject(subject_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT subject_id, product_id, subscription_id, status, valid_until
                FROM pro_entitlements WHERE subject_id = ?
                """,
                (subject_id,),
            ).fetchone()
        if not row:
            return None
        valid_until = datetime.fromisoformat(row[4]) if row[4] else None
        return ProviderEntitlementState(row[0], row[1], row[2], row[3], valid_until)

    def active_features(
        self,
        subject_id: str,
        config: ProProductConfig | None,
        *,
        now: datetime | None = None,
    ) -> frozenset[str]:
        if config is None:
            return frozenset()
        state = self.state_for(subject_id)
        if state is None or state.product_id != config.product_id or not state.grants_access(now):
            return frozenset()
        return config.features

    def has_feature(
        self,
        subject_id: str,
        feature: str,
        config: ProProductConfig | None,
        *,
        now: datetime | None = None,
    ) -> bool:
        if feature not in ALLOWED_PRO_FEATURES:
            return False
        return feature in self.active_features(subject_id, config, now=now)


def normalize_provider_features(features: Iterable[str]) -> frozenset[str]:
    """Validate any future provider entitlement payload before local projection."""

    normalized = frozenset(item.strip() for item in features if item.strip())
    unsupported = normalized - ALLOWED_PRO_FEATURES
    if unsupported:
        raise ValueError(f"unsupported Pro feature(s): {','.join(sorted(unsupported))}")
    return normalized
