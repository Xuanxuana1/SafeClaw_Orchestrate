"""Tests for knowledge store, failure classification, and credit assignment."""

from ontoplan_mvp.knowledge_store import (
    ArtifactFlowStats,
    ExecutionOutcome,
    FailureType,
    KnowledgeStore,
    NodeExecResult,
    PatternRecord,
)
from ontoplan_mvp.models import PatternTemplate, WorkflowEdge, WorkflowGraph, WorkflowNode


def _dummy_workflow():
    return WorkflowGraph(
        nodes=[
            WorkflowNode("src", "QuerySourceNode", "SYSTEM", (), ("mr_url",)),
            WorkflowNode("review", "CodeReview-Agent", "AUTOMATED",
                         ("mr_url",), ("final_review_result",)),
            WorkflowNode("sink", "ResultSinkNode", "SYSTEM", ("final_review_result",), ()),
        ],
        edges=[
            WorkflowEdge("src", "review", ("mr_url",)),
            WorkflowEdge("review", "sink", ("final_review_result",)),
        ],
    )


def test_add_and_retrieve_pattern():
    store = KnowledgeStore()
    t = PatternTemplate(name="test_pattern", required_intents=("a", "b"))
    store.add_pattern(t, confidence=0.7, origin="bootstrap")
    active = store.get_active_patterns()
    assert len(active) == 1
    assert active[0].confidence == 0.7


def test_success_increases_pattern_confidence():
    store = KnowledgeStore()
    t = PatternTemplate(name="p1", required_intents=("a",))
    store.add_pattern(t, confidence=0.5)

    outcome = ExecutionOutcome(
        workflow=_dummy_workflow(),
        success=True,
        matched_pattern_name="p1",
        node_results=[
            NodeExecResult("review", "CodeReview-Agent", success=True),
        ],
    )
    store.record_outcome(outcome)
    assert store.patterns["p1"].confidence > 0.5


def test_structure_error_decreases_pattern_confidence():
    store = KnowledgeStore()
    t = PatternTemplate(name="p1", required_intents=("a",))
    store.add_pattern(t, confidence=0.5)

    outcome = ExecutionOutcome(
        workflow=_dummy_workflow(),
        success=False,
        overall_failure_type=FailureType.STRUCTURE_ERROR,
        matched_pattern_name="p1",
        node_results=[
            NodeExecResult("review", "CodeReview-Agent", success=False,
                           failure_type=FailureType.STRUCTURE_ERROR),
        ],
    )
    store.record_outcome(outcome)
    assert store.patterns["p1"].confidence < 0.5


def test_tool_error_does_not_affect_pattern_confidence():
    store = KnowledgeStore()
    t = PatternTemplate(name="p1", required_intents=("a",))
    store.add_pattern(t, confidence=0.5)

    outcome = ExecutionOutcome(
        workflow=_dummy_workflow(),
        success=False,
        overall_failure_type=FailureType.TOOL_ERROR,
        matched_pattern_name="p1",
        node_results=[
            NodeExecResult("review", "CodeReview-Agent", success=False,
                           failure_type=FailureType.TOOL_ERROR),
        ],
    )
    store.record_outcome(outcome)
    assert store.patterns["p1"].confidence == 0.5


def test_node_type_reliability_tracks_success():
    store = KnowledgeStore()
    outcome = ExecutionOutcome(
        workflow=_dummy_workflow(),
        success=True,
        node_results=[
            NodeExecResult("review", "CodeReview-Agent", success=True),
        ],
    )
    store.record_outcome(outcome)
    stats = store.node_type_stats["CodeReview-Agent"]
    assert stats.reliability > 0.5
    assert stats.success_count == 1


def test_prompt_error_increments_prompt_failure_count():
    store = KnowledgeStore()
    outcome = ExecutionOutcome(
        workflow=_dummy_workflow(),
        success=False,
        overall_failure_type=FailureType.PROMPT_ERROR,
        node_results=[
            NodeExecResult("review", "CodeReview-Agent", success=False,
                           failure_type=FailureType.PROMPT_ERROR),
        ],
    )
    store.record_outcome(outcome)
    stats = store.node_type_stats["CodeReview-Agent"]
    assert stats.prompt_failure_count == 1
    # Prompt error should not decrease reliability
    assert stats.reliability == 0.5


def test_deprecation_on_low_confidence():
    store = KnowledgeStore()
    t = PatternTemplate(name="p1", required_intents=("a",))
    store.add_pattern(t, confidence=0.25)

    for _ in range(3):
        outcome = ExecutionOutcome(
            workflow=_dummy_workflow(),
            success=False,
            overall_failure_type=FailureType.STRUCTURE_ERROR,
            matched_pattern_name="p1",
            node_results=[],
        )
        store.record_outcome(outcome)

    assert store.patterns["p1"].deprecated


def test_time_decay_reduces_confidence():
    store = KnowledgeStore()
    t = PatternTemplate(name="p1", required_intents=("a",))
    store.add_pattern(t, confidence=0.5)

    store.apply_time_decay(days_elapsed=100)
    assert store.patterns["p1"].confidence < 0.5


def test_classify_failure_priority():
    store = KnowledgeStore()
    results = [
        NodeExecResult("n1", "A", False, FailureType.PROMPT_ERROR),
        NodeExecResult("n2", "B", False, FailureType.STRUCTURE_ERROR),
        NodeExecResult("n3", "C", False, FailureType.TOOL_ERROR),
    ]
    assert store.classify_failure(results) == FailureType.STRUCTURE_ERROR


def test_historical_scores_available_for_fitness():
    store = KnowledgeStore()
    outcome = ExecutionOutcome(
        workflow=_dummy_workflow(),
        success=True,
        node_results=[
            NodeExecResult("review", "CodeReview-Agent", success=True),
        ],
    )
    store.record_outcome(outcome)
    scores = store.get_historical_scores()
    assert "CodeReview-Agent" in scores
    assert scores["CodeReview-Agent"] > 0.5
