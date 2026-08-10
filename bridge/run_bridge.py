#!/usr/bin/env python3
"""ECAN–PLN bridge runner.

Tabulated scenarios (B1):
  roman|slice          three-arm steering (weighted / influenced / distracted)
  feedback --map M     feedback protocol on roman or slice map
  suite --map M        steering grid over budgets, then optional feedback

B1 grids vary **budget B** only. RNG --seed is fixed (distracted S), not swept.

Coupled / CIP (B2+; own CLIs preferred):
  from-snapshot|ablate  — or python bridge/mve_bridge.py / mve_pln_probe.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

CAIRN = Path(__file__).resolve().parent.parent
PETTA = CAIRN.parent / "PeTTa" / "run.sh"
BRIDGE = CAIRN / "bridge"
sys.path.insert(0, str(BRIDGE))
import coupled  # noqa: E402
from scenario_from_snapshot import (  # noqa: E402
    cell_name,
    generate as generate_scenario,
    resolve_focus_cap,
    DEFAULT_FOCUS_CAP,
)

# Hand-written maps under bridge/scenarios/
MAPS = {
    "roman": ("scenarios/roman_map", "scenarios/roman_pln"),
    "slice": ("scenarios/slice_map", "scenarios/slice_pln"),
}


def _scenario_dir_name(map_name: str, protocol: str, budget: Optional[int]) -> str:
    """Unique output folder so budget grids never overwrite."""
    if protocol == "feedback":
        base = f"feedback_{map_name}"
    else:
        base = map_name
    if budget is None:
        return base
    return f"{base}_b{int(budget)}"


def driver_src(
    map_path: str,
    pln_path: str,
    protocol: str,
    rng_seed: int,
    pre: str = "pre",
    fx_out: Optional[str] = None,
    fx_out_feedback: Optional[str] = None,
    fx_name: Optional[str] = None,
    budget: Optional[int] = None,
) -> str:
    overrides = []
    if fx_name:
        overrides.append(f'(= (fx-name) "{fx_name}")')
    if fx_out:
        overrides.append(f'(= (fx-out) "{fx_out}")')
    if fx_out_feedback:
        overrides.append(f'(= (fx-out-feedback) "{fx_out_feedback}")')
    # After map import so these shadow map defaults
    ov_block = "\n".join(overrides) + ("\n" if overrides else "")
    b_line = f"!(change-state! &B {int(budget)})\n" if budget is not None else ""
    return f"""!(import! &self boot)
