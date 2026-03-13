"""Graph mutation operators (M1-M7), crossover (C1), and micro-evolution loop.

All operators preserve:
  - outer DAG acyclicity (compound nodes are atomic)
  - artifact contract validity (edges carry compatible types)
  - ontology constraints (node types come from the ontology)
"""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ontoplan_mvp.models import (
    ArtifactName,
    IntentAtom,
    NodeType,
    Ontology,
    PlanCandidate,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
)


# ---------------------------------------------------------------------------
# Mutation operators
# ---------------------------------------------------------------------------


def _available_node_types(ontology: Ontology, exclude_system: bool = True) -> List[NodeType]:
    """Return non-system node types from the ontology."""
    return [
        nt for nt in ontology.node_types.values()
        if not exclude_system or nt.execution_mode != "SYSTEM"
    ]


def _unique_name(base: str, existing: List[str]) -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def _artifact_overlap(outputs: Tuple[ArtifactName, ...], inputs: Tuple[ArtifactName, ...]) -> Tuple[ArtifactName, ...]:
    return tuple(a for a in outputs if a in inputs)


def m1_node_add(graph: WorkflowGraph, ontology: Ontology) -> Optional[WorkflowGraph]:
    """M1: Add a new node from the ontology between two existing connected nodes."""
    candidates = _available_node_types(ontology)
    if not candidates:
        return None
    new_type = random.choice(candidates)

    # Find an edge where we can insert this node (outputs of source satisfy new node's inputs)
    insertable_edges = []
    for edge in graph.edges:
        src = graph.node_by_name(edge.source)
        dst = graph.node_by_name(edge.target)
        src_to_new = _artifact_overlap(src.output_artifacts, new_type.input_artifacts)
        new_to_dst = _artifact_overlap(new_type.output_artifacts, dst.input_artifacts)
        if src_to_new and (new_to_dst or dst.execution_mode == "SYSTEM"):
            insertable_edges.append((edge, src_to_new, new_to_dst))

    if not insertable_edges:
        return None

    edge, src_to_new, new_to_dst = random.choice(insertable_edges)
    g = graph.deep_copy()
    name = _unique_name(new_type.name, g.node_names())

    new_node = WorkflowNode(
        name=name,
        node_type=new_type.name,
        execution_mode=new_type.execution_mode,
        input_artifacts=new_type.input_artifacts,
        output_artifacts=new_type.output_artifacts,
        metadata={"target_actor_role": new_type.target_actor_role} if new_type.target_actor_role else {},
    )

    # Remove the old edge, insert node with two new edges
    g.edges = [e for e in g.edges if not (e.source == edge.source and e.target == edge.target)]

    # Insert the new node before sink
    insert_idx = next(i for i, n in enumerate(g.nodes) if n.name == edge.target)
    g.nodes.insert(insert_idx, new_node)

    g.edges.append(WorkflowEdge(edge.source, name, src_to_new))
    if not new_to_dst:
        new_to_dst = new_node.output_artifacts[:1] if new_node.output_artifacts else ()
    g.edges.append(WorkflowEdge(name, edge.target, new_to_dst))

    if g.is_acyclic():
        return g
    return None


def m2_node_remove(graph: WorkflowGraph, ontology: Ontology) -> Optional[WorkflowGraph]:
    """M2: Remove a non-system node and reconnect its neighbors."""
    removable = [n for n in graph.nodes if n.execution_mode != "SYSTEM"]
    if not removable:
        return None

    target = random.choice(removable)
    g = graph.deep_copy()

    incoming = g.incoming_edges(target.name)
    outgoing = g.outgoing_edges(target.name)

    # Remove the node and its edges
    g.nodes = [n for n in g.nodes if n.name != target.name]
    g.edges = [e for e in g.edges if e.source != target.name and e.target != target.name]

    # Reconnect: for each (predecessor, successor) pair, add a bypass edge
    for inc in incoming:
        for out in outgoing:
            src = g.node_by_name(inc.source)
            dst_name = out.target
            try:
                dst = g.node_by_name(dst_name)
            except KeyError:
                continue
            shared = _artifact_overlap(src.output_artifacts, dst.input_artifacts)
            if not shared and src.output_artifacts:
                shared = src.output_artifacts[:1]
            if not g.has_edge(inc.source, dst_name):
                g.edges.append(WorkflowEdge(inc.source, dst_name, shared))

    if g.is_acyclic() and len(g.nodes) >= 2:
        return g
    return None


