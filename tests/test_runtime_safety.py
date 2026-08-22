import asyncio

import httpx
import pytest

from app.config.runtime import RuntimeFlags
from app.services.retry import RetryPolicy, is_transient_http_error, with_retry


def test_side_effect_flags_default_off(monkeypatch):
    for name in ["MP_AUTOMATED_PUBLISHING", "MP_OUTBOUND_ROUTING", "MP_SOCIAL_DISTRIBUTION"]:
        monkeypatch.delenv(name, raising=False)
    flags = RuntimeFlags.from_env()
    assert flags.automated_publishing is False
    assert flags.outbound_routing is False
    assert flags.social_distribution is False


def test_unknown_venue_fails_closed(monkeypatch):
    flags = RuntimeFlags.from_env()
    assert flags.venue_enabled("unknown") is False


def test_invalid_flag_is_rejected(monkeypatch):
    monkeypatch.setenv("MP_OUTBOUND_ROUTING", "perhaps")
    with pytest.raises(ValueError):
        RuntimeFlags.from_env()


def test_retry_eventually_succeeds():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = asyncio.run(with_retry(operation, RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0)))
    assert result == "ok"
    assert calls == 3


def test_retry_is_bounded():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise RuntimeError("persistent")

    with pytest.raises(RuntimeError):
        asyncio.run(with_retry(operation, RetryPolicy(attempts=2, base_delay_seconds=0, max_delay_seconds=0)))
    assert calls == 2



def http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://venue.example/markets")
    response = httpx.Response(status, request=request)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return exc
    raise AssertionError("status must be an error")


def test_transient_http_error_policy():
    assert is_transient_http_error(http_status_error(429)) is True
    assert is_transient_http_error(http_status_error(503)) is True
    assert is_transient_http_error(http_status_error(400)) is False


def test_permanent_http_error_is_not_retried():
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise http_status_error(400)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            with_retry(
                operation,
                RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
                should_retry=is_transient_http_error,
            )
        )
    assert calls == 1
