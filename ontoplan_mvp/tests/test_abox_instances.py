"""Tests for A-Box instances: intent catalog, preference map, and workflow templates."""

from ontoplan_mvp.abox_instances import (
    INTENT_CATALOG,
    INTENT_NODE_PREFERENCES,
    WORKFLOW_TEMPLATES,
    get_all_intent_names,
    get_template_by_pattern_name,
)
from ontoplan_mvp.seed_patterns import SEED_PATTERNS, build_full_ontology


class TestIntentCatalog:
    """Verify the intent catalog covers everything referenced by seed patterns."""

    def test_catalog_not_empty(self):
        assert len(INTENT_CATALOG) >= 35

    def test_all_seed_pattern_intents_in_catalog(self):
        """Every intent referenced in SEED_PATTERNS must have a catalog entry."""
        missing = set()
        for pattern in SEED_PATTERNS:
            for intent_name in pattern.required_intents:
                if intent_name not in INTENT_CATALOG:
                    missing.add(intent_name)
        assert not missing, f"Intents in patterns but not in catalog: {missing}"

    def test_catalog_entries_have_required_fields(self):
        for name, intent in INTENT_CATALOG.items():
            assert intent.name == name
            assert intent.execution_mode_hint in (
                "AUTOMATED", "INTERACTIVE", "APPROVAL",
            ), f"{name} has invalid mode: {intent.execution_mode_hint}"
            assert len(intent.role_hints) >= 1, f"{name} has no role hints"

    def test_intent_names_are_snake_case(self):
        for name in INTENT_CATALOG:
            assert name == name.lower(), f"{name} not lowercase"
            assert " " not in name, f"{name} contains spaces"


class TestIntentNodePreferences:
    """Verify the intent→node-type preference map is complete and valid."""

    def test_every_catalog_intent_has_preference(self):
        missing = set(INTENT_CATALOG.keys()) - set(INTENT_NODE_PREFERENCES.keys())
        assert not missing, f"Intents without node preferences: {missing}"

    def test_preferences_reference_valid_node_types(self):
        ont = build_full_ontology()
        invalid = []
        for intent_name, prefs in INTENT_NODE_PREFERENCES.items():
            for nt_name in prefs:
                if nt_name not in ont.node_types:
                    invalid.append((intent_name, nt_name))
        assert not invalid, f"Preferences reference unknown node types: {invalid}"

    def test_preferences_are_non_empty_tuples(self):
        for intent_name, prefs in INTENT_NODE_PREFERENCES.items():
            assert isinstance(prefs, tuple), f"{intent_name} prefs not a tuple"
            assert len(prefs) >= 1, f"{intent_name} has empty preferences"


class TestWorkflowTemplates:
    """Verify all pre-assembled workflow templates are structurally valid."""

    def test_template_count(self):
        assert len(WORKFLOW_TEMPLATES) >= 28

    def test_all_templates_are_acyclic(self):
        for name, wf in WORKFLOW_TEMPLATES.items():
            assert wf.is_acyclic(), f"Template {name} has cycles"

    def test_all_templates_have_source_and_sink(self):
        for name, wf in WORKFLOW_TEMPLATES.items():
            names = wf.node_names()
            assert "QuerySourceNode" in names, f"{name} missing source"
            assert "ResultSinkNode" in names, f"{name} missing sink"

    def test_all_templates_have_edges(self):
        for name, wf in WORKFLOW_TEMPLATES.items():
            assert len(wf.edges) >= 1, f"{name} has no edges"

    def test_sink_receives_at_least_one_artifact(self):
        for name, wf in WORKFLOW_TEMPLATES.items():
            incoming = wf.incoming_artifacts("ResultSinkNode")
            assert len(incoming) >= 1, f"{name}: sink receives nothing"

    def test_source_has_no_incoming(self):
        for name, wf in WORKFLOW_TEMPLATES.items():
            incoming = wf.incoming_edges("QuerySourceNode")
            assert len(incoming) == 0, f"{name}: source has incoming edges"

    def test_templates_cover_all_8_orchestration_types(self):
        prefixes = set()
        for name in WORKFLOW_TEMPLATES:
            prefix = name.split("_")[0]
            prefixes.add(prefix)
        expected = {"seq", "debate", "reflect", "hier", "handoff", "moa", "nested", "role"}
        assert expected.issubset(prefixes), f"Missing: {expected - prefixes}"

    def test_non_system_nodes_have_valid_types(self):
        ont = build_full_ontology()
        for name, wf in WORKFLOW_TEMPLATES.items():
            for node in wf.non_system_nodes():
                assert node.node_type in ont.node_types, (
                    f"{name}: node {node.name} uses unknown type {node.node_type}"
                )

    def test_template_lookup_by_pattern_name(self):
        wf = get_template_by_pattern_name("seq_document_analysis")
        assert wf is not None
        assert "QuerySourceNode" in wf.node_names()

    def test_template_lookup_returns_none_for_unknown(self):
        assert get_template_by_pattern_name("nonexistent") is None

    def test_seed_pattern_names_overlap_with_templates(self):
        """Most seed patterns should have a corresponding workflow template."""
        pattern_names = {p.name for p in SEED_PATTERNS}
        template_names = set(WORKFLOW_TEMPLATES.keys())
        overlap = pattern_names & template_names
        # At least 20 of the 30 patterns should have templates
        assert len(overlap) >= 20, (
            f"Only {len(overlap)} patterns have templates. "
            f"Missing: {pattern_names - template_names}"
        )


