"""A-Box: concrete ontology instances for the OntoPlan MVP.

This module provides:
  1. INTENT_CATALOG — 35+ IntentAtom definitions covering all intents
     referenced in seed_patterns.SEED_PATTERNS.
  2. INTENT_NODE_PREFERENCES — mapping from intent name → ranked list of
     preferred NodeType names, used by the engine's retrieve_candidates.
  3. WORKFLOW_TEMPLATES — pre-assembled WorkflowGraph instances for each
     of the 8 orchestration meta-patterns (Sequential, Debate, Reflection,
     Hierarchical, Handoff, MoA, Nested, Role-based) × key enterprise
     domains.
  4. Helper to build a fully-resolved A-Box ontology.

Together with seed_patterns (T-Box extensions), this forms a complete
knowledge base that the OntoPlanEngine can use for template-matching,
retrieval-based assembly, and micro-evolution.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ontoplan_mvp.models import (
    IntentAtom,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
)


# ---------------------------------------------------------------------------
# 1. Intent Catalog — all IntentAtom definitions
# ---------------------------------------------------------------------------

INTENT_CATALOG: Dict[str, IntentAtom] = {
    # === File / Data operations ===
    "file_download": IntentAtom(
        name="file_download",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("OwnCloud",),
        role_hints=("DS", "Finance", "HR", "Admin"),
        input_artifacts=("file_path",),
        output_artifacts=("downloaded_file",),
    ),
    "data_extraction": IntentAtom(
        name="data_extraction",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("OwnCloud",),
        role_hints=("DS", "Finance"),
        input_artifacts=("file_path",),
        output_artifacts=("extracted_data",),
    ),
    "data_transform": IntentAtom(
        name="data_transform",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("DS",),
        input_artifacts=("extracted_data",),
        output_artifacts=("transformed_data",),
    ),
    "visualization": IntentAtom(
        name="visualization",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("DS",),
        input_artifacts=("transformed_data",),
        output_artifacts=("chart_files",),
    ),
    "report_generation": IntentAtom(
        name="report_generation",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("DS", "Finance", "PM"),
        input_artifacts=("transformed_data",),
        output_artifacts=("report_file",),
    ),
    "report_draft": IntentAtom(
        name="report_draft",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("DS", "PM"),
        input_artifacts=("extracted_data",),
        output_artifacts=("report_draft_text",),
    ),

    # === Code / Repo operations ===
    "code_review": IntentAtom(
        name="code_review",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("GitLab",),
        role_hints=("SDE",),
        input_artifacts=("mr_url",),
        output_artifacts=("MR_review_result", "review_comments"),
    ),
    "repo_clone": IntentAtom(
        name="repo_clone",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("GitLab",),
        role_hints=("SDE",),
        input_artifacts=("repo_url",),
        output_artifacts=("repo_metadata", "file_list"),
    ),
    "code_modification": IntentAtom(
        name="code_modification",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("GitLab",),
        role_hints=("SDE",),
        input_artifacts=("file_list",),
        output_artifacts=("modified_files",),
    ),
    "code_push": IntentAtom(
        name="code_push",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("GitLab",),
        role_hints=("SDE",),
        input_artifacts=("modified_files",),
        output_artifacts=("push_result",),
    ),

    # === Issue / Project management ===
    "issue_lookup": IntentAtom(
        name="issue_lookup",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("Plane", "GitLab"),
        role_hints=("PM", "SDE"),
        input_artifacts=("issue_ref",),
        output_artifacts=("issue_status", "issue_metadata"),
    ),
    "issue_update": IntentAtom(
        name="issue_update",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("Plane", "GitLab"),
        role_hints=("PM",),
        input_artifacts=("issue_ref", "update_data"),
        output_artifacts=("issue_updated",),
    ),
    "issue_classification": IntentAtom(
        name="issue_classification",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("Plane",),
        role_hints=("PM",),
        input_artifacts=("issue_metadata",),
        output_artifacts=("issue_category", "priority_level"),
    ),
    "sprint_planning": IntentAtom(
        name="sprint_planning",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("Plane",),
        role_hints=("PM",),
        input_artifacts=("project_ref",),
        output_artifacts=("sprint_plan", "task_assignments"),
    ),

    # === Interactive / Communication ===
    "request_fix_update": IntentAtom(
        name="request_fix_update",
        execution_mode_hint="INTERACTIVE",
        target_service_hints=("RocketChat",),
        role_hints=("SDE",),
        input_artifacts=("MR_review_result",),
        output_artifacts=("fix_commit",),
        target_actor_hint="Developer",
    ),
    "request_status_update": IntentAtom(
        name="request_status_update",
        execution_mode_hint="INTERACTIVE",
        target_service_hints=("RocketChat",),
        role_hints=("PM",),
        input_artifacts=("issue_ref",),
        output_artifacts=("status_update",),
        target_actor_hint="Developer",
    ),
    "status_notification": IntentAtom(
        name="status_notification",
        execution_mode_hint="INTERACTIVE",
        target_service_hints=("RocketChat", "Email"),
        role_hints=("PM",),
        input_artifacts=("final_review_result",),
        output_artifacts=("notification_sent",),
        target_actor_hint="Manager",
    ),
    "info_collection": IntentAtom(
        name="info_collection",
        execution_mode_hint="INTERACTIVE",
        target_service_hints=("RocketChat",),
        role_hints=("Admin", "PM"),
        input_artifacts=("question_list", "target_users"),
        output_artifacts=("collected_responses",),
    ),
    "interview_scheduling": IntentAtom(
        name="interview_scheduling",
        execution_mode_hint="INTERACTIVE",
        target_service_hints=("RocketChat", "Email"),
        role_hints=("HR",),
        input_artifacts=("candidate_ranking",),
        output_artifacts=("schedule_confirmation",),
        target_actor_hint="Candidate",
    ),

    # === Approval ===
    "approval_request": IntentAtom(
        name="approval_request",
        execution_mode_hint="APPROVAL",
        target_service_hints=("RocketChat", "Email", "Form"),
        role_hints=("PM",),
        input_artifacts=("approval_request",),
        output_artifacts=("approval_decision",),
        target_actor_hint="Manager",
    ),

    # === Domain-specific: Finance ===
    "expense_validation": IntentAtom(
        name="expense_validation",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("OwnCloud",),
        role_hints=("Finance",),
        input_artifacts=("expense_files", "policy_rules"),
        output_artifacts=("validation_result", "exceptions"),
    ),
    "invoice_matching": IntentAtom(
        name="invoice_matching",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("OwnCloud",),
        role_hints=("Finance",),
        input_artifacts=("invoice_files", "payment_files"),
        output_artifacts=("match_result", "flagged_items"),
    ),

    # === Domain-specific: HR ===
    "resume_screening": IntentAtom(
        name="resume_screening",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("OwnCloud",),
        role_hints=("HR",),
        input_artifacts=("resume_files",),
        output_artifacts=("screening_result", "candidate_ranking"),
    ),

    # === Debate / MAD ===
    "proposal_generation": IntentAtom(
        name="proposal_generation",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("SDE", "PM", "DS"),
        input_artifacts=("task_spec",),
        output_artifacts=("proposal",),
    ),
    "debate_review": IntentAtom(
        name="debate_review",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("SDE", "PM"),
        input_artifacts=("proposal",),
        output_artifacts=("critique", "counter_proposal"),
    ),
    "final_decision": IntentAtom(
        name="final_decision",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("PM", "SDE"),
        input_artifacts=("proposal", "critique"),
        output_artifacts=("final_decision",),
    ),

    # === Reflection / Critique-Revise ===
    "critique_revise": IntentAtom(
        name="critique_revise",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("SDE", "DS"),
        input_artifacts=("task_spec",),
        output_artifacts=("refined_result",),
    ),

    # === Hierarchical / Supervisor ===
    "task_decomposition": IntentAtom(
        name="task_decomposition",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("PM",),
        input_artifacts=("task_spec",),
        output_artifacts=("subtask_assignments",),
    ),
    "parallel_extraction": IntentAtom(
        name="parallel_extraction",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("OwnCloud",),
        role_hints=("DS",),
        input_artifacts=("subtask_spec",),
        output_artifacts=("subtask_result",),
    ),
    "result_aggregation": IntentAtom(
        name="result_aggregation",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("PM", "DS"),
        input_artifacts=("subtask_result",),
        output_artifacts=("aggregated_result",),
    ),

    # === Handoff / Swarm ===
    "handoff_routing": IntentAtom(
        name="handoff_routing",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("PM",),
        input_artifacts=("issue_category",),
        output_artifacts=("routed_task",),
    ),
    "request_intake": IntentAtom(
        name="request_intake",
        execution_mode_hint="INTERACTIVE",
        target_service_hints=("RocketChat",),
        role_hints=("Admin",),
        input_artifacts=("query_text",),
        output_artifacts=("intake_record",),
    ),
    "task_execution": IntentAtom(
        name="task_execution",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("SDE", "DS"),
        input_artifacts=("routed_task",),
        output_artifacts=("execution_result",),
    ),

    # === MoA (Mixture-of-Agents) ===
    "parallel_review": IntentAtom(
        name="parallel_review",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("GitLab",),
        role_hints=("SDE",),
        input_artifacts=("mr_url",),
        output_artifacts=("proposal_a", "proposal_b", "proposal_c"),
    ),
    "review_synthesis": IntentAtom(
        name="review_synthesis",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("SDE",),
        input_artifacts=("proposal_a", "proposal_b", "proposal_c"),
        output_artifacts=("synthesized_result",),
    ),
    "parallel_analysis": IntentAtom(
        name="parallel_analysis",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("DS",),
        input_artifacts=("extracted_data",),
        output_artifacts=("proposal_a", "proposal_b", "proposal_c"),
    ),
    "analysis_synthesis": IntentAtom(
        name="analysis_synthesis",
        execution_mode_hint="AUTOMATED",
        target_service_hints=(),
        role_hints=("DS",),
        input_artifacts=("proposal_a", "proposal_b", "proposal_c"),
        output_artifacts=("synthesized_result",),
    ),

    # === Role-based / Group Chat ===
    "multi_party_discussion": IntentAtom(
        name="multi_party_discussion",
        execution_mode_hint="INTERACTIVE",
        target_service_hints=("RocketChat",),
        role_hints=("PM", "SDE", "Admin"),
        input_artifacts=("collected_responses",),
        output_artifacts=("discussion_summary",),
    ),
    "decision_recording": IntentAtom(
        name="decision_recording",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("Plane",),
        role_hints=("PM",),
        input_artifacts=("discussion_summary",),
        output_artifacts=("decision_record",),
    ),

    # === Data quality ===
    "data_quality_check": IntentAtom(
        name="data_quality_check",
        execution_mode_hint="AUTOMATED",
        target_service_hints=("OwnCloud",),
        role_hints=("DS",),
        input_artifacts=("extracted_data",),
        output_artifacts=("validated_data",),
    ),
}


# ---------------------------------------------------------------------------
# 2. Intent → NodeType preference map
# ---------------------------------------------------------------------------

INTENT_NODE_PREFERENCES: Dict[str, Tuple[str, ...]] = {
    # File / Data
    "file_download":         ("DataExtract-Agent",),
    "data_extraction":       ("DataExtract-Agent",),
    "data_transform":        ("DataTransform-Agent",),
    "visualization":         ("Visualization-Agent",),
    "report_generation":     ("ReportGenerate-Agent",),
    "report_draft":          ("ReportGenerate-Agent", "Worker-Agent"),
    # Code / Repo
    "code_review":           ("CodeReview-Agent", "review_request_review_loop"),
    "repo_clone":            ("RepoManagement-Agent",),
    "code_modification":     ("Worker-Agent",),
    "code_push":             ("RepoManagement-Agent",),
    # Issue / PM
    "issue_lookup":          ("IssueTracking-Agent",),
    "issue_update":          ("IssueTracking-Agent",),
    "issue_classification":  ("Worker-Agent",),
    "sprint_planning":       ("SprintPlanning-Agent",),
    # Interactive
    "request_fix_update":    ("RequestInfo",),
    "request_status_update": ("RequestInfo", "InfoCollection-Agent"),
    "status_notification":   ("Notify",),
    "info_collection":       ("InfoCollection-Agent",),
    "interview_scheduling":  ("RequestInfo",),
    # Approval
    "approval_request":      ("ApprovalGate", "approval_chain"),
    # Finance
    "expense_validation":    ("ExpenseValidation-Agent",),
    "invoice_matching":      ("InvoiceMatching-Agent",),
    # HR
    "resume_screening":      ("ResumeScreening-Agent",),
    # Debate
    "proposal_generation":   ("Proposer-Agent",),
    "debate_review":         ("Critic-Agent", "debate_loop"),
    "final_decision":        ("Judge-Agent",),
    # Reflection
    "critique_revise":       ("reflection_loop", "Critic-Agent"),
    # Hierarchical
    "task_decomposition":    ("Supervisor-Agent",),
    "parallel_extraction":   ("Worker-Agent", "DataExtract-Agent"),
    "result_aggregation":    ("Aggregator-Agent",),
    # Handoff
    "handoff_routing":       ("Supervisor-Agent",),
    "request_intake":        ("RequestInfo",),
    "task_execution":        ("Worker-Agent",),
    # MoA
    "parallel_review":       ("Parallel-Proposer-A", "Parallel-Proposer-B", "Parallel-Proposer-C"),
    "review_synthesis":      ("MoA-Synthesizer",),
    "parallel_analysis":     ("Parallel-Proposer-A", "Parallel-Proposer-B", "Parallel-Proposer-C"),
    "analysis_synthesis":    ("MoA-Synthesizer",),
    # Role-based
    "multi_party_discussion": ("InfoCollection-Agent",),
    "decision_recording":    ("ReportGenerate-Agent",),
    # Data quality
    "data_quality_check":    ("data_quality_loop", "Critic-Agent"),
}


# ---------------------------------------------------------------------------
# 3. Pre-assembled Workflow Templates
#    Concrete WorkflowGraph instances for each orchestration meta-pattern.
#    These serve as "golden examples" for template matching and as seeds
#    for micro-evolution.
# ---------------------------------------------------------------------------


def _sys(name: str) -> WorkflowNode:
    """Create a system node (QuerySourceNode or ResultSinkNode)."""
    if name == "QuerySourceNode":
        return WorkflowNode(
            name="QuerySourceNode",
            node_type="QuerySourceNode",
            execution_mode="SYSTEM",
            input_artifacts=(),
            output_artifacts=(
                "mr_url", "issue_ref", "target_user", "query_text",
                "approval_request", "file_path", "repo_url", "task_spec",
                "project_ref", "question_list", "target_users",
                "resume_files", "invoice_files", "payment_files",
                "expense_files", "policy_rules", "extracted_data",
            ),
        )
    return WorkflowNode(
        name="ResultSinkNode",
        node_type="ResultSinkNode",
        execution_mode="SYSTEM",
        input_artifacts=(
            "notification_sent", "final_review_result", "status_update",
            "approval_decision", "report_file", "chart_files",
            "upload_url", "push_result", "sprint_plan",
            "schedule_confirmation", "aggregated_result",
            "synthesized_result", "decision_record",
            "execution_result", "debated_result", "refined_result",
            "validated_data",
        ),
        output_artifacts=(),
    )


def _node(
    name: str,
    node_type: str,
    mode: str,
    inputs: Tuple[str, ...],
    outputs: Tuple[str, ...],
    **meta: str,
) -> WorkflowNode:
    return WorkflowNode(
        name=name,
        node_type=node_type,
        execution_mode=mode,
        input_artifacts=inputs,
        output_artifacts=outputs,
        metadata=dict(meta),
    )


def _edge(src: str, dst: str, arts: Tuple[str, ...]) -> WorkflowEdge:
    return WorkflowEdge(source=src, target=dst, artifacts_passed=arts)


# ===================================================================
# 3a. Sequential / Pipeline templates
# ===================================================================

def build_seq_document_analysis() -> WorkflowGraph:
    """Sequential: download → extract → report."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("extract", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("extracted_data",)),
            _node("transform", "DataTransform-Agent", "AUTOMATED",
                  ("extracted_data",), ("transformed_data",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("transformed_data",), ("report_file",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "extract", ("file_path",)),
            _edge("extract", "transform", ("extracted_data",)),
            _edge("transform", "report", ("transformed_data",)),
            _edge("report", "ResultSinkNode", ("report_file",)),
        ],
    )


