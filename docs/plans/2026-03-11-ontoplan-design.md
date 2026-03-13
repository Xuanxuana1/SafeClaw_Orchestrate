# OntoPlan: Ontology-Grounded Graph Evolution for Multi-Agent Orchestration with Human Knowledge Distillation

## Design Document

**Date:** 2026-03-11
**Status:** Draft (Rev 4 - post Codex review round 3)
**Application Domain:** Enterprise Office Automation
**Rev 2 Changes:** Fix DAG cycle (hierarchical DAG + compound nodes), add artifact contracts & actor semantics, add outcome-grounded credit assignment
**Rev 3 Changes:** Propagate actor-aware ontology to retrieval layer & core relations, fix Notifier type inconsistency, fix contract validation ordering (source injection before validation)
**Rev 4 Changes:** Replace runtime human-execution modeling with benchmark-friendly interaction nodes, rename actor hints to execution-mode hints, align retrieval/fitness/lifecycle with interaction-centric semantics

---

## 1. Problem Statement

Existing MAS auto-orchestration methods have three shortcomings:

1. **Blind search** (EvoMAS): Evolutionary methods search the full configuration space without structural guidance, requiring many generations and full executions for fitness evaluation.
2. **Macro-topology only** (AdaptOrch): Routing methods select from a fixed set of canonical topologies (Parallel/Sequential/Hierarchical/Hybrid) based on task DAG features, but don't address agent-level orchestration (which agents, what tools, what prompts, how connected).
3. **Stateless** (All): Every task is handled independently. No knowledge accumulates across tasks. Human operational expertise (tacit knowledge) is never captured.

## 2. Core Idea

OntoPlan represents agent topologies as **ontology-constrained hierarchical DAGs** — the macro layer is a strict DAG for scheduling and evolution; selected nodes may be **compound nodes** that encapsulate an internal finite state machine (FSM) for iterative sub-processes (e.g., review-request-review loops). Nodes carry typed **input/output artifact contracts** with preconditions and postconditions, and are classified by **execution mode**: automated execution, external interaction, approval gating, or system plumbing. External collaborators are modeled as **interaction targets / metadata**, not as executable runtime nodes, which keeps the design benchmark-friendly while still capturing enterprise collaboration points.

The system generates orchestrations through **ontology-grounded subgraph retrieval** from a knowledge graph, followed by **constraint-aware graph micro-evolution** with **outcome-grounded credit assignment**. Knowledge accumulates across three phases: bootstrap self-seeding, autonomous self-evolution, and human-in-the-loop knowledge distillation.

## 3. System Architecture (Four Layers)

```
+-----------------------------------------------------------+
|                     Query Interface                        |
|            Natural language task -> Intent atoms            |
+----------------------------+------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|      Layer 1: Enterprise Office Ontology (EOO)             |
|  +------------+ +----------------+ +--------------------+  |
|  | Node Type  | | Tool/Service   | | SOP Pattern        |  |
|  | Hierarchy  | | Capability     | | Graph Templates    |  |
|  | (T-Box)    | | Graph (T-Box)  | | (A-Box)            |  |
|  +------------+ +----------------+ +--------------------+  |
+----------------------------+------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|      Layer 2: Ontology-Grounded Retrieval & Assembly       |
|  Query embedding -> KG subgraph retrieval (NOT task decomp)|
|  -> Match SOP templates -> Instantiate workflow nodes      |
|  -> Assemble initial DAG                                   |
+----------------------------+------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|      Layer 3: Constraint-Aware Graph Micro-Evolution       |
|  Ontology-constrained search space -> Graph mutation ops   |
|  -> Proxy fitness evaluation -> Local optimization         |
|  (Evolution at node granularity, NOT macro-topology)       |
+----------------------------+------------------------------+
                             |
                             v
+-----------------------------------------------------------+
|      Layer 4: Execution + Human Knowledge Distillation     |
|  DAG execution -> Checkpoint assertions -> UI display      |
|  -> Human edits -> Delta abstraction -> SOP pattern write  |
|  back to KG                                                |
+-----------------------------------------------------------+
```

### Core Data Flow

1. **Query -> Intent Atoms**: LLM extracts capability requirement signals (NOT sub-tasks). Each intent atom has a capability vector, target service hints, role hints, **execution-mode hints**, and **expected artifact types**.
2. **Intent Atoms -> Subgraph Retrieval**: Three-level retrieval in KG (node candidates -> SOP templates -> edge relation inference). **Edges are typed with artifact contracts.**
3. **Candidate Assembly -> Initial DAG**: Template-driven assembly if high coverage, free assembly otherwise. **Contract compatibility validated: each edge's output_artifacts must satisfy the downstream node's input_artifacts.**
4. **Micro-Evolution**: 3-5 generations of local mutations in the ontology-constrained neighborhood. **Compound nodes with internal FSMs are treated as atomic during evolution.**
5. **Execution + Feedback**: Execute optimal DAG, human can edit via UI, edits distilled back to KG. **Failure attribution at node level, not just DAG level.**

### Key Difference from AdaptOrch

- AdaptOrch answers "which macro orchestration pattern?" (4 fixed topologies)
- OntoPlan answers "which specific execution/interaction nodes, doing what, connected how?" (free-form node-level DAG)
- AdaptOrch's graph = task dependency graph (nodes = sub-tasks)
- OntoPlan's graph = workflow topology graph (nodes = automated or interaction nodes with contracts, access bindings, and prompts/templates)

