"""LangGraph-based multi-agent scoring graph."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from calllens.agents.llm import AgentScore, TimedTranscriptSegmentData, get_llm_provider
from calllens.agents.metrics import ConversationMetrics, compute_metrics
from calllens.agents.specialists import FullRubricDimensionData, run_specialist
from calllens.agents.supervisor import SupervisorResult, run_supervisor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State and I/O types
# ---------------------------------------------------------------------------


def _merge_scores(
    left: dict[str, AgentScore],
    right: dict[str, AgentScore],
) -> dict[str, AgentScore]:
    """Reducer: merge parallel specialist writes; right takes precedence on key conflict."""
    return {**left, **right}


class GraphState(TypedDict):
    """Internal state flowing through the scoring graph."""

    # Input — set once at graph entry
    segments: list[TimedTranscriptSegmentData]
    segments_by_id: dict[uuid.UUID, TimedTranscriptSegmentData]
    dimensions: list[FullRubricDimensionData]

    # Computed by preprocess node
    metrics: ConversationMetrics | None

    # Accumulated across parallel specialist node invocations via reducer
    dimension_scores: Annotated[dict[str, AgentScore], _merge_scores]

    # Computed by supervisor node
    supervisor_result: SupervisorResult | None


class SpecialistInput(TypedDict):
    """Minimal state sent to each specialist node invocation via Send."""

    segments: list[TimedTranscriptSegmentData]
    metrics: ConversationMetrics
    dimension: FullRubricDimensionData
    # Included so LangGraph can apply the reducer on output from this node
    dimension_scores: Annotated[dict[str, AgentScore], _merge_scores]


class ScoringContext(TypedDict):
    """External input to run_scoring_graph — caller provides this."""

    segments: list[TimedTranscriptSegmentData]
    dimensions: list[FullRubricDimensionData]


class ScoringResult(TypedDict):
    """External output of run_scoring_graph — returned to Phase 4B for persistence."""

    dimension_scores: dict[str, AgentScore]
    metrics: ConversationMetrics
    supervisor_result: SupervisorResult


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def preprocess_node(state: GraphState) -> dict[str, Any]:
    """Compute ConversationMetrics from timed segments (no LLM).

    Args:
        state: Full graph state with segments populated.

    Returns:
        State update dict setting ``metrics``.
    """
    metrics = compute_metrics(state["segments"])
    logger.info(
        "preprocess: metrics computed",
        extra={
            "total_turns": metrics.total_turns,
            "interruptions": metrics.interruptions,
            "longest_monologue_ms": metrics.longest_monologue_ms,
        },
    )
    return {"metrics": metrics}


async def run_specialist_node(state: SpecialistInput) -> dict[str, Any]:
    """Score a single dimension by dispatching to the appropriate specialist agent.

    Receives per-invocation state via Send; writes one entry to dimension_scores.
    The _merge_scores reducer accumulates concurrent writes from parallel invocations.

    Args:
        state: SpecialistInput with the dimension to score plus segments/metrics.

    Returns:
        State update dict: ``{"dimension_scores": {dim_key: AgentScore}}``.
    """
    dim = state["dimension"]
    provider = get_llm_provider()

    score = await run_specialist(
        dimension=dim,
        segments=state["segments"],
        metrics=state["metrics"],
        provider=provider,
    )

    logger.info(
        "specialist: dimension scored",
        extra={
            "key": dim["key"],
            "score": score.score,
            "is_supported": score.is_supported,
        },
    )
    return {"dimension_scores": {dim["key"]: score}}


async def supervisor_node(state: GraphState) -> dict[str, Any]:
    """Aggregate dimension scores, apply escalation rules, generate narrative.

    Args:
        state: Full graph state with dimension_scores and metrics populated.

    Returns:
        State update dict setting ``supervisor_result``.
    """
    metrics = state["metrics"]
    if metrics is None:
        raise RuntimeError("supervisor_node: metrics not set — preprocess must run first")

    provider = get_llm_provider()

    result = await run_supervisor(
        dimension_scores=state["dimension_scores"],
        dimensions=state["dimensions"],
        segments=state["segments"],
        provider=provider,
    )

    logger.info(
        "supervisor: result produced",
        extra={
            "overall_score": result.overall_score,
            "escalate": result.escalate_for_review,
        },
    )
    return {"supervisor_result": result}


# ---------------------------------------------------------------------------
# Conditional edge: fan-out dispatch
# ---------------------------------------------------------------------------


def dispatch_specialists(state: GraphState) -> list[Any]:
    """Return a list of Send objects for each active (scorable) dimension.

    Dispatches specialist nodes for dimensions with kind "score" or "ratio".
    Dimensions with kind "bool" (e.g., outcome) are excluded — the supervisor
    handles boolean outcome aggregation directly.

    When no active dimensions exist, returns a single Send to "supervisor"
    so the graph still terminates correctly with an empty dimension_scores dict.

    Args:
        state: Graph state after preprocess has set ``metrics``.

    Returns:
        List of Send objects — one per active dimension, or one Send to
        "supervisor" when no scorable dimensions are present.
    """
    metrics = state["metrics"]
    if metrics is None:
        logger.warning("dispatch_specialists: metrics not ready; routing to supervisor")
        return [Send("supervisor", state)]

    sends: list[Any] = []
    for dim in state["dimensions"]:
        # "bool" (outcome) is excluded — supervisor handles it directly
        if dim["kind"] == "bool":
            continue
        sends.append(
            Send(
                "run_specialist",
                SpecialistInput(
                    segments=state["segments"],
                    metrics=metrics,
                    dimension=dim,
                    dimension_scores={},
                ),
            )
        )

    if not sends:
        logger.warning("dispatch_specialists: no active dimensions; routing directly to supervisor")
        return [Send("supervisor", state)]

    return sends


# ---------------------------------------------------------------------------
# Graph compilation (module-level — built once on import)
# ---------------------------------------------------------------------------


def _build_graph() -> Any:
    """Construct and compile the LangGraph scoring graph.

    Graph topology:
        START -> preprocess -> [conditional: dispatch_specialists]
                                      | (one Send per active dimension)
                             run_specialist (xN, parallel)
                                      |
                             supervisor -> END

    Returns:
        A compiled LangGraph CompiledStateGraph.
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)

    builder.add_node("preprocess", preprocess_node)
    builder.add_node("run_specialist", run_specialist_node)
    builder.add_node("supervisor", supervisor_node)

    builder.add_edge(START, "preprocess")
    builder.add_conditional_edges(
        "preprocess",
        dispatch_specialists,
        ["run_specialist", "supervisor"],
    )
    builder.add_edge("run_specialist", "supervisor")
    builder.add_edge("supervisor", END)

    return builder.compile()