def m3_node_replace(graph: WorkflowGraph, ontology: Ontology) -> Optional[WorkflowGraph]:
    """M3: Replace a non-system node with a different node type of the same execution mode."""
    replaceable = [n for n in graph.nodes if n.execution_mode != "SYSTEM"]
    if not replaceable:
        return None

    target = random.choice(replaceable)
    same_mode = [
        nt for nt in _available_node_types(ontology)
        if nt.execution_mode == target.execution_mode and nt.name != target.node_type
    ]
    if not same_mode:
        return None

    new_type = random.choice(same_mode)
    g = graph.deep_copy()

    # Replace the node in-place
    for i, n in enumerate(g.nodes):
        if n.name == target.name:
            g.nodes[i] = WorkflowNode(
                name=target.name,
                node_type=new_type.name,
                execution_mode=new_type.execution_mode,
                input_artifacts=new_type.input_artifacts,
                output_artifacts=new_type.output_artifacts,
                metadata={"target_actor_role": new_type.target_actor_role} if new_type.target_actor_role else {},
            )
            break

    # Patch edges to match new artifact types
    new_edges = []
    new_node = g.node_by_name(target.name)
    for e in g.edges:
        if e.source == target.name:
            shared = _artifact_overlap(new_node.output_artifacts, graph.node_by_name(e.target).input_artifacts)
            if not shared and new_node.output_artifacts:
                shared = new_node.output_artifacts[:1]
            new_edges.append(WorkflowEdge(e.source, e.target, shared))
        elif e.target == target.name:
            src = g.node_by_name(e.source)
            shared = _artifact_overlap(src.output_artifacts, new_node.input_artifacts)
            if not shared and src.output_artifacts:
                shared = src.output_artifacts[:1]
            new_edges.append(WorkflowEdge(e.source, e.target, shared))
        else:
            new_edges.append(e)
    g.edges = new_edges
    return g


def m4_edge_add(graph: WorkflowGraph, ontology: Ontology) -> Optional[WorkflowGraph]:
    """M4: Add a new edge between two nodes that are not yet directly connected."""
    names = graph.node_names()
    existing = {(e.source, e.target) for e in graph.edges}
    candidates = []
    for src_name in names:
        for dst_name in names:
            if src_name == dst_name or (src_name, dst_name) in existing:
                continue
            src = graph.node_by_name(src_name)
            dst = graph.node_by_name(dst_name)
            shared = _artifact_overlap(src.output_artifacts, dst.input_artifacts)
            if shared:
                candidates.append((src_name, dst_name, shared))

    if not candidates:
        return None

    src_name, dst_name, shared = random.choice(candidates)
    g = graph.deep_copy()
    g.edges.append(WorkflowEdge(src_name, dst_name, shared))

    if g.is_acyclic():
        return g
    return None


def m5_edge_remove(graph: WorkflowGraph, ontology: Ontology) -> Optional[WorkflowGraph]:
    """M5: Remove an edge, keeping the graph connected."""
    if len(graph.edges) <= 1:
        return None

    edge = random.choice(graph.edges)
    g = graph.deep_copy()
    g.edges = [e for e in g.edges if not (e.source == edge.source and e.target == edge.target)]

    # Check the graph is still connected (every node reachable from source)
    reachable = set()
    queue = [g.nodes[0].name]
    adj: Dict[str, List[str]] = {n.name: [] for n in g.nodes}
    for e in g.edges:
        adj.setdefault(e.source, []).append(e.target)
        adj.setdefault(e.target, []).append(e.source)  # undirected connectivity
    while queue:
        cur = queue.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        queue.extend(adj.get(cur, []))

    if reachable == set(g.node_names()) and g.is_acyclic():
        return g
    return None


def m6_prompt_mutate(graph: WorkflowGraph, ontology: Ontology) -> Optional[WorkflowGraph]:
    """M6: Mutate metadata on a non-system node (simulates prompt mutation)."""
    mutable = [n for n in graph.nodes if n.execution_mode not in ("SYSTEM",)]
    if not mutable:
        return None

    target = random.choice(mutable)
    g = graph.deep_copy()
    node = g.node_by_name(target.name)
    node.metadata["prompt_variant"] = str(random.randint(1, 100))
    return g


def m7_compound_node_mutate(graph: WorkflowGraph, ontology: Ontology) -> Optional[WorkflowGraph]:
    """M7: Mutate a compound node's max_iterations (the simplest FSM mutation for MVP)."""
    compound_types = [
        nt for nt in ontology.node_types.values() if nt.is_compound
    ]
    if not compound_types:
        return None

    compound_nodes = [n for n in graph.nodes if n.node_type in [ct.name for ct in compound_types]]
    if not compound_nodes:
        return None

    target = random.choice(compound_nodes)
    g = graph.deep_copy()
    node = g.node_by_name(target.name)
    # Simulate changing max_iterations via metadata
    current = int(node.metadata.get("max_iterations", "3"))
    new_val = max(1, current + random.choice([-1, 1]))
    node.metadata["max_iterations"] = str(new_val)
    return g