def build_seq_data_pipeline() -> WorkflowGraph:
    """Sequential: download → extract → transform → visualize."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("extract", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("extracted_data",)),
            _node("transform", "DataTransform-Agent", "AUTOMATED",
                  ("extracted_data",), ("transformed_data",)),
            _node("visualize", "Visualization-Agent", "AUTOMATED",
                  ("transformed_data",), ("chart_files",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "extract", ("file_path",)),
            _edge("extract", "transform", ("extracted_data",)),
            _edge("transform", "visualize", ("transformed_data",)),
            _edge("visualize", "ResultSinkNode", ("chart_files",)),
        ],
    )


def build_seq_repo_modify_commit() -> WorkflowGraph:
    """Sequential: clone repo → modify code → push."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("clone", "RepoManagement-Agent", "AUTOMATED",
                  ("repo_url",), ("repo_metadata", "file_list")),
            _node("modify", "Worker-Agent", "AUTOMATED",
                  ("file_list",), ("modified_files",)),
            _node("push", "RepoManagement-Agent", "AUTOMATED",
                  ("modified_files",), ("push_result",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "clone", ("repo_url",)),
            _edge("clone", "modify", ("file_list",)),
            _edge("modify", "push", ("modified_files",)),
            _edge("push", "ResultSinkNode", ("push_result",)),
        ],
    )