_graph: Any = _build_graph()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_scoring_graph(context: ScoringContext) -> ScoringResult:
    """Run the full multi-agent scoring graph and return a structured result.

    This function is the sole public entry point for the scoring graph. It is
    called by the scoring service (Phase 4B) to score a call. No DB access
    happens here; the result is pure in-memory data ready for persistence.

    Args:
        context: ScoringContext with timed segments and active rubric dimensions.

    Returns:
        A ScoringResult with per-dimension AgentScores, ConversationMetrics,
        and the SupervisorResult (overall score, escalation, narrative).

    Raises:
        RuntimeError: If the graph fails to produce metrics or supervisor_result.
    """
    initial_state: GraphState = {
        "segments": context["segments"],
        "segments_by_id": {s["id"]: s for s in context["segments"]},
        "dimensions": context["dimensions"],
        "metrics": None,
        "dimension_scores": {},
        "supervisor_result": None,
    }

    final_state: GraphState = await _graph.ainvoke(initial_state)

    metrics = final_state.get("metrics")
    supervisor_result = final_state.get("supervisor_result")

    if metrics is None:
        raise RuntimeError("run_scoring_graph: graph completed without setting metrics")
    if supervisor_result is None:
        raise RuntimeError("run_scoring_graph: graph completed without setting supervisor_result")

    return ScoringResult(
        dimension_scores=final_state.get("dimension_scores", {}),
        metrics=metrics,
        supervisor_result=supervisor_result,
    )
