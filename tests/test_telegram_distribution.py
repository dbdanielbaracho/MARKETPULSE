from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.adapters.telegram import send_telegram_message, telegram_configured


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, statuses: list[int]):
        self.statuses = list(statuses)
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status = self.statuses.pop(0)
        body = {"ok": True, "result": {"message_id": 321}} if status == 200 else {"ok": False}
        return httpx.Response(status, request=request, json=body)


def test_configuration_requires_token_and_destination(monkeypatch):
    monkeypatch.delenv("MP_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MP_TELEGRAM_CHAT_ID", raising=False)
    assert telegram_configured() is False
    monkeypatch.setenv("MP_TELEGRAM_BOT_TOKEN", "123:abc")
    assert telegram_configured() is False
    monkeypatch.setenv("MP_TELEGRAM_CHAT_ID", "@predibeacon")
    assert telegram_configured() is True


def test_send_uses_official_bot_endpoint_and_does_not_return_secret(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_TELEGRAM_BOT_TOKEN", "123:supersecret")
        monkeypatch.setenv("MP_TELEGRAM_CHAT_ID", "@predibeacon")
        transport = RecordingTransport([200])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await send_telegram_message("PrediBeacon update", client=client)
        return result, transport

    result, transport = asyncio.run(run())
    assert result.message_id == 321
    assert result.chat_id == "@predibeacon"
    request = transport.requests[0]
    assert request.url.host == "api.telegram.org"
    assert request.url.path == "/bot123:supersecret/sendMessage"
    payload = json.loads(request.content)
    assert payload["chat_id"] == "@predibeacon"
    assert payload["text"] == "PrediBeacon update"
    assert "supersecret" not in repr(result)


def test_transient_provider_failure_is_retried_bounded(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_TELEGRAM_BOT_TOKEN", "123:secret")
        monkeypatch.setenv("MP_TELEGRAM_CHAT_ID", "@predibeacon")
        transport = RecordingTransport([503, 200])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await send_telegram_message("Update", client=client, attempts=2)
        return result, transport

    result, transport = asyncio.run(run())
    assert result.message_id == 321
    assert len(transport.requests) == 2


def test_provider_failure_fails_closed_after_retry_budget(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_TELEGRAM_BOT_TOKEN", "123:secret")
        monkeypatch.setenv("MP_TELEGRAM_CHAT_ID", "@predibeacon")
        transport = RecordingTransport([503, 503])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="bounded retries"):
                await send_telegram_message("Update", client=client, attempts=2)
        return transport

    transport = asyncio.run(run())
    assert len(transport.requests) == 2


def test_invalid_message_never_contacts_provider(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_TELEGRAM_BOT_TOKEN", "123:secret")
        monkeypatch.setenv("MP_TELEGRAM_CHAT_ID", "@predibeacon")
        transport = RecordingTransport([200])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ValueError):
                await send_telegram_message("", client=client)
        return transport

    transport = asyncio.run(run())
    assert transport.requests == []
