"""In-memory knowledge store with failure classification and credit assignment.

Implements:
  - FailureType enum (6 types from design doc)
  - Node-level credit assignment
  - Three-level confidence tracking: pattern / node-type / edge (artifact pair)
  - Pattern lifecycle (active -> deprecated)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from ontoplan_mvp.models import ArtifactName, PatternTemplate, WorkflowGraph


class FailureType(Enum):
    STRUCTURE_ERROR = "structure_error"       # DAG topology wrong
    PROMPT_ERROR = "prompt_error"             # Node prompt inadequate
    TOOL_ERROR = "tool_error"                 # API timeout, auth, rate limit
    ENVIRONMENT_ERROR = "environment_error"   # Service unavailable
    INTERACTION_ERROR = "interaction_error"   # External interaction failed
    CONTRACT_ERROR = "contract_error"         # Artifact type mismatch at runtime


@dataclass
class NodeExecResult:
    node_name: str
    node_type: str
    success: bool
    failure_type: Optional[FailureType] = None
    details: str = ""


@dataclass
class ExecutionOutcome:
    """Result of executing a workflow DAG."""

    workflow: WorkflowGraph
    success: bool
    overall_failure_type: Optional[FailureType] = None
    node_results: List[NodeExecResult] = field(default_factory=list)
    matched_pattern_name: Optional[str] = None


@dataclass
class PatternRecord:
    """Tracked pattern with confidence and usage stats."""

    template: PatternTemplate
    confidence: float = 0.5
    usage_count: int = 0
    success_count: int = 0
    last_used_ts: float = field(default_factory=time.time)
    origin: str = "bootstrap"  # bootstrap | self_evolution | human_edit
    deprecated: bool = False


@dataclass
class NodeTypeStats:
    """Per-node-type reliability and failure tracking."""

    node_type_name: str
    reliability: float = 0.5
    total_executions: int = 0
    success_count: int = 0
    prompt_failure_count: int = 0


@dataclass
class ArtifactFlowStats:
    """Per-artifact-pair reliability tracking for edge contracts."""

    source_artifact: ArtifactName
    target_artifact: ArtifactName
    reliability: float = 0.5
    total_uses: int = 0
    contract_errors: int = 0


class KnowledgeStore:
    """In-memory knowledge store with three-level confidence tracking.

    Level 1: Pattern-level (only STRUCTURE_ERROR/CONTRACT_ERROR affect it)
    Level 2: Node-type-level (tracks per agent type reliability)
    Level 3: Edge-level (tracks per artifact type pair reliability)
    """

    DEPRECATION_THRESHOLD = 0.2
    CONFIDENCE_DECAY_FACTOR = 0.995  # per-day decay for unused patterns

    def __init__(self) -> None:
        self.patterns: Dict[str, PatternRecord] = {}
        self.node_type_stats: Dict[str, NodeTypeStats] = {}
        self.artifact_flow_stats: Dict[Tuple[str, str], ArtifactFlowStats] = {}

    def add_pattern(self, template: PatternTemplate, confidence: float = 0.5,
                    origin: str = "bootstrap") -> None:
        self.patterns[template.name] = PatternRecord(
            template=template, confidence=confidence, origin=origin,
        )

    def get_active_patterns(self) -> List[PatternRecord]:
        return [p for p in self.patterns.values() if not p.deprecated]

    def get_historical_scores(self) -> Dict[str, float]:
        """Return node-type reliability scores for the fitness function."""
        return {name: stats.reliability for name, stats in self.node_type_stats.items()}

    def record_outcome(self, outcome: ExecutionOutcome) -> None:
        """Process an execution outcome with differentiated credit assignment."""
        # Update node-type stats (Level 2)
        for nr in outcome.node_results:
            stats = self.node_type_stats.setdefault(
                nr.node_type, NodeTypeStats(node_type_name=nr.node_type)
            )
            stats.total_executions += 1
            if nr.success:
                stats.success_count += 1
                stats.reliability = min(1.0, stats.reliability + 0.03)
            elif nr.failure_type == FailureType.PROMPT_ERROR:
                stats.prompt_failure_count += 1
                # Don't reduce reliability for prompt errors — it's a prompt issue, not a type issue
            elif nr.failure_type in (FailureType.TOOL_ERROR, FailureType.ENVIRONMENT_ERROR):
                pass  # External failures don't blame the node type
            else:
                stats.reliability = max(0.0, stats.reliability - 0.05)

        # Update pattern confidence (Level 1)
        pattern_name = outcome.matched_pattern_name
        if pattern_name and pattern_name in self.patterns:
            record = self.patterns[pattern_name]
            record.usage_count += 1
            record.last_used_ts = time.time()

            if outcome.success:
                record.success_count += 1
                success_rate = record.success_count / record.usage_count
                record.confidence = min(1.0, record.confidence + 0.05 * success_rate)
            elif outcome.overall_failure_type == FailureType.STRUCTURE_ERROR:
                record.confidence = max(0.0, record.confidence - 0.10)
            elif outcome.overall_failure_type == FailureType.CONTRACT_ERROR:
                record.confidence = max(0.0, record.confidence - 0.05)
            # PROMPT/TOOL/ENV/INTERACTION errors don't affect pattern confidence

            if record.confidence < self.DEPRECATION_THRESHOLD:
                record.deprecated = True

        # Update artifact flow stats (Level 3)
        for nr in outcome.node_results:
            if nr.failure_type == FailureType.CONTRACT_ERROR:
                # Find edges connected to this node in the workflow
                for edge in outcome.workflow.edges:
                    if edge.target == nr.node_name:
                        for art in edge.artifacts_passed:
                            key = (edge.source, art)
                            stats = self.artifact_flow_stats.setdefault(
                                key, ArtifactFlowStats(source_artifact=edge.source, target_artifact=art)
                            )
                            stats.total_uses += 1
                            stats.contract_errors += 1
                            stats.reliability = max(0.0, stats.reliability - 0.1)
            elif nr.success:
                for edge in outcome.workflow.edges:
                    if edge.target == nr.node_name:
                        for art in edge.artifacts_passed:
                            key = (edge.source, art)
                            stats = self.artifact_flow_stats.setdefault(
                                key, ArtifactFlowStats(source_artifact=edge.source, target_artifact=art)
                            )
                            stats.total_uses += 1
                            stats.reliability = min(1.0, stats.reliability + 0.02)

    def apply_time_decay(self, days_elapsed: float = 1.0) -> None:
        """Apply confidence decay to patterns not recently used."""
        for record in self.patterns.values():
            if record.deprecated:
                continue
            record.confidence *= self.CONFIDENCE_DECAY_FACTOR ** days_elapsed
            if record.confidence < self.DEPRECATION_THRESHOLD:
                record.deprecated = True

    def classify_failure(self, node_results: Sequence[NodeExecResult]) -> FailureType:
        """Determine the dominant failure type from node-level results.

        Priority: STRUCTURE > CONTRACT > PROMPT > INTERACTION > TOOL > ENVIRONMENT
        """
        failure_types = [nr.failure_type for nr in node_results if nr.failure_type is not None]
        if not failure_types:
            return FailureType.STRUCTURE_ERROR  # default if unknown

        priority = [
            FailureType.STRUCTURE_ERROR,
            FailureType.CONTRACT_ERROR,
            FailureType.PROMPT_ERROR,
            FailureType.INTERACTION_ERROR,
            FailureType.TOOL_ERROR,
            FailureType.ENVIRONMENT_ERROR,
        ]
        for ft in priority:
            if ft in failure_types:
                return ft
        return failure_types[0]
