from types import SimpleNamespace

from ontoplan_mvp.executor.node_executor import NodeExecutor
from ontoplan_mvp.models import WorkflowNode


def test_extract_artifacts_reads_latest_marker():
    executor = NodeExecutor()
    state = SimpleNamespace(
        history=[
            SimpleNamespace(content="no artifact yet"),
            SimpleNamespace(content='ARTIFACTS_JSON: {"report_file": "/tmp/report.md"}'),
        ]
    )
    node = WorkflowNode(
        name="report",
        node_type="ReportGenerate-Agent",
        execution_mode="AUTOMATED",
        input_artifacts=("transformed_data",),
        output_artifacts=("report_file",),
    )

    artifacts = executor._extract_artifacts(state, node)

    assert artifacts == {"report_file": "/tmp/report.md"}


def test_extract_artifacts_falls_back_on_invalid_json():
    executor = NodeExecutor()
    state = SimpleNamespace(
        history=[
            SimpleNamespace(content="ARTIFACTS_JSON: {not-valid-json}"),
        ]
    )
    node = WorkflowNode(
        name="report",
        node_type="ReportGenerate-Agent",
        execution_mode="AUTOMATED",
        input_artifacts=("transformed_data",),
        output_artifacts=("report_file",),
    )

    artifacts = executor._extract_artifacts(state, node)

    assert artifacts == {"report_file": "completed"}