## 4. Enterprise Office Ontology (EOO) Design

### 4.1 T-Box (Terminology Layer)

**Execution & Node Type Hierarchy:**

The top-level distinction is **execution mode** — whether a node is executed autonomously by the system, represents a request/notification/approval interaction with an external collaborator, or is a system utility node (source/sink). This is more benchmark-friendly than making humans first-class executable nodes, while still preserving the orchestration decision of **when to ask, notify, wait, or escalate**.

```
Thing
  Node
    AutomatedNode                     # System-executed nodes
      AI-Agent
        SDE-Agent
          CodeReview-Agent
          BugFix-Agent
          Deployment-Agent
        PM-Agent
          IssueTracking-Agent
          SprintPlanning-Agent
          StatusReport-Agent
        HR-Agent
          ResumeScreening-Agent
          InterviewScheduling-Agent
          SalaryAnalysis-Agent
        Finance-Agent
          InvoiceMatching-Agent
          ExpenseValidation-Agent
        DS-Agent
          DataCleaning-Agent
          StatAnalysis-Agent
        Admin-Agent
        Coordinator-Agent
          Router-Agent
          Synthesizer-Agent
    InteractionNode                   # System initiates external collaboration
      RequestInfo                     # Request information/action and wait for response
      Notify                          # One-way notification
      ApprovalGate                    # Explicit human/manager approval required
      Escalate                        # Hand off abnormal case to external collaborator
    SystemNode
      QuerySourceNode
      ResultSinkNode

  TargetActorRole                     # Metadata, not executable graph nodes
    Developer                         # e.g., Sarah's role
    Manager                           # e.g., PM lead
    Domain-Expert                     # e.g., HR specialist, finance officer
```

Each node type carries attributes:
- `capabilities`: Capability description vector (for semantic matching)
- `requiredTools`: Required tool set (AutomatedNode only)
- `channelPreference`: Communication channel / system binding (InteractionNode only)
- `targetActorRole`: Intended external collaborator role (InteractionNode only)
- `promptTemplate`: Default prompt or message template (LLM-backed nodes only)
- `modelPreference`: Recommended LLM type/size (LLM-backed nodes only)
- `execution_mode`: enum {AUTOMATED, INTERACTIVE, APPROVAL, SYSTEM}

**Node Contract Schema (input/output artifacts + pre/postconditions):**

Every node in the graph carries a typed contract that specifies what data it consumes, produces, and what conditions must hold:

```yaml
NodeContract:
  input_artifacts:
    - {name: "mr_url", type: "URL", source_service: "GitLab", required: true}
    - {name: "review_criteria", type: "Text", required: false}
  output_artifacts:
    - {name: "review_result", type: "Enum[approved, has_issues, needs_discussion]"}
    - {name: "review_comments", type: "StructuredJSON"}
  preconditions:
    - "mr.status == 'open'"
    - "mr.author != self"       # cannot review own MR
  postconditions:
    - "review_result != null"
    - "review_comments.length > 0 if review_result == 'has_issues'"
```

**Edge Contract Schema (typed data flow between nodes):**

Edges are not bare connections but carry explicit artifact routing:

```yaml
EdgeContract:
  from_node: "?reviewer"
  to_node: "?request_fix"
  artifacts_passed:
    - {name: "review_comments", type: "StructuredJSON"}
    - {name: "mr_url", type: "URL"}
  trigger_condition: "review_result == 'has_issues'"
  # Validation rule: artifacts_passed must be subset of from_node.output_artifacts
  # and must satisfy to_node.input_artifacts requirements
```

**Compound Node Schema (for iterative sub-processes):**

To handle iterative workflows (e.g., review-fix-re-review loops) without breaking the DAG property of the macro graph, we introduce **compound nodes**. A compound node appears as a single atomic node in the outer DAG but encapsulates an internal FSM:

```yaml
CompoundNode:
  id: "review_request_review_loop"
  external_interface:              # How it looks to the outer DAG
    input_artifacts:
      - {name: "mr_url", type: "URL"}
    output_artifacts:
      - {name: "final_review_result", type: "Enum[approved, rejected]"}
      - {name: "fix_history", type: "List[CommitSHA]"}
  internal_fsm:
    states: [REVIEWING, REQUEST_FIX, DONE]
    initial_state: REVIEWING
    transitions:
      - {from: REVIEWING, to: REQUEST_FIX, condition: "review_result == 'has_issues'"}
      - {from: REQUEST_FIX, to: REVIEWING, condition: "fix_commit_received == true"}
      - {from: REVIEWING, to: DONE, condition: "review_result == 'approved'"}
    termination:
      max_iterations: 3            # Hard limit to guarantee termination
      timeout: 600s
      fallback_state: DONE         # Exit with current state if limit reached
    internal_nodes:
      - {state: REVIEWING, node_type: "CodeReview-Agent", execution_mode: AUTOMATED}
      - {state: REQUEST_FIX, node_type: "RequestInfo", execution_mode: INTERACTIVE,
         target_actor_role: "Developer", channel: "RocketChat"}
        # Note: REQUEST_FIX models an interaction point with an external collaborator.
        # The collaborator is not an executable graph node during benchmark evaluation.
```

This design ensures:
- **Outer DAG remains acyclic**: compound nodes are atomic from the scheduler's perspective.
- **Iteration is bounded**: `max_iterations` and `timeout` guarantee termination.
- **Evolution operates on the outer DAG**: mutation/crossover operators treat compound nodes as single units, avoiding accidental cycle creation.
- **Benchmark-friendly semantics**: the internal FSM captures that "ask Sarah to fix" is an interaction point, not a requirement to execute a real human inside the benchmark loop.

