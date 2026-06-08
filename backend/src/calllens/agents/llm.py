"""LLM provider abstractions, schemas, and factory for structured scoring."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Protocol, TypedDict, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from calllens.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TypedDict — avoids importing ORM models
# ---------------------------------------------------------------------------


class TranscriptSegmentData(TypedDict):
    """Lightweight dict representation of a TranscriptSegment row."""

    id: uuid.UUID
    sequence: int
    text: str
    speaker: str


class TimedTranscriptSegmentData(TypedDict):
    """Transcript segment with timing fields for metrics computation."""

    id: uuid.UUID
    sequence: int
    text: str
    speaker: str
    start_ms: int
    end_ms: int


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class EvidenceRef(BaseModel):
    """A reference to a specific segment quote used as evidence."""

    segment_id: uuid.UUID
    quote: str = Field(min_length=1)  # verbatim excerpt from that segment


class AgentScore(BaseModel):
    """Structured output from an LLM scoring agent."""

    score: int  # 0-100
    confidence: float  # 0.0-1.0
    rationale: str
    evidence: list[EvidenceRef]
    is_supported: bool = True  # set to False when all evidence was dropped by validator

    @field_validator("score", mode="before")
    @classmethod
    def clamp_score(cls, v: object) -> int:
        """Clamp score to [0, 100]."""
        return max(0, min(100, int(v)))  # type: ignore[call-overload,no-any-return]

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: object) -> float:
        """Clamp confidence to [0.0, 1.0]."""
        return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]


class KeyMomentRef(BaseModel):
    """A notable moment in the call tied to a specific transcript segment."""

    segment_id: uuid.UUID
    label: str  # e.g. "Agent empathy peak", "Customer objection"


class SupervisorNarrative(BaseModel):
    """LLM-generated narrative output from the supervisor node."""

    summary: str
    key_moments: list[KeyMomentRef]
    action_items: list[str]
    coaching_note: str


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Callable interface for structured LLM scoring."""

    async def structured_score(
        self,
        system: str,
        user: str,
        transcript_segments: list[TranscriptSegmentData],
    ) -> AgentScore:
        """Return a structured score for the given transcript.

        Args:
            system: System prompt directing the model's scoring role.
            user: User-turn prompt containing the transcript and dimension context.
            transcript_segments: All segments of the transcript.

        Returns:
            An AgentScore with score, confidence, rationale, and evidence.
        """
        ...

    async def generate_narrative(
        self,
        system: str,
        user: str,
        transcript_segments: list[TranscriptSegmentData],
    ) -> SupervisorNarrative:
        """Generate a narrative summary for the supervisor.

        Args:
            system: System prompt for the supervisor role.
            user: User prompt containing scored results and transcript context.
            transcript_segments: All base segments (used to pick real segment IDs
                for key_moments in stub; passed for context to real providers).

        Returns:
            A SupervisorNarrative with summary, key_moments, action_items, coaching_note.
        """
        ...


# ---------------------------------------------------------------------------
# StubLLMProvider (default — no deps, no network)
# ---------------------------------------------------------------------------


