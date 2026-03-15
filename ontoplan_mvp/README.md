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

---

## TheAgentCompany Evaluation

OntoPlan replaces the original single-agent runner with a DAG-based multi-node executor.
The entry point is `evaluation/run_eval_orchestrated.py`.

### Prerequisites

- Python >= 3.12 (conda env `TAC` recommended)
- `openhands-ai==0.42.0` installed (`pip install openhands-ai==0.42.0`)
- Docker with `buildx` support
- `config.toml` at the project root (see below)

### config.toml

Create `config.toml` at the project root (already gitignored):

```toml
[core]
workspace_base = "/tmp/openhands_workspace"

[llm.llm]
model = "deepseek-ai/DeepSeek-V3.2"
api_key = "YOUR_API_KEY"
base_url = "http://YOUR_ENDPOINT/v1/"
```

`--agent-llm-config llm` maps to the `[llm.llm]` section.
You can define multiple sections (e.g. `[llm.strong]`, `[llm.fast]`) and reference them by name.

### Image naming convention

Task images follow the pattern: `ghcr.io/theagentcompany/{task_name}-image:1.0.0`

Note the `-image` suffix — e.g. `sde-add-all-repos-to-docs-image`, not `sde-add-all-repos-to-docs`.

### macOS (Docker Desktop)

```bash
# 1. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
#    and start it (whale icon in menu bar)

# 2. Enable host networking (REQUIRED — otherwise runtime gets 502 Bad Gateway)
#    Docker Desktop → Settings → Resources → Network → Enable host networking → Apply & restart
#    Requires Docker Desktop 4.29+. Check version: docker version --format '{{.Server.Version}}'

# 3. Log in to ghcr.io (GitHub token with read:packages scope)
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# 4. Pull the task image
docker pull ghcr.io/theagentcompany/sde-add-all-repos-to-docs-image:1.0.0

# 5. Run evaluation (from project root)
conda activate TAC
PYTHONPATH=$PWD python evaluation/run_eval_orchestrated.py \
  --task-image-name ghcr.io/theagentcompany/sde-add-all-repos-to-docs-image:1.0.0 \
  --agent-llm-config llm \
  --env-llm-config llm \
  --outputs-path ./outputs/orchestrated
```

> First run builds the OpenHands runtime image (~15 min). Subsequent runs reuse the cache and start in seconds.

### Linux Server (SSH, no UI)

Linux Docker Engine natively supports host networking — no extra configuration needed.

```bash
# 1. Install Docker Engine
curl -fsSL https://get.docker.com | sudo sh

# 2. Add your user to the docker group (skip if running as root)
sudo usermod -aG docker $USER
newgrp docker

# 3. Verify Docker daemon is running
docker info | head -5

# 4. Log in to ghcr.io (GitHub token with read:packages scope)
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# 5. Clone the repo and enter it
git clone https://github.com/YOUR_ORG/TheAgentCompany.git
cd TheAgentCompany

# 6. Create conda environment and install dependencies
conda create -n TAC python=3.13 -y
conda activate TAC
pip install -r requirements.txt

# 7. Create config.toml (see config section above)
cat > config.toml << 'EOF'
[core]
workspace_base = "/tmp/openhands_workspace"

[llm.llm]
model = "deepseek-ai/DeepSeek-V3.2"
api_key = "YOUR_API_KEY"
base_url = "http://YOUR_ENDPOINT/v1/"
EOF

# 8. Pull the task image
docker pull ghcr.io/theagentcompany/sde-add-all-repos-to-docs-image:1.0.0

# 9. Run evaluation inside tmux (SSH sessions drop; tmux keeps it alive)
tmux new -s eval
PYTHONPATH=$PWD python evaluation/run_eval_orchestrated.py \
  --task-image-name ghcr.io/theagentcompany/sde-add-all-repos-to-docs-image:1.0.0 \
  --agent-llm-config llm \
  --env-llm-config llm \
  --outputs-path ./outputs/orchestrated
# Detach from tmux: Ctrl+B then D
# Reattach later:   tmux attach -t eval
```

> **Root account**: If running as root (common on EC2/bare metal), skip the `usermod` step.
> OpenHands recommends root for full filesystem access inside containers.

### Fallback behavior

If OntoPlan planning fails or produces ≤1 executable node, the orchestrator
automatically falls back to the original single-agent runner (`run_solver`).
No manual intervention needed.

### Output files

Results are saved under `--outputs-path`:

| File | Description |
|------|-------------|
| `traj_{task_name}.json` | Merged execution trajectory (all nodes) |
| `eval_{task_name}.json` | Evaluation score |
| `screenshots/` | Browser screenshots per node (if enabled) |
