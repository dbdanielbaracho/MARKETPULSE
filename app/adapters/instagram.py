from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx


_GRAPH_VERSION = re.compile(r"^v[1-9][0-9]*\.[0-9]+$")


@dataclass(frozen=True)
class InstagramPublishResult:
    media_id: str


def instagram_configured() -> bool:
    try:
        _config()
    except (RuntimeError, ValueError):
        return False
    return True


def _config() -> tuple[str, str, str]:
    token = os.getenv("MP_INSTAGRAM_ACCESS_TOKEN", "").strip()
    user_id = os.getenv("MP_INSTAGRAM_USER_ID", "").strip()
    version = os.getenv("MP_META_GRAPH_VERSION", "").strip()
    if not token or not user_id or not version:
        raise RuntimeError("Instagram distribution is not configured")
    if any(ch.isspace() for ch in token) or not user_id.isdigit() or not _GRAPH_VERSION.fullmatch(version):
        raise ValueError("Instagram provider configuration is invalid")
    return token, user_id, version


def _https_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Instagram media URL must be an absolute HTTPS URL without credentials")
    return value


async def _post_with_retry(http: httpx.AsyncClient, url: str, *, data: dict[str, str], attempts: int, timeout_seconds: float) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await http.post(url, data=data, timeout=timeout_seconds)
            if response.status_code == 429 or response.status_code >= 500:
                raise httpx.HTTPStatusError("transient Instagram provider response", request=response.request, response=response)
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
            await asyncio.sleep(0.15 * (attempt + 1))
    raise RuntimeError("Instagram distribution failed after bounded retries") from last_error


async def publish_instagram_image(
    image_url: str,
    caption: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_seconds: float = 10.0,
    attempts: int = 2,
) -> InstagramPublishResult:
    """Publish one externally hosted image through Meta's Instagram publishing flow."""
    if not caption.strip() or len(caption) > 2200:
        raise ValueError("Instagram caption must contain 1..2200 characters")
    if attempts < 1 or attempts > 3 or timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("invalid Instagram retry/timeout bounds")
    media_url = _https_url(image_url)
    token, user_id, version = _config()
    base = f"https://graph.facebook.com/{version}/{user_id}"
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout_seconds)
    try:
        container = await _post_with_retry(
            http,
            f"{base}/media",
            data={"image_url": media_url, "caption": caption, "access_token": token},
            attempts=attempts,
            timeout_seconds=timeout_seconds,
        )
        creation_id = str(container.json().get("id") or "").strip()
        if not creation_id:
            raise RuntimeError("Instagram provider did not return a creation id")
        published = await _post_with_retry(
            http,
            f"{base}/media_publish",
            data={"creation_id": creation_id, "access_token": token},
            attempts=attempts,
            timeout_seconds=timeout_seconds,
        )
        media_id = str(published.json().get("id") or "").strip()
        if not media_id:
            raise RuntimeError("Instagram provider did not return a media id")
        return InstagramPublishResult(media_id=media_id)
    finally:
        if own_client:
            await http.aclose()
