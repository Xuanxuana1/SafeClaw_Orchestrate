"""Tests for the LLM client layer (mocked, no real API calls)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from ontoplan_mvp.llm_client import (
    LLMConfig,
    _parse_json_response,
    llm_extract_intents,
    llm_generate_dag,
    llm_quick_judge,
    llm_generate_seed_queries,
)
from ontoplan_mvp.ontology import build_default_ontology
from ontoplan_mvp.seed_patterns import build_full_ontology


# ---------------------------------------------------------------------------
# LLMConfig tests
# ---------------------------------------------------------------------------

class TestLLMConfig:
    def test_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("ONTOPLAN_LLM_MODEL", "test-model")
        monkeypatch.setenv("ONTOPLAN_LLM_API_KEY", "sk-test")
        monkeypatch.setenv("ONTOPLAN_LLM_BASE_URL", "http://localhost:8080")
        cfg = LLMConfig()
        assert cfg.model == "test-model"
        assert cfg.api_key == "sk-test"
        assert cfg.base_url == "http://localhost:8080"

    def test_explicit_values_override_env(self, monkeypatch):
        monkeypatch.setenv("ONTOPLAN_LLM_MODEL", "env-model")
        cfg = LLMConfig(model="explicit-model", api_key="explicit-key")
        assert cfg.model == "explicit-model"
        assert cfg.api_key == "explicit-key"

    def test_default_model_when_no_env(self, monkeypatch):
        monkeypatch.delenv("ONTOPLAN_LLM_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        cfg = LLMConfig()
        assert cfg.model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# JSON parsing tests
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_plain_json(self):
        assert _parse_json_response('{"a": 1}') == {"a": 1}

    def test_json_in_markdown_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert _parse_json_response(text) == {"a": 1}

    def test_json_array(self):
        assert _parse_json_response('[1, 2, 3]') == [1, 2, 3]

    def test_markdown_fence_without_lang(self):
        text = '```\n{"x": true}\n```'
        assert _parse_json_response(text) == {"x": True}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("not json")


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_completion(content: str):
    """Create a mock litellm.completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    return mock_response


# ---------------------------------------------------------------------------
# Intent extraction tests
# ---------------------------------------------------------------------------

class TestLLMExtractIntents:
    def test_parses_valid_response(self):
        response_data = [
            {
                "name": "code_review",
                "execution_mode_hint": "AUTOMATED",
                "target_service_hints": ["GitLab"],
                "role_hints": ["SDE"],
                "input_artifacts": ["mr_url"],
                "output_artifacts": ["MR_review_result"],
                "target_actor_hint": None,
            },
            {
                "name": "status_notification",
                "execution_mode_hint": "INTERACTIVE",
                "target_service_hints": ["RocketChat"],
                "role_hints": ["PM"],
                "input_artifacts": ["final_review_result"],
                "output_artifacts": ["notification_sent"],
                "target_actor_hint": "Manager",
            },
        ]
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(json.dumps(response_data))
            intents = llm_extract_intents(
                "Review MR and notify PM",
                build_default_ontology(),
                config=LLMConfig(model="test"),
            )

        assert len(intents) == 2
        assert intents[0].name == "code_review"
        assert intents[0].execution_mode_hint == "AUTOMATED"
        assert intents[1].name == "status_notification"
        assert intents[1].target_actor_hint == "Manager"

    def test_returns_empty_on_failure(self):
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.side_effect = RuntimeError("API error")
            intents = llm_extract_intents(
                "some query",
                build_default_ontology(),
                config=LLMConfig(model="test"),
            )
        assert intents == []

    def test_skips_malformed_items(self):
        # Missing required 'name' field
        response_data = [
            {"execution_mode_hint": "AUTOMATED"},
            {"name": "valid_intent", "execution_mode_hint": "AUTOMATED",
             "target_service_hints": [], "role_hints": ["SDE"]},
        ]
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(json.dumps(response_data))
            intents = llm_extract_intents(
                "test", build_default_ontology(), config=LLMConfig(model="test"),
            )
        assert len(intents) == 1
        assert intents[0].name == "valid_intent"


# ---------------------------------------------------------------------------
# LLM judge tests
# ---------------------------------------------------------------------------

class TestLLMQuickJudge:
    def test_returns_score(self):
        from ontoplan_mvp.abox_instances import WORKFLOW_TEMPLATES
        wf = WORKFLOW_TEMPLATES["seq_document_analysis"]

        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(
                '{"score": 0.85, "reasoning": "Good coverage"}'
            )
            score = llm_quick_judge(wf, "Analyze document", config=LLMConfig(model="test"))

        assert score == 0.85

    def test_clamps_score_to_range(self):
        from ontoplan_mvp.abox_instances import WORKFLOW_TEMPLATES
        wf = WORKFLOW_TEMPLATES["seq_document_analysis"]

        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(
                '{"score": 1.5, "reasoning": "Over 1"}'
            )
            score = llm_quick_judge(wf, "test", config=LLMConfig(model="test"))
        assert score == 1.0

    def test_returns_neutral_on_failure(self):
        from ontoplan_mvp.abox_instances import WORKFLOW_TEMPLATES
        wf = WORKFLOW_TEMPLATES["seq_document_analysis"]

        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.side_effect = RuntimeError("API error")
            score = llm_quick_judge(wf, "test", config=LLMConfig(model="test"))
        assert score == 0.5


# ---------------------------------------------------------------------------
# DAG generation tests
# ---------------------------------------------------------------------------

