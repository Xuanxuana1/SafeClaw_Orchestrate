"""Batch planning evaluation on TheAgentCompany task descriptions.

Usage:
    python -m ontoplan_mvp.bench_plan          # run 30 tasks (default)
    python -m ontoplan_mvp.bench_plan --n 10   # run 10 tasks
    python -m ontoplan_mvp.bench_plan --all    # run all tasks
    python -m ontoplan_mvp.bench_plan --no-llm # keyword-only mode (no LLM calls)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Repo root is two levels up from this file
_REPO_ROOT = Path(__file__).parent.parent
_TASKS_DIR = _REPO_ROOT / "workspaces" / "tasks"


def _find_task_files() -> List[Path]:
    """Return sorted list of all task.md files."""
    return sorted(_TASKS_DIR.glob("*/task.md"))


def _sample_tasks(task_files: List[Path], n: int) -> List[Path]:
    """Select n tasks spread across domains (sde/pm/hr/finance/ds/admin)."""
    domains = ["sde", "pm", "hr", "finance", "ds", "admin", "qa", "research", "bm", "ml"]
    buckets: Dict[str, List[Path]] = {d: [] for d in domains}
    other: List[Path] = []

    for f in task_files:
        name = f.parent.name.lower()
        matched = False
        for d in domains:
            if name.startswith(d + "-") or name.startswith(d + "_"):
                buckets[d].append(f)
                matched = True
                break
        if not matched:
            other.append(f)

    # Round-robin across domains
    result: List[Path] = []
    per_domain = max(1, n // len([d for d in domains if buckets[d]]))
    for d in domains:
        result.extend(buckets[d][:per_domain])
    # Fill remaining with other or leftover
    remaining = n - len(result)
    for d in domains:
        if remaining <= 0:
            break
        extra = buckets[d][per_domain:]
        take = min(remaining, len(extra))
        result.extend(extra[:take])
        remaining -= take
    result.extend(other[:max(0, n - len(result))])
    return result[:n]


def _domain(task_name: str) -> str:
    for d in ("sde", "pm", "hr", "finance", "ds", "admin", "qa", "research", "bm", "ml"):
        if task_name.startswith(d):
            return d
    return "other"


def run_bench(n: int = 30, use_llm: bool = True, output_json: Optional[str] = None) -> None:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="  [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    # Silence noisy third-party logs
    for noisy in ("httpx", "httpcore", "openai", "litellm"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from ontoplan_mvp.engine import OntoPlanEngine
    from ontoplan_mvp.knowledge_store import KnowledgeStore
    from ontoplan_mvp.seed_patterns import build_full_ontology

    ontology = build_full_ontology()
    store = KnowledgeStore()
    engine = OntoPlanEngine(
        ontology,
        knowledge_store=store,
        use_evolution=False,
        use_llm=use_llm,
    )

    all_files = _find_task_files()
    if n == -1:
        selected = all_files
    else:
        selected = _sample_tasks(all_files, n)

    print(f"\nOntoPlan Bench — {len(selected)} tasks  (llm={'on' if use_llm else 'off'})")
    print("=" * 72)
    sys.stdout.flush()

    results: List[Dict[str, Any]] = []

    for i, task_file in enumerate(selected, 1):
        task_name = task_file.parent.name
        query = task_file.read_text(encoding="utf-8").strip()
        display_query = query[:120].replace("\n", " ") + ("…" if len(query) > 120 else "")

        print(f"\n[{i:3d}/{len(selected)}] {task_name}")
        print(f"  query: {display_query}")
        sys.stdout.flush()

        t0 = time.time()
        try:
            plan = engine.plan(query)
            elapsed = time.time() - t0

            intent_names = [i.name for i in plan.intents]
            node_types = [n.node_type for n in plan.workflow.non_system_nodes()]
            matched_pattern = None
            if intent_names:
                matching = ontology.matching_patterns(tuple(intent_names))
                if matching:
                    matched_pattern = matching[0].name

            status = "OK" if not plan.validation_errors else "ERR"
            print(f"  intents:  {intent_names}")
            print(f"  nodes:    {node_types}")
            if matched_pattern:
                print(f"  pattern:  ✓ {matched_pattern}")
            else:
                print(f"  pattern:  — (linear assembly)")
            print(
                f"  → {status}  score={plan.score:.3f}  "
                f"nodes={len(node_types)}  {elapsed:.1f}s"
            )
            if plan.validation_errors:
                for e in plan.validation_errors[:2]:
                    print(f"  ! {e}")
            sys.stdout.flush()

            results.append({
                "task": task_name,
                "domain": _domain(task_name),
                "score": plan.score,
                "valid": not plan.validation_errors,
                "validation_errors": plan.validation_errors,
                "intents": intent_names,
                "node_types": node_types,
                "matched_pattern": matched_pattern,
                "n_nodes": len(node_types),
                "elapsed_s": round(elapsed, 2),
            })

        except Exception as exc:
            elapsed = time.time() - t0
            print(f"  → FAIL  error={exc}")
            sys.stdout.flush()
            results.append({
                "task": task_name,
                "domain": _domain(task_name),
                "score": 0.0,
                "valid": False,
                "validation_errors": [str(exc)],
                "intents": [],
                "node_types": [],
                "matched_pattern": None,
                "n_nodes": 0,
                "elapsed_s": round(elapsed, 2),
            })

    # Summary
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    total = len(results)
    valid = sum(1 for r in results if r["valid"])
    pattern_hit = sum(1 for r in results if r["matched_pattern"])
    avg_score = sum(r["score"] for r in results) / max(total, 1)
    avg_nodes = sum(r["n_nodes"] for r in results) / max(total, 1)
    avg_intents = sum(len(r["intents"]) for r in results) / max(total, 1)
    avg_time = sum(r["elapsed_s"] for r in results) / max(total, 1)

    print(f"  Tasks run:          {total}")
    print(f"  Valid plans:        {valid}/{total}  ({100*valid//max(total,1)}%)")
    print(f"  Pattern match hit:  {pattern_hit}/{total}  ({100*pattern_hit//max(total,1)}%)")
    print(f"  Avg score:          {avg_score:.3f}")
    print(f"  Avg nodes/plan:     {avg_nodes:.1f}")
    print(f"  Avg intents/query:  {avg_intents:.1f}")
    print(f"  Avg time/task:      {avg_time:.1f}s")

    # Per-domain breakdown
    from collections import defaultdict
    domain_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"total": 0, "valid": 0, "pattern": 0})
    for r in results:
        d = r["domain"]
        domain_stats[d]["total"] += 1
        if r["valid"]:
            domain_stats[d]["valid"] += 1
        if r["matched_pattern"]:
            domain_stats[d]["pattern"] += 1

    print("\n  Domain breakdown:")
    for domain, stats in sorted(domain_stats.items()):
        t = stats["total"]
        v = stats["valid"]
        p = stats["pattern"]
        print(f"    {domain:<10s}  {t} tasks  valid={v}  pattern_hit={p}")

    if output_json:
        Path(output_json).write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\n  Results written to: {output_json}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OntoPlan batch planning benchmark")
    parser.add_argument("--n", type=int, default=30, help="Number of tasks to run (default: 30)")
    parser.add_argument("--all", action="store_true", help="Run all tasks")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM, use keyword extraction only")
    parser.add_argument("--output", type=str, default=None, help="Write results to JSON file")
    args = parser.parse_args()

    n = -1 if args.all else args.n
    run_bench(n=n, use_llm=not args.no_llm, output_json=args.output)


if __name__ == "__main__":
    main()