def build_seq_expense_validate_report() -> WorkflowGraph:
    """Sequential: download expenses → validate → generate report."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("download", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("expense_files", "policy_rules")),
            _node("validate", "ExpenseValidation-Agent", "AUTOMATED",
                  ("expense_files", "policy_rules"),
                  ("validation_result", "exceptions")),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("validation_result",), ("report_file",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "download", ("file_path",)),
            _edge("download", "validate", ("expense_files", "policy_rules")),
            _edge("validate", "report", ("validation_result",)),
            _edge("report", "ResultSinkNode", ("report_file",)),
        ],
    )


def build_seq_resume_screen_schedule() -> WorkflowGraph:
    """Sequential: download resumes → screen → schedule interviews."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("download", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("resume_files",)),
            _node("screen", "ResumeScreening-Agent", "AUTOMATED",
                  ("resume_files",),
                  ("screening_result", "candidate_ranking")),
            _node("schedule", "RequestInfo", "INTERACTIVE",
                  ("candidate_ranking",), ("schedule_confirmation",),
                  target_actor_role="Candidate"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "download", ("file_path",)),
            _edge("download", "screen", ("resume_files",)),
            _edge("screen", "schedule", ("candidate_ranking",)),
            _edge("schedule", "ResultSinkNode", ("schedule_confirmation",)),
        ],
    )


