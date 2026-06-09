"""Tests for Phase 9A: PII/PCI transcript redaction."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from calllens.db.models.call import Call, CallStatus
from calllens.db.models.segment import TranscriptSegment
from calllens.db.models.transcript import Transcript
from calllens.redaction.base import RedactionResult
from calllens.redaction.regex import RegexRedactor, _luhn_check
from calllens.seed.rubric import seed_default_rubric

# ─── RegexRedactor unit tests ────────────────────────────────────────────────


class TestRegexRedactor:
    """Unit tests for the deterministic regex redactor."""

    def setup_method(self) -> None:
        self.r = RegexRedactor()

    def test_redacts_email(self) -> None:
        result = self.r.redact("Contact us at alice@example.com for help.")
        assert "[REDACTED_EMAIL]" in result["redacted_text"]
        assert "alice@example.com" not in result["redacted_text"]
        types = [e["type"] for e in result["entities"]]
        assert "EMAIL" in types

    def test_redacts_phone(self) -> None:
        result = self.r.redact("Call me at (555) 123-4567 today.")
        assert "[REDACTED_PHONE]" in result["redacted_text"]
        assert "(555) 123-4567" not in result["redacted_text"]
        types = [e["type"] for e in result["entities"]]
        assert "PHONE" in types

    def test_redacts_ssn(self) -> None:
        result = self.r.redact("My SSN is 123-45-6789.")
        assert "[REDACTED_SSN]" in result["redacted_text"]
        assert "123-45-6789" not in result["redacted_text"]
        types = [e["type"] for e in result["entities"]]
        assert "SSN" in types

    def test_redacts_ipv4(self) -> None:
        result = self.r.redact("Server at 192.168.1.100 responded.")
        assert "[REDACTED_IP]" in result["redacted_text"]
        assert "192.168.1.100" not in result["redacted_text"]
        types = [e["type"] for e in result["entities"]]
        assert "IP" in types

    def test_redacts_luhn_valid_card(self) -> None:
        result = self.r.redact("Card: 4111 1111 1111 1111 on file.")
        assert "[REDACTED_CARD]" in result["redacted_text"]
        assert "4111" not in result["redacted_text"]

    def test_does_not_redact_luhn_invalid_number(self) -> None:
        result = self.r.redact("Number 1234 5678 9012 3456 is not a card.")
        assert "[REDACTED_CARD]" not in result["redacted_text"]

    def test_typed_placeholders_correct(self) -> None:
        text = "Email alice@test.com, SSN 999-88-7777, IP 10.0.0.1"
        result = self.r.redact(text)
        assert "[REDACTED_EMAIL]" in result["redacted_text"]
        assert "[REDACTED_SSN]" in result["redacted_text"]
        assert "[REDACTED_IP]" in result["redacted_text"]

    def test_idempotent_on_already_redacted(self) -> None:
        text = "Contact [REDACTED_EMAIL] at [REDACTED_PHONE] please."
        result = self.r.redact(text)
        assert result["redacted_text"] == text
        assert result["entities"] == []

    def test_entity_offsets_reference_original(self) -> None:
        text = "Email: alice@example.com ok"
        result = self.r.redact(text)
        assert len(result["entities"]) == 1
        ent = result["entities"][0]
        assert ent["type"] == "EMAIL"
        assert text[ent["start"] : ent["end"]] == "alice@example.com"

    def test_no_entities_returns_original(self) -> None:
        text = "Hello, how can I help you today?"
        result = self.r.redact(text)
        assert result["redacted_text"] == text
        assert result["entities"] == []

    def test_multiple_entities(self) -> None:
        text = "Email alice@test.com and call 555-123-4567."
        result = self.r.redact(text)
        assert "[REDACTED_EMAIL]" in result["redacted_text"]
        assert "[REDACTED_PHONE]" in result["redacted_text"]
        assert len(result["entities"]) == 2


class TestLuhnCheck:
    """Luhn algorithm edge cases."""

    def test_valid_visa_test(self) -> None:
        assert _luhn_check("4111111111111111") is True

    def test_valid_mastercard_test(self) -> None:
        assert _luhn_check("5500000000000004") is True

    def test_invalid_number(self) -> None:
        assert _luhn_check("1234567890123456") is False

    def test_too_short(self) -> None:
        assert _luhn_check("123456") is False

    def test_too_long(self) -> None:
        assert _luhn_check("12345678901234567890") is False


# ─── Pipeline integration tests ──────────────────────────────────────────────


@pytest.fixture
def _enable_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure redaction settings are enabled for tests."""
    monkeypatch.setenv("REDACTION_ENABLED", "true")
    monkeypatch.setenv("REDACTION_PROVIDER", "regex")
    monkeypatch.setenv("REDACT_BEFORE_SCORING", "true")
    from calllens.core.config import get_settings

    get_settings.cache_clear()
    yield  # type: ignore[misc]
    get_settings.cache_clear()


