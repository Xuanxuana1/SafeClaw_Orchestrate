"""Tests for Phase 0 bootstrap (mocked LLM, no real API calls)."""

import json
from unittest.mock import MagicMock, patch

from ontoplan_mvp.bootstrap import (
    BootstrapConfig,
    _extract_intent_names_from_dag,
    _validate_dag,
    bootstrap_from_queries,
    check_coverage,
)
from ontoplan_mvp.knowledge_store import KnowledgeStore
from ontoplan_mvp.llm_client import LLMConfig
from ontoplan_mvp.models import PatternTemplate, WorkflowEdge, WorkflowGraph, WorkflowNode
from ontoplan_mvp.seed_patterns import build_full_ontology


def _mock_completion(content: str):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    return mock_response


def _simple_dag_json():
    return json.dumps({
        "nodes": [
            {"name": "QuerySourceNode", "node_type": "QuerySourceNode",
             "execution_mode": "SYSTEM", "input_artifacts": [],
             "output_artifacts": ["file_path"]},
            {"name": "extract", "node_type": "DataExtract-Agent",
             "execution_mode": "AUTOMATED",
             "input_artifacts": ["file_path"],
             "output_artifacts": ["extracted_data"]},
            {"name": "report", "node_type": "ReportGenerate-Agent",
             "execution_mode": "AUTOMATED",
             "input_artifacts": ["transformed_data"],
             "output_artifacts": ["report_file"]},
            {"name": "ResultSinkNode", "node_type": "ResultSinkNode",
             "execution_mode": "SYSTEM",
             "input_artifacts": ["report_file"],
             "output_artifacts": []},
        ],
        "edges": [
            {"source": "QuerySourceNode", "target": "extract",
             "artifacts_passed": ["file_path"]},
            {"source": "extract", "target": "report",
             "artifacts_passed": ["extracted_data"]},
            {"source": "report", "target": "ResultSinkNode",
             "artifacts_passed": ["report_file"]},
        ],
    })


class TestValidateDAG:
    def test_valid_dag(self):
        ont = build_full_ontology()
        dag = WorkflowGraph(
            nodes=[
                WorkflowNode("QuerySourceNode", "QuerySourceNode", "SYSTEM",
                             (), ("file_path",)),
                WorkflowNode("extract", "DataExtract-Agent", "AUTOMATED",
                             ("file_path",), ("extracted_data",)),
                WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM",
                             ("extracted_data",), ()),
            ],
            edges=[
                WorkflowEdge("QuerySourceNode", "extract", ("file_path",)),
                WorkflowEdge("extract", "ResultSinkNode", ("extracted_data",)),
            ],
        )
        assert _validate_dag(dag, ont) is True

    def test_rejects_cyclic(self):
        ont = build_full_ontology()
        dag = WorkflowGraph(
            nodes=[
                WorkflowNode("A", "Worker-Agent", "AUTOMATED", ("x",), ("y",)),
                WorkflowNode("B", "Worker-Agent", "AUTOMATED", ("y",), ("x",)),
            ],
            edges=[
                WorkflowEdge("A", "B", ("y",)),
                WorkflowEdge("B", "A", ("x",)),
            ],
        )
        assert _validate_dag(dag, ont) is False

    def test_rejects_missing_source(self):
        ont = build_full_ontology()
        dag = WorkflowGraph(
            nodes=[
                WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM", (), ()),
            ],
            edges=[],
        )
        assert _validate_dag(dag, ont) is False

    def test_rejects_unknown_node_type(self):
        ont = build_full_ontology()
        dag = WorkflowGraph(
            nodes=[
                WorkflowNode("QuerySourceNode", "QuerySourceNode", "SYSTEM", (), ()),
                WorkflowNode("fake", "NonExistent-Agent", "AUTOMATED", (), ()),
                WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM", (), ()),
            ],
            edges=[],
        )
        assert _validate_dag(dag, ont) is False


class TestExtractIntentNames:
    def test_extracts_from_keywords(self):
        ont = build_full_ontology()
        dag = WorkflowGraph(
            nodes=[
                WorkflowNode("QuerySourceNode", "QuerySourceNode", "SYSTEM", (), ()),
                WorkflowNode("extract", "DataExtract-Agent", "AUTOMATED",
                             ("file_path",), ("extracted_data",)),
                WorkflowNode("report", "ReportGenerate-Agent", "AUTOMATED",
                             ("transformed_data",), ("report_file",)),
                WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM", (), ()),
            ],
            edges=[],
        )
        names = _extract_intent_names_from_dag(dag, ont)
        assert len(names) >= 1
        # DataExtract-Agent has keywords like "extract", "parse", "read", "download"
        # which map to "data_extraction" and "file_download"


class TestBootstrapFromQueries:
    def test_generates_patterns(self):
        ont = build_full_ontology()
        store = KnowledgeStore()

        intent_response = json.dumps([
            {"name": "data_extraction", "execution_mode_hint": "AUTOMATED",
             "target_service_hints": ["OwnCloud"], "role_hints": ["DS"],
             "input_artifacts": ["file_path"], "output_artifacts": ["extracted_data"]},
        ])
        dag_response = _simple_dag_json()

        call_count = {"n": 0}

        def mock_completion(**kwargs):
            call_count["n"] += 1
            msgs = kwargs.get("messages", [])
            # First call = intent extraction, rest = DAG generation
            if call_count["n"] == 1:
                return _mock_completion(intent_response)
            return _mock_completion(dag_response)

        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.side_effect = mock_completion
            result = bootstrap_from_queries(
                queries=["Download and analyze the sales report"],
                ontology=ont,
                knowledge_store=store,
                llm_config=LLMConfig(model="test"),
                bootstrap_config=BootstrapConfig(
                    candidates_per_query=2,
                    keep_top_k=1,
                ),
            )

        assert result.queries_processed == 1
        assert result.patterns_generated >= 1
        assert len(store.get_active_patterns()) >= 1

    def test_handles_all_failures_gracefully(self):
        ont = build_full_ontology()
        store = KnowledgeStore()

        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.side_effect = RuntimeError("API error")
            result = bootstrap_from_queries(
                queries=["some query"],
                ontology=ont,
                knowledge_store=store,
                llm_config=LLMConfig(model="test"),
            )

        assert result.queries_processed == 1
        assert result.patterns_generated == 0


class TestCoverageCheck:
    def test_detects_gaps(self):
        ont = build_full_ontology()
        store = KnowledgeStore()
        # Empty store = all node types are gaps
        gaps = check_coverage(ont, store, min_count=1)
        assert len(gaps) > 0

    def test_no_gaps_with_full_coverage(self):
        ont = build_full_ontology()
        store = KnowledgeStore()
        # Add a pattern that covers many intents
        from ontoplan_mvp.seed_patterns import SEED_PATTERNS
        for p in SEED_PATTERNS:
            store.add_pattern(p, confidence=0.5, origin="test")
        # With 30 patterns, most node types should be covered
        gaps = check_coverage(ont, store, min_count=1)
        # Some specialized types may still have gaps, but majority covered
        total_non_system = sum(
            1 for nt in ont.node_types.values() if nt.execution_mode != "SYSTEM"
        )
        covered = total_non_system - len(gaps)
        assert covered >= total_non_system * 0.5  # at least 50% coverage
