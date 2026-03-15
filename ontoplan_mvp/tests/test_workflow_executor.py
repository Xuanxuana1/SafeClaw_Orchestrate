import json
from pathlib import Path
from types import SimpleNamespace

from ontoplan_mvp.executor.node_executor import NodeExecutionResult
from ontoplan_mvp.executor.workflow_executor import WorkflowExecutor
from ontoplan_mvp.models import PlanCandidate, WorkflowEdge, WorkflowGraph, WorkflowNode


class StubNodeExecutor:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.calls = []

    def execute(
        self,
        node,
        artifact_store,
        original_query,
        node_index,
        total_nodes,
        runtime,
        config,
        task_name,
    ):
        self.calls.append(node.name)
        trajectory_path = self.temp_dir / f"{node.name}.json"
        trajectory_path.write_text(
            json.dumps({"history": [{"content": f"{node.name}-history"}]}),
            encoding="utf-8",
        )

        success = node.name != "transform"
        return NodeExecutionResult(
            node_name=node.name,
            success=success,
            state=SimpleNamespace(history=[]),
            artifacts={artifact: f"{node.name}:{artifact}" for artifact in node.output_artifacts},
            error=None if success else "failed",
            trajectory_path=str(trajectory_path),
        )

    def _build_empty_state(self):
        return SimpleNamespace(history=[])


def test_topological_sort_filters_system_nodes_and_orders_dependencies():
    executor = WorkflowExecutor(StubNodeExecutor(Path(".")))
    graph = WorkflowGraph(
        nodes=[
            WorkflowNode("QuerySourceNode", "QuerySourceNode", "SYSTEM", (), ("file_path",)),
            WorkflowNode("extract", "DataExtract-Agent", "AUTOMATED", ("file_path",), ("extracted_data",)),
            WorkflowNode("transform", "DataTransform-Agent", "AUTOMATED", ("extracted_data",), ("transformed_data",)),
            WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM", ("transformed_data",), ()),
        ],
        edges=[
            WorkflowEdge("QuerySourceNode", "extract", ("file_path",)),
            WorkflowEdge("extract", "transform", ("extracted_data",)),
            WorkflowEdge("transform", "ResultSinkNode", ("transformed_data",)),
        ],
    )

    ordered = executor._topological_sort(graph)

    assert [node.name for node in ordered] == ["extract", "transform"]


def test_workflow_executor_continues_after_failed_node_and_merges_history(tmp_path):
    node_executor = StubNodeExecutor(tmp_path)
    executor = WorkflowExecutor(node_executor)
    plan = PlanCandidate(
        workflow=WorkflowGraph(
            nodes=[
                WorkflowNode("QuerySourceNode", "QuerySourceNode", "SYSTEM", (), ("file_path",)),
                WorkflowNode("extract", "DataExtract-Agent", "AUTOMATED", ("file_path",), ("extracted_data",)),
                WorkflowNode(
                    "transform",
                    "DataTransform-Agent",
                    "AUTOMATED",
                    ("extracted_data",),
                    ("transformed_data",),
                ),
                WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM", ("transformed_data",), ()),
            ],
            edges=[
                WorkflowEdge("QuerySourceNode", "extract", ("file_path",)),
                WorkflowEdge("extract", "transform", ("extracted_data",)),
                WorkflowEdge("transform", "ResultSinkNode", ("transformed_data",)),
            ],
        ),
        score=1.0,
        validation_errors=[],
    )

    result = executor.execute(
        plan=plan,
        original_query="Analyze a file and transform the extracted data.",
        runtime=None,
        config=None,
        task_name="demo-task",
        output_dir=str(tmp_path),
    )

    merged = json.loads((tmp_path / "traj_demo-task.json").read_text(encoding="utf-8"))

    assert node_executor.calls == ["extract", "transform"]
    assert result.success is False
    assert result.artifact_store.get("extracted_data") == "extract:extracted_data"
    assert result.artifact_store.get("transformed_data") == "transform:transformed_data"
    assert "=== Node: extract ===" in json.dumps(merged)
    assert "=== Node: transform ===" in json.dumps(merged)
