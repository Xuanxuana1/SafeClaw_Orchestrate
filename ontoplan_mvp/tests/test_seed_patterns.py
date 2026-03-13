"""Tests for seed pattern catalog and full ontology."""

from ontoplan_mvp.seed_patterns import (
    ORCHESTRATION_COMPOUND_NODES,
    ORCHESTRATION_NODE_TYPES,
    SEED_PATTERNS,
    build_full_ontology,
)


def test_full_ontology_loads():
    ont = build_full_ontology()
    assert len(ont.node_types) >= 30
    assert len(ont.patterns) >= 25


def test_all_compound_nodes_have_fsm():
    for name, nt in ORCHESTRATION_COMPOUND_NODES.items():
        assert nt.is_compound, f"{name} should be compound"
        assert nt.compound_def.max_iterations >= 1
        assert len(nt.compound_def.states) >= 2
        assert len(nt.compound_def.transitions) >= 2
        assert len(nt.compound_def.internal_nodes) >= 2


def test_debate_loop_structure():
    dl = ORCHESTRATION_COMPOUND_NODES["debate_loop"]
    assert "PROPOSING" in dl.compound_def.states
    assert "CRITIQUING" in dl.compound_def.states
    assert "JUDGING" in dl.compound_def.states
    assert dl.compound_def.max_iterations == 4
    types = {s.node_type_name for s in dl.compound_def.internal_nodes}
    assert "Proposer-Agent" in types
    assert "Critic-Agent" in types
    assert "Judge-Agent" in types


def test_reflection_loop_structure():
    rl = ORCHESTRATION_COMPOUND_NODES["reflection_loop"]
    assert "DRAFTING" in rl.compound_def.states
    assert "CRITIQUING" in rl.compound_def.states
    assert rl.compound_def.max_iterations == 3


def test_approval_chain_has_escalation():
    ac = ORCHESTRATION_COMPOUND_NODES["approval_chain"]
    assert "L1_APPROVAL" in ac.compound_def.states
    assert "L2_ESCALATION" in ac.compound_def.states
    roles = {s.target_actor_role for s in ac.compound_def.internal_nodes}
    assert "Manager" in roles
    assert "Director" in roles


def test_patterns_cover_all_orchestration_types():
    prefixes = {p.name.split("_")[0] for p in SEED_PATTERNS}
    expected = {"seq", "debate", "reflect", "hier", "handoff", "moa", "nested", "role"}
    assert expected.issubset(prefixes), f"Missing: {expected - prefixes}"


def test_patterns_cover_all_task_domains():
    names = {p.name for p in SEED_PATTERNS}
    domain_patterns = [
        "code_review_with_request_flow",     # SDE
        "pm_issue_status_collect_update",     # PM
        "hr_resume_review_schedule_notify",   # HR
        "finance_invoice_match_flag_report",  # Finance
        "ds_download_analyze_visualize_report",  # DS
        "admin_collect_feedback_summarize",   # Admin
    ]
    for dp in domain_patterns:
        assert dp in names, f"Missing domain pattern: {dp}"


def test_no_duplicate_node_type_names():
    ont = build_full_ontology()
    names = list(ont.node_types.keys())
    assert len(names) == len(set(names))


def test_no_duplicate_pattern_names():
    names = [p.name for p in SEED_PATTERNS]
    assert len(names) == len(set(names))


def test_compound_node_internal_types_exist():
    """Every internal node slot references a node type that exists in the ontology."""
    ont = build_full_ontology()
    for name, nt in ont.node_types.items():
        if not nt.is_compound:
            continue
        for slot in nt.compound_def.internal_nodes:
            assert slot.node_type_name in ont.node_types, (
                f"Compound {name} references missing type {slot.node_type_name}"
            )