class StubLLMProvider:
    """Deterministic stub that returns a plausible AgentScore for testing/demo.

    Picks 1-2 real agent segments from the transcript (those with speaker starting
    with "agent" case-insensitively, or else any segment if none qualify). Uses
    verbatim quotes so evidence validation always passes.
    """

    async def structured_score(
        self,
        system: str,
        user: str,
        transcript_segments: list[TranscriptSegmentData],
    ) -> AgentScore:
        """Return a deterministic AgentScore using real segment quotes.

        Args:
            system: System prompt (unused by stub).
            user: User prompt (unused by stub).
            transcript_segments: Segments from which evidence is drawn.

        Returns:
            An AgentScore with score=75, confidence=0.8, and up to 2 evidence refs.
        """
        # Prefer segments where speaker looks like "agent"
        agent_segs = [
            seg for seg in transcript_segments if seg["speaker"].lower().startswith("agent")
        ]
        candidates = agent_segs if agent_segs else transcript_segments
        picked = candidates[:2]

        evidence: list[EvidenceRef] = []
        for seg in picked:
            # Take up to 80 chars — guaranteed verbatim substring
            quote = seg["text"][:80].strip()
            if quote:
                evidence.append(EvidenceRef(segment_id=seg["id"], quote=quote))

        logger.debug("StubLLMProvider returning score=75 with %d evidence ref(s)", len(evidence))

        return AgentScore(
            score=75,
            confidence=0.8,
            rationale=(
                "Stub evaluation: agent demonstrated adequate empathy and maintained "
                "a professional tone throughout the interaction."
            ),
            evidence=evidence,
        )

    async def generate_narrative(
        self,
        system: str,
        user: str,
        transcript_segments: list[TranscriptSegmentData],
    ) -> SupervisorNarrative:
        """Return deterministic plausible narrative with real segment IDs as key_moments.

        Args:
            system: Unused by stub.
            user: Unused by stub.
            transcript_segments: Used to pick real segment IDs for key_moments.

        Returns:
            A SupervisorNarrative with one key_moment referencing a real segment.
        """
        agent_segs = [s for s in transcript_segments if s["speaker"].lower().startswith("agent")]
        candidates = agent_segs if agent_segs else transcript_segments

        key_moments: list[KeyMomentRef] = []
        if candidates:
            key_moments = [
                KeyMomentRef(segment_id=candidates[0]["id"], label="Agent response quality")
            ]

        logger.debug("StubLLMProvider.generate_narrative: returning stub narrative")
        return SupervisorNarrative(
            summary=(
                "Stub: call handled adequately. Agent demonstrated empathy and followed "
                "most of the support call structure."
            ),
            key_moments=key_moments,
            action_items=[
                "Review compliance phrasing with agent.",
                "Encourage more active listening.",
            ],
            coaching_note=(
                "Stub coaching note: focus on script adherence during the opening and "
                "ensure all required compliance phrases are used on every call."
            ),
        )


# ---------------------------------------------------------------------------
# LangchainLLMProvider (optional — guarded against missing dependencies)
# ---------------------------------------------------------------------------

