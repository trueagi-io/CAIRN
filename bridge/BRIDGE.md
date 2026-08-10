# ECAN–PLN bridge

Controlled **cognitive synergy** experiments: attention steers budgeted PLN
(steering) and proofs reweight STI (feedback). 

**Containment:** `CAIRN/bridge/` + `tools/bridge_export.metta` / `tools/cip_probe_hooks.metta`.  
PeTTa / metta-attention / hyperon are **import-only**.

---

## Experiment ladder

```text
STRUCTURAL                          COGNITIVE SYNERGY
demo → mve → assignment             B1  tabulated suite (roman|slice)
                                      B2  coupled workshop — end-of-run / grid
                                      B3  coupled workshop — mid-run CIP schedule
                                      B4  closed-loop wage into live CIP
```

---

## Protocols (all maps)

| Protocol | Arms / flow | Question |
|----------|-------------|----------|
| **steering** | **weighted** / **influenced** / **distracted**, same \(B\) | Does attention-shaped premise selection change solve under fixed PLN steps? |
| **feedback** | One AF-filtered proof → wage proof atoms → one ECAN cycle | Does a successful AF path reweight STI / AF? |

Timing: `PLN.Query` **wall_ms** per arm (or feedback pln), via `pln-query-timed`.  
Still under fixed \(B\) — speed is capped-solver wall time, not unlimited search.

---

## B1 — Tabulated scenarios (`run_bridge.py`)

### Maps

| Map | File | World |
|-----|------|--------|
| **roman** | `scenarios/roman_*.metta` | Tiny dual path \(A\to D\) via B/C |
| **slice** | `scenarios/slice_*.metta` | Hardcoded WordNet-**style** isa (Ant→Insect, …) |

Both are **hard-coded**. Output paths are set by the **driver**.

### Commands

```bash
cd CAIRN && source venv/bin/activate

# Three-arm steering only
python bridge/run_bridge.py roman|slice [options]

# Feedback only (same map family)
python bridge/run_bridge.py feedback --map roman|slice [options]

# One map: steering over budgets, then feedback once per B
python bridge/run_bridge.py suite --map roman|slice [options]
```

Alias: `cairn-bridge-suite` → `suite --map slice` (pass extra flags after if your shell allows; else call `python` explicitly).

### Arguments (B1)

| Argument | Applies to | Default | Meaning |
|----------|------------|---------|---------|
| **`roman` / `slice`** (cmd) | steering | — | Map + **steering** protocol |
| **`feedback`** (cmd) | feedback | — | Feedback protocol; requires **`--map`** (or defaults to slice) |
| **`suite`** (cmd) | both | — | Steering grid then optional feedback on **one** map |
| **`--map roman\|slice`** | `feedback`, `suite` | `slice` | Which tabulated world |
| **`--seed K`** | all | `0` | Fixed RNG seed for **distracted** \(S\) (for reproducibility) |
| **`--budget B`** | all B1 | `10` if neither budget flag set | Single PLN step budget for all arms in that run |
| **`--budgets B1,B2,…`** | all B1 | — | Run **once per B** (wins over single `--budget` when both set—prefer one) |
| **`--no-feedback`** | `suite` only | off | Skip feedback after steering grid |

### What the budget grid does

| Knob | Effect |
|------|--------|
| **`--budgets 5,10,20`** | Separate experiment dirs per \(B\) so results never overwrite. One run per cell. |

### Output layout (B1)

```text
output/cognitive_synergy/
  roman_b10/                 # steering, B=10
    summary.json
    metrics.csv              # one row
  slice_b5/
  slice_b10/
  feedback_roman_b10/        # feedback on roman, B=10
  feedback_slice_b10/
```

### Examples

```bash
# Fast smoke: slice, one budget, then feedback
python bridge/run_bridge.py suite --map slice --budget 10

# Budget sweep + feedback
python bridge/run_bridge.py suite --map slice --budgets 5,10,20

# Roman plumbing only (no feedback)
python bridge/run_bridge.py suite --map roman --budget 10 --no-feedback

# Steering-only budget sweep
python bridge/run_bridge.py slice --budgets 5,10,20
```

### Reading results

| Question | Look at |
|----------|---------|
| Did arms run? | `arms.weighted\|influenced\|distracted.solved` |
| Influenced beats distracted? | `contrast.influenced_beats_distracted` |
| Speed under \(B\) | `arms.*.wall_ms`, `timing`, `metrics.csv` `*_wall_ms` |
| Influenced faster than distracted? | `contrast.influenced_faster_than_distracted` |
| Feedback STI | `feedback.sti_gain`, `proof_retained_in_af` |

**Arm vocabulary (canonical in protocol, JSON, metrics, dashboard):**

| Arm | Meaning |
|-----|---------|
| **weighted** | All premises (full table set / full KB) |
| **influenced** | AF restricted to conditions query set |
| **distracted** | Randomly sampled atom set of AF size |

---

## Coupled workshop (B2 + B3)

One **measurement kernel** (`bridge/coupled.py`):

```text
CIP attention snapshot → dualed map → freeze-f|re-dynamics pre
  → weighted / influenced / distracted under fixed B → wall_ms
```

| | **B2** end-of-run | **B3** mid-run |
|--|-------------------|--------------|
| **Export once** | `--export-only` → `bridge_snapshot.json` | `--export-only` → `probes/cip_*.json` |
| **Offline grid** | `--offline-grid` modes×\(k\)×\(B\) | `--offline-grid` CIP×\(k\)×\(B\) |
| **Entry** | `mve_bridge.py` | `mve_pln_probe.py` |
| **Table** | `ablations/from_<source>/` | `protocol_probes.csv` |

