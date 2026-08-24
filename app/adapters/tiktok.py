from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class TikTokUploadResult:
    publish_id: str


def tiktok_configured() -> bool:
    token = os.getenv("MP_TIKTOK_ACCESS_TOKEN", "").strip()
    return bool(token and not any(ch.isspace() for ch in token))


def _token() -> str:
    token = os.getenv("MP_TIKTOK_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TikTok distribution is not configured")
    if any(ch.isspace() for ch in token):
        raise ValueError("TikTok access token is invalid")
    return token


def _video_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("TikTok video URL must be an absolute HTTPS URL without credentials")
    return value


async def init_tiktok_inbox_video_upload(
    video_url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_seconds: float = 10.0,
    attempts: int = 2,
) -> TikTokUploadResult:
    """Initialize TikTok's user-mediated inbox upload using a verified PULL_FROM_URL source.

    The user must finish review/posting in TikTok. This intentionally does not call
    Direct Post and therefore cannot silently publish on a creator's behalf.
    """
    if attempts < 1 or attempts > 3 or timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("invalid TikTok retry/timeout bounds")
    source_url = _video_url(video_url)
    token = _token()
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout_seconds)
    endpoint = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
    payload = {"source_info": {"source": "PULL_FROM_URL", "video_url": source_url}}
    try:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await http.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
                    json=payload,
                    timeout=timeout_seconds,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError("transient TikTok provider response", request=response.request, response=response)
                response.raise_for_status()
                body = response.json()
                error = body.get("error")
                if isinstance(error, dict) and error.get("code") not in (None, "", "ok"):
                    raise RuntimeError("TikTok provider rejected the upload initialization")
                data = body.get("data")
                publish_id = str(data.get("publish_id") or "").strip() if isinstance(data, dict) else ""
                if not publish_id:
                    raise RuntimeError("TikTok provider did not return a publish id")
                return TikTokUploadResult(publish_id=publish_id)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break
                await asyncio.sleep(0.15 * (attempt + 1))
        raise RuntimeError("TikTok upload initialization failed after bounded retries") from last_error
    finally:
        if own_client:
            await http.aclose()