try:
    from langchain_core.exceptions import OutputParserException
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import ValidationError as PydanticValidationError

    class LangchainLLMProvider:
        """LLM provider backed by a LangChain chat model.

        On first call, builds the structured-output chain. On a parse/validation
        failure, retries ONCE with a corrective instruction appended.
        """

        def __init__(self, model_name: str, api_key: str, provider: str) -> None:
            """Initialise without building the chain (deferred to first call).

            Args:
                model_name: Model identifier passed to the LangChain integration.
                api_key: Provider API key.
                provider: One of "google" or "groq".
            """
            self._model_name = model_name
            self._api_key = api_key
            self._provider = provider
            self._chain: Any = None

        def _get_llm(self) -> Any:
            """Construct and return the raw LangChain chat model (not structured).

            Returns:
                A LangChain chat model instance.

            Raises:
                ImportError: If the provider-specific langchain package is missing.
                ValueError: If an unsupported provider name is given.
            """
            if self._provider == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    model=self._model_name,
                    google_api_key=self._api_key,
                )
            elif self._provider == "groq":
                from langchain_groq import ChatGroq

                return ChatGroq(
                    model=self._model_name,  # type: ignore[call-arg]
                    groq_api_key=self._api_key,
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {self._provider!r}")

        def _build_chain(self) -> Any:
            """Construct and cache the structured-output LangChain chain.

            Returns:
                A LangChain Runnable that produces AgentScore instances.
            """
            return self._get_llm().with_structured_output(AgentScore)

        async def structured_score(
            self,
            system: str,
            user: str,
            transcript_segments: list[TranscriptSegmentData],
        ) -> AgentScore:
            """Invoke the LangChain chain and return a validated AgentScore.

            Retries once on validation failure with a corrective instruction.

            Args:
                system: System prompt for the scoring role.
                user: User prompt with transcript and dimension context.
                transcript_segments: All segments (passed through for context).

            Returns:
                A validated AgentScore.

            Raises:
                PydanticValidationError: If the model fails to produce a valid score
                    even after one retry.
            """
            if self._chain is None:
                self._chain = self._build_chain()

            messages = [SystemMessage(content=system), HumanMessage(content=user)]

            try:
                result: AgentScore = await self._chain.ainvoke(messages)
                return result
            except (PydanticValidationError, OutputParserException) as exc:
                logger.warning(
                    "LangchainLLMProvider: validation error on first attempt, retrying. Error: %s",
                    exc,
                )
                corrective = (
                    "\n\nIMPORTANT: Your previous response was invalid. "
                    "Return ONLY a valid JSON object matching the AgentScore schema. "
                    "Ensure score is 0-100, confidence is 0.0-1.0, and every "
                    "evidence segment_id matches one of the provided segment IDs."
                )
                retry_messages = [
                    SystemMessage(content=system),
                    HumanMessage(content=user + corrective),
                ]
                try:
                    result = await self._chain.ainvoke(retry_messages)
                    return result
                except Exception as retry_exc:
                    logger.error(
                        "LangchainLLMProvider: retry also failed",
                        extra={"error": str(retry_exc)},
                    )
                    raise

        async def generate_narrative(
            self,
            system: str,
            user: str,
            transcript_segments: list[TranscriptSegmentData],
        ) -> SupervisorNarrative:
            """Generate supervisor narrative using structured LangChain output.

            Args:
                system: System prompt for the supervisor role.
                user: User prompt with scoring context.
                transcript_segments: Passed for context (not used in chain directly).

            Returns:
                A validated SupervisorNarrative.
            """
            narrative_chain: Any = self._get_llm().with_structured_output(SupervisorNarrative)
            messages = [SystemMessage(content=system), HumanMessage(content=user)]
            try:
                result: SupervisorNarrative = await narrative_chain.ainvoke(messages)
                return result
            except (PydanticValidationError, OutputParserException) as exc:
                logger.warning(
                    "LangchainLLMProvider.generate_narrative: validation error, retrying. Error: %s",
                    exc,
                )
                corrective = (
                    "\n\nIMPORTANT: Your previous response was invalid. "
                    "Return ONLY a valid JSON object matching the SupervisorNarrative schema. "
                    "Ensure all segment_ids in key_moments match IDs from the provided segments."
                )
                retry_messages = [
                    SystemMessage(content=system),
                    HumanMessage(content=user + corrective),
                ]
                result = await narrative_chain.ainvoke(retry_messages)
                return result

except ImportError:
    LangchainLLMProvider = None  # type: ignore[assignment,misc]
    logger.debug("langchain_core not installed; LangchainLLMProvider is unavailable")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider instance.

    Keyed on settings.llm_provider:
    - "stub"      → StubLLMProvider (always available)
    - "langchain" → LangchainLLMProvider (requires agents extras)

    Returns:
        A concrete LLMProvider implementation.

    Raises:
        ImportError: If llm_provider="langchain" but langchain is not installed.
        ValueError: If llm_provider is set to an unrecognised value.
    """
    settings = get_settings()

    if settings.llm_provider == "stub":
        return StubLLMProvider()

    if settings.llm_provider == "langchain":
        if LangchainLLMProvider is None:
            raise ImportError(
                "Install calllens[agents] to use the langchain provider "
                "(pip install 'calllens[agents]')"
            )
        # Determine underlying provider from which API key is set
        if settings.google_api_key:
            return LangchainLLMProvider(
                model_name=settings.llm_model_google,
                api_key=settings.google_api_key,
                provider="google",
            )
        # Fall back to groq
        if not settings.groq_api_key:
            raise ValueError(
                "Set GOOGLE_API_KEY or GROQ_API_KEY when using the langchain provider."
            )
        return LangchainLLMProvider(
            model_name=settings.llm_model_groq,
            api_key=settings.groq_api_key,
            provider="groq",
        )

    raise ValueError(f"Unknown llm_provider: {settings.llm_provider!r}")
