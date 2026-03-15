from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, cast

from ontoplan_mvp.executor.artifact_store import ArtifactStore
from ontoplan_mvp.executor.node_prompts import build_node_prompt
from ontoplan_mvp.models import WorkflowNode

logger = logging.getLogger(__name__)

try:
    from openhands.controller.state.state import State
    from openhands.core.config import OpenHandsConfig
    from openhands.core.main import run_controller
    from openhands.events.action import MessageAction
    from openhands.runtime.base import Runtime

    OPENHANDS_AVAILABLE = True
except ImportError:
    State = Any  # type: ignore[assignment]
    OpenHandsConfig = Any  # type: ignore[assignment]
    Runtime = Any  # type: ignore[assignment]
    MessageAction = None  # type: ignore[assignment]
    run_controller = None  # type: ignore[assignment]
    OPENHANDS_AVAILABLE = False


ARTIFACTS_PREFIX = "ARTIFACTS_JSON:"


@dataclass
class NodeExecutionResult:
    """Outcome of executing a single workflow node."""

    node_name: str
    success: bool
    state: State
    artifacts: Dict[str, str]
    error: Optional[str] = None
    trajectory_path: Optional[str] = None


def node_user_response(state: State) -> str:
    """Provide a nudge that keeps the agent focused on the current node."""
    msg = (
        "Please continue working on the current workflow step using the available tools.\n"
        "If you think this node is complete, finish the interaction.\n"
        "IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN HELP.\n"
    )

    history = getattr(state, "history", []) or []
    user_msgs = [
        event
        for event in history
        if event.__class__.__name__ == "MessageAction" and getattr(event, "source", None) == "user"
    ]
    if len(user_msgs) >= 2:
        return msg + "If you want to give up, run: <execute_bash> exit </execute_bash>.\n"
    return msg


class NodeExecutor:
    """Run a workflow node as an isolated OpenHands controller session."""

    def __init__(self, max_iterations: int = 50, budget_per_node: float = 1.0):
        self.max_iterations = max_iterations
        self.budget_per_node = budget_per_node

    def execute(
        self,
        node: WorkflowNode,
        artifact_store: ArtifactStore,
        original_query: str,
        node_index: int,
        total_nodes: int,
        runtime: Runtime,
        config: OpenHandsConfig,
        task_name: str,
    ) -> NodeExecutionResult:
        """Execute a workflow node and extract its declared artifacts."""
        prompt = build_node_prompt(
            node=node,
            artifact_store=artifact_store,
            original_query=original_query,
            node_index=node_index,
            total_nodes=total_nodes,
        )
        sid = f"{task_name}__node{node_index}__{node.node_type}"
        trajectory_path = os.path.join("/tmp", f"{sid}_traj.json")

        if not OPENHANDS_AVAILABLE or run_controller is None or MessageAction is None:
            error = "openhands-ai is required to execute workflow nodes"
            logger.warning("Skipping node execution (node=%s): %s", node.name, error)
            return NodeExecutionResult(
                node_name=node.name,
                success=False,
                state=self._build_empty_state(),
                artifacts=self._empty_artifacts(node),
                error=error,
                trajectory_path=trajectory_path,
            )

        node_config = self._clone_config(config)
        setattr(node_config, "max_iterations", self.max_iterations)
        setattr(node_config, "max_budget_per_task", self.budget_per_node)
        setattr(node_config, "save_trajectory_path", trajectory_path)

        try:
            state = asyncio.run(
                run_controller(
                    config=node_config,
                    sid=sid,
                    initial_user_action=MessageAction(content=prompt),
                    runtime=runtime,
                    fake_user_response_fn=node_user_response,
                )
            )
            if state is None:
                raise RuntimeError("run_controller returned no state")

            artifacts = self._extract_artifacts(state, node)
            return NodeExecutionResult(
                node_name=node.name,
                success=True,
                state=state,
                artifacts=artifacts,
                trajectory_path=trajectory_path,
            )
        except Exception as exc:
            logger.warning("Node execution failed (node=%s, sid=%s): %s", node.name, sid, exc)
            return NodeExecutionResult(
                node_name=node.name,
                success=False,
                state=self._build_empty_state(),
                artifacts=self._empty_artifacts(node),
                error=str(exc),
                trajectory_path=trajectory_path,
            )

    def _clone_config(self, config: OpenHandsConfig) -> OpenHandsConfig:
        """Clone an OpenHands config without mutating the shared instance."""
        model_copy = getattr(config, "model_copy", None)
        if callable(model_copy):
            return model_copy(deep=True)

        copy_method = getattr(config, "copy", None)
        if callable(copy_method):
            try:
                return copy_method(deep=True)
            except TypeError:
                return copy_method()

        return copy.deepcopy(config)

    def _extract_artifacts(self, state: State, node: WorkflowNode) -> Dict[str, str]:
        """Parse the last ARTIFACTS_JSON marker from the node trajectory."""
        payload = self._find_last_artifacts_payload(state)
        if payload is None:
            return self._fallback_artifacts(node)

        try:
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                raise TypeError("parsed artifact payload is not a dict")

            if node.output_artifacts:
                normalized: Dict[str, str] = {}
                for artifact_name in node.output_artifacts:
                    value = parsed.get(artifact_name)
                    normalized[artifact_name] = str(value) if value else "completed"
                return normalized

            return {str(key): str(value) for key, value in parsed.items()}
        except Exception as exc:
            logger.warning("Artifact parsing failed (node=%s): %s", node.name, exc)
            return self._fallback_artifacts(node)

    def _find_last_artifacts_payload(self, state: State) -> Optional[str]:
        """Return the most recent JSON payload emitted after ARTIFACTS_JSON."""
        history = getattr(state, "history", []) or []
        for event in reversed(history):
            for text in self._event_texts(event):
                for line in reversed(text.splitlines()):
                    if ARTIFACTS_PREFIX in line:
                        return line.split(ARTIFACTS_PREFIX, 1)[1].strip()
        return None

    def _event_texts(self, event: Any) -> List[str]:
        """Extract string fields that may contain emitted artifacts."""
        texts: List[str] = []
        for attr in ("content", "message", "text"):
            value = getattr(event, attr, None)
            if isinstance(value, str) and value:
                texts.append(value)
        if not texts:
            as_str = str(event)
            if as_str:
                texts.append(as_str)
        return texts

    def _fallback_artifacts(self, node: WorkflowNode) -> Dict[str, str]:
        """Return a non-blocking fallback artifact map after parse failure."""
        return {artifact_name: "completed" for artifact_name in node.output_artifacts}

    def _empty_artifacts(self, node: WorkflowNode) -> Dict[str, str]:
        """Return empty artifact values after node execution failure."""
        return {artifact_name: "" for artifact_name in node.output_artifacts}

    def _build_empty_state(self) -> State:
        """Create a minimal empty state object for failure paths."""
        if OPENHANDS_AVAILABLE:
            try:
                return State()
            except Exception:
                pass
        return cast(State, SimpleNamespace(history=[]))
