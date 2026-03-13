from ontoplan_mvp.engine import OntoPlanEngine
from ontoplan_mvp.models import WorkflowEdge, WorkflowGraph, WorkflowNode
from ontoplan_mvp.ontology import build_default_ontology


def test_extracts_execution_modes_for_review_request_notify():
    engine = OntoPlanEngine(build_default_ontology())

    intents = engine.extract_intents(
        "Check Sarah's MR, if code has issues ask her to fix, notify PM when done"
    )

    assert [intent.name for intent in intents] == [
        "code_review",
        "request_fix_update",
        "status_notification",
    ]
    assert [intent.execution_mode_hint for intent in intents] == [
        "AUTOMATED",
        "INTERACTIVE",
        "INTERACTIVE",
    ]
    assert [intent.target_actor_hint for intent in intents] == [
        None,
        "Developer",
        "Manager",
    ]


def test_retrieval_prefers_interaction_nodes_for_interactive_intents():
    engine = OntoPlanEngine(build_default_ontology())
    intents = engine.extract_intents(
        "Ask the assignee for the issue status and notify the PM afterwards"
    )

    candidates = engine.retrieve_candidates(intents)

    assert candidates["request_status_update"][0].name == "RequestInfo"
    assert candidates["request_status_update"][0].execution_mode == "INTERACTIVE"
    assert candidates["status_notification"][0].name == "Notify"
    assert candidates["status_notification"][0].execution_mode == "INTERACTIVE"


def test_plan_injects_source_sink_and_builds_valid_acyclic_workflow():
    engine = OntoPlanEngine(build_default_ontology())

    plan = engine.plan(
        "Check Sarah's MR, if code has issues ask her to fix, notify PM when done"
    )

    assert plan.workflow.is_acyclic()
    assert plan.workflow.node_names() == [
        "QuerySourceNode",
        "review_request_review_loop",
        "Notify",
        "ResultSinkNode",
    ]
    assert plan.workflow.has_edge("QuerySourceNode", "review_request_review_loop")
    assert plan.workflow.has_edge("review_request_review_loop", "Notify")
    assert plan.workflow.has_edge("Notify", "ResultSinkNode")
    assert plan.validation_errors == []


def test_micro_evolution_improves_or_preserves_score():
    engine = OntoPlanEngine(build_default_ontology())
    intents = engine.extract_intents(
        "Check Sarah's MR, if code has issues ask her to fix, notify PM when done"
    )
    initial = engine.assemble(engine.retrieve_candidates(intents), intents)

    optimized = engine.optimize(initial, intents)

    assert optimized.score >= initial.score


def test_extracts_approval_intent():
    engine = OntoPlanEngine(build_default_ontology())

    intents = engine.extract_intents("Ask manager to approve the deployment")

    assert [intent.name for intent in intents] == ["approval_request"]
    assert [intent.execution_mode_hint for intent in intents] == ["APPROVAL"]
    assert [intent.target_actor_hint for intent in intents] == ["Manager"]


def test_plan_supports_review_approval_notify_flow():
    engine = OntoPlanEngine(build_default_ontology())

    plan = engine.plan("Check MR and get manager approval before notifying PM")

    assert plan.workflow.node_names() == [
        "QuerySourceNode",
        "CodeReview-Agent",
        "ApprovalGate",
        "Notify",
        "ResultSinkNode",
    ]
    assert ("QuerySourceNode", "CodeReview-Agent", ("mr_url",)) in [
        (edge.source, edge.target, edge.artifacts_passed) for edge in plan.workflow.edges
    ]
    assert ("CodeReview-Agent", "ApprovalGate", ("final_review_result",)) in [
        (edge.source, edge.target, edge.artifacts_passed) for edge in plan.workflow.edges
    ]
    assert ("ApprovalGate", "Notify", ("approval_decision",)) in [
        (edge.source, edge.target, edge.artifacts_passed) for edge in plan.workflow.edges
    ]
    assert plan.validation_errors == []


def test_free_assembly_uses_contract_compatible_edges():
    engine = OntoPlanEngine(build_default_ontology())

    plan = engine.plan("Ask the assignee for the issue status and notify the PM afterwards")

    assert ("QuerySourceNode", "RequestInfo", ("issue_ref",)) in [
        (edge.source, edge.target, edge.artifacts_passed) for edge in plan.workflow.edges
    ]
    assert ("RequestInfo", "Notify", ("status_update",)) in [
        (edge.source, edge.target, edge.artifacts_passed) for edge in plan.workflow.edges
    ]
    assert plan.validation_errors == []


def test_plan_without_supported_intents_is_invalid():
    engine = OntoPlanEngine(build_default_ontology())

    plan = engine.plan("Random unrelated text")

    assert "no intents extracted from query" in plan.validation_errors
    assert plan.score == 0.0


def test_result_sink_rejects_non_terminal_artifacts():
    engine = OntoPlanEngine(build_default_ontology())
    workflow = WorkflowGraph(
        nodes=[
            WorkflowNode("QuerySourceNode", "QuerySourceNode", "SYSTEM", (), ("mr_url",)),
            WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM", ("notification_sent",), ()),
        ],
        edges=[WorkflowEdge("QuerySourceNode", "ResultSinkNode", ("mr_url",))],
    )

    errors = engine._validate(workflow)

    assert "edge QuerySourceNode->ResultSinkNode does not satisfy target inputs" in errors
