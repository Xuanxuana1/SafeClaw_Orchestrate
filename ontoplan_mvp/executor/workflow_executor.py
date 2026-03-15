from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ontoplan_mvp.executor.artifact_store import ArtifactStore
from ontoplan_mvp.executor.node_executor import NodeExecutionResult, NodeExecutor
from ontoplan_mvp.models import PlanCandidate, WorkflowGraph, WorkflowNode

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecutionResult:
    """Outcome of executing a planned workflow."""

    plan: PlanCandidate
    node_results: List[NodeExecutionResult]
    artifact_store: ArtifactStore
    merged_trajectory_path: str
    success: bool


class WorkflowExecutor:
    """Execute workflow nodes in topological order and merge their outputs."""

    def __init__(self, node_executor: NodeExecutor):
        self.node_executor = node_executor

    def execute(
        self,
        plan: PlanCandidate,
        original_query: str,
        runtime: Any,
        config: Any,
        task_name: str,
        output_dir: str,
    ) -> WorkflowExecutionResult:
        """Execute a planned workflow while tolerating node-level failures."""
        nodes = self._topological_sort(plan.workflow)
        artifact_store = ArtifactStore()
        artifact_store.put("task_query", original_query)

        node_results: List[NodeExecutionResult] = []
        total_nodes = len(nodes)

        for node_index, node in enumerate(nodes):
            try:
                result = self.node_executor.execute(
                    node=node,
                    artifact_store=artifact_store,
                    original_query=original_query,
                    node_index=node_index,
                    total_nodes=total_nodes,
                    runtime=runtime,
                    config=config,
                    task_name=task_name,
                )
            except Exception as exc:
                logger.warning("Unhandled node executor failure (node=%s): %s", node.name, exc)
                result = NodeExecutionResult(
                    node_name=node.name,
                    success=False,
                    state=self.node_executor._build_empty_state(),
                    artifacts={artifact_name: "" for artifact_name in node.output_artifacts},
                    error=str(exc),
                )

            node_results.append(result)
            for artifact_name, value in result.artifacts.items():
                artifact_store.put(artifact_name, value)

        merged_path = os.path.join(output_dir, f"traj_{task_name}.json")
        merged_trajectory_path = self._merge_trajectories(node_results, merged_path)
        success = all(result.success for result in node_results)

        return WorkflowExecutionResult(
            plan=plan,
            node_results=node_results,
            artifact_store=artifact_store,
            merged_trajectory_path=merged_trajectory_path,
            success=success,
        )

    def _topological_sort(self, graph: WorkflowGraph) -> List[WorkflowNode]:
        """Return non-system nodes ordered by Kahn topological sort."""
        non_system_nodes = [node for node in graph.nodes if node.execution_mode != "SYSTEM"]
        if not non_system_nodes:
            return []

        node_by_name: Dict[str, WorkflowNode] = {node.name: node for node in non_system_nodes}
        positions = {node.name: index for index, node in enumerate(non_system_nodes)}
        indegree: Dict[str, int] = {node.name: 0 for node in non_system_nodes}
        adjacency: Dict[str, List[str]] = {node.name: [] for node in non_system_nodes}

        for edge in graph.edges:
            if edge.source in node_by_name and edge.target in node_by_name:
                adjacency[edge.source].append(edge.target)
                indegree[edge.target] += 1

        ready = sorted(
            [node.name for node in non_system_nodes if indegree[node.name] == 0],
            key=lambda name: positions[name],
        )
        ordered: List[WorkflowNode] = []

        while ready:
            current = ready.pop(0)
            ordered.append(node_by_name[current])
            for child in adjacency[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort(key=lambda name: positions[name])

        if len(ordered) != len(non_system_nodes):
            logger.warning("Workflow graph is not a valid DAG, using original non-system node order")
            return non_system_nodes

        return ordered

    def _merge_trajectories(
        self,
        node_results: List[NodeExecutionResult],
        output_path: str,
    ) -> str:
        """Merge per-node trajectories into one trajectory file for evaluation."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        merged_history: List[Any] = []
        base_document: Optional[Dict[str, Any]] = None
        last_available_path: Optional[str] = None

        try:
            for result in node_results:
                trajectory_path = result.trajectory_path
                if not trajectory_path or not os.path.exists(trajectory_path):
                    continue

                last_available_path = trajectory_path
                with open(trajectory_path, "r", encoding="utf-8") as file:
                    document = json.load(file)

                if base_document is None:
                    if isinstance(document, dict):
                        base_document = dict(document)
                    else:
                        base_document = {}

                history = self._extract_history(document)
                if not history:
                    continue

                merged_history.append(self._separator_event(result.node_name))
                merged_history.extend(history)

            if base_document is None:
                base_document = {}

            base_document["history"] = merged_history

            with open(output_path, "w", encoding="utf-8") as file:
                json.dump(base_document, file, indent=2, ensure_ascii=False)
            return output_path
        except Exception as exc:
            logger.warning("Trajectory merge failed (%s), falling back to last node trajectory", exc)
            if last_available_path and os.path.exists(last_available_path):
                shutil.copyfile(last_available_path, output_path)
                return output_path

            with open(output_path, "w", encoding="utf-8") as file:
                json.dump({"history": []}, file, indent=2, ensure_ascii=False)
            return output_path

    def _extract_history(self, document: Any) -> List[Any]:
        """Extract a history list from a saved trajectory document."""
        if isinstance(document, dict):
            history = document.get("history")
            return history if isinstance(history, list) else []
        if isinstance(document, list):
            return document
        return []

    def _separator_event(self, node_name: str) -> Dict[str, Any]:
        """Create a serialized separator event between node trajectories."""
        content = f"=== Node: {node_name} ==="
        try:
            from openhands.events.action import MessageAction

            event = MessageAction(content=content)
            return self._serialize_event(event)
        except Exception:
            return {
                "type": "MessageAction",
                "source": "user",
                "content": content,
                "message": content,
            }

    def _serialize_event(self, event: Any) -> Dict[str, Any]:
        """Serialize an OpenHands event to JSON-friendly data."""
        for method_name in ("model_dump", "dict", "to_dict"):
            method = getattr(event, method_name, None)
            if callable(method):
                data = method()
                if isinstance(data, dict):
                    return data

        if hasattr(event, "__dict__"):
            return dict(vars(event))

        return {
            "type": event.__class__.__name__,
            "content": str(event),
        }
