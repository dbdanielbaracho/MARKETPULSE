from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_PROVIDER_DEFAULTS = {
    "enabled": True,
    "commercial_verified": False,
    "partner_id": "",
    "affiliate_id": "",
    "referral_code": "",
    "tracking_parameter": "",
    "tracking_value": "",
    "compensation_model": "pending",
    "compensation_rate": None,
    "allowed_countries": [],
    "blocked_countries": [],
}

DEFAULT_CONTROL_PLANE: dict[str, Any] = {
    "version": 1,
    "providers": {
        "kalshi_us": {
            **_PROVIDER_DEFAULTS,
            "allowed_countries": ["US"],
        },
        "polymarket_intl": {
            **_PROVIDER_DEFAULTS,
            "blocked_countries": ["BR", "US"],
        },
        "polymarket_us": {
            **_PROVIDER_DEFAULTS,
            "enabled": False,
            "allowed_countries": ["US"],
        },
    },
    "acquisition": {
        "channels": {
            "instagram": True,
            "tiktok": True,
            "x": True,
            "seo": True,
            "creator": True,
        }
    },
    "publishing": {
        "require_preview": True,
    },
}


_ALLOWED_PROVIDER_KEYS = {
    "enabled", "commercial_verified", "partner_id", "affiliate_id", "referral_code",
    "tracking_parameter", "tracking_value", "compensation_model", "compensation_rate",
    "allowed_countries", "blocked_countries",
}
_ALLOWED_MODELS = {"pending", "cpa", "revenue_share", "referral_fee", "volume_incentive", "other"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _countries(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("country lists must be arrays")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("country codes must be strings")
        code = item.strip().upper()
        if len(code) != 2 or not code.isalpha():
            raise ValueError(f"invalid country code: {item!r}")
        if code not in result:
            result.append(code)
    return result


def _migrate_v1_provider_names(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Accept the first Control Plane shape and migrate it before validation."""
    result = deepcopy(dict(payload))
    providers = result.get("providers")
    if not isinstance(providers, Mapping):
        return result
    converted = dict(providers)
    if "kalshi" in converted and "kalshi_us" not in converted:
        converted["kalshi_us"] = converted.pop("kalshi")
    if "polymarket" in converted and "polymarket_intl" not in converted:
        converted["polymarket_intl"] = converted.pop("polymarket")
    result["providers"] = converted
    return result


def validate_control_plane(payload: Mapping[str, Any]) -> dict[str, Any]:
    payload = _migrate_v1_provider_names(payload)
    if payload.get("version") != 1:
        raise ValueError("unsupported control-plane version")
    providers = payload.get("providers")
    if not isinstance(providers, Mapping):
        raise ValueError("providers must be an object")
    normalized = deepcopy(DEFAULT_CONTROL_PLANE)
    for provider_key in normalized["providers"]:
        incoming = providers.get(provider_key, normalized["providers"][provider_key])
        if not isinstance(incoming, Mapping):
            raise ValueError(f"missing provider: {provider_key}")
        unknown = set(incoming) - _ALLOWED_PROVIDER_KEYS
        if unknown:
            raise ValueError(f"unsupported {provider_key} settings: {', '.join(sorted(unknown))}")
        target = normalized["providers"][provider_key]
        for key in ("enabled", "commercial_verified"):
            if not isinstance(incoming.get(key), bool):
                raise ValueError(f"{provider_key}.{key} must be boolean")
            target[key] = incoming[key]
        for key in ("partner_id", "affiliate_id", "referral_code", "tracking_parameter", "tracking_value"):
            value = incoming.get(key, "")
            if not isinstance(value, str) or len(value.strip()) > 250:
                raise ValueError(f"{provider_key}.{key} must be bounded text")
            target[key] = value.strip()
        model = incoming.get("compensation_model", "pending")
        if model not in _ALLOWED_MODELS:
            raise ValueError(f"unsupported compensation model for {provider_key}")
        target["compensation_model"] = model
        rate = incoming.get("compensation_rate")
        if rate is not None:
            if isinstance(rate, bool) or not isinstance(rate, (int, float)) or rate < 0 or rate > 100:
                raise ValueError(f"{provider_key}.compensation_rate must be between 0 and 100")
            rate = float(rate)
        target["compensation_rate"] = rate
        target["allowed_countries"] = _countries(incoming.get("allowed_countries", []))
        target["blocked_countries"] = _countries(incoming.get("blocked_countries", []))
        if set(target["allowed_countries"]) & set(target["blocked_countries"]):
            raise ValueError(f"{provider_key} country cannot be both allowed and blocked")
        if target["commercial_verified"] and not any(
            target[key] for key in ("partner_id", "affiliate_id", "referral_code")
        ):
            raise ValueError(f"{provider_key} cannot be commercial_verified without a commercial identifier")
        if bool(target["tracking_parameter"]) != bool(target["tracking_value"]):
            raise ValueError(f"{provider_key} tracking parameter and value must be configured together")

    acquisition = payload.get("acquisition", DEFAULT_CONTROL_PLANE["acquisition"])
    if not isinstance(acquisition, Mapping) or not isinstance(acquisition.get("channels"), Mapping):
        raise ValueError("acquisition.channels must be an object")
    for channel in normalized["acquisition"]["channels"]:
        value = acquisition["channels"].get(channel, True)
        if not isinstance(value, bool):
            raise ValueError(f"acquisition channel {channel} must be boolean")
        normalized["acquisition"]["channels"][channel] = value

    publishing = payload.get("publishing", DEFAULT_CONTROL_PLANE["publishing"])
    if not isinstance(publishing, Mapping) or not isinstance(publishing.get("require_preview", True), bool):
        raise ValueError("publishing.require_preview must be boolean")
    normalized["publishing"]["require_preview"] = publishing.get("require_preview", True)
    return normalized


class ControlPlaneStore:
    """Draft/publish control plane with durable revisions and audit history."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
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
                CREATE TABLE IF NOT EXISTS control_plane_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    draft_json TEXT NOT NULL,
                    published_json TEXT NOT NULL,
                    published_version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS control_plane_revisions (
                    version INTEGER PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    published_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS control_plane_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    version INTEGER,
                    occurred_at TEXT NOT NULL
                );
                """
            )
            row = connection.execute("SELECT singleton FROM control_plane_state WHERE singleton=1").fetchone()
            if row is None:
                payload = json.dumps(DEFAULT_CONTROL_PLANE, sort_keys=True, separators=(",", ":"))
                connection.execute(
                    "INSERT INTO control_plane_state(singleton,draft_json,published_json,published_version,updated_at) VALUES(1,?,?,0,?)",
                    (payload, payload, _now()),
                )

    @staticmethod
    def _decode(raw: str) -> dict[str, Any]:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("stored control plane must be an object")
        return validate_control_plane(value)

    def snapshot(self) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM control_plane_state WHERE singleton=1").fetchone()
        assert row is not None
        return {
            "draft": self._decode(row["draft_json"]),
            "published": self._decode(row["published_json"]),
            "published_version": row["published_version"],
            "updated_at": row["updated_at"],
        }

    def published(self) -> dict[str, Any]:
        return self.snapshot()["published"]

    def save_draft(self, payload: Mapping[str, Any], actor: str = "admin") -> dict[str, Any]:
        normalized = validate_control_plane(payload)
        encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        now = _now()
        with self._connection() as connection:
            connection.execute(
                "UPDATE control_plane_state SET draft_json=?, updated_at=? WHERE singleton=1",
                (encoded, now),
            )
            connection.execute(
                "INSERT INTO control_plane_audit(action,actor,version,occurred_at) VALUES('save_draft',?,NULL,?)",
                (actor[:120], now),
            )
        return self.snapshot()

    def publish(self, actor: str = "admin") -> dict[str, Any]:
        now = _now()
        with self._connection() as connection:
            row = connection.execute("SELECT draft_json,published_version FROM control_plane_state WHERE singleton=1").fetchone()
            assert row is not None
            payload = validate_control_plane(self._decode(row["draft_json"]))
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            version = int(row["published_version"]) + 1
            connection.execute(
                "UPDATE control_plane_state SET published_json=?, published_version=?, updated_at=? WHERE singleton=1",
                (encoded, version, now),
            )
            connection.execute(
                "INSERT INTO control_plane_revisions(version,payload_json,actor,published_at) VALUES(?,?,?,?)",
                (version, encoded, actor[:120], now),
            )
            connection.execute(
                "INSERT INTO control_plane_audit(action,actor,version,occurred_at) VALUES('publish',?,?,?)",
                (actor[:120], version, now),
            )
        return self.snapshot()

    def rollback(self, version: int, actor: str = "admin") -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT payload_json FROM control_plane_revisions WHERE version=?", (version,)).fetchone()
        if row is None:
            raise KeyError(version)
        self.save_draft(self._decode(row["payload_json"]), actor)
        return self.publish(actor)

    def audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT action,actor,version,occurred_at FROM control_plane_audit ORDER BY audit_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