**Tool/Service Capability Graph:**

```
Service
  GitLab
    hasCapability: [clone, commit, merge_request, issue_mgmt, ci_cd]
    accessPattern: REST API
  RocketChat
    hasCapability: [send_message, channel_mgmt, user_lookup, notification]
    accessPattern: REST API + WebSocket
  Plane
    hasCapability: [issue_tracking, sprint_mgmt, status_update]
    accessPattern: REST API
  OwnCloud
    hasCapability: [file_upload, file_download, share, search]
    accessPattern: WebDAV + REST API
```

Core relations (execution-aware):
- `AutomatedNode --usesTool--> Tool`         # AI / system nodes directly invoke tools
- `InteractionNode --usesChannel--> Tool`    # Interaction nodes send messages / requests via channels
- `InteractionNode --targetsRole--> TargetActorRole`
- `Tool --belongsTo--> Service`
- `Node --requires--> Capability`
- `Capability --providedBy--> Tool`

### 4.2 SOP Pattern Templates (Key Innovation)

SOP patterns are NOT text descriptions but **subgraph templates** (hierarchical DAG fragments with type variables and artifact contracts):

```yaml
SOPPattern:
  name: "code_review_with_request_flow"
  trigger: "code review / review / merge request / check MR"
  template_graph:
    nodes:
      - id: "?review_request_loop"
        type: CompoundNode
        external_interface:
          input_artifacts:
            - {name: "mr_url", type: "URL", source_service: "GitLab"}
          output_artifacts:
            - {name: "final_review_result", type: "Enum[approved, rejected]"}
        internal_fsm:
          states: [REVIEWING, REQUEST_FIX, DONE]
          transitions:
            - {from: REVIEWING, to: REQUEST_FIX, condition: "has_issues"}
            - {from: REQUEST_FIX, to: REVIEWING, condition: "fix_commit_received"}
            - {from: REVIEWING, to: DONE, condition: "approved"}
          max_iterations: 3
          internal_nodes:
            - {state: REVIEWING, type: "CodeReview-Agent", execution_mode: AUTOMATED}
            - {state: REQUEST_FIX, type: "RequestInfo", execution_mode: INTERACTIVE,
               target_actor_role: "Developer", channel: "RocketChat"}
      - id: "?notifier"
        type: "Notify"
        execution_mode: INTERACTIVE
        target_actor_role: "Manager"
        channel: "RocketChat"
        input_artifacts:
          - {name: "final_review_result", type: "Enum[approved, rejected]"}
        output_artifacts:
          - {name: "notification_sent", type: "Boolean"}
    edges:
      - from: "?review_request_loop"
        to: "?notifier"
        artifacts_passed: [{name: "final_review_result"}]
        trigger_condition: "final_review_result != null"
        # NOTE: No back-edge. The loop is INSIDE the compound node.
        # Outer graph is a strict DAG: review_request_loop -> notifier
    constraints:
      - "?review_request_loop.internal_nodes[REVIEWING].model_size >= medium"
  confidence: 0.85
  usage_count: 47
  origin: "human_edit"  # human_edit | evolution | bootstrap
```

Key design principles:
- **No cycles in outer graph**: iterative processes are encapsulated in compound nodes.
- **Typed edges**: every edge specifies which artifacts flow through it and under what condition.
- **Contract validation**: during assembly and evolution, the system verifies that `edge.artifacts_passed` is a subset of `from_node.output_artifacts` and satisfies `to_node.input_artifacts` requirements.
- **Interaction-aware**: the graph distinguishes automated work from external collaboration points without introducing runtime human nodes.

### 4.3 A-Box (Instance Layer)

Grows continuously with system usage:
- Node instance configurations (specific prompts, model choices, success rate stats)
- SOP template instances distilled from human edits
- Historical execution records (query -> DAG -> result -> feedback)
- Capability-tool mapping instances (specific API endpoints, parameter templates)

### 4.4 Storage

Property graph database (Neo4j or Apache AGE) with OWL/RDF overlay. Key indexes:
- Node type nodes: vector index (semantic matching)
- SOP templates: subgraph structure index (subgraph isomorphism retrieval)
- Capability nodes: keyword + vector dual index

## 5. Ontology-Grounded Retrieval & Assembly

### 5.1 Query -> Intent Atoms

```
Input:  "Check Sarah's MR, if code has issues ask her to fix, notify PM when done"

Step 1: LLM extracts intent atoms (NOT sub-tasks, but capability requirement signals)
        -> {code_review, request_fix_update, status_notification}
        Each intent atom carries:
          - capability_vector: semantic embedding
          - target_service_hints: ["GitLab", "RocketChat"]
          - role_hints: ["SDE", "PM"]
          - expected_artifacts:                          # NEW: what data this intent produces/consumes
              code_review:         produces MR_review_result
              request_fix_update:  consumes MR_review_result, produces fix_commit
              status_notification: consumes final_result, produces notification_sent
          - execution_mode_hint: AUTOMATED | INTERACTIVE | APPROVAL | EITHER
              code_review:         AUTOMATED
              request_fix_update:  INTERACTIVE           # "ask Sarah" = interaction point
              status_notification: INTERACTIVE
          - target_actor_hint:
              request_fix_update:  Developer
              status_notification: Manager

Step 2: Intent atoms -> ontology capability node matching
        code_review           -> CodeReview-Agent [execution_mode: AUTOMATED]
        request_fix_update    -> InteractionNode(RequestInfo, target_role=Developer, channel=RocketChat)
                                 # NOT BugFix-Agent! This is a request/response interaction point.
        status_notification   -> InteractionNode(Notify, target_role=Manager, channel=RocketChat)

Step 3: Iterative intent detection
        # "if code has issues ask her to fix" implies a review-request-review loop
        # -> Wrap {code_review, request_fix_update} into a CompoundNode candidate
        compound_candidates = detect_iterative_patterns(intent_atoms)
        # Uses ontology rules: if intent A produces artifact X consumed by intent B,
        # and B yields an external response or readiness signal that re-triggers A,
        # classify as an iterative interaction pattern
```

