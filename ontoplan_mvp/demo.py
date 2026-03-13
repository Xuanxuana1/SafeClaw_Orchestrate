from __future__ import annotations

from ontoplan_mvp.engine import OntoPlanEngine
from ontoplan_mvp.knowledge_store import (
    ExecutionOutcome,
    FailureType,
    KnowledgeStore,
    NodeExecResult,
)
from ontoplan_mvp.models import PatternTemplate
from ontoplan_mvp.ontology import build_default_ontology


def _print_plan(label: str, plan) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  score: {plan.score}")
    print("  nodes:")
    for node in plan.workflow.nodes:
        extra = ""
        if node.metadata.get("target_actor_role"):
            extra = f" -> {node.metadata['target_actor_role']}"
        if node.metadata.get("max_iterations"):
            extra += f" (max_iter={node.metadata['max_iterations']})"
        print(f"    {node.name} [{node.execution_mode}]{extra}")
    print("  edges:")
    for edge in plan.workflow.edges:
        print(f"    {edge.source} -> {edge.target}: {', '.join(edge.artifacts_passed)}")
    if plan.validation_errors:
        print("  validation errors:")
        for error in plan.validation_errors:
            print(f"    - {error}")
    else:
        print("  validation: OK")


def main() -> None:
    query = "Check Sarah's MR, if code has issues ask her to fix, notify PM when done"
    ontology = build_default_ontology()
    store = KnowledgeStore()

    # Seed a pattern into the knowledge store
    store.add_pattern(
        PatternTemplate(
            name="code_review_with_request_flow",
            required_intents=("code_review", "request_fix_update", "status_notification"),
        ),
        confidence=0.7,
        origin="bootstrap",
    )

    # --- 1) Basic plan (no evolution) ---
    engine = OntoPlanEngine(ontology, knowledge_store=store, use_evolution=False)
    basic_plan = engine.plan(query)
    _print_plan("Basic plan (retrieval + assembly only)", basic_plan)

    # --- 2) Plan with micro-evolution ---
    engine_evo = OntoPlanEngine(ontology, knowledge_store=store, use_evolution=True)
    evolved_plan = engine_evo.plan(query)
    _print_plan("Evolved plan (retrieval + assembly + micro-evolution)", evolved_plan)

    # --- 3) Simulate execution feedback ---
    print(f"\n{'='*60}")
    print("  Knowledge store: simulating execution feedback")
    print(f"{'='*60}")

    # Simulate a successful execution
    outcome_ok = ExecutionOutcome(
        workflow=basic_plan.workflow,
        success=True,
        matched_pattern_name="code_review_with_request_flow",
        node_results=[
            NodeExecResult("review_request_review_loop", "review_request_review_loop", True),
            NodeExecResult("Notify", "Notify", True),
        ],
    )
    store.record_outcome(outcome_ok)
    print(f"  After success: pattern confidence = {store.patterns['code_review_with_request_flow'].confidence:.3f}")

    # Simulate a structure error
    outcome_fail = ExecutionOutcome(
        workflow=basic_plan.workflow,
        success=False,
        overall_failure_type=FailureType.STRUCTURE_ERROR,
        matched_pattern_name="code_review_with_request_flow",
        node_results=[
            NodeExecResult("review_request_review_loop", "review_request_review_loop",
                           False, FailureType.STRUCTURE_ERROR),
        ],
    )
    store.record_outcome(outcome_fail)
    print(f"  After structure error: pattern confidence = {store.patterns['code_review_with_request_flow'].confidence:.3f}")

    # Simulate a tool error (should NOT reduce pattern confidence)
    conf_before = store.patterns["code_review_with_request_flow"].confidence
    outcome_tool = ExecutionOutcome(
        workflow=basic_plan.workflow,
        success=False,
        overall_failure_type=FailureType.TOOL_ERROR,
        matched_pattern_name="code_review_with_request_flow",
        node_results=[
            NodeExecResult("Notify", "Notify", False, FailureType.TOOL_ERROR),
        ],
    )
    store.record_outcome(outcome_tool)
    print(f"  After tool error: pattern confidence = {store.patterns['code_review_with_request_flow'].confidence:.3f} (unchanged)")
    assert store.patterns["code_review_with_request_flow"].confidence == conf_before

    # Show node-type stats
    print("\n  Node-type reliability:")
    for name, stats in store.node_type_stats.items():
        print(f"    {name}: reliability={stats.reliability:.3f}, "
              f"executions={stats.total_executions}, "
              f"prompt_failures={stats.prompt_failure_count}")

    # Show historical scores for fitness
    print(f"\n  Historical scores for fitness F4: {store.get_historical_scores()}")

    # --- 4) Compound node FSM info ---
    print(f"\n{'='*60}")
    print("  Compound node FSM details")
    print(f"{'='*60}")
    compound = ontology.node_types["review_request_review_loop"]
    fsm = compound.compound_def
    print(f"  States: {fsm.states}")
    print(f"  Initial: {fsm.initial_state}")
    print(f"  Max iterations: {fsm.max_iterations}")
    print(f"  Timeout: {fsm.timeout_seconds}s")
    print("  Transitions:")
    for t in fsm.transitions:
        print(f"    {t.from_state} -> {t.to_state} [{t.condition}]")
    print("  Internal nodes:")
    for slot in fsm.internal_nodes:
        role = f" -> {slot.target_actor_role}" if slot.target_actor_role else ""
        print(f"    [{slot.state}] {slot.node_type_name} ({slot.execution_mode}){role}")


if __name__ == "__main__":
    main()