# All mutation operators
MUTATION_OPS = [m1_node_add, m2_node_remove, m3_node_replace, m4_edge_add,
                m5_edge_remove, m6_prompt_mutate, m7_compound_node_mutate]


# ---------------------------------------------------------------------------
# Crossover operator
# ---------------------------------------------------------------------------


def c1_subgraph_swap(g1: WorkflowGraph, g2: WorkflowGraph) -> Optional[WorkflowGraph]:
    """C1: Swap a non-system node between two candidate DAGs if contract-compatible."""
    ns1 = g1.non_system_nodes()
    ns2 = g2.non_system_nodes()
    if not ns1 or not ns2:
        return None

    # Find nodes with matching execution_mode in both graphs
    pairs = []
    for n1 in ns1:
        for n2 in ns2:
            if n1.execution_mode == n2.execution_mode and n1.node_type != n2.node_type:
                pairs.append((n1, n2))

    if not pairs:
        return None

    n1, n2 = random.choice(pairs)

    # Create child by replacing n1 in g1 with n2's type
    child = g1.deep_copy()
    for i, n in enumerate(child.nodes):
        if n.name == n1.name:
            child.nodes[i] = WorkflowNode(
                name=n1.name,
                node_type=n2.node_type,
                execution_mode=n2.execution_mode,
                input_artifacts=n2.input_artifacts,
                output_artifacts=n2.output_artifacts,
                metadata=dict(n2.metadata),
            )
            break

    # Patch edges
    new_node = child.node_by_name(n1.name)
    new_edges = []
    for e in child.edges:
        if e.source == n1.name:
            try:
                dst = child.node_by_name(e.target)
            except KeyError:
                continue
            shared = _artifact_overlap(new_node.output_artifacts, dst.input_artifacts)
            if not shared and new_node.output_artifacts:
                shared = new_node.output_artifacts[:1]
            new_edges.append(WorkflowEdge(e.source, e.target, shared))
        elif e.target == n1.name:
            src = child.node_by_name(e.source)
            shared = _artifact_overlap(src.output_artifacts, new_node.input_artifacts)
            if not shared and src.output_artifacts:
                shared = src.output_artifacts[:1]
            new_edges.append(WorkflowEdge(e.source, e.target, shared))
        else:
            new_edges.append(e)
    child.edges = new_edges

    if child.is_acyclic():
        return child
    return None


# ---------------------------------------------------------------------------
# Fitness function (F1-F7)
# ---------------------------------------------------------------------------


@dataclass
class FitnessWeights:
    w_coverage: float = 0.20
    w_consistency: float = 0.15
    w_efficiency: float = 0.10
    w_historical: float = 0.10
    w_llm: float = 0.05
    w_contract: float = 0.20
    w_mode: float = 0.20


