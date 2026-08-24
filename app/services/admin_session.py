from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from secrets import compare_digest, token_urlsafe

COOKIE_NAME = "predibeacon_admin_session"
SESSION_TTL_SECONDS = 8 * 60 * 60


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _normalized_secret_env(name: str) -> str:
    """Read a secret robustly from deployment UIs without exposing it.

    Railway and similar dashboards normally store the raw value, but operators may
    accidentally paste a value wrapped in matching quotes. We accept that common
    configuration mistake while preserving all interior characters and symbols.
    """
    value = os.getenv(name, "")
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def admin_email() -> str:
    return os.getenv("MP_ADMIN_EMAIL", "admin@predibeacon.com").strip().casefold()


def _admin_password() -> str:
    password = _normalized_secret_env("MP_ADMIN_PASSWORD")
    return password or _normalized_secret_env("MP_ADMIN_TOKEN")


def _session_secret() -> bytes:
    explicit = _normalized_secret_env("MP_ADMIN_SESSION_SECRET")
    if len(explicit) >= 32:
        return explicit.encode("utf-8")
    token = _normalized_secret_env("MP_ADMIN_TOKEN")
    if len(token) >= 32:
        return hashlib.sha256(("predibeacon-admin-session-v1:" + token).encode("utf-8")).digest()
    # When a dedicated admin password exists but no legacy token/session secret does,
    # derive a separate session-signing key. This keeps password-only deployments
    # functional without requiring a second secret to be configured by the operator.
    password = _normalized_secret_env("MP_ADMIN_PASSWORD")
    if len(password) >= 12:
        return hashlib.sha256(("predibeacon-admin-session-v1:password:" + password).encode("utf-8")).digest()
    return b""


def admin_config_status() -> dict[str, object]:
    password = _normalized_secret_env("MP_ADMIN_PASSWORD")
    legacy = _normalized_secret_env("MP_ADMIN_TOKEN")
    session_secret = _session_secret()
    return {
        "password_configured": bool(password),
        "password_valid_length": len(password) >= 12,
        "legacy_token_configured": bool(legacy),
        "session_signing_configured": len(session_secret) >= 32,
        "two_factor_enabled": two_factor_enabled(),
        "configured_email": admin_email(),
    }


def two_factor_enabled() -> bool:
    return bool(_normalized_secret_env("MP_ADMIN_TOTP_SECRET"))


def _totp(secret: str, counter: int) -> str:
    normalized = "".join(secret.split()).upper()
    key = base64.b32decode(normalized + "=" * (-len(normalized) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def verify_totp(code: str | None, now: int | None = None) -> bool:
    secret = _normalized_secret_env("MP_ADMIN_TOTP_SECRET")
    if not secret:
        return True
    candidate = (code or "").strip()
    if len(candidate) != 6 or not candidate.isdigit():
        return False
    stamp = int(now or time.time()) // 30
    try:
        return any(compare_digest(candidate, _totp(secret, stamp + drift)) for drift in (-1, 0, 1))
    except (ValueError, TypeError):
        return False


def verify_credentials(email: str, password: str, totp_code: str | None = None) -> bool:
    expected_password = _admin_password()
    if len(expected_password) < 12:
        return False
    return (
        compare_digest(email.strip().casefold(), admin_email())
        and compare_digest(password, expected_password)
        and verify_totp(totp_code)
    )


def issue_session(email: str, now: int | None = None) -> str:
    secret = _session_secret()
    if len(secret) < 32:
        raise RuntimeError("admin session secret is not configured")
    issued = int(now or time.time())
    payload = {
        "email": email.strip().casefold(),
        "iat": issued,
        "exp": issued + SESSION_TTL_SECONDS,
        "nonce": token_urlsafe(12),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64e(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def read_session(value: str | None, now: int | None = None) -> dict[str, object] | None:
    if not value or "." not in value:
        return None
    secret = _session_secret()
    if len(secret) < 32:
        return None
    body, signature = value.rsplit(".", 1)
    expected = _b64e(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    if not compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64d(body))
        current = int(now or time.time())
        if payload.get("email") != admin_email() or int(payload.get("exp", 0)) <= current:
            return None
        if int(payload.get("iat", current + 1)) > current + 30:
            return None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    return payload