@pytest.mark.usefixtures("_enable_redaction")
async def test_pipeline_populates_redacted_text(
    db_engine: object,
    db: AsyncSession,
    client: AsyncClient,
    auth_token: str,
) -> None:
    """Pipeline run populates redacted_text per segment + transcript summary."""
    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        status=CallStatus.transcribed,
        storage_key=f"{call_id}.mp3",
        original_filename="test.mp3",
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(call_id=call_id, language="en")
    db.add(transcript)
    await db.flush()

    seg1 = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=0,
        start_ms=0,
        end_ms=5000,
        text="Please email alice@example.com for help.",
        speaker="agent",
    )
    seg2 = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=1,
        start_ms=5000,
        end_ms=10000,
        text="My SSN is 123-45-6789 and call 555-123-4567.",
        speaker="customer",
    )
    db.add_all([seg1, seg2])
    await db.flush()

    from calllens.services.call_pipeline import _redact_segments

    await _redact_segments(db, transcript)

    assert seg1.redacted_text is not None
    assert "[REDACTED_EMAIL]" in seg1.redacted_text
    assert "alice@example.com" not in seg1.redacted_text

    assert seg2.redacted_text is not None
    assert "[REDACTED_SSN]" in seg2.redacted_text
    assert "[REDACTED_PHONE]" in seg2.redacted_text

    assert transcript.redaction_provider == "regex"
    assert transcript.entities_redacted is not None
    assert transcript.entities_redacted.get("EMAIL", 0) == 1
    assert transcript.entities_redacted.get("SSN", 0) == 1
    assert transcript.entities_redacted.get("PHONE", 0) == 1


@pytest.mark.usefixtures("_enable_redaction")
async def test_redaction_error_leaves_raw_text(
    db_engine: object,
    db: AsyncSession,
    client: AsyncClient,
    auth_token: str,
) -> None:
    """A redaction error per-segment leaves redacted_text = raw text, doesn't fail pipeline."""
    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        status=CallStatus.transcribed,
        storage_key=f"{call_id}.mp3",
        original_filename="test.mp3",
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(call_id=call_id, language="en")
    db.add(transcript)
    await db.flush()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=0,
        start_ms=0,
        end_ms=5000,
        text="Normal text here.",
        speaker="agent",
    )
    db.add(seg)
    await db.flush()

    def broken_redact(text: str) -> RedactionResult:
        raise RuntimeError("Redaction engine crashed")

    with patch("calllens.services.call_pipeline.get_redactor") as mock_factory:
        mock_redactor = RegexRedactor()
        mock_redactor.redact = broken_redact  # type: ignore[assignment]
        mock_factory.return_value = mock_redactor

        from calllens.services.call_pipeline import _redact_segments

        await _redact_segments(db, transcript)

    assert seg.redacted_text == "Normal text here."


# ─── Backfill tests ──────────────────────────────────────────────────────────


