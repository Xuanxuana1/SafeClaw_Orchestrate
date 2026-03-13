from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ArtifactName = str


@dataclass(frozen=True)
class FSMTransition:
    from_state: str
    to_state: str
    condition: str


@dataclass(frozen=True)
class CompoundNodeDef:
    """Definition of a compound node's internal FSM.

    A compound node appears as a single atomic node in the outer DAG but
    encapsulates an internal finite state machine for iterative processes.
    """

    states: Tuple[str, ...]
    initial_state: str
    transitions: Tuple[FSMTransition, ...]
    max_iterations: int
    timeout_seconds: int
    internal_nodes: Tuple["InternalNodeSlot", ...]


@dataclass(frozen=True)
class InternalNodeSlot:
    state: str
    node_type_name: str
    execution_mode: str
    target_actor_role: Optional[str] = None
    channel: Optional[str] = None


@dataclass(frozen=True)
class IntentAtom:
    name: str
    execution_mode_hint: str
    target_service_hints: Tuple[str, ...]
    role_hints: Tuple[str, ...]
    input_artifacts: Tuple[ArtifactName, ...] = ()
    output_artifacts: Tuple[ArtifactName, ...] = ()
    target_actor_hint: Optional[str] = None


@dataclass(frozen=True)
class NodeType:
    name: str
    execution_mode: str
    access_bindings: Tuple[str, ...]
    input_artifacts: Tuple[ArtifactName, ...]
    output_artifacts: Tuple[ArtifactName, ...]
    target_actor_role: Optional[str] = None
    keywords: Tuple[str, ...] = ()
    compound_def: Optional[CompoundNodeDef] = None

    @property
    def is_compound(self) -> bool:
        return self.compound_def is not None


@dataclass(frozen=True)
class PatternTemplate:
    name: str
    required_intents: Tuple[str, ...]


@dataclass
class WorkflowNode:
    name: str
    node_type: str
    execution_mode: str
    input_artifacts: Tuple[ArtifactName, ...]
    output_artifacts: Tuple[ArtifactName, ...]
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEdge:
    source: str
    target: str
    artifacts_passed: Tuple[ArtifactName, ...]


@dataclass
class WorkflowGraph:
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]

    def node_names(self) -> List[str]:
        return [node.name for node in self.nodes]

    def has_edge(self, source: str, target: str) -> bool:
        return any(edge.source == source and edge.target == target for edge in self.edges)

    def node_by_name(self, name: str) -> WorkflowNode:
        for node in self.nodes:
            if node.name == name:
                return node
        raise KeyError(name)

    def incoming_artifacts(self, node_name: str) -> Tuple[ArtifactName, ...]:
        items: List[ArtifactName] = []
        for edge in self.edges:
            if edge.target == node_name:
                items.extend(edge.artifacts_passed)
        return tuple(items)

    def outgoing_edges(self, node_name: str) -> List[WorkflowEdge]:
        return [edge for edge in self.edges if edge.source == node_name]

    def incoming_edges(self, node_name: str) -> List[WorkflowEdge]:
        return [edge for edge in self.edges if edge.target == node_name]

    def non_system_nodes(self) -> List[WorkflowNode]:
        return [n for n in self.nodes if n.execution_mode != "SYSTEM"]

    def deep_copy(self) -> "WorkflowGraph":
        return WorkflowGraph(
            nodes=[WorkflowNode(
                name=n.name, node_type=n.node_type, execution_mode=n.execution_mode,
                input_artifacts=n.input_artifacts, output_artifacts=n.output_artifacts,
                metadata=dict(n.metadata),
            ) for n in self.nodes],
            edges=[WorkflowEdge(e.source, e.target, e.artifacts_passed) for e in self.edges],
        )

    def is_acyclic(self) -> bool:
        adjacency: Dict[str, List[str]] = {node.name: [] for node in self.nodes}
        for edge in self.edges:
            adjacency.setdefault(edge.source, []).append(edge.target)

        visited: Dict[str, int] = {name: 0 for name in adjacency}

        def visit(name: str) -> bool:
            state = visited[name]
            if state == 1:
                return False
            if state == 2:
                return True
            visited[name] = 1
            for child in adjacency.get(name, []):
                if not visit(child):
                    return False
            visited[name] = 2
            return True

        return all(visit(name) for name in adjacency)


@dataclass
class PlanCandidate:
    workflow: WorkflowGraph
    score: float
    validation_errors: List[str]


@dataclass(frozen=True)
class Ontology:
    node_types: Dict[str, NodeType]
    patterns: Tuple[PatternTemplate, ...]

    def matching_patterns(self, intent_names: Sequence[str]) -> Tuple[PatternTemplate, ...]:
        name_set = set(intent_names)
        return tuple(
            pattern for pattern in self.patterns if set(pattern.required_intents).issubset(name_set)
        )
