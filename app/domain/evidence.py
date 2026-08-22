from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator


class EvidenceKind(StrEnum):
    VENUE = "venue"
    NEWS = "news"
    OFFICIAL = "official"
    RESEARCH = "research"


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
    def evidence_id(self) -> str:
        digest = sha256(f"{self.url}|{self.published_at}|{self.title}".encode()).hexdigest()[:20]
        return f"ev_{digest}"


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
