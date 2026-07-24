# CAIRN 

CAIRN is an evaluation framework for attention mechanisms.

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

4. **Run the full evaluation** (all metrics, insect/poison experiment):
   ```bash
   ../PeTTa/run.sh mve.metta
   ```
   Results: `output/mve/metrics.csv`, `output/mve/trends.csv` , `output/mve/summary.json`

5. **Run the assignment** (mve.metta's pipeline/params against the real insects-100+poisons-50 corpus from `data/sentences/`, after step 4):
   ```bash
   ../PeTTa/run.sh assignment.metta
   ```
   Results: `output/benchmark/metrics.csv`, `output/benchmark/trends.csv`, `output/benchmark/summary.json`

### Watching a run live

Opt-in, best-effort: auto-launches the dashboard (`http://localhost:8501`) and opens a browser tab.

```bash
CAIRN_WATCH=1 ../PeTTa/run.sh mve.metta
# or, with environment.sh aliases:
cairn-mve --watch
```

Manual launch: `streamlit run dashboard/app.py`.

## Project Structure

- **`demo.metta`** – Sanity check: main resource/effectiveness/topology metrics only
- **`mve.metta`** – Full CAIRN/SYNAPSE-style pipeline (resource, effectiveness local+global, assessment, audit, probe)
- **`assignment.metta`** – Same pipeline as mve on `data/sentences/` (insects-100 + poisons-50); Phase VIII gained-efficiency vs mve baseline
- **`evaluation/`** – Metric modules: resource, effectiveness, assessment, audit, probe, benchmark
- **`tools/`** – Utilities: statistics (scipy), graph algorithms (networkx), CIP snapshots, time-series recording
- **`data/`** – Sentence corpora (`.sent`), ECAN parameter presets, reference files
- **`dev-tests/`** – Unit tests for CAIRN internals

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