Intent atoms are capability requirement signals with artifact type hints and execution-mode constraints, enabling correct mapping to automated vs interaction nodes.

### 5.2 Three-Level Subgraph Retrieval

**Level 1: Execution Node Retrieval (mode-aware)**
```
FOR each intent_atom IN intent_atoms:
    IF intent_atom.execution_mode_hint == AUTOMATED:
        search_types = AutomatedNode subtypes
    ELIF intent_atom.execution_mode_hint == INTERACTIVE:
        search_types = [RequestInfo, Notify, Escalate]
    ELIF intent_atom.execution_mode_hint == APPROVAL:
        search_types = [ApprovalGate]
    ELSE:  # EITHER
        search_types = AutomatedNode subtypes + InteractionNode subtypes

    candidate_nodes = KG.semantic_search(
        node_type IN search_types,
        query_vector = intent_atom.capability_vector,
        filters = {
            # For AutomatedNode: match requiredTools
            # For InteractionNode: match channelPreference and targetActorRole
            access_binding intersect intent_atom.target_service_hints,
            target_role ~= intent_atom.target_actor_hint when present
        },
        top_k = 3
    )
```

**Level 2: SOP Template Matching**
```
candidate_patterns = KG.subgraph_search(
    query_capabilities = {atom.capability_vector for atom in intent_atoms},
    scoring = coverage_score(pattern, intent_atoms) * pattern.confidence,
    top_k = 5
)
```

**Level 3: Edge Relation Inference (with Contract Compatibility)**
```
FOR each pair (node_i, node_j) IN candidate_nodes:
    # Structural score (same as before)
    struct_score = ontology_relation_score(node_i.type, node_j.type)
                   + historical_co_occurrence(node_i, node_j)
                   + access_dependency(node_i, node_j)

    # NEW: Contract compatibility score
    # Check if node_i's output_artifacts can satisfy node_j's input_artifacts
    compatible_artifacts = node_i.output_artifacts INTERSECT node_j.input_artifacts (by type)
    contract_score = |compatible_artifacts| / |node_j.required_input_artifacts|

    edge_score = struct_score + w_contract * contract_score
    IF edge_score > threshold AND contract_score > 0:  # Must have at least one compatible artifact
        add_edge(node_i, node_j,
                 weight=edge_score,
                 artifacts_passed=compatible_artifacts)
```

### 5.3 Initial DAG Assembly

```
Algorithm: OntologyGroundedAssembly

Input: intent_atoms, candidate_nodes, candidate_patterns, inferred_edges,
       compound_candidates (from iterative pattern detection)
Output: initial_DAG G0 (hierarchical DAG: outer DAG is acyclic, compound nodes have internal FSMs)

1. # Wrap iterative intent groups into compound nodes
   FOR each group IN compound_candidates:
       compound = create_compound_node(group.intents, group.nodes)
       replace intent_atoms and candidate_nodes accordingly

2. IF best_pattern.coverage >= coverage_threshold (e.g., 0.7):
     G0 = instantiate(best_pattern.template_graph)
     uncovered = intent_atoms - covered_by(best_pattern)
     FOR atom IN uncovered:
         node = best_matching_node(atom)
         attach_to_graph(G0, node, inferred_edges)

3. ELSE:
     G0 = build_DAG(candidate_nodes, inferred_edges)

4. # Inject source/sink nodes BEFORE contract validation
   # The source node provides query-derived and environment artifacts
   # (e.g., mr_url from query context, service credentials from env).
   # Without this, entry nodes would fail validation because their
   # required inputs have no upstream provider yet.
   source_node = QuerySourceNode(
       output_artifacts = extract_artifacts_from_query(query, intent_atoms)
       # e.g., [{name: "mr_url", type: "URL", value: "gitlab.com/..."},
       #        {name: "target_user", type: "UserID", value: "sarah"}]
   )
   sink_node = ResultSinkNode(
       input_artifacts = expected_final_outputs(intent_atoms)
   )
   add_source_sink(G0, source_node, sink_node)
   # Connect source_node to all entry nodes (nodes with no incoming edges)
   # Connect all exit nodes (nodes with no outgoing edges) to sink_node

5. # Validate contracts (after source/sink injection)
   FOR each edge IN G0.edges:
       assert edge.artifacts_passed is subset of edge.from_node.output_artifacts
       assert edge.artifacts_passed satisfies edge.to_node.input_artifacts
   FOR each node IN G0.nodes:
       assert all node.required_input_artifacts are provided by incoming edges
       # Now entry nodes' inputs are provided by source_node -> valid

6. # Validate ontology constraints
   validate_ontology_constraints(G0)
   assert G0.outer_graph is acyclic  # cycles only allowed inside compound nodes

7. RETURN G0
```

