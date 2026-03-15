from __future__ import annotations

from typing import Dict, List

from ontoplan_mvp.executor.artifact_store import ArtifactStore
from ontoplan_mvp.models import WorkflowNode


DEFAULT_NODE_INSTRUCTION = (
    "Complete the workflow step using the available context, produce the required outputs, "
    "and keep the work focused on this node only."
)

NODE_INSTRUCTIONS: Dict[str, str] = {
    "DataExtract-Agent": (
        "Access the required service or files, retrieve the requested source material, "
        "extract the relevant structured information, and summarize the extracted content in text."
    ),
    "DataTransform-Agent": (
        "Clean, normalize, group, and compute over the upstream extracted_data so the result is a "
        "clear transformed_data artifact ready for downstream analysis or reporting."
    ),
    "StatAnalysis-Agent": (
        "Perform statistical analysis on transformed_data and produce concrete numerical findings "
        "that can be consumed by downstream steps."
    ),
    "ReportGenerate-Agent": (
        "Turn the upstream data or analysis into a well-structured report and write it to the "
        "requested location or provide the final report output."
    ),
    "Visualization-Agent": (
        "Create the required charts or visual outputs from the upstream data and provide the paths "
        "to the generated chart files."
    ),
    "RepoManagement-Agent": (
        "Perform the necessary git and repository management operations, such as cloning, branching, "
        "committing, or pushing, and report the repository location and operation outcome."
    ),
    "Worker-Agent": (
        "Modify the required code or project files to satisfy the task, then report which files "
        "changed and summarize the key code edits."
    ),
    "IssueTracking-Agent": (
        "Inspect or update the relevant Plane issue, then report the issue identifier and its current "
        "status after the operation."
    ),
    "Notify": (
        "Send the required status or result message through the requested communication channel and "
        "report whether the notification was delivered successfully."
    ),
    "RequestInfo": (
        "Use the specified service to gather the missing information needed for the workflow and "
        "return the collected content clearly."
    ),
    "InfoCollection-Agent": (
        "Collect information from the relevant sources, consolidate it, and produce a structured "
        "summary for downstream use."
    ),
    "ApprovalGate": (
        "Send an approval request to the specified person, wait for the approval interaction if "
        "needed, and report that the request was issued along with the approval result if available."
    ),
    "MoA-Synthesizer": (
        "Synthesize all upstream analyses or proposals into one coherent conclusion that resolves "
        "differences and captures the final answer."
    ),
    "Aggregator-Agent": (
        "Merge multiple upstream inputs into one combined structure that preserves the essential "
        "information needed by downstream steps."
    ),
    "CodeReview-Agent": (
        "Review the relevant merge request or code changes, identify issues or approval points, "
        "and produce concrete review feedback."
    ),
}


def _build_target_details(node: WorkflowNode) -> str:
    """Add actor and channel guidance for interactive or approval-style nodes."""
    details: List[str] = []
    target_actor_role = node.metadata.get("target_actor_role")
    channel = node.metadata.get("channel")

    if node.execution_mode == "INTERACTIVE":
        details.append("This is an interactive step. Communicate directly with the intended recipient.")
    if target_actor_role:
        details.append(f"Target actor role: {target_actor_role}.")
    if channel:
        details.append(f"Preferred channel: {channel}.")

    return " ".join(details)


def build_node_prompt(
    node: WorkflowNode,
    artifact_store: ArtifactStore,
    original_query: str,
    node_index: int,
    total_nodes: int,
) -> str:
    """Construct the execution prompt for a single workflow node."""
    context_block = artifact_store.to_context_block(node.input_artifacts)
    instruction = NODE_INSTRUCTIONS.get(node.node_type, DEFAULT_NODE_INSTRUCTION)
    expected_outputs = list(node.output_artifacts)

    sections: List[str] = [
        "You are an OpenHands sub-agent responsible for exactly one workflow node.",
        f"Original task:\n{original_query}",
        f"Step {node_index + 1} of {total_nodes}",
        (
            f"Current node: {node.name}\n"
            f"Node type: {node.node_type}\n"
            f"Execution mode: {node.execution_mode}"
        ),
        (
            "Required input artifacts:\n"
            f"{list(node.input_artifacts) if node.input_artifacts else '[]'}"
        ),
        (
            "Upstream artifacts:\n"
            f"{context_block.rstrip() if context_block else '(no upstream artifacts available)'}"
        ),
        f"Node-specific instruction:\n{instruction}",
    ]

    target_details = _build_target_details(node)
    if target_details:
        sections.append(target_details)

    sections.append(
        "Expected output artifacts:\n"
        f"{expected_outputs}"
    )
    sections.append(
        "When you have completed the above step, print exactly one line:\n"
        f'ARTIFACTS_JSON: {{"<artifact_name>": "<brief description or file path>", ...}}\n'
        f"where the keys are the expected output artifacts: {expected_outputs}\n"
        "Do not print this line until the step is fully done."
    )

    return "\n\n".join(sections)
