"""Phase 0 Bootstrap: generate initial A-Box from T-Box using LLM.

Implements the seed pool initialization described in the design doc §7 Phase 0:

  1. Prepare seed queries (from T-Box-driven LLM generation or manual input)
  2. For each query, LLM generates K=5 candidate DAGs at increasing temperature
  3. Filter by ontology validity + contract satisfaction
  4. Score with proxy fitness, keep top 2 per query
  5. Abstract each to SOP pattern, add to A-Box with confidence=0.5

Also provides coverage checking: every installed non-system node type
should appear in at least N SOP templates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ontoplan_mvp.evolution import compute_fitness
from ontoplan_mvp.knowledge_store import KnowledgeStore
from ontoplan_mvp.llm_client import (
    LLMConfig,
    llm_extract_intents,
    llm_generate_dag,
    llm_generate_seed_queries,
)
from ontoplan_mvp.models import (
    IntentAtom,
    Ontology,
    PatternTemplate,
    WorkflowGraph,
)

logger = logging.getLogger(__name__)


@dataclass
class BootstrapConfig:
    """Configuration for Phase 0 bootstrap."""

    candidates_per_query: int = 5
    keep_top_k: int = 2
    initial_confidence: float = 0.5
    min_coverage_count: int = 3
    base_temperature: float = 0.7
    temperature_step: float = 0.1


@dataclass
class BootstrapResult:
    """Result of a Phase 0 bootstrap run."""

    patterns_generated: int = 0
    queries_processed: int = 0
    dags_generated: int = 0
    dags_valid: int = 0
    coverage_gaps: List[str] = field(default_factory=list)
    patterns: List[PatternTemplate] = field(default_factory=list)


def _extract_intent_names_from_dag(
    dag: WorkflowGraph,
    ontology: Ontology,
) -> Tuple[str, ...]:
    """Infer required intent names from a DAG's non-system nodes.

    Uses keyword matching against node types to infer which intents
    this DAG pattern would serve.
    """
    intent_names: List[str] = []
    keyword_to_intent = _build_keyword_intent_map()

    for node in dag.non_system_nodes():
        nt = ontology.node_types.get(node.node_type)
        if not nt:
            continue
        for kw in nt.keywords:
            if kw in keyword_to_intent:
                intent_name = keyword_to_intent[kw]
                if intent_name not in intent_names:
                    intent_names.append(intent_name)

    # Fallback: use node type name as intent hint
    if not intent_names:
        for node in dag.non_system_nodes():
            name_lower = node.node_type.lower().replace("-", "_")
            if name_lower not in intent_names:
                intent_names.append(name_lower)

    return tuple(intent_names)


def _build_keyword_intent_map() -> Dict[str, str]:
    """Build a reverse map from keywords to intent names."""
    return {
        "review": "code_review",
        "mr": "code_review",
        "merge request": "code_review",
        "code": "code_review",
        "extract": "data_extraction",
        "parse": "data_extraction",
        "read": "data_extraction",
        "download": "file_download",
        "transform": "data_transform",
        "clean": "data_transform",
        "merge": "data_transform",
        "convert": "data_transform",
        "report": "report_generation",
        "generate": "report_generation",
        "create": "report_generation",
        "write": "report_generation",
        "output": "report_generation",
        "upload": "file_upload",
        "save": "file_upload",
        "store": "file_upload",
        "chart": "visualization",
        "plot": "visualization",
        "visualize": "visualization",
        "graph": "visualization",
        "propose": "proposal_generation",
        "draft": "proposal_generation",
        "initial": "proposal_generation",
        "critique": "debate_review",
        "challenge": "debate_review",
        "argue": "debate_review",
        "debate": "debate_review",
        "judge": "final_decision",
        "decide": "final_decision",
        "vote": "final_decision",
        "consensus": "final_decision",
        "supervise": "task_decomposition",
        "coordinate": "task_decomposition",
        "manage": "task_decomposition",
        "delegate": "task_decomposition",
        "worker": "task_execution",
        "execute": "task_execution",
        "implement": "task_execution",
        "aggregate": "result_aggregation",
        "combine": "result_aggregation",
        "synthesize": "result_aggregation",
        "collect": "info_collection",
        "survey": "info_collection",
        "gather": "info_collection",
        "ask": "request_fix_update",
        "request": "request_fix_update",
        "contact": "request_fix_update",
        "fix": "request_fix_update",
        "notify": "status_notification",
        "inform": "status_notification",
        "message": "status_notification",
        "approve": "approval_request",
        "approval": "approval_request",
        "signoff": "approval_request",
        "issue": "issue_lookup",
        "tracking": "issue_lookup",
        "status": "request_status_update",
        "resume": "resume_screening",
        "screen": "resume_screening",
        "candidate": "resume_screening",
        "invoice": "invoice_matching",
        "payment": "invoice_matching",
        "match": "invoice_matching",
        "expense": "expense_validation",
        "validate": "expense_validation",
        "policy": "expense_validation",
        "repo": "repo_clone",
        "repository": "repo_clone",
        "clone": "repo_clone",
        "sprint": "sprint_planning",
        "plan": "sprint_planning",
        "backlog": "sprint_planning",
        "reflect": "critique_revise",
        "revise": "critique_revise",
        "improve": "critique_revise",
        "iterate": "critique_revise",
        "refine": "critique_revise",
        "quality": "data_quality_check",
        "check": "data_quality_check",
    }


def _validate_dag(dag: WorkflowGraph, ontology: Ontology) -> bool:
    """Check that a DAG is structurally valid for the given ontology."""
    if not dag.is_acyclic():
        return False

    node_names = dag.node_names()
    if "QuerySourceNode" not in node_names:
        return False
    if "ResultSinkNode" not in node_names:
        return False

    # Check all non-system node types exist in ontology
    for node in dag.non_system_nodes():
        if node.node_type not in ontology.node_types:
            return False

    return True


def _make_pattern_name(query: str, index: int) -> str:
    """Generate a pattern name from query text."""
    # Take first few significant words
    words = query.lower().split()
    significant = [w for w in words if len(w) > 3 and w.isalpha()][:4]
    base = "_".join(significant) if significant else "auto_pattern"
    return f"bootstrap_{base}_{index}"


def bootstrap_from_queries(
    queries: Sequence[str],
    ontology: Ontology,
    knowledge_store: KnowledgeStore,
    llm_config: Optional[LLMConfig] = None,
    bootstrap_config: Optional[BootstrapConfig] = None,
) -> BootstrapResult:
    """Run Phase 0 bootstrap: generate A-Box patterns from seed queries.

    For each query:
      1. Extract intents via LLM
      2. Generate K candidate DAGs at increasing temperature
      3. Filter by validity
      4. Score with proxy fitness
      5. Keep top-N, abstract to SOP patterns
      6. Add to knowledge store

    Args:
        queries: List of natural language task queries.
        ontology: The T-Box ontology (with all node types).
        knowledge_store: Knowledge store to add patterns to.
        llm_config: LLM configuration.
        bootstrap_config: Bootstrap parameters.

    Returns:
        BootstrapResult with statistics and generated patterns.
    """
    cfg = bootstrap_config or BootstrapConfig()
    result = BootstrapResult()

    for qi, query in enumerate(queries):
        logger.info("Bootstrap query %d/%d: %s", qi + 1, len(queries), query[:80])
        result.queries_processed += 1

        # Step 1: Extract intents
        intents = llm_extract_intents(query, ontology, config=llm_config)
        if not intents:
            logger.warning("No intents extracted for query: %s", query[:80])
            continue

        # Step 2: Generate K candidates at increasing temperature
        scored_candidates: List[Tuple[float, WorkflowGraph, List[IntentAtom]]] = []
        for k in range(cfg.candidates_per_query):
            temp = cfg.base_temperature + cfg.temperature_step * k
            dag = llm_generate_dag(query, ontology, config=llm_config, temperature=temp)
            result.dags_generated += 1

            if dag is None:
                continue

            # Step 3: Validate
            if not _validate_dag(dag, ontology):
                continue
            result.dags_valid += 1

            # Step 4: Score
            score = compute_fitness(dag, intents, ontology)
            scored_candidates.append((score, dag, intents))

        if not scored_candidates:
            logger.warning("No valid DAGs generated for query: %s", query[:80])
            continue

        # Step 5: Keep top-k
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_k = scored_candidates[:cfg.keep_top_k]

        # Step 6: Abstract to SOP patterns and add to knowledge store
        for pi, (score, dag, intents) in enumerate(top_k):
            intent_names = _extract_intent_names_from_dag(dag, ontology)
            if not intent_names:
                intent_names = tuple(i.name for i in intents)

            pattern_name = _make_pattern_name(query, qi * cfg.keep_top_k + pi)
            pattern = PatternTemplate(
                name=pattern_name,
                required_intents=intent_names,
            )

            knowledge_store.add_pattern(
                pattern,
                confidence=cfg.initial_confidence,
                origin="bootstrap",
            )
            result.patterns.append(pattern)
            result.patterns_generated += 1

    # Coverage check
    result.coverage_gaps = check_coverage(ontology, knowledge_store, cfg.min_coverage_count)
    if result.coverage_gaps:
        logger.warning(
            "Coverage gaps after bootstrap: %s",
            ", ".join(result.coverage_gaps),
        )

    return result


def check_coverage(
    ontology: Ontology,
    knowledge_store: KnowledgeStore,
    min_count: int = 3,
) -> List[str]:
    """Check that every non-system node type appears in at least min_count patterns.

    Returns a list of node type names with insufficient coverage.
    """
    # Count node type appearances across all active patterns
    type_counts: Dict[str, int] = {}
    for nt_name in ontology.node_types:
        nt = ontology.node_types[nt_name]
        if nt.execution_mode == "SYSTEM":
            continue
        type_counts[nt_name] = 0

    # Count from keyword mapping (indirect coverage)
    kw_map = _build_keyword_intent_map()
    active_patterns = knowledge_store.get_active_patterns()

    for record in active_patterns:
        for intent_name in record.template.required_intents:
            # Find which node types could serve this intent
            for nt_name, nt in ontology.node_types.items():
                if nt.execution_mode == "SYSTEM":
                    continue
                for kw in nt.keywords:
                    if kw in kw_map and kw_map[kw] == intent_name:
                        type_counts[nt_name] = type_counts.get(nt_name, 0) + 1
                        break

    gaps = [name for name, count in type_counts.items() if count < min_count]
    return sorted(gaps)


def bootstrap_full(
    ontology: Ontology,
    knowledge_store: Optional[KnowledgeStore] = None,
    seed_queries: Optional[Sequence[str]] = None,
    llm_config: Optional[LLMConfig] = None,
    auto_generate_queries: bool = True,
    query_count: int = 20,
) -> BootstrapResult:
    """Full Phase 0 bootstrap: generate queries (if needed) + generate patterns.

    This is the main entry point for bootstrapping a new deployment.

    Args:
        ontology: The full T-Box ontology.
        knowledge_store: Knowledge store (created if None).
        seed_queries: Manual seed queries. If None and auto_generate_queries=True,
                      LLM generates queries from T-Box.
        llm_config: LLM configuration.
        auto_generate_queries: Whether to auto-generate queries from T-Box.
        query_count: Number of queries to generate.

    Returns:
        BootstrapResult with statistics.
    """
    if knowledge_store is None:
        knowledge_store = KnowledgeStore()

    queries: List[str] = []
    if seed_queries:
        queries.extend(seed_queries)

    if auto_generate_queries and not queries:
        logger.info("Auto-generating %d seed queries from T-Box...", query_count)
        generated = llm_generate_seed_queries(ontology, count=query_count, config=llm_config)
        for item in generated:
            if isinstance(item, dict) and "query" in item:
                queries.append(item["query"])
            elif isinstance(item, str):
                queries.append(item)

    if not queries:
        logger.warning("No seed queries available for bootstrap")
        return BootstrapResult()

    logger.info("Starting bootstrap with %d seed queries", len(queries))
    return bootstrap_from_queries(
        queries=queries,
        ontology=ontology,
        knowledge_store=knowledge_store,
        llm_config=llm_config,
    )