@pytest.mark.usefixtures("_enable_redaction")
async def test_backfill_idempotent(
    db_engine: object,
    db: AsyncSession,
    client: AsyncClient,
    auth_token: str,
) -> None:
    """Backfill redacts segments with null redacted_text; second run is a no-op."""
    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        status=CallStatus.transcribed,
        storage_key=f"{call_id}.mp3",
        original_filename="test.mp3",
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(call_id=call_id, language="en")
    db.add(transcript)
    await db.flush()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=0,
        start_ms=0,
        end_ms=5000,
        text="Email: bob@test.org",
        speaker="customer",
    )
    db.add(seg)
    await db.commit()

    assert seg.redacted_text is None

    from calllens.redaction.backfill import backfill_redaction

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    total1 = await backfill_redaction(batch_size=10, session_factory=factory)
    assert total1 == 1

    # Verify it was redacted
    async with factory() as db2:
        from sqlalchemy import select

        result = await db2.execute(select(TranscriptSegment).where(TranscriptSegment.id == seg.id))
        updated_seg = result.scalar_one()
        assert updated_seg.redacted_text is not None
        assert "[REDACTED_EMAIL]" in updated_seg.redacted_text

    # Second run is idempotent
    total2 = await backfill_redaction(batch_size=10, session_factory=factory)
    assert total2 == 0


# ─── Redact-before-scoring tests ──────────────────────────────────────────────


@pytest.mark.usefixtures("_enable_redaction")
async def test_scoring_uses_redacted_text_when_flag_on(
    db_engine: object,
    db: AsyncSession,
    client: AsyncClient,
    auth_token: str,
) -> None:
    """When REDACT_BEFORE_SCORING=true, the graph receives redacted text."""
    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        status=CallStatus.scoring,
        storage_key=f"{call_id}.mp3",
        original_filename="test.mp3",
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(call_id=call_id, language="en")
    db.add(transcript)
    await db.flush()

    raw_text = "My email is alice@secret.com and I need help."
    redacted_text = "My email is [REDACTED_EMAIL] and I need help."

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=0,
        start_ms=0,
        end_ms=5000,
        text=raw_text,
        redacted_text=redacted_text,
        speaker="customer",
    )
    db.add(seg)
    await db.flush()

    await seed_default_rubric(db)
    await db.commit()

    captured_segments: list[dict[str, object]] = []

    async def mock_run_scoring_graph(context: dict[str, object]) -> dict[str, object]:
        from calllens.agents.graph import SupervisorResult

        for s in context["segments"]:  # type: ignore[union-attr]
            captured_segments.append(dict(s))  # type: ignore[arg-type]

        return {
            "supervisor_result": SupervisorResult(
                overall_score=85,
                summary="Good call",
                key_moments=[],
                action_items=[],
                escalate_for_review=False,
                escalation_reason=None,
            ),
            "metrics": type(
                "M",
                (),
                {
                    "talk_listen_ratio": 0.6,
                    "interruptions": 0,
                    "longest_monologue_ms": 2000,
                    "total_turns": 4,
                },
            )(),
            "dimension_scores": {},
        }

    with patch("calllens.services.scoring_service.run_scoring_graph", mock_run_scoring_graph):
        from calllens.services.scoring_service import score_call

        await score_call(call_id, db=db)

    assert len(captured_segments) >= 1
    assert captured_segments[0]["text"] == redacted_text
    assert "alice@secret.com" not in str(captured_segments[0]["text"])


