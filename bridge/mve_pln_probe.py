#!/usr/bin/env python3
"""B3: mid-run schedule of the coupled workshop (optional B4 closed-loop wage).

Same measurement kernel as B2 (`bridge/coupled.py` → freeze-F three-arm PLN),
sampled at CIP boundaries instead of end-of-run / offline grid.

Recommended B3 workflow (same pattern as B2 --export-only → --offline-grid):

  # 1) one mve: export AF snapshots only (no PLN)
  python bridge/mve_pln_probe.py --export-only --every 2

  # 2) offline workshop grid on those snapshots
  python bridge/mve_pln_probe.py --offline-grid \\
      --focus-caps 6,12 --budgets 5,10,20

Live single-cell probes (one k, one B during mve):

  python bridge/mve_pln_probe.py --every 2 --focus-cap 12 --budget 10
  python bridge/mve_pln_probe.py --every 2 --closed-loop --wage 200   # B4

Default mve.metta is not modified. This entry builds a temp mve with probe hooks.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CAIRN = Path(__file__).resolve().parent.parent
PETTA = CAIRN.parent / "PeTTa" / "run.sh"
MVE = CAIRN / "mve.metta"

_PROBE_IMPORTS = """
; ---- mve_pln_probe: mid-run PLN dual-process hooks ----
!(import! &self "bridge/export_snapshot.py")
!(import! &self "bridge/cip_probe.py")
!(import! &self tools/bridge_export)
!(import! &self tools/cip_probe_hooks)
"""

_HOOK_OPEN = (
    "                      ($_ (println! (CIP: $cip-index)))\n"
    "                      ($_ (maybe-pln-probe! $cip-index))\n"
)
_HOOK_CLOSED = (
    "                      ($_ (println! (CIP: $cip-index)))\n"
    "                      ($_ (pln-probe-and-maybe-wage! $cip-index {wage}))\n"
)
_HOOK_MARKER = "                      ($_ (println! (CIP: $cip-index)))\n"


def _inject(body: str, closed_loop: bool, wage: float) -> str:
    if "cip_probe_hooks" in body:
        return body
    if _HOOK_MARKER not in body:
        raise RuntimeError(
            "mve.metta batch boundary marker not found; cannot inject probe hook"
        )
    hook = (
        _HOOK_CLOSED.format(wage=float(wage))
        if closed_loop
        else _HOOK_OPEN
    )
    body = body.replace(_HOOK_MARKER, hook, 1)
    anchor = '!(import! &self tools/recorder)\n'
    if anchor in body:
        body = body.replace(anchor, anchor + _PROBE_IMPORTS, 1)
    else:
        body = _PROBE_IMPORTS + "\n" + body
    close = "!(py-call (recorder.close_recorder))\n"
    fin = "!(py-call (cip_probe.finalize_run))\n"
    if close in body and "finalize_run" not in body:
        body = body.replace(close, close + fin, 1)
    return body


def run_mve_with_probes(
    every: int = 2,
    focus_cap: int = 12,
    budget: int = 10,
    closed_loop: bool = False,
    wage: float = 200.0,
    export_only: bool = False,
    out: str = "output/cognitive_synergy/mve_pln_probe",
) -> int:
    if not MVE.is_file():
        print(f"[mve_pln_probe] missing {MVE}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["CAIRN_PLN_PROBE"] = "1"
    env["CAIRN_PLN_PROBE_EVERY"] = str(max(1, every))
    env["CAIRN_PLN_PROBE_FOCUS_CAP"] = str(max(2, focus_cap))
    env["CAIRN_PLN_PROBE_BUDGET"] = str(max(1, budget))
    env["CAIRN_PLN_PROBE_CLOSED_LOOP"] = "1" if closed_loop else "0"
    env["CAIRN_PLN_PROBE_WAGE"] = str(wage)
    env["CAIRN_PLN_PROBE_OUT"] = out
    # Shared name with B2; DUMP_ONLY kept as env alias for older injects
    env["CAIRN_PLN_PROBE_EXPORT_ONLY"] = "1" if export_only else "0"
    env["CAIRN_PLN_PROBE_DUMP_ONLY"] = "1" if export_only else "0"
    if "CAIRN_BRIDGE_TIMEOUT" not in env:
        env["CAIRN_BRIDGE_TIMEOUT"] = "180"

    body = _inject(MVE.read_text(encoding="utf-8"), closed_loop, wage)
    fd, tmp = tempfile.mkstemp(prefix="_mve_pln_probe_", suffix=".metta", dir=str(CAIRN))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        tmp_path.write_text(body, encoding="utf-8")
        print(
            f"[mve_pln_probe] mve + probes every={every} k={focus_cap} B={budget} "
            f"closed_loop={closed_loop} export_only={export_only}"
        )
        r = subprocess.run(
            ["bash", str(PETTA), tmp_path.name],
            cwd=str(CAIRN),
            env=env,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    # Export-only / live: success if mid-run probes or protocol table exist even
    # when PeTTa tears down with SIGALRM (rc 142) after a long mve.
    sys.path.insert(0, str(CAIRN / "bridge"))
    import cip_probe  # noqa: E402
    import coupled  # noqa: E402

    probes = cip_probe.list_probe_snapshots()
    probes_ok = any(coupled.attention_snapshot_ok(p) for _i, p in probes)
    protocol = CAIRN / out / "protocol_probes.csv"
    # export_only needs probes; live open/closed may only write protocol rows
    artifact_ok = probes_ok or (not export_only and protocol.is_file())
    rc = coupled.petta_export_rc(r.returncode, artifact_ok=artifact_ok, label="mve_pln_probe")
    if rc == 0:
        if export_only:
            print(
                f"[mve_pln_probe] export-only done → {len(probes)} probe(s) under "
                f"output/mve/probes/"
            )
        else:
            print(f"[mve_pln_probe] done → {out}/protocol_probes.csv")
    return rc


def main() -> int:
    sys.path.insert(0, str(CAIRN / "bridge"))
    import cip_probe  # noqa: E402
    import coupled  # noqa: E402

    ap = argparse.ArgumentParser(
        description=(
            "B3: mid-run coupled probes — live, export-only, or offline k×B grid"
        )
    )
    ap.add_argument("--every", type=int, default=2, help="probe every N CIP indices")
    ap.add_argument("--focus-cap", type=int, default=None)
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument(
        "--focus-caps",
        default=None,
        help="offline-grid: comma list of k (e.g. 6,12,20)",
    )
    ap.add_argument(
        "--budgets",
        default=None,
        help="offline-grid: comma list of B (e.g. 5,10,20)",
    )
    ap.add_argument(
        "--closed-loop",
        action="store_true",
        help="B4: after influenced solve, stimulate proof atoms in live CIP",
    )
    ap.add_argument("--wage", type=float, default=200.0)
    ap.add_argument(
        "--export-only",
        action="store_true",
        help="export AF snapshots only (no PLN); same idea as B2 --export-only",
    )
    ap.add_argument(
        "--dump-only",
        action="store_true",
        help=argparse.SUPPRESS,  # alias for --export-only
    )
    ap.add_argument(
        "--offline-grid",
        action="store_true",
        help="sweep k×B on saved output/mve/probes/cip_*.json (no mve)",
    )
    ap.add_argument(
        "--probes-dir",
        default="output/mve/probes",
        help="probe snapshots dir for --offline-grid",
    )
    ap.add_argument(
        "--mode",
        choices=("freeze-f", "re-dynamics"),
        default="freeze-f",
        help="offline-grid pre mode (default freeze-f)",
    )
    ap.add_argument("--seed", type=int, default=coupled.DEFAULT_SEED)
    ap.add_argument(
        "--out",
        default="output/cognitive_synergy/mve_pln_probe",
        help="protocol output directory",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="per-cell PeTTa worker timeout seconds (0=unlimited)",
    )
    args = ap.parse_args()

    if args.timeout and args.timeout > 0:
        os.environ["CAIRN_BRIDGE_TIMEOUT"] = str(args.timeout)
    elif args.timeout == 0:
        os.environ["CAIRN_BRIDGE_TIMEOUT"] = "0"

    if args.offline_grid:
        if args.closed_loop:
            print(
                "[mve_pln_probe] --closed-loop needs live CIP; ignored for offline-grid",
                file=sys.stderr,
            )
        return cip_probe.run_offline_grid(
            probes_root=args.probes_dir,
            focus_caps=coupled.resolve_axis(
                args.focus_cap, args.focus_caps, coupled.DEFAULT_FOCUS_CAP
            ),
            budgets=coupled.resolve_axis(
                args.budget, args.budgets, coupled.DEFAULT_BUDGET
            ),
            seed=args.seed,
            mode=args.mode,
            out=args.out,
        )

    k = coupled.resolve_axis(
        args.focus_cap, None, coupled.DEFAULT_FOCUS_CAP
    )[0]
    b = coupled.resolve_axis(args.budget, None, coupled.DEFAULT_BUDGET)[0]
    return run_mve_with_probes(
        every=args.every,
        focus_cap=k,
        budget=b,
        closed_loop=args.closed_loop,
        wage=args.wage,
        export_only=bool(args.export_only or args.dump_only),
        out=args.out,
    )


if __name__ == "__main__":
    sys.exit(main())
