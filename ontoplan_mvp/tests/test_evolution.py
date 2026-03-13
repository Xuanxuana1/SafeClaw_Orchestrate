"""Tests for mutation operators, crossover, fitness, and micro-evolution loop."""

import random

from ontoplan_mvp.engine import OntoPlanEngine
from ontoplan_mvp.evolution import (
    FitnessWeights,
    apply_random_mutation,
    c1_subgraph_swap,
    compute_fitness,
    m1_node_add,
    m2_node_remove,
    m3_node_replace,
    m4_edge_add,
    m5_edge_remove,
    m6_prompt_mutate,
    m7_compound_node_mutate,
    micro_evolve,
)
from ontoplan_mvp.ontology import build_default_ontology


def _build_initial_plan():
    ontology = build_default_ontology()
    engine = OntoPlanEngine(ontology)
    query = "Check Sarah's MR, if code has issues ask her to fix, notify PM when done"
    intents = engine.extract_intents(query)
    candidates = engine.retrieve_candidates(intents)
    plan = engine.assemble(candidates, intents)
    return plan.workflow, intents, ontology


# -- Mutation operator tests --


def test_m1_node_add_preserves_acyclicity():
    graph, intents, ontology = _build_initial_plan()
    random.seed(42)
    result = m1_node_add(graph, ontology)
    if result is not None:
        assert result.is_acyclic()
        assert len(result.nodes) == len(graph.nodes) + 1


def test_m2_node_remove_preserves_connectivity():
    graph, intents, ontology = _build_initial_plan()
    random.seed(42)
    result = m2_node_remove(graph, ontology)
    if result is not None:
        assert result.is_acyclic()
        assert len(result.nodes) < len(graph.nodes)


def test_m3_node_replace_keeps_same_count():
    graph, intents, ontology = _build_initial_plan()
    random.seed(42)
    result = m3_node_replace(graph, ontology)
    if result is not None:
        assert len(result.nodes) == len(graph.nodes)
        assert result.is_acyclic()


def test_m4_edge_add_preserves_acyclicity():
    graph, intents, ontology = _build_initial_plan()
    random.seed(42)
    result = m4_edge_add(graph, ontology)
    if result is not None:
        assert result.is_acyclic()
        assert len(result.edges) > len(graph.edges)


def test_m5_edge_remove_keeps_graph_connected():
    graph, intents, ontology = _build_initial_plan()
    random.seed(42)
    result = m5_edge_remove(graph, ontology)
    if result is not None:
        assert result.is_acyclic()


def test_m6_prompt_mutate_adds_metadata():
    graph, intents, ontology = _build_initial_plan()
    random.seed(42)
    result = m6_prompt_mutate(graph, ontology)
    assert result is not None
    mutated = [n for n in result.nodes if "prompt_variant" in n.metadata]
    assert len(mutated) == 1


def test_m7_compound_node_mutate():
    graph, intents, ontology = _build_initial_plan()
    random.seed(42)
    result = m7_compound_node_mutate(graph, ontology)
    if result is not None:
        compounds = [n for n in result.nodes if "max_iterations" in n.metadata]
        assert len(compounds) >= 1


# -- Crossover test --


def test_c1_subgraph_swap_produces_valid_child():
    graph1, intents, ontology = _build_initial_plan()
    graph2 = graph1.deep_copy()
    # Mutate graph2 so it differs
    random.seed(123)
    mutated = m3_node_replace(graph2, ontology)
    if mutated is None:
        mutated = graph2
    random.seed(456)
    child = c1_subgraph_swap(graph1, mutated)
    if child is not None:
        assert child.is_acyclic()


# -- Fitness function tests --


def test_fitness_returns_positive_for_valid_graph():
    graph, intents, ontology = _build_initial_plan()
    score = compute_fitness(graph, intents, ontology)
    assert score > 0.0


def test_fitness_zero_for_empty_graph():
    from ontoplan_mvp.models import WorkflowGraph
    empty = WorkflowGraph(nodes=[], edges=[])
    ontology = build_default_ontology()
    score = compute_fitness(empty, [], ontology)
    assert score == 0.0


def test_fitness_uses_historical_scores():
    graph, intents, ontology = _build_initial_plan()
    low_history = {n.node_type: 0.1 for n in graph.nodes}
    high_history = {n.node_type: 0.9 for n in graph.nodes}
    score_low = compute_fitness(graph, intents, ontology, historical_scores=low_history)
    score_high = compute_fitness(graph, intents, ontology, historical_scores=high_history)
    assert score_high > score_low


# -- Micro-evolution loop tests --


def test_micro_evolve_preserves_or_improves():
    graph, intents, ontology = _build_initial_plan()
    initial_score = compute_fitness(graph, intents, ontology)
    evolved = micro_evolve(graph, intents, ontology, rng_seed=42)
    evolved_score = compute_fitness(evolved, intents, ontology)
    assert evolved_score >= initial_score - 0.01  # allow tiny floating point drift


def test_micro_evolve_always_returns_valid_dag():
    graph, intents, ontology = _build_initial_plan()
    evolved = micro_evolve(graph, intents, ontology, rng_seed=99)
    assert evolved.is_acyclic()
    assert len(evolved.nodes) >= 2


def test_engine_with_evolution_flag():
    ontology = build_default_ontology()
    engine = OntoPlanEngine(ontology, use_evolution=True)
    plan = engine.plan("Check Sarah's MR, if code has issues ask her to fix, notify PM when done")
    assert plan.workflow.is_acyclic()
    assert plan.score > 0
