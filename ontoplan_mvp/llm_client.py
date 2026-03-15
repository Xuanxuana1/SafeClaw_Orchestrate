"""LLM client layer using LiteLLM for unified multi-provider access.

Provides three core LLM capabilities required by the OntoPlan design:
  1. Intent extraction — structured output from natural language queries
  2. LLM quick judge (F5) — score candidate DAG quality
  3. DAG generation — generate candidate workflow DAGs for Phase 0 bootstrap

Configuration priority (high → low):
  1. Explicit LLMConfig(model=..., api_key=...) in code
  2. .env file at ontoplan_mvp/.env (auto-loaded)
  3. Environment variables: OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
     (also supports ONTOPLAN_LLM_* prefix for override)

Per-node model routing (design doc §4.1 modelPreference):
  Different agent node types can use different models based on task complexity.
  Configure via ModelRouter or NODE_MODEL_OVERRIDES dict.

LiteLLM supports 100+ providers with a unified interface:
  - OpenAI:    model="gpt-4o"          or model="openai/gpt-4o"
  - Anthropic: model="claude-sonnet-4-20250514"
  - Ollama:    model="ollama/llama3"
  - Azure:     model="azure/gpt-4o"
  - Custom:    model="openai/gpt-5.1"  + base_url="http://..."
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import litellm as _litellm
except ImportError:
    _litellm = None  # type: ignore[assignment]

from ontoplan_mvp.models import (
    IntentAtom,
    NodeType,
    Ontology,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# .env file loading
# ---------------------------------------------------------------------------

_ENV_LOADED = False


def _load_env_file() -> None:
    """Load .env file from ontoplan_mvp/ directory if it exists.

    Supports standard OPENAI_* variables and ONTOPLAN_LLM_* overrides.
    Uses python-dotenv if available; falls back to manual parsing.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        logger.info("Loaded .env from %s", env_path)
    except ImportError:
        # Manual fallback: parse KEY="value" lines
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key not in os.environ:  # don't override existing
                    os.environ[key] = value
        logger.info("Loaded .env (manual parse) from %s", env_path)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """LLM configuration, populated from .env file and/or environment.

    Resolution order for each field (first non-empty wins):
      1. Explicit value passed to constructor
      2. ONTOPLAN_LLM_* env var (project-specific override)
      3. OPENAI_* env var (standard provider variable)
      4. Built-in default
    """

    model: str = ""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60

    def __post_init__(self) -> None:
        _load_env_file()

        if not self.model:
            self.model = (
                os.environ.get("ONTOPLAN_LLM_MODEL")
                or os.environ.get("OPENAI_MODEL")
                or "gpt-4o-mini"
            )
        if self.api_key is None:
            self.api_key = (
                os.environ.get("ONTOPLAN_LLM_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY")
            )
        if self.base_url is None:
            raw = (
                os.environ.get("ONTOPLAN_LLM_BASE_URL")
                or os.environ.get("OPENAI_BASE_URL")
            )
            self.base_url = raw or None


# ---------------------------------------------------------------------------
# Per-node model routing (design doc §4.1 modelPreference)
# ---------------------------------------------------------------------------

# Model tier classification:
#   "strong"  — complex reasoning: debate judge, critic, supervisor, DAG generation
#   "default" — standard tasks: intent extraction, worker agents, most nodes
#   "fast"    — high-volume/cost-sensitive: parallel proposers, prompt mutation, seed gen