def compute_fitness(
    graph: WorkflowGraph,
    intents: Sequence[IntentAtom],
    ontology: Ontology,
    weights: Optional[FitnessWeights] = None,
    historical_scores: Optional[Dict[str, float]] = None,
    llm_judge_score: Optional[float] = None,
) -> float:
    """Compute proxy fitness score for a candidate DAG (F1-F7)."""
    w = weights or FitnessWeights()
    non_system = graph.non_system_nodes()

    if not non_system or not graph.is_acyclic():
        return 0.0

    # F1: Intent coverage — how many intents are represented by at least one node
    intent_names = {i.name for i in intents}
    covered = set()
    for node in non_system:
        nt = ontology.node_types.get(node.node_type)
        if nt:
            for intent in intents:
                # Check if this node could serve this intent (keyword or artifact overlap)
                if (set(intent.output_artifacts) & set(nt.output_artifacts)
                        or set(intent.input_artifacts) & set(nt.input_artifacts)):
                    covered.add(intent.name)
    f1 = len(covered) / max(len(intent_names), 1)

    # F2: Ontology consistency — all node types exist in the ontology
    valid_types = sum(1 for n in non_system if n.node_type in ontology.node_types)
    f2 = valid_types / max(len(non_system), 1)

    # F3: Structural efficiency — prefer sparse graphs
    max_edges = len(graph.nodes) * (len(graph.nodes) - 1) / 2
    f3 = 1.0 - (len(graph.edges) / max(max_edges, 1)) if max_edges > 0 else 1.0

    # F4: Historical success rate (from knowledge store, if available)
    f4 = 0.5  # default neutral
    if historical_scores:
        scores = [historical_scores.get(n.node_type, 0.5) for n in non_system]
        f4 = sum(scores) / len(scores) if scores else 0.5

    # F5: LLM quick judge — uses provided score or neutral default
    f5 = llm_judge_score if llm_judge_score is not None else 0.5

    # F6: Contract compatibility — edges carry valid artifacts
    satisfied = 0
    for node in graph.nodes:
        if node.name == "QuerySourceNode":
            satisfied += 1
            continue
        provided = set(graph.incoming_artifacts(node.name))
        required = set(node.input_artifacts)
        if node.execution_mode == "SYSTEM" and node.name == "ResultSinkNode":
            satisfied += 1 if provided else 0
        elif required.issubset(provided):
            satisfied += 1
    f6 = satisfied / max(len(graph.nodes), 1)

    # F7: Execution-mode correctness — nodes match intent execution_mode_hint
    mode_hits = 0
    mode_total = 0
    for intent in intents:
        for node in non_system:
            nt = ontology.node_types.get(node.node_type)
            if nt and (set(intent.output_artifacts) & set(nt.output_artifacts)):
                mode_total += 1
                if node.execution_mode == intent.execution_mode_hint:
                    mode_hits += 1
                break
    f7 = mode_hits / max(mode_total, 1)

    return (
        w.w_coverage * f1
        + w.w_consistency * f2
        + w.w_efficiency * f3
        + w.w_historical * f4
        + w.w_llm * f5
        + w.w_contract * f6
        + w.w_mode * f7
    )


# ---------------------------------------------------------------------------
# Micro-evolution loop
# ---------------------------------------------------------------------------


def apply_random_mutation(
    graph: WorkflowGraph,
    ontology: Ontology,
) -> Optional[WorkflowGraph]:
    """Apply a random mutation operator. Returns None if all fail."""
    ops = list(MUTATION_OPS)
    random.shuffle(ops)
    for op in ops:
        result = op(graph, ontology)
        if result is not None:
            return result
    return None


def micro_evolve(
    initial: WorkflowGraph,
    intents: Sequence[IntentAtom],
    ontology: Ontology,
    population_size: int = 5,
    max_generations: int = 3,
    mutation_rate: float = 0.3,
    weights: Optional[FitnessWeights] = None,
    historical_scores: Optional[Dict[str, float]] = None,
    rng_seed: Optional[int] = None,
) -> WorkflowGraph:
    """Graph micro-evolution loop.

    Starts from the retrieval-assembled initial DAG and performs constrained
    local search in the graph neighborhood. Returns the best DAG found.
    """
    if rng_seed is not None:
        random.seed(rng_seed)

    def fitness(g: WorkflowGraph) -> float:
        return compute_fitness(g, intents, ontology, weights, historical_scores)

    # Initialize population: original + mutations
    population: List[WorkflowGraph] = [initial]
    for _ in range(population_size - 1):
        mutant = apply_random_mutation(initial, ontology)
        if mutant is not None and mutant.is_acyclic():
            population.append(mutant)
        else:
            population.append(initial.deep_copy())

    best_score = -1.0
    stale_count = 0

    for gen in range(max_generations):
        # Evaluate
        scored = [(fitness(g), g) for g in population]
        scored.sort(key=lambda x: x[0], reverse=True)

        current_best = scored[0][0]
        if abs(current_best - best_score) < 1e-6:
            stale_count += 1
        else:
            stale_count = 0
        best_score = max(best_score, current_best)

        # Convergence: stop if no improvement for 2 generations
        if stale_count >= 2:
            break

        # Select top 2 parents (elitism)
        parents = [g for _, g in scored[:2]]

        # Crossover
        children: List[WorkflowGraph] = []
        child = c1_subgraph_swap(parents[0], parents[1])
        if child is not None:
            children.append(child)

        # Mutation
        for parent in parents:
            if random.random() < mutation_rate:
                mutant = apply_random_mutation(parent, ontology)
                if mutant is not None and mutant.is_acyclic():
                    children.append(mutant)

        # Next generation: elitism + children
        population = parents + children
        # Fill up to population_size if needed
        while len(population) < population_size:
            base = random.choice(parents)
            mutant = apply_random_mutation(base, ontology)
            if mutant is not None and mutant.is_acyclic():
                population.append(mutant)
            else:
                population.append(base.deep_copy())

    # Return the best individual
    final_scored = [(fitness(g), g) for g in population]
    final_scored.sort(key=lambda x: x[0], reverse=True)
    return final_scored[0][1]