## 6. Constraint-Aware Graph Micro-Evolution

### 6.1 Design Rationale

Unlike EvoMAS's global evolution, we evolve **locally in the neighborhood of the retrieval-initialized DAG**. The initial DAG is already a reasonable starting point (from historical patterns in KG). Evolution handles:
- Imperfect retrieval (coverage < 1.0)
- Task-specific constraints unseen in historical templates
- Selection among multiple candidate templates

### 6.2 Mutation Operators (Ontology-Constrained)

All operators preserve the hierarchical DAG invariant: outer graph must remain acyclic; compound nodes are treated as atomic units during outer-graph mutations.

```
M1: NodeAdd(G, node_type)
    Constraint: node_type.requiredTools subset of available_services
    Constraint: new node's input_artifacts must be satisfiable by existing nodes' outputs

M2: NodeRemove(G, node_id)
    Constraint: Cannot remove the only node providing a required capability
    Constraint: Removing node must not leave downstream nodes with unsatisfied input_artifacts

M3: NodeReplace(G, node_id, new_type)
    Constraint: new_type must be execution-mode-compatible sibling/parent/child in ontology hierarchy
    Constraint: new_type's input/output artifact types must be compatible with connected edges

M4: EdgeAdd(G, src, dst, artifacts_passed)
    Constraint: src and dst must have an ontology relation path
    Constraint: artifacts_passed must be subset of src.output_artifacts
    Constraint: adding edge must not create a cycle in outer graph
    Constraint: artifacts_passed types must match dst.input_artifacts types

M5: EdgeRemove(G, edge_id)
    Constraint: G must remain a connected DAG after removal
    Constraint: Removal must not leave dst node with unsatisfied required input_artifacts

M6: PromptMutate(G, node_id, new_prompt_fragment)
    Constraint: Mutated prompt must still match node type's capability description
    Note: Only applicable to LLM-backed nodes (not SystemNode)

M7: CompoundNodeMutate(G, compound_node_id, fsm_change)    # NEW
    Modify a compound node's internal FSM:
      - Add/remove internal state
      - Change transition conditions
      - Change max_iterations
      - Replace internal node type (within execution-mode-compatible ontology hierarchy)
    Constraint: Modified FSM must still guarantee termination (max_iterations > 0)
    Constraint: Internal node contracts must remain consistent
```

### 6.3 Crossover Operator

```
C1: SubgraphSwap(G1, G2, subgraph_boundary)
    Find functionally equivalent subgraphs (covering same intent atom subsets)
    Swap between two candidate DAGs
    Constraint: Both resulting graphs must satisfy ontology constraints
```

### 6.4 Proxy Fitness Function (with Contract Validation)

```
FitnessFunction(G, query, intent_atoms):

    F1: Intent coverage (0-1)
        coverage = |covered_intent_atoms(G)| / |intent_atoms|

    F2: Ontology consistency (0-1)
        consistency = ontology_constraint_satisfaction(G)

    F3: Structural efficiency (0-1)
        efficiency = 1 - (|edges(G)| - |nodes(G)| + 1) / max_possible_edges

    F4: Historical success rate
        historical = avg_success_rate(similar_patterns_in_KG(G))

    F5: (Optional) LLM quick judge
        llm_score = llm_quick_judge(G, query)  # 1 LLM call, no execution

    F6: Contract compatibility (0-1)                    # NEW
        # Verify all edges have valid artifact flow and all nodes' inputs are satisfied
        satisfied_nodes = count(n for n in G.nodes
                                if all required input_artifacts are provided by incoming edges)
        contract_compat = satisfied_nodes / |G.nodes|

    F7: Execution-mode correctness (0-1)               # NEW
        # Verify automated intents map to AutomatedNode,
        # interactive intents map to InteractionNode,
        # approval intents map to ApprovalGate
        aligned_pairs = align_nodes_to_intents(G, intent_atoms)
        mode_correct = count((n, a) for (n, a) in aligned_pairs
                             if n.execution_mode satisfies a.execution_mode_hint)
        mode_score = mode_correct / |aligned_pairs|

    RETURN w1*F1 + w2*F2 + w3*F3 + w4*F4 + w5*F5 + w6*F6 + w7*F7
```

### 6.5 Micro-Evolution Loop

```
Algorithm: GraphMicroEvolution

Input: G0 (initial DAG), query, intent_atoms
Output: G* (optimized DAG)
Params: population_size=5, max_generations=3, mutation_rate=0.3

1. population = [G0] + [mutate(G0) for _ in range(population_size - 1)]
2. FOR gen IN 1..max_generations:
     a. scores = [Fitness(G) for G in population]
     b. parents = top_k(population, k=2, by=scores)
     c. children = [SubgraphSwap(p1, p2) for p1,p2 in pairs(parents)]
     d. children = [apply_random_mutation(c) for c in children if rand() < mutation_rate]
     e. # Validate: outer DAG acyclic + contracts consistent + ontology valid
        children = [c for c in children
                    if is_acyclic(c.outer_graph)
                    and contracts_satisfied(c)
                    and ontology_valid(c)]
     f. population = parents + children
     g. IF convergence_detected(scores): BREAK
3. RETURN argmax(population, key=Fitness)
```

### 6.6 Periodic Full-Execution Calibration

Proxy fitness may systematically diverge from real execution outcomes. To prevent this:

```
Algorithm: ProxyCalibration

Params: calibration_interval=20 (every 20 proxy evaluations, do 1 full execution)

Maintain: calibration_buffer = []

After each full execution:
    proxy_score = Fitness(G)
    real_score = full_execution_score(G)
    calibration_buffer.append((proxy_score, real_score))

    IF len(calibration_buffer) >= 10:
        # Compute calibration factor per fitness component
        FOR each F_i IN {F1..F7}:
            correlation_i = pearson(F_i_scores, real_scores)
            IF correlation_i < 0.3:
                # This fitness component is misleading, reduce its weight
                w_i *= 0.8
            ELIF correlation_i > 0.7:
                # This component is predictive, increase its weight
                w_i *= 1.1
        normalize(w1..w7)  # Keep weights summing to 1
```

Key difference from EvoMAS: population=5 vs 8, generations=3 vs 10+, proxy fitness with calibration vs full execution every time. Orders of magnitude faster with drift correction.

## 7. Three-Phase Lifecycle & Cold Start

### Phase 0: Bootstrap (Seed Pool Initialization)

```
Step 1: Prepare seed queries
    Sources: TheAgentCompany 175 task descriptions, manual templates,
             LLM-generated diverse queries from T-Box

Step 2: LLM generates candidate DAGs
    FOR each query:
        Generate K=5 candidate DAGs with increasing temperature
        Filter by ontology validity

Step 3: Evaluate and filter
    With execution environment: execute and evaluate, keep best
    Without: use proxy fitness, keep top 2 per query
    Abstract each to SOP pattern, add to KG A-Box (confidence=0.5)
```

### Phase 1: Self-Evolution (No Human Runtime)

```
FOR each incoming query:
    1. Retrieval + Assembly -> G0 (using Phase 0 seed patterns)
    2. Micro-Evolution -> G*
    3. Execute G* -> result (with per-node checkpoint tracking)
    4. Outcome-Grounded Credit Assignment (NEW):

       # Step 4a: Classify failure type
       IF execution failed:
           failure_type = classify_failure(execution_log):
             STRUCTURE_ERROR:     DAG topology itself is wrong (missing node, wrong edge)
             PROMPT_ERROR:        A specific node's prompt is inadequate for this task
             TOOL_ERROR:          Tool/API call failed (timeout, auth, rate limit)
             ENVIRONMENT_ERROR:   Service unavailable, network issue
             INTERACTION_ERROR:   External interaction failed (no response, malformed response, timeout)
             CONTRACT_ERROR:      Artifact type mismatch at runtime (NEW)

       # Step 4b: Node-level attribution
       FOR each node IN G*:
           node.execution_status = checkpoint_results.get(node.checkpoint_id)
           # Map checkpoints to the specific node that was responsible

       failed_nodes = [n for n in G* if not n.execution_status.success]
       passed_nodes = [n for n in G* if n.execution_status.success]

       # Step 4c: Differentiated feedback (NOT blanket pattern update)
       IF failure_type == STRUCTURE_ERROR:
           weaken_pattern(matched_pattern, delta=-0.1)       # Pattern structure is wrong
       ELIF failure_type == PROMPT_ERROR:
           FOR node IN failed_nodes:
               mark_prompt_issue(node.type, node.prompt)     # Don't blame the pattern
               trigger PromptMutate for next evolution round
       ELIF failure_type in {TOOL_ERROR, ENVIRONMENT_ERROR}:
           # Do NOT weaken pattern — failure is external
           log_external_failure(node, failure_type)
       ELIF failure_type == INTERACTION_ERROR:
           log_interaction_issue(node, failure_details)       # May need simulator/NPC tuning
       ELIF failure_type == CONTRACT_ERROR:
           weaken_pattern(matched_pattern, delta=-0.05)       # Mild penalty
           log_contract_mismatch(edge, expected_type, actual_type)

       # Step 4d: Strengthen what worked
       FOR node IN passed_nodes:
           strengthen_node_pattern(node.type, node.prompt, delta=+0.03)

       # Step 4e: Novel pattern distillation (unchanged)
       IF execution_success AND structural_diff(G*, matched_pattern) > novelty_threshold:
           new_pattern = abstract_to_sop_pattern(G*, query)
           new_pattern.origin = "self_evolution"
           KG.A_Box.add(new_pattern)
```

### Phase 2: Human-in-the-Loop (After UI Deployment)

```
FOR each incoming query:
    1-3. Same as Phase 1
    4. Display DAG on UI for human review
    5. Human edits (add/modify/delete nodes/edges)
    6. Record GraphDelta operations
    7. DeltaDistillation: cluster similar deltas -> abstract to SOP patterns -> write back KG
```

### Seed Pool vs EvoMAS Initial Population

| Dimension | EvoMAS | OntoPlan |
|-----------|--------|----------|
| Source | Human-designed MAS configs | LLM generates under ontology constraints |
| Storage | In-memory candidate list | KG SOP patterns (persistent, retrievable) |
| Cross-task reuse | Experience memory (text summary) | Subgraph template matching (structural) |
| Growth | Per-task independent evolution | Cumulative: new patterns continuously added |

## 8. Human Knowledge Distillation

### 8.1 Edit Operations Formalized as Graph Deltas

```
GraphDelta:
  operation: ADD_NODE | REMOVE_NODE | REPLACE_NODE | ADD_EDGE |
             REMOVE_EDGE | MODIFY_PROMPT | REORDER
  target: node_id | edge_id
  params: {type, prompt, tool, ...}
  context:
    query: "original query text"
    original_dag: G_before
    timestamp: ...
    user_id: ...
    reason: "optional user-provided edit reason"
```