# ===================================================================
# 3b. Debate / MAD templates
# ===================================================================

def build_debate_code_review() -> WorkflowGraph:
    """Debate: propose review → critic challenges → judge decides."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("reviewer_a", "Proposer-Agent", "AUTOMATED",
                  ("task_spec",), ("proposal",)),
            _node("reviewer_b", "Critic-Agent", "AUTOMATED",
                  ("proposal",), ("critique", "counter_proposal")),
            _node("judge", "Judge-Agent", "AUTOMATED",
                  ("proposal", "critique"), ("final_decision",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "reviewer_a", ("task_spec",)),
            _edge("reviewer_a", "reviewer_b", ("proposal",)),
            _edge("reviewer_a", "judge", ("proposal",)),
            _edge("reviewer_b", "judge", ("critique",)),
            _edge("judge", "ResultSinkNode", ("final_decision",)),
        ],
    )


def build_debate_loop_code_review() -> WorkflowGraph:
    """Debate with compound loop: use debate_loop FSM for multi-round."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("debate", "debate_loop", "AUTOMATED",
                  ("task_spec",), ("debated_result",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("debated_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "debate", ("task_spec",)),
            _edge("debate", "notify", ("debated_result",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_debate_proposal_evaluation() -> WorkflowGraph:
    """Debate: multi-party proposal evaluation with notification."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("proposer", "Proposer-Agent", "AUTOMATED",
                  ("task_spec",), ("proposal",)),
            _node("critic_1", "Critic-Agent", "AUTOMATED",
                  ("proposal",), ("critique", "counter_proposal")),
            _node("critic_2", "Critic-Agent", "AUTOMATED",
                  ("counter_proposal",), ("critique", "counter_proposal")),
            _node("judge", "Judge-Agent", "AUTOMATED",
                  ("proposal", "critique"), ("final_decision",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("final_decision",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "proposer", ("task_spec",)),
            _edge("proposer", "critic_1", ("proposal",)),
            _edge("critic_1", "critic_2", ("counter_proposal",)),
            _edge("proposer", "judge", ("proposal",)),
            _edge("critic_2", "judge", ("critique",)),
            _edge("judge", "notify", ("final_decision",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


# ===================================================================
# 3c. Reflection / Critique-Revise templates
# ===================================================================

def build_reflect_report_writing() -> WorkflowGraph:
    """Reflection: extract data → draft report → critique-revise loop."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("extract", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("extracted_data",)),
            _node("reflect", "reflection_loop", "AUTOMATED",
                  ("task_spec",), ("refined_result",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("refined_result",), ("report_file",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "extract", ("file_path",)),
            _edge("extract", "reflect", ("extracted_data",)),
            _edge("reflect", "report", ("refined_result",)),
            _edge("report", "ResultSinkNode", ("report_file",)),
        ],
    )


def build_reflect_code_improvement() -> WorkflowGraph:
    """Reflection: review code → critique-revise loop → push."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("review", "CodeReview-Agent", "AUTOMATED",
                  ("mr_url",), ("MR_review_result", "review_comments")),
            _node("reflect", "reflection_loop", "AUTOMATED",
                  ("task_spec",), ("refined_result",)),
            _node("push", "RepoManagement-Agent", "AUTOMATED",
                  ("refined_result",), ("push_result",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "review", ("mr_url",)),
            _edge("review", "reflect", ("MR_review_result",)),
            _edge("reflect", "push", ("refined_result",)),
            _edge("push", "ResultSinkNode", ("push_result",)),
        ],
    )


def build_reflect_invoice_matching() -> WorkflowGraph:
    """Reflection: download invoices → match → critique-revise → report."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("download", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("invoice_files", "payment_files")),
            _node("match", "InvoiceMatching-Agent", "AUTOMATED",
                  ("invoice_files", "payment_files"),
                  ("match_result", "flagged_items")),
            _node("reflect", "reflection_loop", "AUTOMATED",
                  ("task_spec",), ("refined_result",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("refined_result",), ("report_file",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "download", ("file_path",)),
            _edge("download", "match", ("invoice_files", "payment_files")),
            _edge("match", "reflect", ("match_result",)),
            _edge("reflect", "report", ("refined_result",)),
            _edge("report", "ResultSinkNode", ("report_file",)),
        ],
    )


# ===================================================================
# 3d. Hierarchical / Supervisor templates
# ===================================================================

def build_hier_multi_file_analysis() -> WorkflowGraph:
    """Hierarchical: supervisor decomposes → workers extract → aggregator → report."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("supervisor", "Supervisor-Agent", "AUTOMATED",
                  ("task_spec",), ("subtask_assignments", "final_synthesis")),
            _node("worker_1", "Worker-Agent", "AUTOMATED",
                  ("subtask_spec",), ("subtask_result",)),
            _node("worker_2", "Worker-Agent", "AUTOMATED",
                  ("subtask_spec",), ("subtask_result",)),
            _node("aggregator", "Aggregator-Agent", "AUTOMATED",
                  ("subtask_result",), ("aggregated_result",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("aggregated_result",), ("report_file",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "supervisor", ("task_spec",)),
            _edge("supervisor", "worker_1", ("subtask_assignments",)),
            _edge("supervisor", "worker_2", ("subtask_assignments",)),
            _edge("worker_1", "aggregator", ("subtask_result",)),
            _edge("worker_2", "aggregator", ("subtask_result",)),
            _edge("aggregator", "report", ("aggregated_result",)),
            _edge("report", "ResultSinkNode", ("report_file",)),
        ],
    )


def build_hier_sprint_planning() -> WorkflowGraph:
    """Hierarchical: supervisor → collect status from devs → aggregate → plan sprint."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("supervisor", "Supervisor-Agent", "AUTOMATED",
                  ("task_spec",), ("subtask_assignments",)),
            _node("lookup", "IssueTracking-Agent", "AUTOMATED",
                  ("issue_ref",), ("issue_status", "issue_metadata")),
            _node("collect", "InfoCollection-Agent", "INTERACTIVE",
                  ("question_list", "target_users"),
                  ("collected_responses",)),
            _node("aggregator", "Aggregator-Agent", "AUTOMATED",
                  ("subtask_result",), ("aggregated_result",)),
            _node("planner", "SprintPlanning-Agent", "AUTOMATED",
                  ("project_ref",), ("sprint_plan", "task_assignments")),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "supervisor", ("task_spec",)),
            _edge("supervisor", "lookup", ("subtask_assignments",)),
            _edge("supervisor", "collect", ("subtask_assignments",)),
            _edge("lookup", "aggregator", ("issue_status",)),
            _edge("collect", "aggregator", ("collected_responses",)),
            _edge("aggregator", "planner", ("aggregated_result",)),
            _edge("planner", "ResultSinkNode", ("sprint_plan",)),
        ],
    )


