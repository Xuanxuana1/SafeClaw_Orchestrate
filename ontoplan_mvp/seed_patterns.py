"""Initial A-Box: SOP pattern templates covering 8 orchestration meta-patterns
crossed with enterprise office task domains.

Orchestration meta-patterns:
  1. Sequential / Pipeline
  2. Debate / MAD
  3. Reflection / Critique-Revise
  4. Hierarchical / Supervisor
  5. Handoff / Swarm
  6. MoA (Mixture-of-Agents)
  7. Nested / Compound
  8. Role-based / Group Chat

Task domains (from TheAgentCompany analysis):
  - SDE: code review, repo management, CI/CD
  - PM: issue tracking, sprint planning, status reporting
  - HR: resume screening, scheduling, salary analysis
  - Finance: invoice matching, expense validation, tax
  - DS: data extraction, analysis, visualization
  - Admin: meeting arrangement, info collection
"""

from __future__ import annotations

from ontoplan_mvp.models import (
    CompoundNodeDef,
    FSMTransition,
    InternalNodeSlot,
    NodeType,
    Ontology,
    PatternTemplate,
)


# ---------------------------------------------------------------------------
# Extended node types for orchestration patterns
# ---------------------------------------------------------------------------

ORCHESTRATION_NODE_TYPES = {
    # --- Sequential / Pipeline building blocks ---
    "DataExtract-Agent": NodeType(
        name="DataExtract-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("file_path",),
        output_artifacts=("extracted_data",),
        keywords=("extract", "parse", "read", "download"),
    ),
    "DataTransform-Agent": NodeType(
        name="DataTransform-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("extracted_data",),
        output_artifacts=("transformed_data",),
        keywords=("transform", "clean", "merge", "convert"),
    ),
    "ReportGenerate-Agent": NodeType(
        name="ReportGenerate-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("transformed_data",),
        output_artifacts=("report_file",),
        keywords=("report", "generate", "create", "write", "output"),
    ),
    "FileUpload-Agent": NodeType(
        name="FileUpload-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("report_file",),
        output_artifacts=("upload_url",),
        keywords=("upload", "save", "store", "publish"),
    ),
    "Visualization-Agent": NodeType(
        name="Visualization-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("transformed_data",),
        output_artifacts=("chart_files",),
        keywords=("chart", "plot", "visualize", "graph", "pie", "bar"),
    ),

    # --- Debate / MAD ---
    "Proposer-Agent": NodeType(
        name="Proposer-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("task_spec",),
        output_artifacts=("proposal",),
        keywords=("propose", "draft", "initial", "generate"),
    ),
    "Critic-Agent": NodeType(
        name="Critic-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("proposal",),
        output_artifacts=("critique", "counter_proposal"),
        keywords=("critique", "review", "challenge", "argue", "debate"),
    ),
    "Judge-Agent": NodeType(
        name="Judge-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("proposal", "critique"),
        output_artifacts=("final_decision",),
        keywords=("judge", "decide", "vote", "consensus", "select"),
    ),

    # --- Hierarchical / Supervisor ---
    "Supervisor-Agent": NodeType(
        name="Supervisor-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("task_spec",),
        output_artifacts=("subtask_assignments", "final_synthesis"),
        keywords=("supervise", "coordinate", "manage", "orchestrate", "delegate"),
    ),
    "Worker-Agent": NodeType(
        name="Worker-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("subtask_spec",),
        output_artifacts=("subtask_result",),
        keywords=("execute", "worker", "task", "implement"),
    ),
    "Aggregator-Agent": NodeType(
        name="Aggregator-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("subtask_result",),
        output_artifacts=("aggregated_result",),
        keywords=("aggregate", "combine", "merge", "synthesize", "collect"),
    ),

    # --- MoA (Mixture of Agents) ---
    "Parallel-Proposer-A": NodeType(
        name="Parallel-Proposer-A",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("task_spec",),
        output_artifacts=("proposal_a",),
        keywords=("propose", "variant", "alternative"),
    ),
    "Parallel-Proposer-B": NodeType(
        name="Parallel-Proposer-B",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("task_spec",),
        output_artifacts=("proposal_b",),
        keywords=("propose", "variant", "alternative"),
    ),
    "Parallel-Proposer-C": NodeType(
        name="Parallel-Proposer-C",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("task_spec",),
        output_artifacts=("proposal_c",),
        keywords=("propose", "variant", "alternative"),
    ),
    "MoA-Synthesizer": NodeType(
        name="MoA-Synthesizer",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("proposal_a", "proposal_b", "proposal_c"),
        output_artifacts=("synthesized_result",),
        keywords=("synthesize", "best-of", "select", "merge"),
    ),

    # --- Domain-specific agents ---
    "ResumeScreening-Agent": NodeType(
        name="ResumeScreening-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("resume_files",),
        output_artifacts=("screening_result", "candidate_ranking"),
        keywords=("resume", "screen", "candidate", "hire", "recruit"),
    ),
    "InvoiceMatching-Agent": NodeType(
        name="InvoiceMatching-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("invoice_files", "payment_files"),
        output_artifacts=("match_result", "flagged_items"),
        keywords=("invoice", "payment", "match", "reconcile"),
    ),
    "ExpenseValidation-Agent": NodeType(
        name="ExpenseValidation-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("expense_files", "policy_rules"),
        output_artifacts=("validation_result", "exceptions"),
        keywords=("expense", "validate", "policy", "reimburse"),
    ),
    "RepoManagement-Agent": NodeType(
        name="RepoManagement-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("GitLab",),
        input_artifacts=("repo_url",),
        output_artifacts=("repo_metadata", "file_list"),
        keywords=("repo", "repository", "clone", "branch", "pipeline"),
    ),
    "SprintPlanning-Agent": NodeType(
        name="SprintPlanning-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("Plane",),
        input_artifacts=("project_ref",),
        output_artifacts=("sprint_plan", "task_assignments"),
        keywords=("sprint", "plan", "milestone", "backlog"),
    ),
    "InfoCollection-Agent": NodeType(
        name="InfoCollection-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("RocketChat",),
        input_artifacts=("question_list", "target_users"),
        output_artifacts=("collected_responses",),
        keywords=("collect", "survey", "gather", "poll", "feedback"),
    ),

    # --- SDE Pack additions ---
    "BugFix-Agent": NodeType(
        name="BugFix-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("GitLab",),
        input_artifacts=("issue_ref", "repo_url"),
        output_artifacts=("fix_commit", "test_result"),
        keywords=("bug", "fix", "patch", "debug", "implement"),
    ),
    "Deployment-Agent": NodeType(
        name="Deployment-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("GitLab",),
        input_artifacts=("repo_url", "branch"),
        output_artifacts=("deploy_status", "pipeline_url"),
        keywords=("deploy", "pipeline", "release", "ci", "cd"),
    ),

    # --- HR Pack additions ---
    "InterviewScheduling-Agent": NodeType(
        name="InterviewScheduling-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("RocketChat", "OwnCloud"),
        input_artifacts=("candidate_ranking", "interviewer_list"),
        output_artifacts=("schedule",),
        keywords=("interview", "schedule", "calendar", "arrange"),
    ),
    "SalaryAnalysis-Agent": NodeType(
        name="SalaryAnalysis-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("salary_data",),
        output_artifacts=("salary_report",),
        keywords=("salary", "compensation", "pay", "wage"),
    ),
    "AttendanceCheck-Agent": NodeType(
        name="AttendanceCheck-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud", "RocketChat"),
        input_artifacts=("date_range", "department"),
        output_artifacts=("attendance_data",),
        keywords=("attendance", "leave", "absence", "checkin"),
    ),

    # --- Finance Pack additions ---
    "TaxCalculation-Agent": NodeType(
        name="TaxCalculation-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("financial_data", "tax_rules"),
        output_artifacts=("tax_report",),
        keywords=("tax", "calculate", "fiscal", "deduction"),
    ),

    # --- DS Pack additions ---
    "DataCleaning-Agent": NodeType(
        name="DataCleaning-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("raw_data_files",),
        output_artifacts=("cleaned_data",),
        keywords=("clean", "deduplicate", "normalize", "preprocess"),
    ),
    "StatAnalysis-Agent": NodeType(
        name="StatAnalysis-Agent",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("cleaned_data", "analysis_spec"),
        output_artifacts=("analysis_result", "charts"),
        keywords=("stat", "statistics", "analyze", "correlation", "regression"),
    ),

    # --- Admin Pack additions ---
    "MeetingArrange-Agent": NodeType(
        name="MeetingArrange-Agent",
        execution_mode="AUTOMATED",
        access_bindings=("RocketChat", "OwnCloud"),
        input_artifacts=("attendee_list", "time_range"),
        output_artifacts=("meeting_schedule",),
        keywords=("meeting", "calendar", "book", "room", "conference"),
    ),
}

