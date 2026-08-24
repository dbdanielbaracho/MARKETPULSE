from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass

import httpx


_GRAPH_VERSION = re.compile(r"^v[1-9][0-9]*\.[0-9]+$")
_TEMPLATE = re.compile(r"^[a-z0-9_]{1,512}$")
_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(?:_[A-Za-z]{2})?$")


@dataclass(frozen=True)
class WhatsAppSendResult:
    message_id: str


def whatsapp_configured() -> bool:
    try:
        _config()
    except (RuntimeError, ValueError):
        return False
    return True


def _config() -> tuple[str, str, str]:
    token = os.getenv("MP_WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_number_id = os.getenv("MP_WHATSAPP_PHONE_NUMBER_ID", "").strip()
    version = os.getenv("MP_META_GRAPH_VERSION", "").strip()
    if not token or not phone_number_id or not version:
        raise RuntimeError("WhatsApp distribution is not configured")
    if any(ch.isspace() for ch in token) or not phone_number_id.isdigit() or not _GRAPH_VERSION.fullmatch(version):
        raise ValueError("WhatsApp provider configuration is invalid")
    return token, phone_number_id, version


async def send_whatsapp_template(
    to: str,
    template_name: str,
    language_code: str,
    *,
    components: list[dict[str, object]] | None = None,
    client: httpx.AsyncClient | None = None,
    timeout_seconds: float = 10.0,
    attempts: int = 2,
) -> WhatsAppSendResult:
    """Send an approved template message; arbitrary proactive text is intentionally unsupported."""
    recipient = to.strip().lstrip("+")
    if not recipient.isdigit() or len(recipient) < 8 or len(recipient) > 15:
        raise ValueError("WhatsApp recipient must be an international phone number")
    if not _TEMPLATE.fullmatch(template_name) or not _LANGUAGE.fullmatch(language_code):
        raise ValueError("invalid WhatsApp template or language code")
    if attempts < 1 or attempts > 3 or timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("invalid WhatsApp retry/timeout bounds")
    token, phone_number_id, version = _config()
    payload: dict[str, object] = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "template",
        "template": {"name": template_name, "language": {"code": language_code}},
    }
    if components:
        template = payload["template"]
        assert isinstance(template, dict)
        template["components"] = components
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout_seconds)
    endpoint = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    try:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await http.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                    timeout=timeout_seconds,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError("transient WhatsApp provider response", request=response.request, response=response)
                response.raise_for_status()
                messages = response.json().get("messages")
                message_id = str(messages[0].get("id") or "").strip() if isinstance(messages, list) and messages and isinstance(messages[0], dict) else ""
                if not message_id:
                    raise RuntimeError("WhatsApp provider did not return a message id")
                return WhatsAppSendResult(message_id=message_id)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                await asyncio.sleep(0.15 * (attempt + 1))
        raise RuntimeError("WhatsApp distribution failed after bounded retries") from last_error
    finally:
        if own_client:
            await http.aclose()
