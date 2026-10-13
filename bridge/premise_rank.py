#!/usr/bin/env python3
"""Rank premises inside the Real Focus and re-query PLN on the closed export.

C_Q ∧ F keeps every dualized table with a leg in the query and in F. Cap k
does not order those tables. This sweep ranks them by the STI of the leg
outside C_Q (a direct query edge, with both legs in C_Q, ranks by the lower
of those two STIs) and admits a prefix. A target width never splits an STI
tie: the realized set grows to the end of the band that crosses the target.

Top is that order. Bottom is the reverse order, same rule. The full filter
is one extra query per snapshot, so a prefix that solves can be read against
the unranked aperture. W and D are not re-run.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

CAIRN = Path(__file__).resolve().parent.parent
PETTA = CAIRN.parent / "PeTTa" / "run.sh"
BRIDGE = CAIRN / "bridge"
sys.path.insert(0, str(BRIDGE))

from scenario_from_snapshot import (  # noqa: E402
    _stv_from_sti,
    _top_focus,
    safe_sym,
)

DEFAULT_RANKS = [1, 2, 3, 6, 12]
SENTENCE_CONF = 0.9
RANK_FIELDS = [
    "cip_index",
    "query",
    "n_full",
    "end",
    "target_r",
    "n_kept",
    "marginal_sti",
    "solved",
    "confidence",
    "wall_ms",
]


def focus_atoms(snap: dict, focus_cap: int) -> list[str]:
    """Same freeze-F set the scenario generator admits, query atoms retained."""
    sti = {str(k): float(v) for k, v in (snap.get("sti") or {}).items()}
    af = [str(a) for a in (snap.get("af") or [])]
    query = [str(x) for x in ((snap.get("query") or {}).get("objects") or [])][:2]
    ranked = _top_focus(af, sti, focus_cap)
    for atom in query:
        if atom not in ranked and (atom in set(af) or atom in sti):
            if len(ranked) >= focus_cap and ranked:
                ranked = ranked[:-1]
            if atom not in ranked:
                ranked.append(atom)
    return ranked


def kept_premises(snap: dict, focus_cap: int) -> list[dict]:
    """Tables kept by C_Q ∧ F, scored by outside-leg STI."""
    sti = {str(k): float(v) for k, v in (snap.get("sti") or {}).items()}
    focus = set(focus_atoms(snap, focus_cap))
    query = [str(x) for x in ((snap.get("query") or {}).get("objects") or [])][:2]
    qset = set(query)
    rows: list[dict] = []
    for idx, edge in enumerate(snap.get("edges") or [], start=1):
        if not isinstance(edge, (list, tuple)) or len(edge) < 2:
            continue
        a, b = str(edge[0]), str(edge[1])
        weight = float(edge[2]) if len(edge) >= 3 else 0.5
        legs = (a, b)
        if not any(leg in qset and leg in focus for leg in legs):
            continue
        outside = [leg for leg in legs if leg not in qset]
        if outside:
            score = max(sti.get(leg, 0.0) for leg in outside)
        else:
            score = min(sti.get(a, 0.0), sti.get(b, 0.0))
        # Four decimals keeps real STI gaps and drops binary residue, so a
        # tie is one attention band rather than a split float.
        score = round(score, 4)
        rows.append(
            {
                "stamp": idx,
                "src": a,
                "tgt": b,
                "weight": weight,
                "score": score,
            }
        )
    return rows


def prefix_for_width(rows: list[dict], target: int, *, bottom: bool) -> list[dict]:
    """Shortest STI band-prefix whose size is at least target.

    Equal scores stay together. bottom=True walks the low-STI end.
    """
    if not rows or target >= len(rows):
        return list(rows)
    ordered = sorted(rows, key=lambda row: row["score"], reverse=not bottom)
    chosen: list[dict] = []
    band: list[dict] = []
    band_score = None
    for row in ordered:
        if band and row["score"] != band_score:
            chosen.extend(band)
            if len(chosen) >= target:
                return chosen
            band = []
        band.append(row)
        band_score = row["score"]
    chosen.extend(band)
    return chosen


def _query_objects(snap: dict) -> list[str]:
    return [str(x) for x in ((snap.get("query") or {}).get("objects") or [])][:2]


def _kb_expr(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        strength = max(0.05, min(0.95, float(row["weight"])))
        src, tgt = safe_sym(row["src"]), safe_sym(row["tgt"])
        lines.append(
            f"(Sentence ((Inheritance {src} {tgt}) (stv {strength} {SENTENCE_CONF})) ({row['stamp']}))"
        )
    body = "\n    ".join(lines) if lines else ""
    return f"(\n    {body}\n)" if body else "()"


def _prior_lines(snap: dict) -> str:
    sti = {str(k): float(v) for k, v in (snap.get("sti") or {}).items()}
    nodes = set(sti)
    for edge in snap.get("edges") or []:
        if isinstance(edge, (list, tuple)) and len(edge) >= 2:
            nodes.add(str(edge[0]))
            nodes.add(str(edge[1]))
    values = [sti.get(node, 0.0) for node in nodes] or [0.0]
    lo, hi = min(values), max(values)
    lines = []
    for node in sorted(nodes):
        strength, conf = _stv_from_sti(sti.get(node, 0.0), lo, hi)
        lines.append(f"(= (STV {safe_sym(node)}) (stv {strength} {conf}))")
    return "\n".join(lines)


def _metta_src(snap: dict, jobs: list[tuple[str, int, list[dict]]], budget: int) -> str:
    query = _query_objects(snap)
    term = f"(Inheritance {safe_sym(query[0])} {safe_sym(query[1])})"
    parts = [
        "!(import! &self boot)",
        "!(import! &self (library lib_pln))",
        _prior_lines(snap),
    ]
    for end, target, rows in jobs:
        kept = len(rows)
        parts.append(
            "!(let $ans (PLN.Query "
            f"{_kb_expr(rows)} {term} {int(budget)})\n"
            f"     (println! (rank-result {end} {int(target)} {kept} $ans)))"
        )
    return "\n".join(parts) + "\n"


_RESULT_RE = re.compile(
    r"\(rank-result\s+(\w+)\s+(\d+)\s+(\d+)\s+(.*)\)\s*$"
)
_STV_RE = re.compile(r"\(stv\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\)")


def _parse_results(stdout: str) -> dict[tuple[str, int, int], tuple[bool, float]]:
    found: dict[tuple[str, int, int], tuple[bool, float]] = {}
    for line in stdout.splitlines():
        text = line.strip()
        match = _RESULT_RE.match(text)
        if not match:
            continue
        end, target, kept = match.group(1), int(match.group(2)), int(match.group(3))
        stv = _STV_RE.search(match.group(4))
        if stv:
            found[(end, target, kept)] = (True, float(stv.group(2)))
        else:
            found[(end, target, kept)] = (False, 0.0)
    return found


def _run_petta(src: str, timeout_s: float) -> tuple[str, str, int]:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".metta", dir=BRIDGE, delete=False
    ) as handle:
        handle.write(src)
        path = Path(handle.name)
    try:
        proc = subprocess.run(
            ["bash", str(PETTA), f"bridge/{path.name}"],
            cwd=str(CAIRN),
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
    finally:
        path.unlink(missing_ok=True)
    return proc.stdout or "", proc.stderr or "", proc.returncode


def _specs(
    rows: list[dict], targets: list[int]
) -> list[tuple[str, int, list[dict]]]:
    """Every reported row. Full is the unranked filter. Repeated sets stay."""
    specs: list[tuple[str, int, list[dict]]] = [("full", len(rows), list(rows))]
    for end, bottom in (("top", False), ("bottom", True)):
        for target in targets:
            specs.append((end, int(target), prefix_for_width(rows, target, bottom=bottom)))
    return specs


def _query_jobs(
    specs: list[tuple[str, int, list[dict]]]
) -> list[tuple[str, int, list[dict]]]:
    """One PLN call per distinct (label, width, premise set)."""
    seen: set[tuple] = set()
    jobs: list[tuple[str, int, list[dict]]] = []
    for end, target, chosen in specs:
        ident = (end, target, tuple(sorted(row["stamp"] for row in chosen)))
        if ident in seen:
            continue
        seen.add(ident)
        jobs.append((end, target, chosen))
    return jobs


def run_premise_rank_sweep(
    probes_root: Optional[str | Path] = None,
    ranks: Optional[list[int]] = None,
    focus_cap: int = 12,
    budget: int = 10,
    out: Optional[str] = None,
    timeout_s: float = 180.0,
    cips: Optional[list[int]] = None,
) -> int:
    """Re-query ranked prefixes of C_Q ∧ F on saved CIP snapshots."""
    import cip_probe

    targets = [max(1, int(r)) for r in (ranks or DEFAULT_RANKS)]
    root = Path(probes_root) if probes_root else cip_probe.probes_dir()
    if not root.is_absolute():
        root = CAIRN / root
    snaps = cip_probe.list_probe_snapshots(root)
    if cips:
        wanted = {int(i) for i in cips}
        snaps = [(i, path) for i, path in snaps if i in wanted]
    if not snaps:
        print(f"[premise_rank] no cip_*.json under {root}", file=sys.stderr)
        return 2

    dest = Path(out) if out else CAIRN / "output" / "cognitive_synergy" / "b4_premise_rank"
    if not dest.is_absolute():
        dest = CAIRN / dest
    dest.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    n_fail = 0
    for cip_index, path in snaps:
        with open(path, encoding="utf-8") as handle:
            snap = json.load(handle)
        rows = kept_premises(snap, focus_cap)
        query = "Inheritance " + " ".join(_query_objects(snap))
        specs = _specs(rows, targets)
        jobs = _query_jobs(specs)
        print(
            f"[premise_rank] cip={cip_index} n={len(rows)} "
            f"queries={len(jobs)} targets={targets}"
        )
        started = time.perf_counter()
        stdout, stderr, rc = _run_petta(_metta_src(snap, jobs, budget), timeout_s)
        elapsed = (time.perf_counter() - started) * 1000.0
        parsed = _parse_results(stdout)
        if rc:
            n_fail += 1
            tail = (stderr or stdout)[-1500:]
            print(f"[premise_rank] cip={cip_index} rc={rc}\n{tail}", file=sys.stderr)
        for end, target, chosen in specs:
            key = (end, target, len(chosen))
            solved, confidence = parsed.get(key, (False, 0.0))
            if key not in parsed:
                n_fail += 1
                print(f"[premise_rank] missing result {key} cip={cip_index}", file=sys.stderr)
            scores = [row["score"] for row in chosen]
            marginal = min(scores) if end != "bottom" and scores else (max(scores) if scores else 0.0)
            if end == "bottom" and scores:
                marginal = max(scores)
            records.append(
                {
                    "cip_index": cip_index,
                    "query": query,
                    "n_full": len(rows),
                    "end": end,
                    "target_r": target if end != "full" else len(rows),
                    "n_kept": len(chosen),
                    "marginal_sti": f"{marginal:.6f}",
                    "solved": "true" if solved else "false",
                    "confidence": confidence,
                    "wall_ms": f"{elapsed:.1f}",
                }
            )
            print(
                f"  {end:6} r={target:<3} n={len(chosen):<3} "
                f"solved={solved} conf={confidence}"
            )

    csv_path = dest / "rank_sweep.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RANK_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    print(f"[premise_rank] wrote {csv_path}")
    return 0 if n_fail == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rank premises inside C_Q ∧ F")
    parser.add_argument("--probes-dir", default="output/mve/probes")
    parser.add_argument("--ranks", default="1,2,3,6,12")
    parser.add_argument("--focus-cap", type=int, default=12)
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--out", default="output/cognitive_synergy/b4_premise_rank")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--cips", default=None, help="comma list of CIP indices")
    args = parser.parse_args(argv)
    ranks = [int(part) for part in str(args.ranks).split(",") if part.strip()]
    cips = None
    if args.cips:
        cips = [int(part) for part in str(args.cips).split(",") if part.strip()]
    return run_premise_rank_sweep(
        probes_root=args.probes_dir,
        ranks=ranks,
        focus_cap=args.focus_cap,
        budget=args.budget,
        out=args.out,
        timeout_s=args.timeout,
        cips=cips,
    )


if __name__ == "__main__":
    sys.exit(main())