@dataclass
class ModelRouter:
    """Route different OntoPlan tasks/node-types to different models.

    The design doc §4.1 specifies that each node type can carry a
    `modelPreference` attribute. This router implements that at the
    system level by mapping task categories and node type names to
    specific model identifiers.

    If a node type or task has no explicit override, the default model
    from LLMConfig is used.
    """

    # Tier → model mapping (user-configurable)
    strong_model: str = ""
    default_model: str = ""
    fast_model: str = ""

    # Explicit node-type → model overrides
    node_overrides: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _load_env_file()

        if not self.strong_model:
            self.strong_model = (
                os.environ.get("ONTOPLAN_STRONG_MODEL")
                or os.environ.get("OPENAI_MODEL")
                or ""
            )
        if not self.default_model:
            self.default_model = (
                os.environ.get("ONTOPLAN_DEFAULT_MODEL")
                or os.environ.get("OPENAI_MODEL")
                or ""
            )
        if not self.fast_model:
            self.fast_model = (
                os.environ.get("ONTOPLAN_FAST_MODEL")
                or os.environ.get("OPENAI_MODEL")
                or ""
            )

    def resolve(
        self,
        task: Optional[str] = None,
        node_type: Optional[str] = None,
        fallback_config: Optional[LLMConfig] = None,
    ) -> str:
        """Resolve the model to use for a given task or node type.

        Priority:
          1. Explicit node_overrides[node_type]
          2. Tier mapping based on _NODE_TIER classification
          3. Tier mapping based on task name
          4. fallback_config.model
          5. self.default_model
        """
        # 1. Explicit override
        if node_type and node_type in self.node_overrides:
            return self.node_overrides[node_type]

        # 2. Node-type tier
        tier = _NODE_TIER.get(node_type or "", None)

        # 3. Task-name tier
        if tier is None:
            tier = _TASK_TIER.get(task or "", None)

        # 4. Apply tier
        if tier == "strong" and self.strong_model:
            return self.strong_model
        if tier == "fast" and self.fast_model:
            return self.fast_model
        if tier == "default" and self.default_model:
            return self.default_model

        # 5. Fallback
        if fallback_config and fallback_config.model:
            return fallback_config.model
        return self.default_model or "gpt-4o-mini"


# Node types → model tier classification
# Based on the cognitive complexity of each agent's task
_NODE_TIER: Dict[str, str] = {
    # Strong tier: complex reasoning, multi-step judgment
    "Judge-Agent":          "strong",
    "Critic-Agent":         "strong",
    "Supervisor-Agent":     "strong",
    "MoA-Synthesizer":      "strong",
    "debate_loop":          "strong",
    "reflection_loop":      "strong",
    "CodeReview-Agent":     "strong",

    # Default tier: standard agent tasks
    "Proposer-Agent":       "default",
    "Worker-Agent":         "default",
    "Aggregator-Agent":     "default",
    "DataExtract-Agent":    "default",
    "DataTransform-Agent":  "default",
    "ReportGenerate-Agent": "default",
    "Visualization-Agent":  "default",
    "IssueTracking-Agent":  "default",
    "SprintPlanning-Agent": "default",
    "ResumeScreening-Agent": "default",
    "InvoiceMatching-Agent": "default",
    "ExpenseValidation-Agent": "default",
    "RepoManagement-Agent": "default",
    "InfoCollection-Agent": "default",
    "FileUpload-Agent":     "default",

    # Fast tier: parallel/high-volume, cost-sensitive
    "Parallel-Proposer-A":  "fast",
    "Parallel-Proposer-B":  "fast",
    "Parallel-Proposer-C":  "fast",
    "RequestInfo":          "fast",
    "Notify":               "fast",
    "ApprovalGate":         "fast",
}

# System-level task → model tier
_TASK_TIER: Dict[str, str] = {
    "intent_extraction":    "strong",   # Must understand complex queries
    "dag_generation":       "strong",   # Must reason about graph structure
    "llm_judge":            "strong",   # Must evaluate DAG quality
    "seed_query_gen":       "default",  # Creative but less critical
    "prompt_mutation":      "fast",     # Lightweight variation
}


def _get_default_config() -> LLMConfig:
    return LLMConfig()


_default_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get or create the global ModelRouter singleton."""
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router


def set_model_router(router: ModelRouter) -> None:
    """Replace the global ModelRouter (for testing or reconfiguration)."""
    global _default_router
    _default_router = router


# ---------------------------------------------------------------------------
# Low-level LiteLLM wrapper
# ---------------------------------------------------------------------------

def _call_llm(
    messages: List[Dict[str, str]],
    config: Optional[LLMConfig] = None,
    temperature: Optional[float] = None,
    response_format: Optional[Dict[str, Any]] = None,
    task: Optional[str] = None,
    node_type: Optional[str] = None,
) -> str:
    """Call LiteLLM completion and return the assistant message content.

    Args:
        messages: Chat messages.
        config: LLM configuration (API key, base URL, defaults).
        temperature: Override temperature.
        response_format: Optional response format constraint.
        task: System-level task name for model routing (e.g., "intent_extraction").
        node_type: Agent node type name for model routing (e.g., "Judge-Agent").

    Raises RuntimeError if litellm is not available or the call fails.
    """
    if _litellm is None:
        raise RuntimeError(
            "litellm is required for LLM features. Install with: pip install litellm"
        )

    cfg = config or _get_default_config()

    # Resolve model via router (allows per-node/per-task model selection)
    router = get_model_router()
    resolved_model = router.resolve(
        task=task, node_type=node_type, fallback_config=cfg,
    )

    # When using a custom base_url (OpenAI-compatible proxy), litellm needs
    # the "openai/" prefix to route through the OpenAI provider path.
    if cfg.base_url and not resolved_model.startswith(("openai/", "azure/", "ollama/")):
        resolved_model = f"openai/{resolved_model}"

    kwargs: Dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature if temperature is not None else cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "timeout": cfg.timeout,
    }
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    if cfg.base_url:
        kwargs["api_base"] = cfg.base_url
    if response_format:
        kwargs["response_format"] = response_format

    logger.debug("LLM call: model=%s task=%s node_type=%s", resolved_model, task, node_type)

    try:
        response = _litellm.completion(**kwargs)
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM call failed (model=%s): %s", resolved_model, exc)
        raise


def _parse_json_response(text: str) -> Any:
    """Extract and parse JSON from LLM response, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])
    return json.loads(text)


