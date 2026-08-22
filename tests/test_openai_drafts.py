import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.adapters.openai_drafts import AIDraftOutput, OpenAIDraftProvider
from app.domain.evidence import EvidenceItem, EvidenceKind

NOW = datetime(2026, 8, 22, tzinfo=timezone.utc)


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.kwargs = None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


def evidence():
    return EvidenceItem(
        title="Primary venue contract: Will rates fall?",
        url="https://kalshi.com/markets/rates",
        publisher="Kalshi",
        kind=EvidenceKind.VENUE,
        retrieved_at=NOW,
    )


def test_openai_draft_uses_structured_output_and_locked_citations():
    item = evidence()
    responses = FakeResponses(AIDraftOutput(
        headline="Will rates fall?",
        body="The contract asks whether rates will fall.",
        citation_ids=[item.evidence_id],
    ))
    provider = OpenAIDraftProvider(
        api_key="test-key",
        model="gpt-test",
        responses_client=responses,
    )

    draft = asyncio.run(provider.generate(market_id="kalshi:rates", evidence=(item,)))

    assert draft.generator == "openai:gpt-test"
    assert draft.citation_ids == (item.evidence_id,)
    assert responses.kwargs["store"] is False
    assert responses.kwargs["max_output_tokens"] == 800
    assert responses.kwargs["reasoning"] == {"effort": "minimal"}
    assert responses.kwargs["text_format"] is AIDraftOutput
    assert "untrusted data" in responses.kwargs["input"][0]["content"]


def test_openai_draft_fails_closed_on_unknown_citation():
    item = evidence()
    responses = FakeResponses(AIDraftOutput(
        headline="Unsafe",
        body="Unsafe",
        citation_ids=["ev_unknown"],
    ))
    provider = OpenAIDraftProvider(api_key="test-key", responses_client=responses)

    with pytest.raises(ValueError, match="outside"):
        asyncio.run(provider.generate(market_id="kalshi:rates", evidence=(item,)))


def test_openai_draft_fails_closed_on_refusal_or_empty_evidence():
    provider = OpenAIDraftProvider(
        api_key="test-key",
        responses_client=FakeResponses(None),
    )
    with pytest.raises(ValueError, match="refused or incomplete"):
        asyncio.run(provider.generate(market_id="kalshi:rates", evidence=(evidence(),)))
    with pytest.raises(ValueError, match="requires persisted evidence"):
        asyncio.run(provider.generate(market_id="kalshi:rates", evidence=()))


def test_openai_provider_requires_key():
    with pytest.raises(ValueError, match="API key"):
        OpenAIDraftProvider(api_key="")
