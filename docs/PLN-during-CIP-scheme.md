# Scheme: PLN during CIP + closing the loop

**Status:** Shipped (B3 open probes + B4 closed-loop wage)  
**Date:** 2026-08-04  
**Depends on:** coupled workshop kernel (`bridge/coupled.py`), B2 end-of-run  
**Ladder:** B3 = mid-run schedule; B4 = `--closed-loop` CIP wage

---

## Mission

| Phase | Claim | Question |
|-------|--------|----------|
| **III — During CIP** | Trajectory | At CIP boundaries, does **influenced** PLN beat **distracted** under fixed \(B\)? |
| **IV — Close the loop** | Synergy feedback | After proof, does waging those atoms in live CIP change later attention? |

End-of-run B2 `mve_bridge` = static P0. B3/B4 (scheme III/IV) use the **CIP clock**.

---

## Locked decisions

| Item | Choice |
|------|--------|
| Order | III then IV |
| Architecture | Dual-process sync; no `lib_pln` in CIP PeTTa |
| Entry | `python bridge/mve_pln_probe.py` (default mve pure) |
| Schedule | Every N CIP indices (default 2), skip 0 |
| Focus / B | freeze-F, focus_cap=12, B=10 |
| Closed loop | Bridge writes wage list (stamps→originals); CIP `stimulate`s those names |

---

## Output

```text
output/mve/probes/cip_{i}.json
output/mve/wage/cip_{i}_wage.json          # --closed-loop
output/cognitive_synergy/mve_pln_probe/
  protocol_probes.csv
  summary.json
  cells/cip_{i}/summary.json               # optional per-probe steering
```

Never write protocol fields into CIP `metrics.csv`.

---

## CLI

```bash
python bridge/mve_pln_probe.py --every 2 --focus-cap 12 --budget 10
python bridge/mve_pln_probe.py --every 2 --closed-loop --wage 200
python bridge/cip_probe.py --snapshot output/mve/probes/cip_2.json --cip-index 2
```

---

## Pathway

```text
demo → mve → assignment          structural
           ↘ mve_bridge          end-of-run PLN
           ↘ mve_pln_probe       mid-run PLN ± closed loop
```