# ---------------------------------------------------------------------------
# 1. Intent Extraction
# ---------------------------------------------------------------------------

_INTENT_EXTRACTION_SYSTEM = """You are an intent extraction module for an enterprise workflow orchestration system.

Given a natural language task query, extract a list of "intent atoms" — these are capability requirement signals, NOT sub-tasks.

Each intent atom has:
- name: a snake_case identifier from the known intent catalog
- execution_mode_hint: one of AUTOMATED, INTERACTIVE, APPROVAL
- target_service_hints: list of services needed (e.g., GitLab, RocketChat, OwnCloud, Plane, Email)
- role_hints: list of roles involved (e.g., SDE, PM, HR, Finance, DS, Admin)
- input_artifacts: list of expected input artifact names
- output_artifacts: list of expected output artifact names
- target_actor_hint: if this is an interaction with a specific role (e.g., "Developer", "Manager"), null otherwise

IMPORTANT:
- Extract capability SIGNALS, not task decomposition steps
- "ask someone to do X" → INTERACTIVE intent (not AUTOMATED)
- "notify someone" → INTERACTIVE intent
- "approve / sign off" → APPROVAL intent
- Map to the closest intent from the known catalog when possible
- If a query implies iteration (e.g., "if issues, ask to fix, then re-review"), note that in the intents

Return a JSON array of intent objects."""


def _build_intent_extraction_prompt(
    query: str,
    known_intents: Sequence[str],
    node_types: Sequence[str],
    patterns: Optional[Sequence[Any]] = None,   # PatternTemplate list
) -> List[Dict[str, str]]:
    catalog_str = ", ".join(sorted(known_intents))
    types_str = ", ".join(sorted(node_types))

    # Build SOP pattern hint block
    pattern_hint = ""
    if patterns:
        lines = []
        for p in patterns:
            intents_str = ", ".join(p.required_intents)
            lines.append(f"  - {p.name}: [{intents_str}]")
        pattern_hint = (
            "\n\nKnown SOP patterns (if the query matches one of these intent combinations, "
            "use EXACTLY these intent names to maximize template matching):\n"
            + "\n".join(lines)
        )

    user_msg = (
        f'Extract intent atoms from this query:\n\n"{query}"\n\n'
        f"Known intent catalog: [{catalog_str}]\n"
        f"Known node types: [{types_str}]"
        f"{pattern_hint}\n\n"
        "Return ONLY a JSON array of objects with keys: name, execution_mode_hint, "
        "target_service_hints, role_hints, input_artifacts, output_artifacts, target_actor_hint.\n"
        "Prefer intents from the known catalog. If no exact match, create a new descriptive snake_case name."
    )

    return [
        {"role": "system", "content": _INTENT_EXTRACTION_SYSTEM},
        {"role": "user", "content": user_msg},
    ]