!(import! &self {map_path})
{ov_block}!(updateAttentionParam MAX_AF_SIZE (fx-af-size))
!(import! &self {pre})
{b_line}!(change-state! &rngSeed {int(rng_seed)})
!(import! &self {pln_path})
!(import! &self pln_api)
!(import! &self {protocol})
"""


def _worker_timeout_s() -> Optional[float]:
    """Optional PeTTa worker timeout (seconds). 0 / unset → no limit for B1; probes set env."""
    raw = os.environ.get("CAIRN_BRIDGE_TIMEOUT", "").strip()
    if not raw:
        return None
    try:
        t = float(raw)
    except ValueError:
        return None
    return t if t > 0 else None


def run_petta(src: str) -> int:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".metta", dir=BRIDGE, delete=False
    ) as f:
        f.write(src)
        path = Path(f.name)
    timeout = _worker_timeout_s()
    try:
        try:
            r = subprocess.run(
                ["bash", str(PETTA), f"bridge/{path.name}"],
                cwd=str(CAIRN),
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            print(
                f"[run_bridge] PeTTa worker timeout after {timeout}s",
                file=sys.stderr,
            )
            out = (e.stdout or "") if isinstance(e.stdout, str) else ""
            err = (e.stderr or "") if isinstance(e.stderr, str) else ""
            if err:
                print(err[-1500:], file=sys.stderr)
            elif out:
                print(out[-1500:], file=sys.stderr)
            return 124
    finally:
        path.unlink(missing_ok=True)
    for ln in (r.stdout or "").splitlines():
        s = ln.strip()
        if not s or s == "()":
            continue
        if s.startswith("[cognitive_synergy_io]") or s.startswith("[export_snapshot]"):
            print(ln)
            continue
        if s.startswith(("(steering", "(freeze-f", "(ecan ", "(feedback", "(Done")):
            print(ln)
    if r.returncode:
        err = r.stderr or ""
        print(err[-2500:] if err else (r.stdout or "")[-1500:], file=sys.stderr)
    return r.returncode


def _run_once(
    map_rel: str,
    pln_rel: str,
    protocol: str,
    scenario: str,
    pre: str,
    seed: Optional[int] = None,
    budget: Optional[int] = None,
) -> int:
    """One PeTTa protocol run → summary.json + metrics.csv under scenario dir."""
    out_dir = CAIRN / "output" / "cognitive_synergy" / scenario
    summary_rel = (out_dir / "summary.json").relative_to(CAIRN).as_posix()
    rng = 0 if seed is None else int(seed)
    return run_petta(
        driver_src(
            map_rel,
            pln_rel,
            protocol,
            rng,
            pre=pre,
            budget=budget,
            fx_name=scenario,
            fx_out=summary_rel,
            fx_out_feedback=summary_rel,
        )
    )


def run_steering(
    map_name: str,
    seed: Optional[int] = None,
    budget: Optional[int] = None,
) -> int:
    """Three-arm steering on roman or slice (weighted / influenced / distracted)."""
    if map_name not in MAPS:
        print(f"unknown map: {map_name} (roman|slice)", file=sys.stderr)
        return 2
    m, p = MAPS[map_name]
    scenario = _scenario_dir_name(map_name, "steering", budget)
    print(f"[run_bridge] steering map={map_name} B={budget} seed={0 if seed is None else seed} → {scenario}")
    return _run_once(m, p, "steering", scenario, "pre", seed=seed, budget=budget)


def run_feedback(
    map_name: str = "slice",
    budget: Optional[int] = None,
    seed: Optional[int] = None,
) -> int:
    """Feedback (proof → wage → ECAN) on roman or slice map."""
    if map_name not in MAPS:
        print(f"unknown map: {map_name} (roman|slice)", file=sys.stderr)
        return 2
    m, p = MAPS[map_name]
    scenario = _scenario_dir_name(map_name, "feedback", budget)
    print(f"[run_bridge] feedback map={map_name} B={budget} → {scenario}")
    return _run_once(m, p, "feedback", scenario, "pre", seed=seed, budget=budget)


def run_budget_grid(
    map_name: str,
    protocol: str,
    budgets: list[int],
    seed: Optional[int] = None,
) -> int:
    """Run one map for each B (one run per cell; seed fixed)."""
    if not budgets:
        budgets = [coupled.DEFAULT_BUDGET]
    for b in budgets:
        if protocol == "feedback":
            rc = run_feedback(map_name, budget=b, seed=seed)
        else:
            rc = run_steering(map_name, seed=seed, budget=b)
        if rc:
            return rc
    return 0


def run_suite(
    map_name: str = "slice",
    seed: Optional[int] = None,
    budgets: Optional[list[int]] = None,
    with_feedback: bool = True,
) -> int:
    """One map: three-arm steering over budgets, then feedback per budget.

    Example:
      suite --map slice --budgets 5,10,20
      suite --map roman --budget 10 --no-feedback
    """
    if map_name not in MAPS:
        print(f"unknown map: {map_name} (roman|slice)", file=sys.stderr)
        return 2
    budgets = budgets if budgets else [coupled.DEFAULT_BUDGET]
    print(
        f"[run_bridge suite] map={map_name} budgets={budgets} "
        f"seed={0 if seed is None else seed} feedback={with_feedback}"
    )
    rc = run_budget_grid(map_name, "steering", budgets, seed=seed)
    if rc:
        return rc
    if with_feedback:
        rc = run_budget_grid(map_name, "feedback", budgets, seed=seed)
        if rc:
            return rc
    print(
        f"[run_bridge suite] done → output/cognitive_synergy/"
        f"{{{map_name}_b*,feedback_{map_name}_b*}}/"
    )
    return 0


def run_from_snapshot(
    snapshot_path: str,
    mode: str = "freeze-f",
    seed: Optional[int] = None,
    protocol: str = "steering",
    budget: int = 10,
    focus_cap: Optional[int] = None,
    name: Optional[str] = None,
) -> int:
    """Generate scenario from snapshot JSON and run bridge protocol.

    Output dir always encodes mode/k/B via cell_name unless name is forced.
    """
    snap = Path(snapshot_path)
    if not snap.is_file():
        print(f"snapshot not found: {snap}", file=sys.stderr)
        return 2
    proto = protocol if protocol in ("steering", "feedback") else "steering"
    mode = mode if mode in ("freeze-f", "re-dynamics") else "freeze-f"
    budget = max(1, int(budget))

    with open(snap, encoding="utf-8") as f:
        snap_data = json.load(f)
    source = snap_data.get("source") or "snapshot"
    k = resolve_focus_cap(snap_data, focus_cap)
    if name is None:
        name = cell_name(source, mode, k, budget, protocol=proto)

    try:
        meta = generate_scenario(
            snap,
            mode=mode,
            focus_cap=k,
            budget=budget,
            name=name,
            protocol=proto,
        )
    except ValueError as e:
        print(f"[run_bridge] skip: {e}", file=sys.stderr)
        return 3
    fname = meta["name"]
    map_rel = f"scenarios/generated/{fname}_map"
    pln_rel = f"scenarios/generated/{fname}_pln"
    pre = "pre_freeze" if mode == "freeze-f" else "pre"
    print(
        f"[run_bridge] from-snapshot mode={mode} protocol={proto} "
        f"focus={meta.get('n_focus')}/{meta.get('n_af_export')} "
        f"tables={meta.get('n_tables')} k={meta.get('focus_cap')} B={budget} → {fname}"
    )
    return _run_once(
        map_rel, pln_rel, proto, fname, pre, seed=seed, budget=budget
    )


_GRID_FIELDS = [
    "mode",
    "focus_cap",
    "budget",
    "scenario",
    "status",
    "seed",
    "query",
    "weighted_solve",
    "influenced_solve",
    "distracted_solve",
    "influenced_beats_distracted",
    "influenced_premises",
    "distracted_premises",
    "weighted_premises",
    "weighted_wall_ms",
    "influenced_wall_ms",
    "distracted_wall_ms",
    "focus_size",
    "query_af_overlap",
]


def _ablation_row_key(row: dict) -> tuple:
    """Stable identity for upsert: prefer scenario, else mode×k×B."""
    scen = str(row.get("scenario") or "").strip()
    if scen:
        return ("scenario", scen)
    return (
        "axes",
        str(row.get("mode") or ""),
        str(row.get("focus_cap") or ""),
        str(row.get("budget") or ""),
    )


def _merge_ablation_rows(existing: list[dict], new_rows: list[dict]) -> list[dict]:
    """Upsert new_rows into existing by scenario/axes; sort for stable CSV."""
    by: dict[tuple, dict] = {}
    for r in existing:
        by[_ablation_row_key(r)] = r
    for r in new_rows:
        by[_ablation_row_key(r)] = r

    def sort_key(r: dict):
        mode = str(r.get("mode") or "")
        try:
            k = int(r.get("focus_cap"))
        except (TypeError, ValueError):
            k = 0
        try:
            b = int(r.get("budget"))
        except (TypeError, ValueError):
            b = 0
        return (mode, k, b, str(r.get("scenario") or ""))

    return sorted(by.values(), key=sort_key)


def _write_coupled_table(
    snap: Path,
    source: str,
    modes: list[str],
    focus_caps: list[int],
    budgets: list[int],
    seed: Optional[int],
    rows: list[dict],
    with_feedback: bool,
) -> Path:
    """Write ablations/from_<source>/{ablations.csv,index.json}; return table path.

    Merges with any existing ablations.csv (upsert by scenario) so a later
    narrow or --feedback run does not wipe a wider grid.
    """
    out_root = CAIRN / "output" / "cognitive_synergy" / "ablations" / f"from_{source}"
    out_root.mkdir(parents=True, exist_ok=True)
    table_path = out_root / "ablations.csv"

    existing: list[dict] = []
    if table_path.is_file():
        try:
            with open(table_path, newline="", encoding="utf-8") as f:
                existing = list(csv.DictReader(f))
        except OSError:
            existing = []

    merged = _merge_ablation_rows(existing, rows)
    if existing and len(merged) > len(rows):
        print(
            f"[run_bridge coupled] merged {len(rows)} new cell(s) into "
            f"{len(existing)} existing → {len(merged)} total",
            file=sys.stderr,
        )

    with open(table_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_GRID_FIELDS)
        w.writeheader()
        for row in merged:
            w.writerow({k: row.get(k, "") for k in _GRID_FIELDS})

    # Index axes = union of this call's request and merged table contents
    mode_u = sorted(
        {str(r.get("mode")) for r in merged if r.get("mode")} | set(modes)
    )
    def _ints(vals, key):
        out = set(vals)
        for r in merged:
            try:
                out.add(int(r.get(key)))
            except (TypeError, ValueError):
                pass
        return sorted(out)

    index = {
        "run_timestamp": datetime.now().isoformat(),
        "snapshot": str(snap),
        "source": source,
        "modes": mode_u,
        "focus_caps": _ints(focus_caps, "focus_cap"),
        "budgets": _ints(budgets, "budget"),
        "seed": 0 if seed is None else int(seed),
        "with_feedback": with_feedback,
        "n_cells": len(merged),
        "n_ok": sum(1 for r in merged if r.get("status") == "ok"),
        "table": str(table_path.relative_to(CAIRN)),
        "cells": merged,
        "last_write_cells": len(rows),
    }
    index_path = out_root / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, default=str)
        f.write("\n")
    print(f"[run_bridge coupled] wrote {table_path}")
    print(f"[run_bridge coupled] wrote {index_path}")
    print(
        f"{'mode':12} {'k':>3} {'B':>3} {'inf':>5} {'dst':>5} {'beat':>5} "
        f"{'i_n':>5} {'d_n':>5}"
    )
    for r in merged:
        print(
            f"{r.get('mode','?'):12} {r.get('focus_cap','?'):>3} {r.get('budget','?'):>3} "
            f"{str(r.get('influenced_solve',''))[:5]:>5} "
            f"{str(r.get('distracted_solve',''))[:5]:>5} "
            f"{str(r.get('influenced_beats_distracted',''))[:5]:>5} "
            f"{str(r.get('influenced_premises',''))[:5]:>5} "
            f"{str(r.get('distracted_premises',''))[:5]:>5}"
        )
    return table_path


def run_coupled_grid(
    snapshot_path: str,
    modes: Optional[list[str]] = None,
    mode: Optional[str] = None,
    budgets: Optional[list[int]] = None,
    focus_caps: Optional[list[int]] = None,
    seed: Optional[int] = None,
    with_feedback: bool = False,
) -> int:
    """B2 coupled suite: modes × focus_cap × budget on one snapshot.

    Defaults stay cheap (freeze-f × k=12 × B=10). Wider grids set --modes / --budgets
    / --focus-caps. Always writes ablations/from_<source>/{ablations.csv,index.json}.
    Optional feedback after each steering cell. Fixed seed (not swept).
    """
    snap = Path(snapshot_path)
    if not snap.is_file():
        print(f"snapshot not found: {snap}", file=sys.stderr)
        return 2

    if modes:
        mode_list = [
            m if m in ("freeze-f", "re-dynamics") else "freeze-f"
            for m in modes
            if m
        ]
    elif mode:
        mode_list = [mode if mode in ("freeze-f", "re-dynamics") else "freeze-f"]
    else:
        mode_list = ["freeze-f"]
    if not mode_list:
        mode_list = ["freeze-f"]

    budgets = budgets if budgets else [coupled.DEFAULT_BUDGET]
    focus_caps = focus_caps if focus_caps else [coupled.DEFAULT_FOCUS_CAP]

    with open(snap, encoding="utf-8") as f:
        source = json.load(f).get("source") or "snapshot"

    total = len(mode_list) * len(budgets) * len(focus_caps)
    print(
        f"[run_bridge coupled] source={source} modes={mode_list} "
        f"k={focus_caps} B={budgets} feedback={with_feedback} "
        f"seed={0 if seed is None else seed} cells={total}"
    )

    rows: list[dict] = []
    i = 0
    for m in mode_list:
        for k in focus_caps:
            for b in budgets:
                i += 1
                cname = cell_name(source, m, k, b)
                print(f"[run_bridge coupled] ({i}/{total}) steering {cname}")
                rc = run_from_snapshot(
                    str(snap),
                    mode=m,
                    seed=seed,
                    protocol="steering",
                    budget=b,
                    focus_cap=k,
                    name=cname,
                )
                summary = CAIRN / "output" / "cognitive_synergy" / cname / "summary.json"
                row = _cell_row(summary, m, k, b)
                if rc:
                    row["status"] = f"fail_rc={rc}"
                rows.append(row)
                if rc:
                    _write_coupled_table(
                        snap, source, mode_list, focus_caps, budgets, seed, rows, with_feedback
                    )
                    return rc
                if with_feedback:
                    print(f"[run_bridge coupled] ({i}/{total}) feedback {cname}")
                    rc_fb = run_from_snapshot(
                        str(snap),
                        mode=m,
                        seed=seed,
                        protocol="feedback",
                        budget=b,
                        focus_cap=k,
                    )
                    if rc_fb:
                        _write_coupled_table(
                            snap,
                            source,
                            mode_list,
                            focus_caps,
                            budgets,
                            seed,
                            rows,
                            with_feedback,
                        )
                        return rc_fb

    _write_coupled_table(
        snap, source, mode_list, focus_caps, budgets, seed, rows, with_feedback
    )
    print("[run_bridge coupled] done")
    return 0 if all(r.get("status") == "ok" for r in rows) else 1


def run_ablate(
    snapshot_path: str,
    modes: list[str] | None = None,
    budgets: list[int] | None = None,
    focus_caps: list[int] | None = None,
    seed: Optional[int] = None,
    with_feedback: bool = False,
) -> int:
    """Back-compat alias for run_coupled_grid (multi-mode wide grid)."""
    return run_coupled_grid(
        snapshot_path,
        modes=modes or ["freeze-f", "re-dynamics"],
        budgets=budgets or [5, 10, 20],
        focus_caps=focus_caps or [6, 12, 20],
        seed=seed,
        with_feedback=with_feedback,
    )


def parse_int_list(s: str, default: list[int]) -> list[int]:
    """Parse '5,10,20' → [5,10,20]; empty → default. (delegates to coupled)"""
    return coupled.parse_int_list(s, default)


def _cell_row(summary_path: Path, mode: str, focus_cap: int, budget: int) -> dict:
    """Flatten one summary.json into a coupled grid table row."""
    row = {
        "mode": mode,
        "focus_cap": focus_cap,
        "budget": budget,
        "scenario": summary_path.parent.name,
        "status": "missing",
    }
    if not summary_path.is_file():
        return row
    with open(summary_path, encoding="utf-8") as f:
        s = json.load(f)
    params = s.get("parameters") or {}
    fields = coupled.arm_fields_from_summary(s)
    row.update(
        {
            "status": "ok",
            "query": fields.get("query") or params.get("query"),
            "seed": params.get("random_seed", coupled.DEFAULT_SEED),
            "weighted_solve": fields.get("weighted_solved"),
            "influenced_solve": fields.get("influenced_solved"),
            "distracted_solve": fields.get("distracted_solved"),
            "influenced_beats_distracted": fields.get("influenced_beats_distracted"),
            "influenced_premises": fields.get("influenced_n_premises"),
            "distracted_premises": fields.get("distracted_n_premises"),
            "weighted_premises": fields.get("weighted_n_premises"),
            "weighted_wall_ms": fields.get("weighted_wall_ms"),
            "influenced_wall_ms": fields.get("influenced_wall_ms"),
            "distracted_wall_ms": fields.get("distracted_wall_ms"),
            "focus_size": fields.get("focus_size") or None,
            "query_af_overlap": fields.get("query_af_overlap"),
        }
    )
    return row


def main():
    ap = argparse.ArgumentParser(description="ECAN–PLN bridge runner")
    ap.add_argument(
        "cmd",
        nargs="?",
        default="list",
        help="roman|slice|feedback|suite|from-snapshot|ablate",
    )
    ap.add_argument(
        "snapshot",
        nargs="?",
        default=None,
        help="path to bridge_snapshot.json (from-snapshot|ablate)",
    )
    ap.add_argument(
        "--map",
        choices=("roman", "slice"),
        default=None,
        help="map for feedback|suite (default: slice)",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for distracted arm S (default 0; not a sweep axis)",
    )
    ap.add_argument(
        "--mode",
        choices=("freeze-f", "re-dynamics"),
        default="freeze-f",
        help="from-snapshot only",
    )
    ap.add_argument(
        "--protocol",
        choices=("steering", "feedback"),
        default="steering",
        help="from-snapshot protocol",
    )
    ap.add_argument(
        "--budget",
        type=int,
        default=None,
        help="single PLN budget B (default 10 if neither --budget nor --budgets)",
    )
    ap.add_argument(
        "--budgets",
        default=None,
        help="comma list of B values for roman|slice|suite|feedback|ablate",
    )
    ap.add_argument(
        "--no-feedback",
        action="store_true",
        help="suite: steering grid only (skip feedback on the map)",
    )
    ap.add_argument(
        "--focus-cap",
        type=int,
        default=None,
        help="freeze-F / re-dynamics top-STI focus size (default 12)",
    )
    ap.add_argument(
        "--focus-caps",
        default=None,
        help="comma list of focus caps k (from-snapshot grid / ablate; ablate default 6,12,20)",
    )
    ap.add_argument(
        "--modes",
        default=None,
        help="coupled: comma list of modes (e.g. freeze-f,re-dynamics); overrides --mode",
    )
    ap.add_argument(
        "--feedback",
        action="store_true",
        help="coupled: after each steering cell, also run feedback protocol",
    )
    args = ap.parse_args()
    cmd = args.cmd

    def budgets_list(default_single: int = 10) -> list[int]:
        if args.budgets:
            return parse_int_list(args.budgets, [default_single])
        if args.budget is not None:
            return [int(args.budget)]
        return [default_single]

    def focus_caps_list(default_single: int = DEFAULT_FOCUS_CAP) -> list[int]:
        if args.focus_caps:
            return parse_int_list(args.focus_caps, [default_single])
        if args.focus_cap is not None:
            return [int(args.focus_cap)]
        return [default_single]

    if cmd in ("list", "-h", "--help"):
        print("Usage (tabulated B1):")
        print("  python bridge/run_bridge.py roman|slice [--budget B|--budgets 5,10,20] [--seed K]")
        print("  python bridge/run_bridge.py feedback --map roman|slice [--budget B|--budgets …]")
        print("  python bridge/run_bridge.py suite --map roman|slice [--budgets …] [--no-feedback]")
        print("Usage (coupled B2):")
        print(
            "  python bridge/run_bridge.py from-snapshot PATH "
            "[--modes …] [--budgets …] [--focus-caps …] [--feedback] [--seed K]"
        )
        print(
            "  python bridge/run_bridge.py ablate PATH   # multi-mode wide offline grid"
        )
        print("  python bridge/mve_bridge.py --export-only | --offline-grid …")
        print("  python bridge/mve_pln_probe.py --export-only | --offline-grid …")
        print("B2/B3: dump once, offline modes×k×B (or CIP×k×B). Seed fixed, not swept.")
        return 0

    if cmd in MAPS:
        return run_budget_grid(
            cmd,
            "steering",
            budgets_list(10),
            seed=args.seed,
        )
    if cmd == "feedback":
        return run_budget_grid(
            args.map or "slice",
            "feedback",
            budgets_list(10),
            seed=args.seed,
        )
    if cmd == "suite":
        return run_suite(
            map_name=args.map or "slice",
            seed=args.seed,
            budgets=budgets_list(10),
            with_feedback=not args.no_feedback,
        )
    if cmd == "from-snapshot":
        if not args.snapshot:
            print("from-snapshot requires PATH to bridge_snapshot.json", file=sys.stderr)
            return 2
        b_list = budgets_list(10)
        k_list = focus_caps_list(DEFAULT_FOCUS_CAP)
        if args.modes:
            mode_list = [
                m.strip()
                for m in args.modes.split(",")
                if m.strip() in ("freeze-f", "re-dynamics")
            ] or ["freeze-f"]
        else:
            mode_list = [args.mode]
        # Single feedback-only cell (no grid table)
        if (
            len(b_list) == 1
            and len(k_list) == 1
            and len(mode_list) == 1
            and not args.feedback
            and args.protocol == "feedback"
        ):
            return run_from_snapshot(
                args.snapshot,
                mode=mode_list[0],
                seed=args.seed,
                protocol="feedback",
                budget=b_list[0],
                focus_cap=k_list[0],
            )
        return run_coupled_grid(
            args.snapshot,
            modes=mode_list,
            budgets=b_list,
            focus_caps=k_list,
            seed=args.seed,
            with_feedback=args.feedback,
        )
    if cmd == "ablate":
        # Back-compat: multi-mode wide defaults
        if not args.snapshot:
            print("ablate requires PATH to bridge_snapshot.json", file=sys.stderr)
            return 2
        if args.modes:
            mode_list = [
                m.strip()
                for m in args.modes.split(",")
                if m.strip() in ("freeze-f", "re-dynamics")
            ] or ["freeze-f", "re-dynamics"]
        else:
            mode_list = ["freeze-f", "re-dynamics"]
        b_list = (
            parse_int_list(args.budgets, [5, 10, 20])
            if args.budgets
            else ([args.budget] if args.budget is not None else [5, 10, 20])
        )
        k_list = (
            parse_int_list(args.focus_caps, [6, 12, 20])
            if args.focus_caps
            else ([args.focus_cap] if args.focus_cap is not None else [6, 12, 20])
        )
        return run_coupled_grid(
            args.snapshot,
            modes=mode_list,
            budgets=b_list,
            focus_caps=k_list,
            seed=args.seed,
            with_feedback=args.feedback,
        )
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
