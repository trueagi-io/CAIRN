# Cognitive synergy ladder (B1–B4)

**Status:** B1–B4 shipped (scaffold + hardened closed loop)  
**Date:** 2026-08-04  

| # | Scope | Status |
|---|--------|--------|
| **B1** | Tabulated roman\|slice suite | ✅ |
| **B2** | Coupled workshop — end-of-run / offline grid | ✅ |
| **B3** | Coupled workshop — mid-run CIP (+ offline \(k\)×\(B\) grid) | ✅ |
| **B4** | Closed-loop CIP wage on B3 schedule | ✅ |

Shared kernel: `bridge/coupled.py`.

## B1 decisions

- Maps: roman \| slice; three arms weighted / influenced / distracted.  
- Feedback is a protocol on a map.  
- Grids: budgets (B2: modes × k × B). No multi-seed axis.  
- Fixed `--seed` for distracted \(S\) only.  
- `wall_ms` under fixed \(B\).  

## Coupled workshop (B2 + B3)

| Axis | B2 | B3 |
|------|----|----|
| Schedule | `--export-only` then `--offline-grid` | `--export-only` then `--offline-grid` |
| Grid | modes × \(k\) × \(B\) | CIP × offline \(k\)×\(B\) |
| Kernel | `run_from_snapshot` / three arms | same via `cip_probe` |

## B4 closed loop

| Item | Choice |
|------|--------|
| Trigger | influenced arm solved at probe CIP |
| Wage atoms | proof stamps → original endpoints; else query; else attention |
| Bank | live CIP `stimulate` (not bridge feedback only) |
| Empty list | soft-fail |
| Recipe | open vs closed paired runs (different `--out`) |

## Shared infrastructure

| # | Task | Status |
|---|------|--------|
| S.1 | `cell_name` / mid-run naming | ✅ |
| S.2 | `run_coupled_grid` + probe worker | ✅ |
| S.3 | Arm vocabulary | ✅ |
| S.4 | `wall_ms` | ✅ |
| S.5 | No multi-seed | ✅ |
| S.6 | Worker timeout (`CAIRN_BRIDGE_TIMEOUT`) | ✅ |
| S.7 | Dashboard grid + probe trajectory | ✅ |

## Success criteria

- B1 template for tabulated maps.  
- B2 end-of-run grid lab; B3 trajectory lab; same measurement.  
- B4 clearly CIP-side wage with stamp→original wage lists.  
- No multi-seed experiment axis.
