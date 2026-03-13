from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Tuple

from ontoplan_mvp.models import (
    IntentAtom,
    NodeType,
    Ontology,
    PlanCandidate,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
)
from ontoplan_mvp.evolution import compute_fitness, micro_evolve, FitnessWeights
from ontoplan_mvp.knowledge_store import KnowledgeStore

logger = logging.getLogger(__name__)


class OntoPlanEngine:
    def __init__(
        self,
        ontology: Ontology,
        knowledge_store: Optional[KnowledgeStore] = None,
        use_evolution: bool = False,
        use_llm: bool = False,
        llm_config: Optional["LLMConfig"] = None,
    ) -> None:
        self.ontology = ontology
        self.knowledge_store = knowledge_store or KnowledgeStore()
        self.use_evolution = use_evolution
        self.use_llm = use_llm
        self.llm_config = llm_config

    def extract_intents(self, query: str) -> List[IntentAtom]:
        """Extract intent atoms from a natural language query.

        When use_llm=True, delegates to LLM-based extraction (§5.1 of design doc).
        Falls back to keyword-based extraction if LLM call fails.
        """
        if self.use_llm:
            return self._extract_intents_llm(query)
        return self._extract_intents_keyword(query)

    def _extract_intents_llm(self, query: str) -> List[IntentAtom]:
        """LLM-based intent extraction with keyword fallback."""
        try:
            from ontoplan_mvp.llm_client import llm_extract_intents
            intents = llm_extract_intents(
                query, self.ontology, config=self.llm_config,
            )
            if intents:
                return intents
            logger.warning("LLM returned empty intents, falling back to keyword")
        except Exception as exc:
            logger.warning("LLM intent extraction failed (%s), falling back to keyword", exc)
        return self._extract_intents_keyword(query)

    def _extract_intents_keyword(self, query: str) -> List[IntentAtom]:
        lower = query.lower()
        intents: List[IntentAtom] = []
        has_review = any(token in lower for token in ("mr", "merge request", "review", "check"))
        has_status = "status" in lower
        has_fix = "fix" in lower
        has_notify = any(token in lower for token in ("notify", "inform", "message"))
        has_approval = any(token in lower for token in ("approve", "approval", "signoff"))

        if has_review:
            intents.append(
                IntentAtom(
                    name="code_review",
                    execution_mode_hint="AUTOMATED",
                    target_service_hints=("GitLab",),
                    role_hints=("SDE",),
                    input_artifacts=("mr_url",),
                    output_artifacts=("MR_review_result",),
                )
            )

        if "ask" in lower and has_status:
            intents.append(
                IntentAtom(
                    name="request_status_update",
                    execution_mode_hint="INTERACTIVE",
                    target_service_hints=("RocketChat",),
                    role_hints=("PM",),
                    input_artifacts=("issue_ref",),
                    output_artifacts=("status_update",),
                    target_actor_hint="Developer",
                )
            )
        elif "ask" in lower and has_fix:
            intents.append(
                IntentAtom(
                    name="request_fix_update",
                    execution_mode_hint="INTERACTIVE",
                    target_service_hints=("RocketChat",),
                    role_hints=("SDE",),
                    input_artifacts=("MR_review_result",),
                    output_artifacts=("fix_commit",),
                    target_actor_hint="Developer",
                )
            )

        if has_approval:
            intents.append(
                IntentAtom(
                    name="approval_request",
                    execution_mode_hint="APPROVAL",
                    target_service_hints=("RocketChat", "Email", "Form"),
                    role_hints=("PM",),
                    input_artifacts=("final_review_result",) if has_review else ("approval_request",),
                    output_artifacts=("approval_decision",),
                    target_actor_hint="Manager",
                )
            )

        if has_notify:
            notify_inputs = ("final_review_result",)
            if has_status and not has_review:
                notify_inputs = ("status_update",)
            elif has_approval:
                notify_inputs = ("approval_decision",)
            intents.append(
                IntentAtom(
                    name="status_notification",
                    execution_mode_hint="INTERACTIVE",
                    target_service_hints=("RocketChat", "Email"),
                    role_hints=("PM",),
                    input_artifacts=notify_inputs,
                    output_artifacts=("notification_sent",),
                    target_actor_hint="Manager",
                )
            )

        return intents

    def retrieve_candidates(self, intents: Sequence[IntentAtom]) -> Dict[str, List[NodeType]]:
        result: Dict[str, List[NodeType]] = {}
        for intent in intents:
            candidates = []
            for node_type in self.ontology.node_types.values():
                if node_type.execution_mode != intent.execution_mode_hint:
                    continue
                score = self._node_relevance(intent, node_type)
                if score <= 0:
                    continue
                candidates.append((score, node_type))
            ranked = [node for _, node in sorted(candidates, key=lambda item: item[0], reverse=True)]
            result[intent.name] = ranked
        return result

    def assemble(
        self, candidates: Dict[str, List[NodeType]], intents: Sequence[IntentAtom]
    ) -> PlanCandidate:
        intent_names = tuple(intent.name for intent in intents)
        matching = self.ontology.matching_patterns(intent_names)

        workflow: Optional[WorkflowGraph] = None

        if matching:
            # Try template-based assembly first (§5.3 Step 2)
            workflow = self._assemble_from_template(matching[0].name)
            if workflow is None:
                # Fallback to hardcoded review-request-notify assembly
                if matching[0].name == "code_review_with_request_flow":
                    workflow = self._assemble_review_request_notify()

        if workflow is None:
            workflow = self._assemble_linear(candidates, intents)

        validation_errors = self._validate(workflow)
        return PlanCandidate(
            workflow=workflow,
            validation_errors=validation_errors,
            score=self._score(workflow, intents, validation_errors),
        )

    def _assemble_from_template(self, pattern_name: str) -> Optional[WorkflowGraph]:
        """Try to assemble from a pre-built workflow template."""
        try:
            from ontoplan_mvp.abox_instances import get_template_by_pattern_name
            template = get_template_by_pattern_name(pattern_name)
            if template is not None:
                return template.deep_copy()
        except ImportError:
            pass
        return None

    def optimize(self, candidate: PlanCandidate, intents: Sequence[IntentAtom]) -> PlanCandidate:
        if self.use_evolution:
            return self._optimize_evolution(candidate, intents)
        return self._optimize_patch(candidate, intents)

    def _optimize_patch(self, candidate: PlanCandidate, intents: Sequence[IntentAtom]) -> PlanCandidate:
        """Lightweight optimization: patch a missing sink edge if it helps."""
        best = candidate
        workflow = candidate.workflow
        if workflow.nodes and workflow.nodes[-1].name != "ResultSinkNode":
            return best
        if not workflow.has_edge(workflow.nodes[-2].name, "ResultSinkNode"):
            patched = WorkflowGraph(
                nodes=list(workflow.nodes),
                edges=list(workflow.edges)
                + [
                    WorkflowEdge(
                        source=workflow.nodes[-2].name,
                        target="ResultSinkNode",
                        artifacts_passed=workflow.nodes[-2].output_artifacts[:1],
                    )
                ],
            )
            errors = self._validate(patched)
            patched_candidate = PlanCandidate(
                workflow=patched,
                validation_errors=errors,
                score=self._score(patched, intents, errors),
            )
            if patched_candidate.score > best.score:
                best = patched_candidate
        return best

    def _optimize_evolution(self, candidate: PlanCandidate, intents: Sequence[IntentAtom]) -> PlanCandidate:
        """Full micro-evolution optimization using mutation operators and crossover."""
        historical = self.knowledge_store.get_historical_scores()
        evolved = micro_evolve(
            initial=candidate.workflow,
            intents=intents,
            ontology=self.ontology,
            population_size=5,
            max_generations=3,
            mutation_rate=0.3,
            historical_scores=historical,
        )
        errors = self._validate(evolved)
        evolved_score = self._score(evolved, intents, errors)

        evolved_candidate = PlanCandidate(
            workflow=evolved,
            validation_errors=errors,
            score=evolved_score,
        )
        # Elitism: only return evolved if it's at least as good
        return evolved_candidate if evolved_candidate.score >= candidate.score else candidate

    def plan(self, query: str) -> PlanCandidate:
        intents = self.extract_intents(query)
        if not intents:
            return PlanCandidate(
                workflow=WorkflowGraph(
                    nodes=[
                        self._system_node("QuerySourceNode"),
                        self._system_node("ResultSinkNode"),
                    ],
                    edges=[],
                ),
                validation_errors=["no intents extracted from query"],
                score=0.0,
            )
        candidates = self.retrieve_candidates(intents)
        initial = self.assemble(candidates, intents)
        optimized = self.optimize(initial, intents)

        # Optional: LLM quick judge (F5) for final scoring
        if self.use_llm and optimized.score > 0:
            optimized = self._apply_llm_judge(optimized, query)

        return optimized

    def _apply_llm_judge(self, candidate: PlanCandidate, query: str) -> PlanCandidate:
        """Apply LLM quick judge score (F5) as a secondary quality signal."""
        try:
            from ontoplan_mvp.llm_client import llm_quick_judge
            llm_score = llm_quick_judge(
                candidate.workflow, query, config=self.llm_config,
            )
            # Blend LLM judge score with existing score (5% weight per design doc)
            blended = candidate.score * 0.95 + llm_score * 0.05
            return PlanCandidate(
                workflow=candidate.workflow,
                validation_errors=candidate.validation_errors,
                score=round(blended, 4),
            )
        except Exception as exc:
            logger.warning("LLM judge failed (%s), keeping original score", exc)
            return candidate

    def _node_relevance(self, intent: IntentAtom, node_type: NodeType) -> int:
        # Static fallback preferences
        preferred = {
            "code_review": "CodeReview-Agent",
            "request_fix_update": "RequestInfo",
            "request_status_update": "RequestInfo",
            "status_notification": "Notify",
        }
        # Try to use the richer preference map from abox_instances
        try:
            from ontoplan_mvp.abox_instances import INTENT_NODE_PREFERENCES
            prefs = INTENT_NODE_PREFERENCES.get(intent.name, ())
            if prefs:
                # First preference gets +5, second +3, rest +1
                for rank, pref_name in enumerate(prefs):
                    if pref_name == node_type.name:
                        preferred[intent.name] = node_type.name
                        break
        except ImportError:
            pass

        score = 1
        if preferred.get(intent.name) == node_type.name:
            score += 5
        if any(binding in intent.target_service_hints for binding in node_type.access_bindings):
            score += 2
        if intent.target_actor_hint and node_type.target_actor_role == intent.target_actor_hint:
            score += 2
        if intent.target_actor_hint and node_type.target_actor_role is None:
            score += 1
        if set(intent.input_artifacts) & set(node_type.input_artifacts):
            score += 1
        return score

    def _assemble_review_request_notify(self) -> WorkflowGraph:
        source = self._system_node("QuerySourceNode")
        loop = self._node_instance(
            name="review_request_review_loop",
            node_type=self.ontology.node_types["review_request_review_loop"],
        )
        notify = self._node_instance(name="Notify", node_type=self.ontology.node_types["Notify"])
        sink = self._system_node("ResultSinkNode")
        edges = [
            WorkflowEdge("QuerySourceNode", "review_request_review_loop", ("mr_url",)),
            WorkflowEdge("review_request_review_loop", "Notify", ("final_review_result",)),
            WorkflowEdge("Notify", "ResultSinkNode", ("notification_sent",)),
        ]
        return WorkflowGraph(nodes=[source, loop, notify, sink], edges=edges)

    def _assemble_linear(
        self, candidates: Dict[str, List[NodeType]], intents: Sequence[IntentAtom]
    ) -> WorkflowGraph:
        nodes = [self._system_node("QuerySourceNode")]
        edges: List[WorkflowEdge] = []

        for intent in intents:
            node_type = candidates[intent.name][0]
            instance = self._node_instance(node_type.name, node_type, intent)
            nodes.append(instance)
            parent = self._best_parent(nodes[:-1], instance)
            if parent is not None:
                parent_name, shared = parent
                edges.append(WorkflowEdge(parent_name, instance.name, shared))

        sink = self._system_node("ResultSinkNode")
        nodes.append(sink)
        for node in nodes[:-1]:
            if any(edge.source == node.name for edge in edges):
                continue
            shared = tuple(artifact for artifact in node.output_artifacts if artifact in sink.input_artifacts)
            if shared:
                edges.append(WorkflowEdge(node.name, "ResultSinkNode", shared))
        return WorkflowGraph(nodes=nodes, edges=edges)

    def _best_parent(
        self, existing_nodes: Sequence[WorkflowNode], target: WorkflowNode
    ) -> Optional[Tuple[str, Tuple[str, ...]]]:
        for node in reversed(existing_nodes):
            shared = tuple(artifact for artifact in node.output_artifacts if artifact in target.input_artifacts)
            if shared:
                return node.name, shared
        return None

    def _system_node(self, name: str) -> WorkflowNode:
        node_type = self.ontology.node_types[name]
        return self._node_instance(name, node_type)

    def _node_instance(
        self, name: str, node_type: NodeType, intent: Optional[IntentAtom] = None
    ) -> WorkflowNode:
        input_artifacts = node_type.input_artifacts
        output_artifacts = node_type.output_artifacts
        metadata = {}
        if intent and node_type.execution_mode in {"INTERACTIVE", "APPROVAL"}:
            input_artifacts = intent.input_artifacts or node_type.input_artifacts
            output_artifacts = intent.output_artifacts or node_type.output_artifacts
        target_actor_role = intent.target_actor_hint if intent and intent.target_actor_hint else node_type.target_actor_role
        if target_actor_role:
            metadata["target_actor_role"] = target_actor_role
        return WorkflowNode(
            name=name,
            node_type=node_type.name,
            execution_mode=node_type.execution_mode,
            input_artifacts=input_artifacts,
            output_artifacts=output_artifacts,
            metadata=metadata,
        )

    def _validate(self, workflow: WorkflowGraph) -> List[str]:
        errors: List[str] = []
        if not workflow.is_acyclic():
            errors.append("workflow must be acyclic")

        for edge in workflow.edges:
            source = workflow.node_by_name(edge.source)
            target = workflow.node_by_name(edge.target)
            if not set(edge.artifacts_passed).issubset(set(source.output_artifacts)):
                errors.append(f"edge {edge.source}->{edge.target} passes unavailable artifacts")
            required = set(target.input_artifacts)
            if required and not set(edge.artifacts_passed) & required:
                errors.append(f"edge {edge.source}->{edge.target} does not satisfy target inputs")

        for node in workflow.nodes:
            if node.name == "QuerySourceNode":
                continue
            provided = set(workflow.incoming_artifacts(node.name))
            required = set(node.input_artifacts)
            if node.name == "ResultSinkNode":
                if not provided:
                    errors.append("result sink must receive at least one artifact")
                elif required and not provided & required:
                    errors.append("result sink received unsupported artifacts")
                continue
            if not required.issubset(provided):
                errors.append(f"node {node.name} is missing required inputs")

        return errors

    def _score(
        self, workflow: WorkflowGraph, intents: Sequence[IntentAtom], validation_errors: Sequence[str]
    ) -> float:
        if validation_errors:
            return 0.0
        expected_modes = [intent.execution_mode_hint for intent in intents]
        actual_modes = [node.execution_mode for node in workflow.nodes if node.execution_mode != "SYSTEM"]
        matched = sum(
            1 for expected, actual in zip(expected_modes, actual_modes) if expected == actual
        )
        mode_score = matched / max(len(expected_modes), 1)
        compactness = 1.0 / max(len(workflow.nodes), 1)
        return round(mode_score + compactness, 4)