### 8.2 Delta -> SOP Pattern Distillation

```
Algorithm: DeltaDistillation

Phase 1: Cluster similar deltas
    Similarity = same operation type + same/close agent types (ontology distance)

Phase 2: Pattern abstraction (per cluster, min_support >= 3)
    Extract maximal common subgraph from resulting DAGs
    Generalize concrete instances to type variables
    Extract trigger conditions from query texts

Phase 3: KG write-back
    If similar pattern exists: update confidence and usage stats
    Else: create new SOP pattern (origin="human_edit")

Phase 4: Ontology evolution (low-frequency)
    If new patterns involve agent type combinations absent from T-Box
    -> suggest ontology extension to admin
```

### 8.3 Confidence Decay and Reinforcement (with Differentiated Attribution)

Pattern-level confidence is only updated when the cause is structural. Node-level and prompt-level issues are tracked separately.

```
# Pattern-level (structure): only affected by STRUCTURE_ERROR or CONTRACT_ERROR
Retrieved + execution success:                   pattern.confidence += 0.05 * success_rate
Retrieved + STRUCTURE_ERROR:                      pattern.confidence -= 0.10
Retrieved + CONTRACT_ERROR:                       pattern.confidence -= 0.05
Retrieved + PROMPT/TOOL/ENV/INTERACTION_ERROR:    pattern.confidence unchanged (not pattern's fault)
Not retrieved for long:                           pattern.confidence *= 0.995^days_since_last_use
Below deprecation threshold (0.2):                mark deprecated (excluded from retrieval)

# Node-type-level (tracked per node type in ontology):
Node execution success:                           node_type.reliability += 0.03
Node PROMPT_ERROR:                                node_type.prompt_failure_count += 1
                                                  # If prompt_failure_count > threshold:
                                                  # flag node type for prompt redesign

# Edge-level (tracked per artifact type pair):
Edge contract match at runtime:                   artifact_flow.reliability += 0.02
Edge CONTRACT_ERROR:                              artifact_flow.reliability -= 0.1
                                                  # If reliability < threshold:
                                                  # flag this artifact type pairing as unreliable
```

This three-level attribution prevents the "popular but wrong template gets reinforced" failure mode identified in review.

### 8.4 Flywheel Effect

```
First use:  Query -> KG retrieval (no match) -> free assembly -> heavy human edit -> distill new pattern
Nth use:    Query -> KG retrieval (high match) -> template assembly -> minor tweak / approve directly
```

## 9. Novelty Summary

| # | Novelty | vs EvoMAS | vs CodeAgents | vs AdaptOrch | vs MAS-GPT |
|---|---------|-----------|---------------|-------------|------------|
| N1 | **Hierarchical DAG**: outer acyclic graph + compound nodes with internal FSMs for iterative processes | YAML config (flat) | Pseudocode | Task dep graph -> 4 topologies | Executable code |
| N2 | Ontology-constrained search space | Unconstrained | None | Rule thresholds | None |
| N3 | Retrieval seeding + micro-evolution | Global evolution | No search | Rule routing | Fine-tuning |
| N4 | SOP subgraph templates with typed artifact contracts | Text experience memory | None | None | Fine-tuned params |
| N5 | Three-phase knowledge accumulation | Single evolution | No accumulation | Stateless | Fine-tuning dependent |
| N6 | Human edit distillation loop | None | None | None | None |
| N7 | Proxy fitness with periodic full-execution calibration | Full execution | None | Rules (no eval) | Single generation |
| N8 | **Interaction-native node types**: AutomatedNode / InteractionNode / ApprovalGate model collaboration points without requiring runtime human executors | No interaction distinction | No interaction distinction | No interaction distinction | No interaction distinction |
| N9 | **Outcome-grounded credit assignment**: node-level attribution + failure type classification prevents wrong pattern reinforcement | DAG-level only | None | None | None |

## 10. Experiment Design

### 10.1 Main Experiment

- **Datasets:** TheAgentCompany (175 tasks) + self-built enterprise scenarios
- **Baselines:** EvoMAS, AdaptOrch, MAS-GPT, fixed topologies (Sequential/Parallel/Hierarchical)
- **Metrics:** Task success rate, token consumption, orchestration generation time

### 10.2 Ablation Study

- w/o ontology constraints (unconstrained evolution)
- w/o retrieval seeding (pure evolution vs retrieval + evolution)
- w/o micro-evolution (pure retrieval assembly)
- w/o human feedback (Phase 1 only vs Phase 2)
- w/o compound nodes (flat DAG only, iterative tasks excluded or linearized)
- w/o artifact contracts (bare edges without type checking)
- w/o node-level credit assignment (DAG-level only, as in original design)
- w/o proxy calibration (proxy fitness only, no periodic full-execution correction)

### 10.3 Knowledge Accumulation Experiment

Longitudinal study showing KG growth curve and system performance improvement over time.

### 10.4 Case Study

Visualize orchestration generation process for representative queries across different task categories (SDE, PM, HR, Finance).

---

## Appendix: Comparison Matrix