@pytest.mark.usefixtures("_enable_redaction")
async def test_scoring_uses_raw_text_when_flag_off(
    db_engine: object,
    db: AsyncSession,
    client: AsyncClient,
    auth_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When REDACT_BEFORE_SCORING=false, the graph receives raw text."""
    monkeypatch.setenv("REDACT_BEFORE_SCORING", "false")
    from calllens.core.config import get_settings

    get_settings.cache_clear()

    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        status=CallStatus.scoring,
        storage_key=f"{call_id}.mp3",
        original_filename="test.mp3",
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(call_id=call_id, language="en")
    db.add(transcript)
    await db.flush()

    raw_text = "My email is alice@secret.com and I need help."
    redacted_text = "My email is [REDACTED_EMAIL] and I need help."

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=0,
        start_ms=0,
        end_ms=5000,
        text=raw_text,
        redacted_text=redacted_text,
        speaker="customer",
    )
    db.add(seg)
    await db.flush()

    await seed_default_rubric(db)
    await db.commit()

    captured_segments: list[dict[str, object]] = []

    async def mock_run_scoring_graph(context: dict[str, object]) -> dict[str, object]:
        from calllens.agents.graph import SupervisorResult

        for s in context["segments"]:  # type: ignore[union-attr]
            captured_segments.append(dict(s))  # type: ignore[arg-type]

        return {
            "supervisor_result": SupervisorResult(
                overall_score=85,
                summary="Good call",
                key_moments=[],
                action_items=[],
                escalate_for_review=False,
                escalation_reason=None,
            ),
            "metrics": type(
                "M",
                (),
                {
                    "talk_listen_ratio": 0.6,
                    "interruptions": 0,
                    "longest_monologue_ms": 2000,
                    "total_turns": 4,
                },
            )(),
            "dimension_scores": {},
        }

    with patch("calllens.services.scoring_service.run_scoring_graph", mock_run_scoring_graph):
        from calllens.services.scoring_service import score_call

        await score_call(call_id, db=db)

    assert len(captured_segments) >= 1
    assert captured_segments[0]["text"] == raw_text

    get_settings.cache_clear()


# ─── API: transcript endpoint returns redacted fields ─────────────────────────


async def test_transcript_returns_redacted_fields(
    db_engine: object,
    db: AsyncSession,
    client: AsyncClient,
    auth_token: str,
) -> None:
    """GET /calls/{id}/transcript returns text + redacted_text + summary."""
    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        status=CallStatus.transcribed,
        storage_key=f"{call_id}.mp3",
        original_filename="test.mp3",
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(
        call_id=call_id,
        language="en",
        redaction_provider="regex",
        entities_redacted={"EMAIL": 1, "SSN": 1},
    )
    db.add(transcript)
    await db.flush()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=0,
        start_ms=0,
        end_ms=5000,
        text="Email alice@example.com and SSN 123-45-6789.",
        redacted_text="Email [REDACTED_EMAIL] and SSN [REDACTED_SSN].",
        speaker="customer",
    )
    db.add(seg)
    await db.commit()

    resp = await client.get(
        f"/api/v1/calls/{call_id}/transcript",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["redaction_provider"] == "regex"
    assert data["entities_redacted"] == {"EMAIL": 1, "SSN": 1}

    seg_out = data["segments"][0]
    assert seg_out["text"] == "Email alice@example.com and SSN 123-45-6789."
    assert seg_out["redacted_text"] == "Email [REDACTED_EMAIL] and SSN [REDACTED_SSN]."


async def test_transcript_without_redaction_returns_null(
    db_engine: object,
    db: AsyncSession,
    client: AsyncClient,
    auth_token: str,
) -> None:
    """Without redaction, fields are null (backward compatible)."""
    call_id = uuid.uuid4()
    call = Call(
        id=call_id,
        status=CallStatus.transcribed,
        storage_key=f"{call_id}.mp3",
        original_filename="test.mp3",
    )
    db.add(call)
    await db.flush()

    transcript = Transcript(call_id=call_id, language="en")
    db.add(transcript)
    await db.flush()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        sequence=0,
        start_ms=0,
        end_ms=5000,
        text="Hello world",
        speaker="agent",
    )
    db.add(seg)
    await db.commit()

    resp = await client.get(
        f"/api/v1/calls/{call_id}/transcript",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["redaction_provider"] is None
    assert data["entities_redacted"] is None
    assert data["segments"][0]["redacted_text"] is None