# ---------------------------------------------------------------------------
# Compound nodes for iterative orchestration patterns
# ---------------------------------------------------------------------------

ORCHESTRATION_COMPOUND_NODES = {
    # --- Debate loop (2 rounds of propose-critique-revise) ---
    "debate_loop": NodeType(
        name="debate_loop",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("task_spec",),
        output_artifacts=("debated_result",),
        keywords=("debate", "argue", "discuss", "challenge"),
        compound_def=CompoundNodeDef(
            states=("PROPOSING", "CRITIQUING", "REVISING", "JUDGING", "DONE"),
            initial_state="PROPOSING",
            transitions=(
                FSMTransition("PROPOSING", "CRITIQUING", "proposal_ready"),
                FSMTransition("CRITIQUING", "REVISING", "critique_ready"),
                FSMTransition("REVISING", "CRITIQUING", "revision_ready AND rounds < max"),
                FSMTransition("REVISING", "JUDGING", "rounds >= max"),
                FSMTransition("CRITIQUING", "JUDGING", "consensus_reached"),
                FSMTransition("JUDGING", "DONE", "decision_made"),
            ),
            max_iterations=4,
            timeout_seconds=300,
            internal_nodes=(
                InternalNodeSlot("PROPOSING", "Proposer-Agent", "AUTOMATED"),
                InternalNodeSlot("CRITIQUING", "Critic-Agent", "AUTOMATED"),
                InternalNodeSlot("REVISING", "Proposer-Agent", "AUTOMATED"),
                InternalNodeSlot("JUDGING", "Judge-Agent", "AUTOMATED"),
            ),
        ),
    ),

    # --- Reflection / Critique-Revise loop ---
    "reflection_loop": NodeType(
        name="reflection_loop",
        execution_mode="AUTOMATED",
        access_bindings=(),
        input_artifacts=("task_spec",),
        output_artifacts=("refined_result",),
        keywords=("reflect", "revise", "improve", "iterate", "refine"),
        compound_def=CompoundNodeDef(
            states=("DRAFTING", "CRITIQUING", "REVISING", "DONE"),
            initial_state="DRAFTING",
            transitions=(
                FSMTransition("DRAFTING", "CRITIQUING", "draft_ready"),
                FSMTransition("CRITIQUING", "REVISING", "has_issues"),
                FSMTransition("CRITIQUING", "DONE", "quality_ok"),
                FSMTransition("REVISING", "CRITIQUING", "revision_ready"),
            ),
            max_iterations=3,
            timeout_seconds=300,
            internal_nodes=(
                InternalNodeSlot("DRAFTING", "Worker-Agent", "AUTOMATED"),
                InternalNodeSlot("CRITIQUING", "Critic-Agent", "AUTOMATED"),
                InternalNodeSlot("REVISING", "Worker-Agent", "AUTOMATED"),
            ),
        ),
    ),

    # --- Approval escalation chain ---
    "approval_chain": NodeType(
        name="approval_chain",
        execution_mode="AUTOMATED",
        access_bindings=("RocketChat", "Email"),
        input_artifacts=("approval_request",),
        output_artifacts=("approval_decision",),
        keywords=("approval", "chain", "escalate", "authorize"),
        compound_def=CompoundNodeDef(
            states=("L1_APPROVAL", "L2_ESCALATION", "APPROVED", "REJECTED"),
            initial_state="L1_APPROVAL",
            transitions=(
                FSMTransition("L1_APPROVAL", "APPROVED", "approved_by_l1"),
                FSMTransition("L1_APPROVAL", "L2_ESCALATION", "escalate_to_l2"),
                FSMTransition("L1_APPROVAL", "REJECTED", "rejected_by_l1"),
                FSMTransition("L2_ESCALATION", "APPROVED", "approved_by_l2"),
                FSMTransition("L2_ESCALATION", "REJECTED", "rejected_by_l2"),
            ),
            max_iterations=2,
            timeout_seconds=600,
            internal_nodes=(
                InternalNodeSlot("L1_APPROVAL", "ApprovalGate", "APPROVAL",
                                 target_actor_role="Manager", channel="RocketChat"),
                InternalNodeSlot("L2_ESCALATION", "ApprovalGate", "APPROVAL",
                                 target_actor_role="Director", channel="Email"),
            ),
        ),
    ),

    # --- Data quality check loop ---
    "data_quality_loop": NodeType(
        name="data_quality_loop",
        execution_mode="AUTOMATED",
        access_bindings=("OwnCloud",),
        input_artifacts=("extracted_data",),
        output_artifacts=("validated_data",),
        keywords=("quality", "check", "validate", "data", "clean"),
        compound_def=CompoundNodeDef(
            states=("CHECKING", "REQUESTING_CORRECTION", "DONE"),
            initial_state="CHECKING",
            transitions=(
                FSMTransition("CHECKING", "REQUESTING_CORRECTION", "has_quality_issues"),
                FSMTransition("REQUESTING_CORRECTION", "CHECKING", "correction_received"),
                FSMTransition("CHECKING", "DONE", "quality_ok"),
            ),
            max_iterations=5,
            timeout_seconds=600,
            internal_nodes=(
                InternalNodeSlot("CHECKING", "Critic-Agent", "AUTOMATED"),
                InternalNodeSlot("REQUESTING_CORRECTION", "RequestInfo", "INTERACTIVE",
                                 target_actor_role="Developer", channel="RocketChat"),
            ),
        ),
    ),
}