```
                    EvoMAS    CodeAgents   AdaptOrch    MAS-GPT    OntoPlan
Representation      YAML      Pseudocode   Task DAG     Code       Hierarchical DAG
                    (flat)    (flat)       (flat)       (flat)     (DAG + compound FSM)
Generation          Global    LLM single   Rule route   LLM+FT    Retrieve+Evolve
                    evolution pass         4 topologies
Knowledge           Text      None         None         FT params  KG (explicit,
accumulation        memory                                         structured)
Human feedback      No        No           No           No         Edit distillation
Search space        Full      N/A          4 templates  N/A        Ontology-constrained
Fitness eval        Full exec N/A          Rules        N/A        Proxy + calibration
Cross-task reuse    Weak      None         None         Via FT     Subgraph templates
Artifact contracts  No        No           No           No         Typed I/O + pre/post
Interaction types   No        No           No           No         Automated/Interactive/Approval
Credit assignment   DAG-level N/A          N/A          N/A        Node-level + failure
                                                                   type classification
```

## Appendix B: Review Change Log

### Rev 2 (2026-03-11) — Post Codex Review

**Issue 1 (High): DAG cycle in SOP template**
- Root cause: `?reviewer -> ?fixer -> ?reviewer` back-edge violates DAG constraint
- Fix: Introduced **compound nodes** with internal FSMs. Outer graph is strict DAG; iterative processes (review-fix loops) are encapsulated inside compound nodes with bounded termination (`max_iterations`, `timeout`).
- Affected sections: 2, 4.1, 4.2, 5.3, 6.2 (added M7), 6.5

**Issue 2 (High): Missing data/artifact contracts and actor semantics**
- Root cause: Edges had no artifact type information; intent atoms had no I/O; "ask Sarah to fix" was mapped to BugFix-Agent instead of human delegation.
- Fix: Added **NodeContract** (input/output artifacts, pre/postconditions), **EdgeContract** (typed artifact routing), **Actor type hierarchy** (AI-Agent / Human-Actor / Delegation-Agent). Updated intent atom extraction to include `expected_artifacts` and `actor_hint`.
- Affected sections: 4.1 (major rewrite), 4.2, 5.1, 5.2 Level 3, 5.3, 6.2, 6.4 (F6, F7)

**Issue 3 (Medium-High): Proxy fitness lacks outcome-grounded credit assignment**
- Root cause: Blanket pattern strengthen/weaken couldn't distinguish structure error from prompt/tool/environment error. Popular-but-wrong templates could get reinforced.
- Fix: Added **failure type classification** (6 types), **node-level attribution**, **three-level confidence tracking** (pattern / node-type / edge), **periodic full-execution calibration** for proxy fitness weights.
- Affected sections: 6.4, 6.6 (new), 7 Phase 1, 8.3

### Rev 3 (2026-03-11) — Post Codex Review Round 2

**Issue 4 (High): Actor-aware ontology not propagated to retrieval layer**
- Root cause: T-Box top-level changed to `Actor` hierarchy, but retrieval still used `node_type = "Agent"`, core relations still said `Agent --usesTool--> Tool`, and `Notifier` was inconsistently typed as `Coordinator-Agent / AI_AGENT` despite belonging to `Delegation-Agent` in ontology.
- Fix: (a) Core relations rewritten to be actor-aware: `AI-Agent --usesTool-->`, `Delegation-Agent --communicatesVia-->`, `Human-Actor --reachableVia-->`. (b) Level 1 retrieval rewritten to filter by `actor_hint` and search correct actor subtypes. (c) `?notifier` in SOP template and intent atom mapping both corrected to `Delegation-Agent(Notifier)` with `actor_type: DELEGATION_AGENT`.
- Affected sections: 4.1 (core relations), 4.2 (SOP template ?notifier), 5.1 (intent mapping), 5.2 Level 1

**Issue 5 (Medium-High): Contract validation ordering — source artifacts rejected**
- Root cause: Assembly algorithm validated contracts (step 4) before injecting source/sink nodes (step 6). Entry nodes whose `required_input_artifacts` come from the query/context (e.g., `mr_url`) would fail validation because no upstream node provides them yet.
- Fix: Introduced explicit `QuerySourceNode` (carries query-derived artifacts) and `ResultSinkNode`. Source/sink injection moved to step 4 (before validation). Contract validation moved to step 5 (after injection). Entry nodes now correctly receive their inputs from `QuerySourceNode` edges.
- Affected sections: 5.3 (assembly algorithm reordered)

### Rev 4 (2026-03-11) — Interaction-Centric Benchmark Modeling

**Issue 6 (High): Runtime human-execution semantics make paper evaluation ambiguous**
- Root cause: The prior design modeled `Human-Actor` / `Delegation-Agent` as runtime ontology entities, which blurs the boundary between "the system contacts someone" and "a human becomes an executable node". That is awkward for benchmark evaluation, where real humans should not be required in the main loop.
- Fix: Replaced runtime actor modeling with **execution-mode-aware nodes**: `AutomatedNode`, `InteractionNode`, `ApprovalGate`, and `SystemNode`. External collaborators are now represented as `TargetActorRole` metadata on interaction nodes, not as executable graph nodes.
- Affected sections: 2, 4.1, 4.2, 5.1, 5.2, 6.2, 6.4, 7 Phase 1, 8.3, 9, Appendix

**Issue 7 (Medium): `actor_hint` was too coarse and entangled ontology with retrieval routing**
- Root cause: `actor_hint` mixed "who is involved" with "how the system should execute this intent", which made cross-domain orchestration brittle and retrieval logic hard to keep consistent.
- Fix: Renamed it to `execution_mode_hint` with values `{AUTOMATED, INTERACTIVE, APPROVAL, EITHER}` and updated retrieval plus fitness scoring to operate on execution mode rather than runtime actor family.
- Affected sections: 5.1, 5.2 Level 1, 6.4
