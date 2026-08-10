# CAIRN

CAIRN instruments ECAN attention state (AF, STI/LTI, Hebbian structure) at CIP boundaries and reports closed-form resource, effectiveness, and trajectory metrics.

## Prerequisites

CAIRN requires these repos cloned as siblings:
```
dev-env/
  ├── hyperon-experimental/
  ├── PeTTa/
  ├── metta-attention/
  └── CAIRN/
```

### Required Software
- **SWI-Prolog ≥ 9.3** with Janus (Python bridge) — see [PeTTa README](../PeTTa/README.md)
- **Python** matching Janus's linked version — `setup.sh` detects this automatically

## Quick Start

1. **Clone CAIRN** (alongside the other repos):
   ```bash
   git clone <cairn-repo-url>
   cd CAIRN
   ```

2. **Run setup** (detects the correct Python, creates venv, installs deps):
   ```bash
   bash setup.sh
   ```

3. **Activate the virtual environment** (for future shells):
   ```bash
   source venv/bin/activate
   ```

### Experiment progression

```text
demo  →  mve  →  assignment      structural CIP (insect/poison metrics)
              ↘  mve_bridge      cognitive synergy (export mve AF → PLN steering)
```

4. **demo** (smoke / resource + effectiveness):
   ```bash
   ../PeTTa/run.sh demo.metta          # or: cairn-demo
   ```

5. **mve** (full structural metric set — **no bridge**):
   ```bash
   ../PeTTa/run.sh mve.metta           # or: cairn-mve
   ```
   Results: `output/mve/{metrics.csv,trends.csv,summary.json}`

6. **Then either:**

   **A. assignment** (same pipeline on insects-100+poisons-50; vs mve baseline):
   ```bash
   ../PeTTa/run.sh assignment.metta    # or: cairn-assignment
   ```
   Results: `output/benchmark/…` — pure CIP, no bridge.

   **B. Coupled workshop B2** (end-of-run; dump once → offline grid):
   ```bash
   python bridge/mve_bridge.py --export-only          # mve + snapshot only
   python bridge/mve_bridge.py --offline-grid \
     --modes freeze-f,re-dynamics --focus-caps 6,12 --budgets 5,10,20
   # one-shot: python bridge/mve_bridge.py
   ```
   Same three-arm kernel as B3 (`bridge/coupled.py`).  
   Results: `output/mve/bridge_snapshot.json` +  
   `from_mve_{ff|rd}_k{K}_b{B}/` + `ablations/from_mve/`

7. **Scenario suite** (roman **or** slice; not CIP):
   ```bash
   python bridge/run_bridge.py suite --map slice --budgets 5,10,20
   python bridge/run_bridge.py roman --budgets 5,10,20
   python bridge/run_bridge.py feedback --map roman --budget 10
   ```
   Results: `output/cognitive_synergy/{roman,slice}_b{B}/`, `feedback_{map}_b{B}/`

8. **Coupled workshop B3** (mid-run CIP; B4 = closed loop):
   ```bash
   # export snapshots once, then offline k×B grid (no mve replay)
   python bridge/mve_pln_probe.py --export-only --every 2
   python bridge/mve_pln_probe.py --offline-grid --focus-caps 6,12 --budgets 5,10,20
   # live single k,B:  python bridge/mve_pln_probe.py --every 2 --focus-cap 12 --budget 10
   # B4: --closed-loop --wage 200  (live only)
   ```
   Results: `output/mve/probes/cip_*.json`,  
   `from_mve_cip{i}_ff_k{K}_b{B}/`, `mve_pln_probe/protocol_probes.csv`

### Watching a run live

Opt-in, best-effort: auto-launches the dashboard (`http://localhost:8501`) and opens a browser tab.

```bash
CAIRN_WATCH=1 ../PeTTa/run.sh mve.metta
# or, with environment.sh aliases:
cairn-mve --watch
```

Manual launch: `streamlit run dashboard/app.py`.

Dashboard **surfaces** (sidebar radio — never mixed in one chart):

- **Structural CIP** — `output/{demo,mve,benchmark}/`
- **Cognitive synergy** — `output/cognitive_synergy/<scenario>/`

Inventory: `python tools/write_output_index.py` → `output/index.json`.

## Project Structure

- **`demo.metta`** – CIP smoke: resource, effectiveness, topology
- **`mve.metta`** – Full structural CIP metrics (no bridge)
- **`assignment.metta`** – CIP corpus benchmark vs mve (no bridge)
- **`cognitive_synergy.metta`** – Coupled entry → `mve_bridge.run` (defaults)
- **`bridge/coupled.py`** – shared B2/B3 workshop kernel (defaults, naming, arm fields)
- **`bridge/mve_bridge.py`** – B2 end-of-run / offline grid
- **`bridge/mve_pln_probe.py`** / **`cip_probe.py`** – B3 mid-run schedule / B4 wage
- **`bridge/`** – ECAN–PLN protocols, scenarios, `run_bridge.py`
- **`evaluation/`** – Structural metric modules only (resource, effectiveness, …)
- **`tools/`** – CIP helpers; `bridge_export.metta` loaded only by mve_bridge tail
- **`data/`** – Sentence corpora (`.sent`), ECAN parameter presets
- **`dev-tests/`** – Unit tests for CAIRN internals
- **`references/main.tex`** – Formula and pseudocode specs

## Architecture

CAIRN runs on **PeTTa** (`../PeTTa/run.sh`), importing the full **metta-attention** agent stack and knowledge graph:

```metta
; Core API
!(import! &self ../metta-attention/attention-bank/attention-value/getter-and-setter)
!(import! &self ../metta-attention/attention-bank/bank/attention-bank)

; Agents
!(import! &self ../metta-attention/attention/ImportanceDiffusionAgent/AFImportanceDiffusionAgent/AFImportanceDiffusionAgent)
!(import! &self ../metta-attention/attention/HebbianCreationAgent/HebbianCreationAgent)

; Knowledge graph (fast load via pre-compiled .qlf)
!(import! &self (library lib_import))
!(static-import! &incident ../metta-attention/experiments/data/kg)
```

Three polyfills bridge hyperon builtins not available in PeTTa: `match-count`, `find`, `unify`.

Python graph algorithms (`tools/utils.py`) delegate to networkx and scipy via PeTTa's Janus bridge (`py-call`).

**Unit tests**:
   ```bash
   ../PeTTa/run.sh dev-tests/test_regression.metta
   ../PeTTa/run.sh dev-tests/test_resource.metta
   ../PeTTa/run.sh dev-tests/test_utils_py.metta
   ...
   ```

## Troubleshooting

**`ModuleNotFoundError` for installed packages (networkx, etc.)**

SWI-Prolog's Janus embeds a specific Python version. If the venv was built with a different Python, Janus can't find the installed packages. Fix:

```bash
bash setup.sh --rebuild
source venv/bin/activate
```

To check which Python Janus uses:
```bash
swipl -g "use_module(library(janus)), py_call(sys:version, V), writeln(V), halt"
```

**Slow knowledge graph loading**

The demo uses `static-import!` which loads a pre-compiled `.qlf` file. If the `.qlf` is missing, PeTTa generates it from the `.metta` source on first run (slow), then caches it for subsequent runs.