**Shared export API:** `export_snapshot.write_attention_snapshot`  
(schedule=`end` vs `midrun`). Cell dirs: `from_…_{ff|rd}_k{K}_b{B}` (mid-run inserts `cip{i}`).

---

## B2 — Coupled workshop: end-of-run / offline grid

**Schedule:** final CIP attention after mve (one snapshot).  
**Grid:** mode × \(k\) × \(B\); optional bridge-side feedback. Fixed `--seed`.  
Writes `ablations/from_<source>/{ablations.csv,index.json}`.

**Preferred (same pattern as B3):**

```bash
# 1) one mve: export final AF snapshot only (no PLN)
python bridge/mve_bridge.py --export-only

# 2) offline modes × k × B on that snapshot (no mve)
python bridge/mve_bridge.py --offline-grid \
  --modes freeze-f,re-dynamics --focus-caps 6,12 --budgets 5,10,20

# optional bridge feedback on offline cells
python bridge/mve_bridge.py --offline-grid --budget 10 --focus-cap 12 --feedback
```

**One-shot** (mve + default freeze-f, B=10, k=12):

```bash
python bridge/mve_bridge.py
../PeTTa/run.sh cognitive_synergy.metta   # same defaults
```

| Arg | Default | Meaning |
|-----|---------|---------|
| `--export-only` | off | mve + `bridge_snapshot.json` (no PLN) |
| `--offline-grid` | off | PLN grid on existing snapshot only (no mve) |
| `--skip-mve` | off | Alias for `--offline-grid` |
| `--snapshot PATH` | `output/mve/bridge_snapshot.json` | Snapshot for offline-grid |
| `--mode` / `--modes` | `freeze-f` | Pre mode(s) |
| `--budget(s)` / `--focus-cap(s)` | `10` / `12` | Grid axes |
| `--feedback` | off | Bridge-side feedback after each steering |
| `--seed K` | `0` | Distracted-arm RNG (fixed seed) |

**Outputs** (cell dirs never clobber different names; always include mode, \(k\), \(B\)):

```text
output/cognitive_synergy/
  from_mve_ff_k12_b10/              # steering cell
  from_mve_rd_k6_b10/               # re-dynamics cell
  feedback_from_mve_ff_k12_b10/     # if --feedback
  ablations/from_mve/
    ablations.csv                   # upsert by scenario (narrow/--feedback merge into wide)
    index.json
```

---

## B3 — Coupled workshop: mid-run CIP schedule

**Schedule:** same kernel as B2, at CIP boundaries (trajectory).  
Default `mve.metta` unchanged (temp inject only). Dual-process freeze-F; no PLN in CIP.

**Preferred (sweep \(k\)×\(B\) without replaying mve):**

```bash
# 1) one CIP pass: export AF snapshots only (shared API with B2)
python bridge/mve_pln_probe.py --export-only --every 2

# 2) offline workshop grid on those snapshots
python bridge/mve_pln_probe.py --offline-grid --focus-caps 6,12 --budgets 5,10,20
# same as: python bridge/cip_probe.py --offline-grid --focus-caps … --budgets …
```

**Live single-cell (one \(k\), one \(B\) during mve):**

```bash
python bridge/mve_pln_probe.py --every 2 --focus-cap 12 --budget 10
python bridge/mve_pln_probe.py --timeout 180
python bridge/cip_probe.py --snapshot output/mve/probes/cip_2.json --cip-index 2
```

| Arg | Default | Meaning |
|-----|---------|---------|
| `--every N` | `2` | Live/export: probe CIP indices \(N, 2N, …\) (skip 0) |
| `--export-only` | off | Snapshots only (no PLN); same idea as B2 `--export-only` |
| `--offline-grid` | off | Sweep \(k\)×\(B\) on `probes/cip_*.json` (no mve) |
| `--focus-cap K` / `--focus-caps …` | `12` | Freeze-F size (list for offline-grid) |
| `--budget B` / `--budgets …` | `10` | PLN budget (list for offline-grid) |
| `--timeout S` | `180` | Soft-fail if PeTTa worker exceeds \(S\) s (`0` = unlimited) |
| `--out` | `…/mve_pln_probe` | Protocol root |

**Outputs:**

```text
output/mve/probes/cip_{i}.json
output/cognitive_synergy/
  from_mve_cip{i}_ff_k{K}_b{B}/     # workshop cell (same shape as B2)
  mve_pln_probe/
    protocol_probes.csv             # one row per CIP probe
    summary.json
    cells/cip_{i}/summary.json
```

Dashboard (**Cognitive synergy** surface): tabs **Overview · B2 grid · B3/B4 trajectories · Single cell**
(open vs closed series, ablations charts, battery inventory).

---

## B4 — Closed loop (CIP wage)

Same **B3 schedule**, different feedback bank: after **influenced** solves, wage into **live CIP**.

```bash
# open loop (B3)
python bridge/mve_pln_probe.py --every 2 --focus-cap 12 --budget 10

# closed loop (B4) — pair with open run (separate --out)
python bridge/mve_pln_probe.py --every 2 --closed-loop --wage 200 \
  --out output/cognitive_synergy/mve_pln_probe_closed
```

**Wage list** (`coupled.wage_atoms_from_steering`):

1. Proof **stamps** → original edge endpoints on the probe snapshot  
2. Snapshot **query objects** (original CIP names)  
3. Attention query∩focus, reverse-mapped when possible  

Empty list → soft-fail (no stimulate).  
Artifacts: `output/mve/wage/cip_{i}_wage.json` (`atoms`, `method`, `stamps`).

---

## Dynamics & driver order

Per ECAN cycle: AF/WA rent+diffusion → hebbian → forgetting.

```text
boot → map → MAX_AF_SIZE → pre|pre_freeze → [&B] → rng
    → late *_pln STV → pln_api → steering|feedback
```

---