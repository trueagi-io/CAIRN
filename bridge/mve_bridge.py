#!/usr/bin/env python3
"""B2: end-of-run schedule of the coupled workshop.

Same kernel as B3 (`bridge/coupled.py`). Preferred workflow mirrors B3:

  # 1) one mve: export final AF snapshot only (no PLN)
  python bridge/mve_bridge.py --export-only

  # 2) offline modes × k × B on that snapshot (no mve)
  python bridge/mve_bridge.py --offline-grid \\
      --modes freeze-f,re-dynamics --focus-caps 6,12 --budgets 5,10,20

  # one-shot (mve + default freeze-f B=10 k=12):
  python bridge/mve_bridge.py

Always writes ablations/from_<source>/{ablations.csv,index.json}.
PLN never loads inside the CIP process.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

CAIRN = Path(__file__).resolve().parent.parent
PETTA = CAIRN.parent / "PeTTa" / "run.sh"
SNAP = CAIRN / "output" / "mve" / "bridge_snapshot.json"
MVE = CAIRN / "mve.metta"

_EXPORT_TAIL = """
; ---- mve_bridge: forced AF+Hebbian snapshot (not part of plain mve.metta) ----
!(import! &self "bridge/export_snapshot.py")
!(import! &self tools/bridge_export)
!(export-bridge-snapshot-force! "output/mve" "mve")
!(println! (mve_bridge snapshot written))
"""

sys.path.insert(0, str(CAIRN / "bridge"))
import coupled  # noqa: E402
import run_bridge  # noqa: E402


def run_mve_with_export() -> int:
    """Run mve.metta + force-export tail in one PeTTa process."""
    if not MVE.is_file():
        print(f"[mve_bridge] missing {MVE}", file=sys.stderr)
        return 2
    body = MVE.read_text(encoding="utf-8")
    fd, tmp = tempfile.mkstemp(prefix="_mve_bridge_", suffix=".metta", dir=str(CAIRN))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        tmp_path.write_text(body + "\n" + _EXPORT_TAIL, encoding="utf-8")
        print("[mve_bridge] running mve + export tail …")
        r = subprocess.run(
            ["bash", str(PETTA), tmp_path.name],
            cwd=str(CAIRN),
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    ok = coupled.attention_snapshot_ok(SNAP)
    if not ok and not SNAP.is_file():
        print(f"[mve_bridge] expected snapshot missing: {SNAP}", file=sys.stderr)
        return 2 if r.returncode == 0 else r.returncode
    if not ok:
        print(f"[mve_bridge] snapshot unusable: {SNAP}", file=sys.stderr)
        return 2 if r.returncode == 0 else r.returncode
    rc = coupled.petta_export_rc(r.returncode, artifact_ok=True, label="mve_bridge")
    if rc == 0:
        print(f"[mve_bridge] snapshot → {SNAP.relative_to(CAIRN)}")
    return rc


def _modes_list(mode: str, modes: Optional[str]) -> list[str]:
    """--modes wins when set; else single --mode (default freeze-f)."""
    if modes and str(modes).strip():
        out = [
            m.strip()
            for m in modes.split(",")
            if m.strip() in ("freeze-f", "re-dynamics")
        ]
        return out or ["freeze-f"]
    if mode in ("freeze-f", "re-dynamics"):
        return [mode]
    return ["freeze-f"]


def run(
    skip_mve: bool = False,
    export_only: bool = False,
    mode: str = "freeze-f",
    modes: Optional[str] = None,
    budget: Optional[int] = None,
    budgets: Optional[str] = None,
    focus_cap: Optional[int] = None,
    focus_caps: Optional[str] = None,
    seed: Optional[int] = None,
    feedback: bool = False,
    snapshot: Optional[str] = None,
) -> int:
    """Programmatic entry.

    export_only: mve + snapshot, stop.
    skip_mve / offline-grid: PLN grid on existing snapshot only.
    default: mve + export then grid.
    """
    snap_path = Path(snapshot) if snapshot else SNAP
    if not snap_path.is_absolute():
        snap_path = CAIRN / snap_path

    if export_only:
        return run_mve_with_export()

    if not skip_mve:
        rc = run_mve_with_export()
        if rc:
            return rc
    elif not snap_path.is_file():
        print(
            f"[mve_bridge] no snapshot at {snap_path}; "
            "run --export-only first or omit --offline-grid/--skip-mve",
            file=sys.stderr,
        )
        return 2

    if not snap_path.is_file():
        print(f"[mve_bridge] expected snapshot missing: {snap_path}", file=sys.stderr)
        return 2

    mode_list = _modes_list(mode, modes)
    b_list = coupled.resolve_axis(budget, budgets, coupled.DEFAULT_BUDGET)
    k_list = coupled.resolve_axis(focus_cap, focus_caps, coupled.DEFAULT_FOCUS_CAP)
    print(
        f"[mve_bridge] offline-grid snap={coupled.relpath_cairn(snap_path)} "
        f"modes={mode_list} k={k_list} B={b_list} "
        f"feedback={feedback} seed={0 if seed is None else seed}"
    )
    return run_bridge.run_coupled_grid(
        str(snap_path),
        modes=mode_list,
        budgets=b_list,
        focus_caps=k_list,
        seed=seed,
        with_feedback=feedback,
    )


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "B2: end-of-run coupled workshop — export snapshot and/or offline modes×k×B grid"
        )
    )
    ap.add_argument(
        "--export-only",
        action="store_true",
        help="run mve + write bridge_snapshot.json only (no PLN); same as B3 --export-only",
    )
    ap.add_argument(
        "--offline-grid",
        action="store_true",
        help="sweep modes×k×B on existing snapshot only (no mve); like B3 --offline-grid",
    )
    ap.add_argument(
        "--skip-mve",
        action="store_true",
        help="alias for --offline-grid (back-compat)",
    )
    ap.add_argument(
        "--snapshot",
        default=None,
        help="snapshot path (default output/mve/bridge_snapshot.json)",
    )
    ap.add_argument(
        "--mode",
        choices=("freeze-f", "re-dynamics"),
        default=coupled.DEFAULT_MODE,
        help="single pre mode when --modes is not set",
    )
    ap.add_argument(
        "--modes",
        default=None,
        help="comma list of modes (e.g. freeze-f,re-dynamics)",
    )
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--budgets", default=None, help="comma list of B values")
    ap.add_argument("--focus-cap", type=int, default=None)
    ap.add_argument("--focus-caps", default=None, help="comma list of k values")
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for distracted arm (default 0; not a sweep axis)",
    )
    ap.add_argument(
        "--feedback",
        action="store_true",
        help="after each steering cell, run bridge-side feedback protocol",
    )
    ap.add_argument(
        "--ablate",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = ap.parse_args(argv)

    if args.export_only and (args.offline_grid or args.skip_mve):
        print(
            "[mve_bridge] use --export-only alone, then a second call with --offline-grid",
            file=sys.stderr,
        )
        return 2

    modes = args.modes
    budgets = args.budgets
    focus_caps = args.focus_caps
    if args.ablate:
        if not modes:
            modes = "freeze-f,re-dynamics"
        if not budgets and args.budget is None:
            budgets = "5,10,20"
        if not focus_caps and args.focus_cap is None:
            focus_caps = "6,12,20"

    offline = args.offline_grid or args.skip_mve or bool(args.ablate)
    return run(
        skip_mve=offline,
        export_only=args.export_only,
        mode=args.mode,
        modes=modes,
        budget=args.budget,
        budgets=budgets,
        focus_cap=args.focus_cap,
        focus_caps=focus_caps,
        seed=args.seed,
        feedback=args.feedback,
        snapshot=args.snapshot,
    )


if __name__ == "__main__":
    sys.exit(main())
