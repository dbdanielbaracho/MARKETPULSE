from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.adapters.instagram import instagram_configured, publish_instagram_image
from app.adapters.tiktok import init_tiktok_inbox_video_upload, tiktok_configured
from app.adapters.whatsapp import send_whatsapp_template, whatsapp_configured


class QueueTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: list[tuple[int, dict[str, object]]]):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return httpx.Response(status, request=request, json=body)


def _meta(monkeypatch):
    monkeypatch.setenv("MP_META_GRAPH_VERSION", "v99.0")


def test_instagram_requires_complete_configuration(monkeypatch):
    monkeypatch.setenv("MP_INSTAGRAM_ACCESS_TOKEN", "secret")
    monkeypatch.delenv("MP_INSTAGRAM_USER_ID", raising=False)
    monkeypatch.delenv("MP_META_GRAPH_VERSION", raising=False)
    assert instagram_configured() is False
    monkeypatch.setenv("MP_INSTAGRAM_USER_ID", "12345")
    _meta(monkeypatch)
    assert instagram_configured() is True


def test_instagram_uses_container_then_publish_and_hides_secret(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_INSTAGRAM_ACCESS_TOKEN", "supersecret")
        monkeypatch.setenv("MP_INSTAGRAM_USER_ID", "12345")
        _meta(monkeypatch)
        transport = QueueTransport([(200, {"id": "container-1"}), (200, {"id": "media-9"})])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await publish_instagram_image("https://cdn.example.com/post.jpg", "PrediBeacon update", client=client)
        return result, transport

    result, transport = asyncio.run(run())
    assert result.media_id == "media-9"
    assert "supersecret" not in repr(result)
    assert [r.url.path for r in transport.requests] == ["/v99.0/12345/media", "/v99.0/12345/media_publish"]
    first = parse_qs(transport.requests[0].content.decode())
    assert first["image_url"] == ["https://cdn.example.com/post.jpg"]
    assert first["caption"] == ["PrediBeacon update"]


def test_instagram_rejects_non_https_before_network(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_INSTAGRAM_ACCESS_TOKEN", "secret")
        monkeypatch.setenv("MP_INSTAGRAM_USER_ID", "12345")
        _meta(monkeypatch)
        transport = QueueTransport([(200, {"id": "unused"})])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ValueError, match="HTTPS"):
                await publish_instagram_image("http://example.com/x.jpg", "caption", client=client)
        return transport
    assert asyncio.run(run()).requests == []


def test_whatsapp_is_template_only_and_returns_provider_message_id(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_WHATSAPP_ACCESS_TOKEN", "wa-secret")
        monkeypatch.setenv("MP_WHATSAPP_PHONE_NUMBER_ID", "98765")
        _meta(monkeypatch)
        transport = QueueTransport([(200, {"messages": [{"id": "wamid.123"}]})])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await send_whatsapp_template("+14155552671", "market_update", "en_US", client=client)
        return result, transport

    result, transport = asyncio.run(run())
    assert result.message_id == "wamid.123"
    assert whatsapp_configured() is True
    request = transport.requests[0]
    assert request.url.path == "/v99.0/98765/messages"
    payload = json.loads(request.content)
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "market_update"
    assert "wa-secret" not in repr(result)


def test_whatsapp_invalid_recipient_never_contacts_provider(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_WHATSAPP_ACCESS_TOKEN", "secret")
        monkeypatch.setenv("MP_WHATSAPP_PHONE_NUMBER_ID", "98765")
        _meta(monkeypatch)
        transport = QueueTransport([(200, {"messages": [{"id": "unused"}]})])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ValueError, match="international"):
                await send_whatsapp_template("not-a-number", "market_update", "en_US", client=client)
        return transport
    assert asyncio.run(run()).requests == []


def test_tiktok_initializes_user_mediated_inbox_upload(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_TIKTOK_ACCESS_TOKEN", "tt-secret")
        transport = QueueTransport([(200, {"data": {"publish_id": "v_inbox_url~123"}, "error": {"code": "ok"}})])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await init_tiktok_inbox_video_upload("https://media.example.com/video.mp4", client=client)
        return result, transport

    result, transport = asyncio.run(run())
    assert tiktok_configured() is True
    assert result.publish_id == "v_inbox_url~123"
    request = transport.requests[0]
    assert request.url.path == "/v2/post/publish/inbox/video/init/"
    payload = json.loads(request.content)
    assert payload == {"source_info": {"source": "PULL_FROM_URL", "video_url": "https://media.example.com/video.mp4"}}
    assert "tt-secret" not in repr(result)


def test_tiktok_transient_failure_is_bounded(monkeypatch):
    async def run():
        monkeypatch.setenv("MP_TIKTOK_ACCESS_TOKEN", "tt-secret")
        transport = QueueTransport([(503, {}), (200, {"data": {"publish_id": "ok"}, "error": {"code": "ok"}})])
        async with httpx.AsyncClient(transport=transport) as client:
            result = await init_tiktok_inbox_video_upload("https://media.example.com/video.mp4", client=client, attempts=2)
        return result, transport
    result, transport = asyncio.run(run())
    assert result.publish_id == "ok"
    assert len(transport.requests) == 2
