"""Tests for compound node model and FSM definitions."""

from ontoplan_mvp.models import CompoundNodeDef, FSMTransition, InternalNodeSlot
from ontoplan_mvp.ontology import build_default_ontology


def test_compound_node_def_exists_in_ontology():
    ontology = build_default_ontology()
    nt = ontology.node_types["review_request_review_loop"]
    assert nt.is_compound
    assert nt.compound_def is not None


def test_compound_fsm_has_correct_states():
    ontology = build_default_ontology()
    fsm = ontology.node_types["review_request_review_loop"].compound_def
    assert fsm.states == ("REVIEWING", "REQUEST_FIX", "DONE")
    assert fsm.initial_state == "REVIEWING"


def test_compound_fsm_transitions():
    ontology = build_default_ontology()
    fsm = ontology.node_types["review_request_review_loop"].compound_def
    assert len(fsm.transitions) == 3
    transition_pairs = [(t.from_state, t.to_state) for t in fsm.transitions]
    assert ("REVIEWING", "REQUEST_FIX") in transition_pairs
    assert ("REQUEST_FIX", "REVIEWING") in transition_pairs
    assert ("REVIEWING", "DONE") in transition_pairs


def test_compound_fsm_termination_guarantee():
    ontology = build_default_ontology()
    fsm = ontology.node_types["review_request_review_loop"].compound_def
    assert fsm.max_iterations >= 1
    assert fsm.timeout_seconds > 0


def test_compound_internal_nodes():
    ontology = build_default_ontology()
    fsm = ontology.node_types["review_request_review_loop"].compound_def
    assert len(fsm.internal_nodes) == 2

    reviewing = next(n for n in fsm.internal_nodes if n.state == "REVIEWING")
    assert reviewing.execution_mode == "AUTOMATED"
    assert reviewing.node_type_name == "CodeReview-Agent"

    request_fix = next(n for n in fsm.internal_nodes if n.state == "REQUEST_FIX")
    assert request_fix.execution_mode == "INTERACTIVE"
    assert request_fix.target_actor_role == "Developer"
    assert request_fix.channel == "RocketChat"


def test_non_compound_nodes_have_no_def():
    ontology = build_default_ontology()
    for name, nt in ontology.node_types.items():
        if name != "review_request_review_loop":
            assert not nt.is_compound
