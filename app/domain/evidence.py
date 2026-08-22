from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator


class EvidenceKind(StrEnum):
    VENUE = "venue"
    NEWS = "news"
    OFFICIAL = "official"
    RESEARCH = "research"


class EvidenceFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    FUTURE_DATED = "future_dated"
    UNDATED = "undated"


class EvidenceItem(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: HttpUrl
    publisher: str = Field(min_length=1, max_length=200)
    kind: EvidenceKind
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str | None = Field(default=None, max_length=1200)

    @field_validator("published_at", "retrieved_at")
    @classmethod
    def timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value

    @property
    def source_domain(self) -> str:
        return (urlparse(str(self.url)).hostname or "").lower()

    @property
    def canonical_url(self) -> str:
        parsed = urlparse(str(self.url))
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"

    @property
    def evidence_id(self) -> str:
        digest = sha256(f"{self.canonical_url}|{self.title.strip().casefold()}".encode()).hexdigest()[:20]
        return f"ev_{digest}"

    def freshness(self, *, max_age: timedelta, now: datetime | None = None) -> EvidenceFreshness:
        now = now or datetime.now(timezone.utc)
        if self.published_at is None:
            return EvidenceFreshness.UNDATED
        if self.published_at > now + timedelta(minutes=5):
            return EvidenceFreshness.FUTURE_DATED
        if now - self.published_at > max_age:
            return EvidenceFreshness.STALE
        return EvidenceFreshness.FRESH


class EvidenceBundle(BaseModel):
    market_id: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    items: list[EvidenceItem] = Field(default_factory=list, max_length=20)

    @property
    def publisher_count(self) -> int:
        return len({item.source_domain for item in self.items})

    @property
    def latest_published_at(self) -> datetime | None:
        values = [item.published_at for item in self.items if item.published_at is not None]
        return max(values) if values else None

    def deduplicated(self) -> "EvidenceBundle":
        unique: dict[str, EvidenceItem] = {}
        for item in self.items:
            unique.setdefault(item.evidence_id, item)
        return EvidenceBundle(market_id=self.market_id, generated_at=self.generated_at, items=list(unique.values()))
