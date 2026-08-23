from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class TelegramSendResult:
    message_id: int
    chat_id: str


def telegram_configured() -> bool:
    token = os.getenv("MP_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("MP_TELEGRAM_CHAT_ID", "").strip()
    return bool(token and chat_id)


def _config() -> tuple[str, str]:
    token = os.getenv("MP_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("MP_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Telegram distribution is not configured")
    if any(ch.isspace() for ch in token):
        raise ValueError("MP_TELEGRAM_BOT_TOKEN is invalid")
    if len(chat_id) > 200:
        raise ValueError("MP_TELEGRAM_CHAT_ID is invalid")
    return token, chat_id


async def send_telegram_message(
    text: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_seconds: float = 10.0,
    attempts: int = 2,
) -> TelegramSendResult:
    """Send an approved text message through Telegram Bot API.

    The caller remains responsible for PrediBeacon's editorial/country/contract
    readiness gates. This adapter only performs the provider call and fails
    closed on provider errors. Tokens are used solely in the request endpoint
    and never returned from this function.
    """
    if not text.strip() or len(text) > 4096:
        raise ValueError("Telegram text must contain 1..4096 characters")
    if attempts < 1 or attempts > 3:
        raise ValueError("attempts must be between 1 and 3")
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("timeout_seconds must be between 0 and 30")

    token, chat_id = _config()
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout_seconds)
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await http.post(
                    endpoint,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "disable_web_page_preview": False,
                    },
                    timeout=timeout_seconds,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "transient Telegram provider response",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
                if payload.get("ok") is not True or not isinstance(payload.get("result"), dict):
                    raise RuntimeError("Telegram provider returned an invalid response")
                message_id = payload["result"].get("message_id")
                if not isinstance(message_id, int):
                    raise RuntimeError("Telegram response did not contain a message id")
                return TelegramSendResult(message_id=message_id, chat_id=chat_id)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                await asyncio.sleep(0.15 * (attempt + 1))
        raise RuntimeError("Telegram distribution failed after bounded retries") from last_error
    finally:
        if own_client:
            await http.aclose()