class TestLLMGenerateDAG:
    def test_parses_valid_dag(self):
        dag_json = {
            "nodes": [
                {"name": "QuerySourceNode", "node_type": "QuerySourceNode",
                 "execution_mode": "SYSTEM", "input_artifacts": [],
                 "output_artifacts": ["file_path"]},
                {"name": "extract", "node_type": "DataExtract-Agent",
                 "execution_mode": "AUTOMATED",
                 "input_artifacts": ["file_path"],
                 "output_artifacts": ["extracted_data"]},
                {"name": "ResultSinkNode", "node_type": "ResultSinkNode",
                 "execution_mode": "SYSTEM",
                 "input_artifacts": ["extracted_data"],
                 "output_artifacts": []},
            ],
            "edges": [
                {"source": "QuerySourceNode", "target": "extract",
                 "artifacts_passed": ["file_path"]},
                {"source": "extract", "target": "ResultSinkNode",
                 "artifacts_passed": ["extracted_data"]},
            ],
        }
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(json.dumps(dag_json))
            dag = llm_generate_dag(
                "Extract data from file",
                build_full_ontology(),
                config=LLMConfig(model="test"),
            )

        assert dag is not None
        assert dag.is_acyclic()
        assert len(dag.nodes) == 3
        assert dag.has_edge("QuerySourceNode", "extract")

    def test_returns_none_for_cyclic_dag(self):
        dag_json = {
            "nodes": [
                {"name": "A", "node_type": "Worker-Agent",
                 "execution_mode": "AUTOMATED",
                 "input_artifacts": ["x"], "output_artifacts": ["y"]},
                {"name": "B", "node_type": "Worker-Agent",
                 "execution_mode": "AUTOMATED",
                 "input_artifacts": ["y"], "output_artifacts": ["x"]},
            ],
            "edges": [
                {"source": "A", "target": "B", "artifacts_passed": ["y"]},
                {"source": "B", "target": "A", "artifacts_passed": ["x"]},
            ],
        }
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(json.dumps(dag_json))
            dag = llm_generate_dag(
                "test", build_full_ontology(), config=LLMConfig(model="test"),
            )
        assert dag is None

    def test_returns_none_on_failure(self):
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.side_effect = RuntimeError("API error")
            dag = llm_generate_dag(
                "test", build_full_ontology(), config=LLMConfig(model="test"),
            )
        assert dag is None


# ---------------------------------------------------------------------------
# Seed query generation tests
# ---------------------------------------------------------------------------

class TestLLMGenerateSeedQueries:
    def test_parses_valid_queries(self):
        queries = [
            {"query": "Review the MR", "expected_intents": ["code_review"],
             "complexity": "simple"},
            {"query": "Download and analyze data", "expected_intents": ["file_download"],
             "complexity": "sequential"},
        ]
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(json.dumps(queries))
            result = llm_generate_seed_queries(
                build_full_ontology(), count=2, config=LLMConfig(model="test"),
            )
        assert len(result) == 2
        assert result[0]["query"] == "Review the MR"

    def test_returns_empty_on_failure(self):
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.side_effect = RuntimeError("API error")
            result = llm_generate_seed_queries(
                build_full_ontology(), config=LLMConfig(model="test"),
            )
        assert result == []


# ---------------------------------------------------------------------------
# Engine integration tests (LLM mode)
# ---------------------------------------------------------------------------

class TestEngineWithLLM:
    def test_engine_use_llm_flag(self):
        from ontoplan_mvp.engine import OntoPlanEngine
        engine = OntoPlanEngine(
            build_default_ontology(),
            use_llm=True,
            llm_config=LLMConfig(model="test"),
        )
        assert engine.use_llm is True

    def test_engine_llm_fallback_to_keyword(self):
        """When LLM fails, engine falls back to keyword extraction."""
        from ontoplan_mvp.engine import OntoPlanEngine
        engine = OntoPlanEngine(
            build_default_ontology(),
            use_llm=True,
            llm_config=LLMConfig(model="test"),
        )
        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.side_effect = RuntimeError("no API key")
            intents = engine.extract_intents(
                "Check Sarah's MR, if code has issues ask her to fix, notify PM"
            )
        # Should fall back to keyword extraction
        assert len(intents) >= 2
        names = [i.name for i in intents]
        assert "code_review" in names

    def test_engine_llm_judge_blends_score(self):
        """When LLM judge works, score is blended."""
        from ontoplan_mvp.engine import OntoPlanEngine
        from ontoplan_mvp.models import PlanCandidate, WorkflowGraph, WorkflowNode

        engine = OntoPlanEngine(
            build_default_ontology(),
            use_llm=True,
            llm_config=LLMConfig(model="test"),
        )
        # Create a minimal candidate
        wf = WorkflowGraph(
            nodes=[
                WorkflowNode("QuerySourceNode", "QuerySourceNode", "SYSTEM", (), ("mr_url",)),
                WorkflowNode("ResultSinkNode", "ResultSinkNode", "SYSTEM",
                             ("notification_sent",), ()),
            ],
            edges=[],
        )
        candidate = PlanCandidate(workflow=wf, validation_errors=[], score=1.0)

        with patch("ontoplan_mvp.llm_client._litellm") as mock_llm:
            mock_llm.completion.return_value = _mock_completion(
                '{"score": 0.9, "reasoning": "ok"}'
            )
            result = engine._apply_llm_judge(candidate, "test query")

        # Score should be blended: 1.0 * 0.95 + 0.9 * 0.05 = 0.995
        assert abs(result.score - 0.995) < 0.001