def llm_extract_intents(
    query: str,
    ontology: Ontology,
    config: Optional[LLMConfig] = None,
    known_intent_names: Optional[Sequence[str]] = None,
) -> List[IntentAtom]:
    """Use LLM to extract structured intent atoms from a natural language query.

    Falls back to returning an empty list if the LLM call fails.
    """
    if known_intent_names is None:
        # Try to import the full catalog
        try:
            from ontoplan_mvp.abox_instances import INTENT_CATALOG
            known_intent_names = list(INTENT_CATALOG.keys())
        except ImportError:
            known_intent_names = []

    node_type_names = [
        nt.name for nt in ontology.node_types.values()
        if nt.execution_mode != "SYSTEM"
    ]

    messages = _build_intent_extraction_prompt(
        query, known_intent_names, node_type_names,
        patterns=list(ontology.patterns),   # pass SOP template list
    )

    try:
        raw = _call_llm(messages, config=config, temperature=0.1, task="intent_extraction")
        parsed = _parse_json_response(raw)
    except Exception:
        logger.warning("LLM intent extraction failed, returning empty list")
        return []

    intents: List[IntentAtom] = []
    for item in parsed:
        try:
            intents.append(IntentAtom(
                name=item["name"],
                execution_mode_hint=item.get("execution_mode_hint", "AUTOMATED"),
                target_service_hints=tuple(item.get("target_service_hints", ())),
                role_hints=tuple(item.get("role_hints", ())),
                input_artifacts=tuple(item.get("input_artifacts", ())),
                output_artifacts=tuple(item.get("output_artifacts", ())),
                target_actor_hint=item.get("target_actor_hint"),
            ))
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping malformed intent atom: %s", exc)
    return intents


# ---------------------------------------------------------------------------
# 2. LLM Quick Judge (F5)
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = """You are a workflow quality judge. Given a task query and a candidate workflow DAG, score how well the DAG accomplishes the task.

Score on a 0.0 to 1.0 scale considering:
- Does the workflow cover all aspects of the query?
- Are the node types appropriate for each step?
- Is the execution mode correct (automated vs interactive vs approval)?
- Are artifact flows logical (outputs connect to needed inputs)?
- Is the structure efficient (not overly complex)?

Return ONLY a JSON object: {"score": 0.X, "reasoning": "brief explanation"}"""


def _format_dag_for_judge(workflow: WorkflowGraph) -> str:
    """Format a workflow DAG as readable text for the LLM judge."""
    lines = ["Nodes:"]
    for node in workflow.nodes:
        meta = ""
        if node.metadata.get("target_actor_role"):
            meta = f" → {node.metadata['target_actor_role']}"
        lines.append(
            f"  - {node.name} (type={node.node_type}, mode={node.execution_mode}, "
            f"in={list(node.input_artifacts)}, out={list(node.output_artifacts)}){meta}"
        )
    lines.append("Edges:")
    for edge in workflow.edges:
        lines.append(
            f"  - {edge.source} → {edge.target}: [{', '.join(edge.artifacts_passed)}]"
        )
    return "\n".join(lines)


def llm_quick_judge(
    workflow: WorkflowGraph,
    query: str,
    config: Optional[LLMConfig] = None,
) -> float:
    """Use LLM to score a candidate DAG's quality (F5 fitness component).

    Returns a score between 0.0 and 1.0. Falls back to 0.5 (neutral) on failure.
    """
    dag_text = _format_dag_for_judge(workflow)
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": f"Task: \"{query}\"\n\nCandidate DAG:\n{dag_text}"},
    ]

    try:
        raw = _call_llm(messages, config=config, temperature=0.0, task="llm_judge")
        parsed = _parse_json_response(raw)
        score = float(parsed.get("score", 0.5))
        return max(0.0, min(1.0, score))
    except Exception:
        logger.warning("LLM quick judge failed, returning neutral score 0.5")
        return 0.5


# ---------------------------------------------------------------------------
# 3. DAG Generation (Phase 0 Bootstrap)
# ---------------------------------------------------------------------------

_DAG_GEN_SYSTEM = """You are a workflow DAG generator for an enterprise automation system.

Given a task query and available node types, generate a valid workflow DAG as JSON.

Rules:
1. The DAG must start with "QuerySourceNode" and end with "ResultSinkNode"
2. The outer graph must be acyclic (no cycles)
3. Each edge must specify which artifacts flow through it
4. Artifacts passed on an edge must be a subset of the source node's output_artifacts
5. Each non-system node's required input_artifacts must be provided by incoming edges
6. Use INTERACTIVE execution_mode for nodes that request info from or notify humans
7. Use APPROVAL execution_mode for approval gates
8. Use AUTOMATED for all other processing nodes

Return ONLY a JSON object with:
{
  "nodes": [{"name": "...", "node_type": "...", "execution_mode": "...", "input_artifacts": [...], "output_artifacts": [...], "metadata": {}}],
  "edges": [{"source": "...", "target": "...", "artifacts_passed": [...]}]
}"""