class TestSequentialTemplates:
    """Spot-check sequential pattern structure."""

    def test_seq_document_analysis_is_linear(self):
        wf = WORKFLOW_TEMPLATES["seq_document_analysis"]
        # Should be source → extract → transform → report → sink
        assert len(wf.nodes) == 5
        assert len(wf.edges) == 4
        # Verify linear chain
        for i in range(len(wf.edges) - 1):
            assert wf.edges[i].target == wf.edges[i + 1].source

    def test_seq_data_pipeline_ends_with_visualization(self):
        wf = WORKFLOW_TEMPLATES["seq_data_pipeline"]
        # Last non-system node should produce chart_files
        non_sys = wf.non_system_nodes()
        assert non_sys[-1].node_type == "Visualization-Agent"


class TestDebateTemplates:
    """Spot-check debate pattern structure."""

    def test_debate_has_fan_in_to_judge(self):
        wf = WORKFLOW_TEMPLATES["debate_code_review"]
        judge_incoming = wf.incoming_edges("judge")
        assert len(judge_incoming) == 2  # proposal + critique

    def test_debate_loop_uses_compound_node(self):
        wf = WORKFLOW_TEMPLATES["debate_loop_code_review"]
        debate_node = wf.node_by_name("debate")
        assert debate_node.node_type == "debate_loop"


class TestHierarchicalTemplates:
    """Spot-check hierarchical pattern structure."""

    def test_hier_has_supervisor_at_top(self):
        wf = WORKFLOW_TEMPLATES["hier_multi_file_analysis"]
        # Source connects to supervisor
        source_edges = wf.outgoing_edges("QuerySourceNode")
        targets = {e.target for e in source_edges}
        assert "supervisor" in targets

    def test_hier_has_fan_out_to_workers(self):
        wf = WORKFLOW_TEMPLATES["hier_multi_file_analysis"]
        sup_edges = wf.outgoing_edges("supervisor")
        assert len(sup_edges) >= 2  # at least 2 workers

    def test_hier_has_aggregator_before_report(self):
        wf = WORKFLOW_TEMPLATES["hier_multi_file_analysis"]
        agg_out = wf.outgoing_edges("aggregator")
        targets = {e.target for e in agg_out}
        assert "report" in targets


class TestMoATemplates:
    """Spot-check MoA (Mixture-of-Agents) structure."""

    def test_moa_has_3_parallel_proposers(self):
        wf = WORKFLOW_TEMPLATES["moa_multi_reviewer"]
        # Source should fan out to 3 reviewers
        source_edges = wf.outgoing_edges("QuerySourceNode")
        assert len(source_edges) == 3

    def test_moa_synthesizer_receives_3_proposals(self):
        wf = WORKFLOW_TEMPLATES["moa_multi_reviewer"]
        synth_incoming = wf.incoming_edges("synthesizer")
        assert len(synth_incoming) == 3
        arts = set()
        for e in synth_incoming:
            arts.update(e.artifacts_passed)
        assert {"proposal_a", "proposal_b", "proposal_c"} == arts


class TestHandoffTemplates:
    """Spot-check handoff/swarm pattern structure."""

    def test_handoff_has_router(self):
        wf = WORKFLOW_TEMPLATES["handoff_issue_triage"]
        router = wf.node_by_name("router")
        assert router.node_type == "Supervisor-Agent"

    def test_handoff_is_linear_chain(self):
        wf = WORKFLOW_TEMPLATES["handoff_customer_request"]
        # intake → router → executor → notify → sink
        assert len(wf.non_system_nodes()) == 4


class TestNestedTemplates:
    """Spot-check nested compound pattern structure."""

    def test_nested_uses_compound_review_loop(self):
        wf = WORKFLOW_TEMPLATES["nested_review_then_approve"]
        loop_node = wf.node_by_name("review_loop")
        assert loop_node.node_type == "review_request_review_loop"

    def test_nested_uses_compound_approval_chain(self):
        wf = WORKFLOW_TEMPLATES["nested_review_then_approve"]
        approval_node = wf.node_by_name("approval")
        assert approval_node.node_type == "approval_chain"

    def test_nested_debate_then_execute(self):
        wf = WORKFLOW_TEMPLATES["nested_debate_then_execute"]
        debate_node = wf.node_by_name("debate")
        assert debate_node.node_type == "debate_loop"
        executor = wf.node_by_name("executor")
        assert executor.node_type == "Worker-Agent"


class TestGetAllIntentNames:
    def test_returns_sorted_list(self):
        names = get_all_intent_names()
        assert names == sorted(names)
        assert len(names) == len(INTENT_CATALOG)