# ---------------------------------------------------------------------------
# A-Box: SOP Pattern Templates
# Cross of 8 orchestration patterns x enterprise domains
# ---------------------------------------------------------------------------

SEED_PATTERNS = (
    # =======================================================================
    # 1. Sequential / Pipeline patterns
    # =======================================================================
    PatternTemplate(
        name="seq_document_analysis",
        required_intents=("file_download", "data_extraction", "report_generation"),
    ),
    PatternTemplate(
        name="seq_data_pipeline",
        required_intents=("file_download", "data_extraction", "data_transform", "visualization"),
    ),
    PatternTemplate(
        name="seq_repo_modify_commit",
        required_intents=("repo_clone", "code_modification", "code_push"),
    ),
    PatternTemplate(
        name="seq_issue_check_notify",
        required_intents=("issue_lookup", "status_notification"),
    ),
    PatternTemplate(
        name="seq_expense_validate_report",
        required_intents=("file_download", "expense_validation", "report_generation"),
    ),
    PatternTemplate(
        name="seq_resume_screen_schedule",
        required_intents=("file_download", "resume_screening", "interview_scheduling"),
    ),

    # =======================================================================
    # 2. Debate / MAD patterns
    # =======================================================================
    PatternTemplate(
        name="debate_code_review",
        required_intents=("code_review", "debate_review", "final_decision"),
    ),
    PatternTemplate(
        name="debate_proposal_evaluation",
        required_intents=("proposal_generation", "debate_review", "final_decision",
                          "status_notification"),
    ),
    PatternTemplate(
        name="debate_data_interpretation",
        required_intents=("data_extraction", "debate_review", "final_decision",
                          "report_generation"),
    ),

    # =======================================================================
    # 3. Reflection / Critique-Revise patterns
    # =======================================================================
    PatternTemplate(
        name="reflect_report_writing",
        required_intents=("data_extraction", "report_draft", "critique_revise"),
    ),
    PatternTemplate(
        name="reflect_code_improvement",
        required_intents=("code_review", "critique_revise", "code_push"),
    ),
    PatternTemplate(
        name="reflect_invoice_matching",
        required_intents=("file_download", "invoice_matching", "critique_revise",
                          "report_generation"),
    ),

    # =======================================================================
    # 4. Hierarchical / Supervisor patterns
    # =======================================================================
    PatternTemplate(
        name="hier_multi_file_analysis",
        required_intents=("task_decomposition", "parallel_extraction",
                          "result_aggregation", "report_generation"),
    ),
    PatternTemplate(
        name="hier_sprint_planning",
        required_intents=("task_decomposition", "issue_lookup",
                          "request_status_update", "result_aggregation",
                          "sprint_planning"),
    ),
    PatternTemplate(
        name="hier_team_status_collection",
        required_intents=("task_decomposition", "info_collection",
                          "result_aggregation", "status_notification"),
    ),

    # =======================================================================
    # 5. Handoff / Swarm patterns
    # =======================================================================
    PatternTemplate(
        name="handoff_issue_triage",
        required_intents=("issue_lookup", "issue_classification", "handoff_routing",
                          "status_notification"),
    ),
    PatternTemplate(
        name="handoff_customer_request",
        required_intents=("request_intake", "handoff_routing", "task_execution",
                          "status_notification"),
    ),

    # =======================================================================
    # 6. MoA (Mixture-of-Agents) patterns
    # =======================================================================
    PatternTemplate(
        name="moa_multi_reviewer",
        required_intents=("code_review", "parallel_review", "review_synthesis",
                          "status_notification"),
    ),
    PatternTemplate(
        name="moa_data_analysis",
        required_intents=("data_extraction", "parallel_analysis",
                          "analysis_synthesis", "report_generation"),
    ),

    # =======================================================================
    # 7. Nested / Compound patterns (use compound nodes as sub-workflows)
    # =======================================================================
    PatternTemplate(
        name="nested_review_then_approve",
        required_intents=("code_review", "request_fix_update",
                          "approval_request", "status_notification"),
    ),
    PatternTemplate(
        name="nested_extract_validate_approve",
        required_intents=("file_download", "data_extraction", "data_quality_check",
                          "approval_request", "report_generation"),
    ),
    PatternTemplate(
        name="nested_debate_then_execute",
        required_intents=("proposal_generation", "debate_review",
                          "final_decision", "task_execution",
                          "status_notification"),
    ),

    # =======================================================================
    # 8. Role-based / Group Chat patterns
    # =======================================================================
    PatternTemplate(
        name="role_cross_functional_meeting",
        required_intents=("info_collection", "multi_party_discussion",
                          "decision_recording", "status_notification"),
    ),
    PatternTemplate(
        name="role_incident_response",
        required_intents=("issue_lookup", "info_collection",
                          "multi_party_discussion", "task_execution",
                          "status_notification"),
    ),

    # =======================================================================
    # TheAgentCompany specific composite patterns
    # =======================================================================
    PatternTemplate(
        name="code_review_with_request_flow",
        required_intents=("code_review", "request_fix_update", "status_notification"),
    ),
    PatternTemplate(
        name="pm_issue_status_collect_update",
        required_intents=("issue_lookup", "request_status_update",
                          "issue_update", "status_notification"),
    ),
    PatternTemplate(
        name="hr_resume_review_schedule_notify",
        required_intents=("file_download", "resume_screening",
                          "interview_scheduling", "status_notification"),
    ),
    PatternTemplate(
        name="finance_invoice_match_flag_report",
        required_intents=("file_download", "invoice_matching",
                          "report_generation", "status_notification"),
    ),
    PatternTemplate(
        name="ds_download_analyze_visualize_report",
        required_intents=("file_download", "data_extraction",
                          "data_transform", "visualization",
                          "report_generation"),
    ),
    PatternTemplate(
        name="admin_collect_feedback_summarize",
        required_intents=("info_collection", "data_transform",
                          "report_generation", "status_notification"),
    ),
)


def build_full_ontology() -> Ontology:
    """Build the complete ontology with all node types and seed patterns.

    Merges:
      - Original base node types (from ontology.py)
      - Orchestration node types (Proposer, Critic, Judge, Supervisor, etc.)
      - Compound nodes (debate_loop, reflection_loop, approval_chain, etc.)
      - Full seed pattern library (30 patterns)
    """
    from ontoplan_mvp.ontology import build_default_ontology

    base = build_default_ontology()
    all_node_types = dict(base.node_types)
    all_node_types.update(ORCHESTRATION_NODE_TYPES)
    all_node_types.update(ORCHESTRATION_COMPOUND_NODES)

    return Ontology(
        node_types=all_node_types,
        patterns=SEED_PATTERNS,
    )
