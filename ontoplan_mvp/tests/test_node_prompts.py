from ontoplan_mvp.executor.artifact_store import ArtifactStore
from ontoplan_mvp.executor.node_prompts import NODE_INSTRUCTIONS, build_node_prompt
from ontoplan_mvp.models import WorkflowNode


EXPECTED_NODE_TYPES = {
    "DataExtract-Agent",
    "DataTransform-Agent",
    "StatAnalysis-Agent",
    "ReportGenerate-Agent",
    "Visualization-Agent",
    "RepoManagement-Agent",
    "Worker-Agent",
    "IssueTracking-Agent",
    "Notify",
    "RequestInfo",
    "InfoCollection-Agent",
    "ApprovalGate",
    "MoA-Synthesizer",
    "Aggregator-Agent",
    "CodeReview-Agent",
}


def test_node_instructions_cover_required_node_types():
    assert EXPECTED_NODE_TYPES.issubset(set(NODE_INSTRUCTIONS))


def test_build_node_prompt_includes_context_and_output_contract():
    store = ArtifactStore()
    store.put("extracted_data", "clean me")
    node = WorkflowNode(
        name="transform",
        node_type="DataTransform-Agent",
        execution_mode="AUTOMATED",
        input_artifacts=("extracted_data",),
        output_artifacts=("transformed_data",),
    )

    prompt = build_node_prompt(
        node=node,
        artifact_store=store,
        original_query="Transform a dataset and report the result.",
        node_index=1,
        total_nodes=3,
    )

    assert "Step 2 of 3" in prompt
    assert "[extracted_data]\nclean me" in prompt
    assert "ARTIFACTS_JSON:" in prompt
    assert "transformed_data" in prompt


def test_build_node_prompt_includes_interactive_target_details():
    node = WorkflowNode(
        name="notify-manager",
        node_type="Notify",
        execution_mode="INTERACTIVE",
        input_artifacts=("final_review_result",),
        output_artifacts=("notification_sent",),
        metadata={"target_actor_role": "Manager", "channel": "RocketChat"},
    )

    prompt = build_node_prompt(
        node=node,
        artifact_store=ArtifactStore(),
        original_query="Notify the manager after the review completes.",
        node_index=0,
        total_nodes=1,
    )

    assert "Target actor role: Manager." in prompt
    assert "Preferred channel: RocketChat." in prompt