def _build_dag_gen_prompt(
    query: str,
    ontology: Ontology,
) -> List[Dict[str, str]]:
    types_desc = []
    for nt in ontology.node_types.values():
        if nt.execution_mode == "SYSTEM":
            continue
        compound_note = " [COMPOUND/iterative]" if nt.is_compound else ""
        types_desc.append(
            f"  - {nt.name} (mode={nt.execution_mode}, "
            f"in={list(nt.input_artifacts)}, out={list(nt.output_artifacts)}, "
            f"services={list(nt.access_bindings)}){compound_note}"
        )
    types_str = "\n".join(types_desc)

    user_msg = f"""Generate a workflow DAG for this task:

"{query}"

Available node types:
{types_str}

System nodes (always include):
  - QuerySourceNode (mode=SYSTEM, in=[], out=[any artifacts the query provides])
  - ResultSinkNode (mode=SYSTEM, in=[final artifacts], out=[])

Return ONLY the JSON object with "nodes" and "edges" arrays."""

    return [
        {"role": "system", "content": _DAG_GEN_SYSTEM},
        {"role": "user", "content": user_msg},
    ]


def llm_generate_dag(
    query: str,
    ontology: Ontology,
    config: Optional[LLMConfig] = None,
    temperature: float = 0.7,
) -> Optional[WorkflowGraph]:
    """Use LLM to generate a candidate DAG for a given query.

    Returns None if generation or parsing fails.
    """
    messages = _build_dag_gen_prompt(query, ontology)

    try:
        raw = _call_llm(messages, config=config, temperature=temperature, task="dag_generation")
        parsed = _parse_json_response(raw)
    except Exception:
        logger.warning("LLM DAG generation failed")
        return None

    try:
        nodes = []
        for n in parsed["nodes"]:
            nodes.append(WorkflowNode(
                name=n["name"],
                node_type=n["node_type"],
                execution_mode=n["execution_mode"],
                input_artifacts=tuple(n.get("input_artifacts", ())),
                output_artifacts=tuple(n.get("output_artifacts", ())),
                metadata=n.get("metadata", {}),
            ))

        edges = []
        for e in parsed["edges"]:
            edges.append(WorkflowEdge(
                source=e["source"],
                target=e["target"],
                artifacts_passed=tuple(e["artifacts_passed"]),
            ))

        graph = WorkflowGraph(nodes=nodes, edges=edges)

        # Validate basic structure
        if not graph.is_acyclic():
            logger.warning("LLM generated cyclic DAG, discarding")
            return None

        return graph
    except (KeyError, TypeError) as exc:
        logger.warning("Failed to parse LLM DAG output: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 4. Seed Query Generation from T-Box
# ---------------------------------------------------------------------------

_SEED_GEN_SYSTEM = """You are a seed query generator for an enterprise workflow orchestration system.

Given a set of node types (agent capabilities), generate diverse natural language task queries that would exercise different combinations of these capabilities.

Requirements:
- Generate realistic enterprise task descriptions
- Cover different domains: software development, project management, HR, finance, data science, admin
- Include simple (2-3 nodes) and complex (4+ nodes) queries
- Include queries that require iteration (review-fix loops)
- Include queries that require human interaction (notifications, approvals)
- Each query should exercise at least 2 node types

Return a JSON array of objects: [{"query": "...", "expected_intents": ["..."], "complexity": "simple|compound|sequential|hierarchical"}]"""


def llm_generate_seed_queries(
    ontology: Ontology,
    count: int = 20,
    config: Optional[LLMConfig] = None,
) -> List[Dict[str, Any]]:
    """Generate diverse seed queries from the T-Box for Phase 0 bootstrap.

    Returns a list of dicts with keys: query, expected_intents, complexity.
    Falls back to empty list on failure.
    """
    types_desc = []
    for nt in ontology.node_types.values():
        if nt.execution_mode == "SYSTEM":
            continue
        types_desc.append(f"  - {nt.name} ({nt.execution_mode}): {list(nt.keywords)}")
    types_str = "\n".join(types_desc)

    messages = [
        {"role": "system", "content": _SEED_GEN_SYSTEM},
        {"role": "user", "content": (
            f"Generate {count} diverse seed queries exercising these node types:\n"
            f"{types_str}\n\n"
            f"Return ONLY the JSON array."
        )},
    ]

    try:
        raw = _call_llm(messages, config=config, temperature=0.8, task="seed_query_gen")
        return _parse_json_response(raw)
    except Exception:
        logger.warning("Seed query generation failed, returning empty list")
        return []
