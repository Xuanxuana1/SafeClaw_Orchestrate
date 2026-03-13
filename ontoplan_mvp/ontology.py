from __future__ import annotations

from ontoplan_mvp.models import (
    CompoundNodeDef,
    FSMTransition,
    InternalNodeSlot,
    NodeType,
    Ontology,
    PatternTemplate,
)


def build_default_ontology() -> Ontology:
    node_types = {
        "CodeReview-Agent": NodeType(
            name="CodeReview-Agent",
            execution_mode="AUTOMATED",
            access_bindings=("GitLab",),
            input_artifacts=("mr_url",),
            output_artifacts=("MR_review_result", "review_comments", "final_review_result"),
            keywords=("review", "mr", "merge request", "code"),
        ),
        "IssueTracking-Agent": NodeType(
            name="IssueTracking-Agent",
            execution_mode="AUTOMATED",
            access_bindings=("Plane", "GitLab"),
            input_artifacts=("issue_ref",),
            output_artifacts=("issue_status", "issue_metadata"),
            keywords=("issue", "tracking", "status"),
        ),
        "RequestInfo": NodeType(
            name="RequestInfo",
            execution_mode="INTERACTIVE",
            access_bindings=("RocketChat", "Email"),
            input_artifacts=("MR_review_result",),
            output_artifacts=("fix_commit", "status_update"),
            target_actor_role=None,
            keywords=("ask", "request", "contact", "status", "fix"),
        ),
        "Notify": NodeType(
            name="Notify",
            execution_mode="INTERACTIVE",
            access_bindings=("RocketChat", "Email"),
            input_artifacts=("final_review_result",),
            output_artifacts=("notification_sent",),
            target_actor_role="Manager",
            keywords=("notify", "inform", "message"),
        ),
        "ApprovalGate": NodeType(
            name="ApprovalGate",
            execution_mode="APPROVAL",
            access_bindings=("RocketChat", "Email", "Form"),
            input_artifacts=("approval_request",),
            output_artifacts=("approval_decision",),
            target_actor_role="Manager",
            keywords=("approve", "approval", "signoff"),
        ),
        "QuerySourceNode": NodeType(
            name="QuerySourceNode",
            execution_mode="SYSTEM",
            access_bindings=(),
            input_artifacts=(),
            output_artifacts=("mr_url", "issue_ref", "target_user", "query_text", "approval_request"),
            keywords=(),
        ),
        "ResultSinkNode": NodeType(
            name="ResultSinkNode",
            execution_mode="SYSTEM",
            access_bindings=(),
            input_artifacts=("notification_sent", "final_review_result", "status_update", "approval_decision"),
            output_artifacts=(),
            keywords=(),
        ),
        "review_request_review_loop": NodeType(
            name="review_request_review_loop",
            execution_mode="AUTOMATED",
            access_bindings=("GitLab", "RocketChat"),
            input_artifacts=("mr_url",),
            output_artifacts=("final_review_result", "fix_history"),
            keywords=("review", "request", "loop"),
            compound_def=CompoundNodeDef(
                states=("REVIEWING", "REQUEST_FIX", "DONE"),
                initial_state="REVIEWING",
                transitions=(
                    FSMTransition("REVIEWING", "REQUEST_FIX", "review_result == 'has_issues'"),
                    FSMTransition("REQUEST_FIX", "REVIEWING", "fix_commit_received"),
                    FSMTransition("REVIEWING", "DONE", "review_result == 'approved'"),
                ),
                max_iterations=3,
                timeout_seconds=600,
                internal_nodes=(
                    InternalNodeSlot(
                        state="REVIEWING",
                        node_type_name="CodeReview-Agent",
                        execution_mode="AUTOMATED",
                    ),
                    InternalNodeSlot(
                        state="REQUEST_FIX",
                        node_type_name="RequestInfo",
                        execution_mode="INTERACTIVE",
                        target_actor_role="Developer",
                        channel="RocketChat",
                    ),
                ),
            ),
        ),
    }
    patterns = (
        PatternTemplate(
            name="code_review_with_request_flow",
            required_intents=("code_review", "request_fix_update", "status_notification"),
        ),
    )
    return Ontology(node_types=node_types, patterns=patterns)