def build_hier_team_status_collection() -> WorkflowGraph:
    """Hierarchical: supervisor → collect from multiple people → aggregate → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("supervisor", "Supervisor-Agent", "AUTOMATED",
                  ("task_spec",), ("subtask_assignments",)),
            _node("collector_1", "InfoCollection-Agent", "INTERACTIVE",
                  ("question_list", "target_users"),
                  ("collected_responses",)),
            _node("collector_2", "InfoCollection-Agent", "INTERACTIVE",
                  ("question_list", "target_users"),
                  ("collected_responses",)),
            _node("aggregator", "Aggregator-Agent", "AUTOMATED",
                  ("subtask_result",), ("aggregated_result",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("aggregated_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "supervisor", ("task_spec",)),
            _edge("supervisor", "collector_1", ("subtask_assignments",)),
            _edge("supervisor", "collector_2", ("subtask_assignments",)),
            _edge("collector_1", "aggregator", ("collected_responses",)),
            _edge("collector_2", "aggregator", ("collected_responses",)),
            _edge("aggregator", "notify", ("aggregated_result",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


# ===================================================================
# 3e. Handoff / Swarm templates
# ===================================================================

def build_handoff_issue_triage() -> WorkflowGraph:
    """Handoff: lookup issue → classify → route to specialist → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("lookup", "IssueTracking-Agent", "AUTOMATED",
                  ("issue_ref",), ("issue_status", "issue_metadata")),
            _node("classify", "Worker-Agent", "AUTOMATED",
                  ("issue_metadata",), ("issue_category", "priority_level")),
            _node("router", "Supervisor-Agent", "AUTOMATED",
                  ("issue_category",), ("routed_task",)),
            _node("executor", "Worker-Agent", "AUTOMATED",
                  ("routed_task",), ("execution_result",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("execution_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "lookup", ("issue_ref",)),
            _edge("lookup", "classify", ("issue_metadata",)),
            _edge("classify", "router", ("issue_category",)),
            _edge("router", "executor", ("routed_task",)),
            _edge("executor", "notify", ("execution_result",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_handoff_customer_request() -> WorkflowGraph:
    """Handoff: intake request → route → execute → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("intake", "RequestInfo", "INTERACTIVE",
                  ("query_text",), ("intake_record",)),
            _node("router", "Supervisor-Agent", "AUTOMATED",
                  ("intake_record",), ("routed_task",)),
            _node("executor", "Worker-Agent", "AUTOMATED",
                  ("routed_task",), ("execution_result",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("execution_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "intake", ("query_text",)),
            _edge("intake", "router", ("intake_record",)),
            _edge("router", "executor", ("routed_task",)),
            _edge("executor", "notify", ("execution_result",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


# ===================================================================
# 3f. MoA (Mixture-of-Agents) templates
# ===================================================================

def build_moa_multi_reviewer() -> WorkflowGraph:
    """MoA: 3 parallel reviewers → synthesizer → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("reviewer_a", "Parallel-Proposer-A", "AUTOMATED",
                  ("task_spec",), ("proposal_a",)),
            _node("reviewer_b", "Parallel-Proposer-B", "AUTOMATED",
                  ("task_spec",), ("proposal_b",)),
            _node("reviewer_c", "Parallel-Proposer-C", "AUTOMATED",
                  ("task_spec",), ("proposal_c",)),
            _node("synthesizer", "MoA-Synthesizer", "AUTOMATED",
                  ("proposal_a", "proposal_b", "proposal_c"),
                  ("synthesized_result",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("synthesized_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "reviewer_a", ("task_spec",)),
            _edge("QuerySourceNode", "reviewer_b", ("task_spec",)),
            _edge("QuerySourceNode", "reviewer_c", ("task_spec",)),
            _edge("reviewer_a", "synthesizer", ("proposal_a",)),
            _edge("reviewer_b", "synthesizer", ("proposal_b",)),
            _edge("reviewer_c", "synthesizer", ("proposal_c",)),
            _edge("synthesizer", "notify", ("synthesized_result",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_moa_data_analysis() -> WorkflowGraph:
    """MoA: extract → 3 parallel analysts → synthesizer → report."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("extract", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("extracted_data",)),
            _node("analyst_a", "Parallel-Proposer-A", "AUTOMATED",
                  ("task_spec",), ("proposal_a",)),
            _node("analyst_b", "Parallel-Proposer-B", "AUTOMATED",
                  ("task_spec",), ("proposal_b",)),
            _node("analyst_c", "Parallel-Proposer-C", "AUTOMATED",
                  ("task_spec",), ("proposal_c",)),
            _node("synthesizer", "MoA-Synthesizer", "AUTOMATED",
                  ("proposal_a", "proposal_b", "proposal_c"),
                  ("synthesized_result",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("synthesized_result",), ("report_file",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "extract", ("file_path",)),
            _edge("extract", "analyst_a", ("extracted_data",)),
            _edge("extract", "analyst_b", ("extracted_data",)),
            _edge("extract", "analyst_c", ("extracted_data",)),
            _edge("analyst_a", "synthesizer", ("proposal_a",)),
            _edge("analyst_b", "synthesizer", ("proposal_b",)),
            _edge("analyst_c", "synthesizer", ("proposal_c",)),
            _edge("synthesizer", "report", ("synthesized_result",)),
            _edge("report", "ResultSinkNode", ("report_file",)),
        ],
    )


# ===================================================================
# 3g. Nested / Compound templates
# ===================================================================

def build_nested_review_then_approve() -> WorkflowGraph:
    """Nested: review-request loop (compound) → approval chain (compound) → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("review_loop", "review_request_review_loop", "AUTOMATED",
                  ("mr_url",), ("final_review_result", "fix_history")),
            _node("approval", "approval_chain", "AUTOMATED",
                  ("approval_request",), ("approval_decision",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("approval_decision",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "review_loop", ("mr_url",)),
            _edge("review_loop", "approval", ("final_review_result",)),
            _edge("approval", "notify", ("approval_decision",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_nested_extract_validate_approve() -> WorkflowGraph:
    """Nested: extract → data quality loop (compound) → approval → report."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("extract", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("extracted_data",)),
            _node("quality", "data_quality_loop", "AUTOMATED",
                  ("extracted_data",), ("validated_data",)),
            _node("approval", "approval_chain", "AUTOMATED",
                  ("approval_request",), ("approval_decision",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("validated_data",), ("report_file",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "extract", ("file_path",)),
            _edge("extract", "quality", ("extracted_data",)),
            _edge("quality", "approval", ("validated_data",)),
            _edge("approval", "report", ("approval_decision",)),
            _edge("report", "ResultSinkNode", ("report_file",)),
        ],
    )


def build_nested_debate_then_execute() -> WorkflowGraph:
    """Nested: debate loop (compound) → execute decision → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("debate", "debate_loop", "AUTOMATED",
                  ("task_spec",), ("debated_result",)),
            _node("executor", "Worker-Agent", "AUTOMATED",
                  ("debated_result",), ("execution_result",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("execution_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "debate", ("task_spec",)),
            _edge("debate", "executor", ("debated_result",)),
            _edge("executor", "notify", ("execution_result",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


# ===================================================================
# 3h. Role-based / Group Chat templates
# ===================================================================

def build_role_cross_functional_meeting() -> WorkflowGraph:
    """Role-based: collect info from roles → group discussion → record decision → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("collect", "InfoCollection-Agent", "INTERACTIVE",
                  ("question_list", "target_users"),
                  ("collected_responses",)),
            _node("discuss", "InfoCollection-Agent", "INTERACTIVE",
                  ("collected_responses",),
                  ("discussion_summary",)),
            _node("record", "ReportGenerate-Agent", "AUTOMATED",
                  ("discussion_summary",), ("decision_record",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("decision_record",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "collect",
                  ("question_list", "target_users")),
            _edge("collect", "discuss", ("collected_responses",)),
            _edge("discuss", "record", ("discussion_summary",)),
            _edge("record", "notify", ("decision_record",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_role_incident_response() -> WorkflowGraph:
    """Role-based: lookup issue → collect context → discuss → execute fix → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("lookup", "IssueTracking-Agent", "AUTOMATED",
                  ("issue_ref",), ("issue_status", "issue_metadata")),
            _node("collect", "InfoCollection-Agent", "INTERACTIVE",
                  ("question_list", "target_users"),
                  ("collected_responses",)),
            _node("discuss", "InfoCollection-Agent", "INTERACTIVE",
                  ("collected_responses",),
                  ("discussion_summary",)),
            _node("executor", "Worker-Agent", "AUTOMATED",
                  ("discussion_summary",), ("execution_result",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("execution_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "lookup", ("issue_ref",)),
            _edge("lookup", "collect", ("issue_metadata",)),
            _edge("collect", "discuss", ("collected_responses",)),
            _edge("discuss", "executor", ("discussion_summary",)),
            _edge("executor", "notify", ("execution_result",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


# ===================================================================
# 3i. TheAgentCompany domain-specific composite templates
# ===================================================================

def build_code_review_with_request_flow() -> WorkflowGraph:
    """SDE: review loop (compound) → notify manager."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("review_request_review_loop", "review_request_review_loop", "AUTOMATED",
                  ("mr_url",), ("final_review_result", "fix_history")),
            _node("Notify", "Notify", "INTERACTIVE",
                  ("final_review_result",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "review_request_review_loop", ("mr_url",)),
            _edge("review_request_review_loop", "Notify", ("final_review_result",)),
            _edge("Notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_pm_issue_status_collect_update() -> WorkflowGraph:
    """PM: look up issues → request status → update issue → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("lookup", "IssueTracking-Agent", "AUTOMATED",
                  ("issue_ref",), ("issue_status", "issue_metadata")),
            _node("request", "RequestInfo", "INTERACTIVE",
                  ("issue_ref",), ("status_update",),
                  target_actor_role="Developer"),
            _node("update", "IssueTracking-Agent", "AUTOMATED",
                  ("issue_ref", "update_data"),
                  ("issue_updated",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("issue_updated",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "lookup", ("issue_ref",)),
            _edge("lookup", "request", ("issue_ref",)),
            _edge("request", "update", ("status_update",)),
            _edge("update", "notify", ("issue_updated",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_hr_resume_review_schedule_notify() -> WorkflowGraph:
    """HR: download → debate screen (multi-reviewer) → schedule → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("download", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("resume_files",)),
            _node("screen", "ResumeScreening-Agent", "AUTOMATED",
                  ("resume_files",),
                  ("screening_result", "candidate_ranking")),
            _node("schedule", "RequestInfo", "INTERACTIVE",
                  ("candidate_ranking",), ("schedule_confirmation",),
                  target_actor_role="Candidate"),
            _node("notify", "Notify", "INTERACTIVE",
                  ("schedule_confirmation",), ("notification_sent",),
                  target_actor_role="HR_Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "download", ("file_path",)),
            _edge("download", "screen", ("resume_files",)),
            _edge("screen", "schedule", ("candidate_ranking",)),
            _edge("schedule", "notify", ("schedule_confirmation",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_finance_invoice_match_flag_report() -> WorkflowGraph:
    """Finance: download → match invoices → flag → report → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("download", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("invoice_files", "payment_files")),
            _node("match", "InvoiceMatching-Agent", "AUTOMATED",
                  ("invoice_files", "payment_files"),
                  ("match_result", "flagged_items")),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("match_result",), ("report_file",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("report_file",), ("notification_sent",),
                  target_actor_role="Finance_Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "download", ("file_path",)),
            _edge("download", "match", ("invoice_files", "payment_files")),
            _edge("match", "report", ("match_result",)),
            _edge("report", "notify", ("report_file",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


def build_ds_download_analyze_visualize_report() -> WorkflowGraph:
    """DS: download → extract → transform → visualize → report (with fork)."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("extract", "DataExtract-Agent", "AUTOMATED",
                  ("file_path",), ("extracted_data",)),
            _node("transform", "DataTransform-Agent", "AUTOMATED",
                  ("extracted_data",), ("transformed_data",)),
            _node("visualize", "Visualization-Agent", "AUTOMATED",
                  ("transformed_data",), ("chart_files",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("transformed_data",), ("report_file",)),
            _node("upload", "FileUpload-Agent", "AUTOMATED",
                  ("report_file",), ("upload_url",)),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "extract", ("file_path",)),
            _edge("extract", "transform", ("extracted_data",)),
            _edge("transform", "visualize", ("transformed_data",)),
            _edge("transform", "report", ("transformed_data",)),
            _edge("report", "upload", ("report_file",)),
            _edge("upload", "ResultSinkNode", ("upload_url",)),
            _edge("visualize", "ResultSinkNode", ("chart_files",)),
        ],
    )


def build_admin_collect_feedback_summarize() -> WorkflowGraph:
    """Admin: collect feedback → transform → generate summary report → notify."""
    return WorkflowGraph(
        nodes=[
            _sys("QuerySourceNode"),
            _node("collect", "InfoCollection-Agent", "INTERACTIVE",
                  ("question_list", "target_users"),
                  ("collected_responses",)),
            _node("transform", "DataTransform-Agent", "AUTOMATED",
                  ("collected_responses",), ("transformed_data",)),
            _node("report", "ReportGenerate-Agent", "AUTOMATED",
                  ("transformed_data",), ("report_file",)),
            _node("notify", "Notify", "INTERACTIVE",
                  ("report_file",), ("notification_sent",),
                  target_actor_role="Manager"),
            _sys("ResultSinkNode"),
        ],
        edges=[
            _edge("QuerySourceNode", "collect",
                  ("question_list", "target_users")),
            _edge("collect", "transform", ("collected_responses",)),
            _edge("transform", "report", ("transformed_data",)),
            _edge("report", "notify", ("report_file",)),
            _edge("notify", "ResultSinkNode", ("notification_sent",)),
        ],
    )


# ===================================================================
# Registry of all workflow templates
# ===================================================================

WORKFLOW_TEMPLATES: Dict[str, WorkflowGraph] = {}


def _register_all() -> None:
    """Build and register all workflow templates lazily."""
    builders = {
        # Sequential
        "seq_document_analysis":     build_seq_document_analysis,
        "seq_data_pipeline":         build_seq_data_pipeline,
        "seq_repo_modify_commit":    build_seq_repo_modify_commit,
        "seq_expense_validate_report": build_seq_expense_validate_report,
        "seq_resume_screen_schedule": build_seq_resume_screen_schedule,
        # Debate
        "debate_code_review":        build_debate_code_review,
        "debate_loop_code_review":   build_debate_loop_code_review,
        "debate_proposal_evaluation": build_debate_proposal_evaluation,
        # Reflection
        "reflect_report_writing":    build_reflect_report_writing,
        "reflect_code_improvement":  build_reflect_code_improvement,
        "reflect_invoice_matching":  build_reflect_invoice_matching,
        # Hierarchical
        "hier_multi_file_analysis":  build_hier_multi_file_analysis,
        "hier_sprint_planning":      build_hier_sprint_planning,
        "hier_team_status_collection": build_hier_team_status_collection,
        # Handoff
        "handoff_issue_triage":      build_handoff_issue_triage,
        "handoff_customer_request":  build_handoff_customer_request,
        # MoA
        "moa_multi_reviewer":        build_moa_multi_reviewer,
        "moa_data_analysis":         build_moa_data_analysis,
        # Nested
        "nested_review_then_approve":      build_nested_review_then_approve,
        "nested_extract_validate_approve": build_nested_extract_validate_approve,
        "nested_debate_then_execute":      build_nested_debate_then_execute,
        # Role-based
        "role_cross_functional_meeting": build_role_cross_functional_meeting,
        "role_incident_response":    build_role_incident_response,
        # Domain-specific composites
        "code_review_with_request_flow":     build_code_review_with_request_flow,
        "pm_issue_status_collect_update":    build_pm_issue_status_collect_update,
        "hr_resume_review_schedule_notify":  build_hr_resume_review_schedule_notify,
        "finance_invoice_match_flag_report": build_finance_invoice_match_flag_report,
        "ds_download_analyze_visualize_report": build_ds_download_analyze_visualize_report,
        "admin_collect_feedback_summarize":  build_admin_collect_feedback_summarize,
    }
    for name, builder in builders.items():
        WORKFLOW_TEMPLATES[name] = builder()


_register_all()


# ===================================================================
# 4. Helper: get all intent names referenced in seed patterns
# ===================================================================

def get_all_intent_names() -> List[str]:
    """Return sorted list of all intent names in the catalog."""
    return sorted(INTENT_CATALOG.keys())


def get_template_by_pattern_name(pattern_name: str) -> WorkflowGraph | None:
    """Look up a pre-assembled workflow template by pattern name."""
    return WORKFLOW_TEMPLATES.get(pattern_name)
