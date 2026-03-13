# OntoPlan MVP

Self-contained Python implementation of the OntoPlan design — ontology-grounded graph evolution for multi-agent orchestration.

## Components

| Module | Description |
|--------|-------------|
| `models.py` | Data models: IntentAtom, NodeType, WorkflowGraph, CompoundNodeDef (FSM), PlanCandidate |
| `ontology.py` | Default enterprise office ontology (8 node types, 1 compound node, 1 SOP pattern) |
| `engine.py` | Core planning engine: intent extraction, retrieval, assembly, optimization |
| `evolution.py` | Mutation operators (M1-M7), crossover (C1), fitness function (F1-F7), micro-evolution loop |
| `knowledge_store.py` | Failure classification (6 types), 3-level credit assignment, pattern confidence tracking |
| `demo.py` | End-to-end demonstration with feedback simulation |

## Design doc coverage

- Hierarchical DAG (outer acyclic + compound node FSMs)
- Typed artifact contracts on nodes and edges
- Execution-mode-aware node types (AUTOMATED / INTERACTIVE / APPROVAL / SYSTEM)
- Ontology-grounded retrieval with pattern-based and linear assembly
- 7 constraint-preserving mutation operators + subgraph-swap crossover
- Population-based micro-evolution (5 individuals, 3 generations)
- 7-component proxy fitness function (coverage, consistency, efficiency, historical, LLM placeholder, contract compat, mode correctness)
- Knowledge store with differentiated credit assignment (pattern / node-type / edge levels)
- 6 failure types with priority-based classification

## Run

```bash
# Tests (34 tests)
pytest ontoplan_mvp/tests/ -v

# Demo
python -m ontoplan_mvp.demo
```
