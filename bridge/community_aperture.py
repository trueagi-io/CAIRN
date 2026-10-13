#!/usr/bin/env python3
"""Cut C_Q ∧ F by the whole-bank Louvain partition and re-query PLN.

The live closed loop still admits the unranked filter. This sweep reads the
capped probe plus the sibling cip_N.hebbian.json recorded on that pass,
partitions the full bank with utils.identify_modules (resolution 1.01,
seed 42), and queries three apertures: the full filter, the intra-community
premises, and the inter-community premises. The first high-STI band is
queried once and labeled by the same cut.

A missing sidecar stops the sweep. Louvain is not run on the 200-edge export.
W and D are not re-run. An empty intra or inter arm is not sent to PLN.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Optional

CAIRN = Path(__file__).resolve().parent.parent
BRIDGE = CAIRN / "bridge"
TOOLS = CAIRN / "tools"
sys.path.insert(0, str(BRIDGE))
sys.path.insert(0, str(TOOLS))

import premise_rank  # noqa: E402
from utils import identify_modules  # noqa: E402

SIDES = ("intra", "inter", "bridge", "unassigned")
ARM_ORDER = ("full", "intra", "inter", "band")

FIELDS = [
    "cip_index",
    "query",
    "query_m0",
    "query_m1",
    "query_one_community",
    "skip_reason",
    "n_hebbian",
    "n_modules",
    "n_full",
    "n_intra",
    "n_inter",
    "n_bridge",
    "n_unassigned",
    "full_solved",
    "full_confidence",
    "intra_solved",
    "intra_confidence",
    "inter_solved",
    "inter_confidence",
    "band_n",
    "band_intra",
    "band_inter",
    "band_bridge",
    "band_unassigned",
    "band_solved",
    "band_confidence",
    "wall_ms",
]


def membership_from_modules(modules: list) -> dict[str, int]:
    """Index is only a label within this CIP's community list."""
    membership: dict[str, int] = {}
    for index, community in enumerate(modules or []):
        for atom in community:
            membership[str(atom)] = index
    return membership


def query_state(
    query: list[str], membership: dict[str, int]
) -> tuple[list[Optional[int]], bool, str]:
    """Indices of the two query atoms, whether they share one, and a skip reason.

    A query atom absent from the Hebbian graph has no community. The cut is
    skipped and every premise is unassigned. The full filter is still queried.
    """
    indices = [membership.get(atom) for atom in query]
    if len(query) < 2 or any(index is None for index in indices):
        return indices, False, "query_unassigned"
    return indices, indices[0] == indices[1], ""


def label_premise(
    src: str,
    tgt: str,
    query: list[str],
    membership: dict[str, int],
    skip_reason: str,
) -> str:
    """Intra, inter, bridge, or unassigned. See the module docstring."""
    if skip_reason:
        return "unassigned"
    qset = set(query)
    q_legs = [leg for leg in (src, tgt) if leg in qset]
    outside = [leg for leg in (src, tgt) if leg not in qset]
    one = membership[query[0]] == membership[query[1]]
    if not q_legs:
        return "unassigned"
    if not outside:
        if len(q_legs) < 2:
            return "unassigned"
        return "intra" if one else "bridge"
    if any(leg not in membership for leg in outside) or any(
        leg not in membership for leg in q_legs
    ):
        return "unassigned"
    if one:
        module = membership[query[0]]
        if all(membership[leg] == module for leg in outside):
            return "intra"
        if all(membership[leg] != module for leg in outside):
            return "inter"
        return "unassigned"
    if any(membership[leg] == membership[qleg] for leg in outside for qleg in q_legs):
        return "intra"
    return "inter"


def label_rows(
    rows: list[dict], query: list[str], membership: dict[str, int]
) -> tuple[dict[int, str], list[Optional[int]], bool, str]:
    indices, one, reason = query_state(query, membership)
    labels = {
        int(row["stamp"]): label_premise(
            str(row["src"]), str(row["tgt"]), query, membership, reason
        )
        for row in rows
    }
    return labels, indices, one, reason


def side_counts(rows: list[dict], labels: dict[int, str]) -> dict[str, int]:
    counts = {side: 0 for side in SIDES}
    for row in rows:
        counts[labels[int(row["stamp"])]] += 1
    return counts


def _side(rows: list[dict], labels: dict[int, str], side: str) -> list[dict]:
    return [row for row in rows if labels[int(row["stamp"])] == side]


def cip4_followup_sets(
    rows: list[dict], labels: dict[int, str]
) -> list[tuple[str, list[dict]]]:
    """Full filter, each pure arm, the tied top band, and each member of it.

    band_a and band_b are ordered by stamp. The tie means neither outranks
    the other.
    """
    band = premise_rank.prefix_for_width(rows, 1, bottom=False)
    sets = [
        ("full", list(rows)),
        ("intra", _side(rows, labels, "intra")),
        ("inter", _side(rows, labels, "inter")),
        ("band", list(band)),
    ]
    for offset, row in enumerate(sorted(band, key=lambda item: int(item["stamp"]))):
        sets.append((f"band_{chr(ord('a') + offset)}", [row]))
    return sets


def cip5_followup_sets(
    rows: list[dict], labels: dict[int, str]
) -> list[tuple[str, list[dict]]]:
    """Full filter, the bridge, the filter without it, and the top inter band.

    The inter band keeps every inter premise tied for the highest outside-leg
    STI. One member of that tie is not split off.
    """
    inter = _side(rows, labels, "inter")
    return [
        ("full", list(rows)),
        ("bridge", _side(rows, labels, "bridge")),
        (
            "full_minus_bridge",
            [row for row in rows if labels[int(row["stamp"])] != "bridge"],
        ),
        ("inter_band", premise_rank.prefix_for_width(inter, 1, bottom=False)),
        ("intra", _side(rows, labels, "intra")),
    ]


def cip5_budget_sets(
    rows: list[dict], labels: dict[int, str]
) -> list[tuple[str, list[dict]]]:
    """Full filter, the bridge, the inter arm, and the filter without the bridge."""
    return [
        ("full", list(rows)),
        ("bridge", _side(rows, labels, "bridge")),
        ("inter", _side(rows, labels, "inter")),
        (
            "full_minus_bridge",
            [row for row in rows if labels[int(row["stamp"])] != "bridge"],
        ),
    ]


def named_jobs(
    sets: list[tuple[str, list[dict]]]
) -> list[tuple[str, list[dict]]]:
    """One PLN call per non-empty distinct premise set, in the given order."""
    seen: set[tuple] = set()
    jobs: list[tuple[str, list[dict]]] = []
    for name, rows in sets:
        if not rows:
            continue
        ident = tuple(sorted(int(row["stamp"]) for row in rows))
        if ident in seen:
            continue
        seen.add(ident)
        jobs.append((name, rows))
    return jobs


# B=10 cells already reported. A mismatch stops interpretation of the new cells.
_ANCHORS = {
    (4, 10, "full"): (True, 0.4736842105263158),
    (4, 10, "band"): (True, 0.4736842105263158),
    (4, 10, "intra"): (False, 0.0),
    (4, 10, "inter"): (False, 0.0),
    (5, 10, "full"): (True, 0.9),
    (5, 10, "bridge"): (True, 0.9),
    (5, 10, "intra"): (False, 0.0),
    (5, 10, "inter"): (True, 0.4736842105263158),
    (5, 10, "full_minus_bridge"): (False, 0.0),
}


def anchor_ok(cip: int, budget: int, arm: str, solved: Optional[bool], confidence) -> bool:
    expected = _ANCHORS.get((cip, budget, arm))
    if expected is None or solved is None:
        return expected is None
    want_solved, want_conf = expected
    if bool(solved) != want_solved:
        return False
    try:
        got = float(confidence)
    except (TypeError, ValueError):
        return False
    return abs(got - want_conf) < 1e-9


def query_jobs(arms: dict[str, list[dict]]) -> list[tuple[str, list[dict]]]:
    """One PLN call per non-empty distinct premise set. Empty arms are omitted.

    ARM_ORDER decides which name owns a shared set, so a band that equals the
    full filter reuses that query.
    """
    seen: set[tuple] = set()
    jobs: list[tuple[str, list[dict]]] = []
    for name in ARM_ORDER:
        rows = arms.get(name) or []
        if not rows:
            continue
        ident = tuple(sorted(int(row["stamp"]) for row in rows))
        if ident in seen:
            continue
        seen.add(ident)
        jobs.append((name, rows))
    return jobs


def _hebbian_path(probe: Path, cip_index: int) -> Path:
    return probe.parent / f"cip_{cip_index}.hebbian.json"


def _blank(solved: Optional[bool], confidence: Optional[float]) -> tuple[str, str]:
    if solved is None:
        return "", ""
    return ("true" if solved else "false"), confidence


def _lookup(
    parsed: dict, jobs: list[tuple[str, list[dict]]], rows: list[dict]
) -> tuple[Optional[bool], Optional[float], bool]:
    """Return solved, confidence, and whether the result line was missing.

    An empty premise list was not queried: solved is None.
    """
    if not rows:
        return None, None, False
    ident = tuple(sorted(int(row["stamp"]) for row in rows))
    owner = None
    for name, chosen in jobs:
        if tuple(sorted(int(row["stamp"]) for row in chosen)) == ident:
            owner = name
            break
    if owner is None:
        return False, 0.0, True
    key = (owner, len(rows), len(rows))
    if key not in parsed:
        return False, 0.0, True
    solved, confidence = parsed[key]
    return solved, confidence, False


def run_community_sweep(
    probes_root: Optional[str | Path] = None,
    focus_cap: int = 12,
    budget: int = 10,
    out: Optional[str] = None,
    timeout_s: float = 180.0,
    cips: Optional[list[int]] = None,
) -> int:
    """Re-query community cuts of C_Q ∧ F on saved CIP snapshots."""
    import cip_probe

    root = Path(probes_root) if probes_root else cip_probe.probes_dir()
    if not root.is_absolute():
        root = CAIRN / root
    snaps = cip_probe.list_probe_snapshots(root)
    if cips:
        wanted = {int(i) for i in cips}
        snaps = [(i, path) for i, path in snaps if i in wanted]
    if not snaps:
        print(f"[community_aperture] no cip_*.json under {root}", file=sys.stderr)
        return 2

    missing = [i for i, path in snaps if not _hebbian_path(path, i).is_file()]
    if missing:
        print(
            "[community_aperture] missing hebbian sidecar for cip "
            + ",".join(str(i) for i in missing)
            + f" under {root}",
            file=sys.stderr,
        )
        return 2

    dest = (
        Path(out)
        if out
        else CAIRN / "output" / "cognitive_synergy" / "b4_community_aperture"
    )
    if not dest.is_absolute():
        dest = CAIRN / dest
    dest.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    n_fail = 0
    for cip_index, path in snaps:
        with open(path, encoding="utf-8") as handle:
            snap = json.load(handle)
        with open(_hebbian_path(path, cip_index), encoding="utf-8") as handle:
            bank = json.load(handle)
        bank_edges = bank.get("edges") or []
        modules = identify_modules(bank_edges)
        membership = membership_from_modules(modules)
        rows = premise_rank.kept_premises(snap, focus_cap)
        query = premise_rank._query_objects(snap)
        labels, indices, one, reason = label_rows(rows, query, membership)
        counts = side_counts(rows, labels)
        if sum(counts.values()) != len(rows):
            n_fail += 1
            print(
                f"[community_aperture] cip={cip_index} label identity failed",
                file=sys.stderr,
            )
        band = premise_rank.prefix_for_width(rows, 1, bottom=False)
        band_counts = side_counts(band, labels)
        arms = {
            "full": list(rows),
            "intra": [row for row in rows if labels[int(row["stamp"])] == "intra"],
            "inter": [row for row in rows if labels[int(row["stamp"])] == "inter"],
            "band": list(band),
        }
        jobs = query_jobs(arms)
        print(
            f"[community_aperture] cip={cip_index} n={len(rows)} "
            f"intra={counts['intra']} inter={counts['inter']} "
            f"bridge={counts['bridge']} unassigned={counts['unassigned']} "
            f"modules={len(modules)} hebbian={len(bank_edges)} queries={len(jobs)}"
        )
        parsed: dict = {}
        elapsed = 0.0
        if jobs:
            metta_jobs = [(name, len(chosen), chosen) for name, chosen in jobs]
            started = time.perf_counter()
            stdout, stderr, rc = premise_rank._run_petta(
                premise_rank._metta_src(snap, metta_jobs, budget), timeout_s
            )
            elapsed = (time.perf_counter() - started) * 1000.0
            parsed = premise_rank._parse_results(stdout)
            if rc:
                n_fail += 1
                tail = (stderr or stdout)[-1500:]
                print(
                    f"[community_aperture] cip={cip_index} rc={rc}\n{tail}",
                    file=sys.stderr,
                )
        arm_result: dict[str, tuple[Optional[bool], Optional[float]]] = {}
        for name in ARM_ORDER:
            solved, confidence, missing_line = _lookup(parsed, jobs, arms[name])
            if missing_line:
                n_fail += 1
                print(
                    f"[community_aperture] missing result {name} cip={cip_index}",
                    file=sys.stderr,
                )
            arm_result[name] = (solved, confidence)
            shown = "skip" if solved is None else solved
            print(f"  {name:6} n={len(arms[name]):<4} solved={shown} conf={confidence}")

        def cell(name: str) -> tuple[str, str]:
            return _blank(*arm_result[name])

        full_solved, full_conf = cell("full")
        intra_solved, intra_conf = cell("intra")
        inter_solved, inter_conf = cell("inter")
        band_solved, band_conf = cell("band")
        records.append(
            {
                "cip_index": cip_index,
                "query": "Inheritance " + " ".join(query),
                "query_m0": "" if indices[0] is None else indices[0],
                "query_m1": "" if len(indices) < 2 or indices[1] is None else indices[1],
                "query_one_community": "true" if one else "false",
                "skip_reason": reason,
                "n_hebbian": len(bank_edges),
                "n_modules": len(modules),
                "n_full": len(rows),
                "n_intra": counts["intra"],
                "n_inter": counts["inter"],
                "n_bridge": counts["bridge"],
                "n_unassigned": counts["unassigned"],
                "full_solved": full_solved,
                "full_confidence": full_conf,
                "intra_solved": intra_solved,
                "intra_confidence": intra_conf,
                "inter_solved": inter_solved,
                "inter_confidence": inter_conf,
                "band_n": len(band),
                "band_intra": band_counts["intra"],
                "band_inter": band_counts["inter"],
                "band_bridge": band_counts["bridge"],
                "band_unassigned": band_counts["unassigned"],
                "band_solved": band_solved,
                "band_confidence": band_conf,
                "wall_ms": f"{elapsed:.1f}",
            }
        )

    csv_path = dest / "community_sweep.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    print(f"[community_aperture] wrote {csv_path}")
    return 0 if n_fail == 0 else 1


FOLLOWUP_FIELDS = [
    "cip_index",
    "budget",
    "arm",
    "n",
    "n_intra",
    "n_inter",
    "n_bridge",
    "solved",
    "confidence",
]
FOLLOWUP_SPECS = {
    4: {"budgets": (5, 10, 20), "build": cip4_followup_sets},
    5: {"budgets": (10,), "build": cip5_followup_sets},
}
CIP5_BUDGET_SPECS = {
    5: {"budgets": (5, 10, 20), "build": cip5_budget_sets},
}


def _load_labeled(path: Path, cip_index: int, focus_cap: int):
    with open(path, encoding="utf-8") as handle:
        snap = json.load(handle)
    with open(_hebbian_path(path, cip_index), encoding="utf-8") as handle:
        bank = json.load(handle)
    modules = identify_modules(bank.get("edges") or [])
    membership = membership_from_modules(modules)
    rows = premise_rank.kept_premises(snap, focus_cap)
    query = premise_rank._query_objects(snap)
    labels, _, _, reason = label_rows(rows, query, membership)
    return snap, rows, labels, reason


def run_followup(
    probes_root: Optional[str | Path] = None,
    focus_cap: int = 12,
    out: Optional[str] = None,
    timeout_s: float = 180.0,
    specs: Optional[dict] = None,
    csv_name: str = "followup.csv",
) -> int:
    """Re-query named premise sets on saved banks. specs selects the cells."""
    import cip_probe

    specs = FOLLOWUP_SPECS if specs is None else specs
    root = Path(probes_root) if probes_root else cip_probe.probes_dir()
    if not root.is_absolute():
        root = CAIRN / root
    snaps = {i: path for i, path in cip_probe.list_probe_snapshots(root)}
    missing = [
        i
        for i in specs
        if i not in snaps or not _hebbian_path(snaps[i], i).is_file()
    ]
    if missing:
        print(
            "[community_aperture] followup missing probe or sidecar for cip "
            + ",".join(str(i) for i in missing),
            file=sys.stderr,
        )
        return 2

    dest = (
        Path(out)
        if out
        else CAIRN / "output" / "cognitive_synergy" / "b4_community_followup"
    )
    if not dest.is_absolute():
        dest = CAIRN / dest
    dest.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    n_fail = 0
    n_anchor = 0
    for cip_index, spec in specs.items():
        snap, rows, labels, reason = _load_labeled(snaps[cip_index], cip_index, focus_cap)
        if reason:
            print(
                f"[community_aperture] cip={cip_index} cut skipped: {reason}",
                file=sys.stderr,
            )
            return 2
        sets = spec["build"](rows, labels)
        for budget in spec["budgets"]:
            jobs = named_jobs(sets)
            print(
                f"[community_aperture] followup cip={cip_index} B={budget} "
                f"queries={len(jobs)}"
            )
            metta_jobs = [(name, len(chosen), chosen) for name, chosen in jobs]
            stdout, stderr, rc = premise_rank._run_petta(
                premise_rank._metta_src(snap, metta_jobs, int(budget)), timeout_s
            )
            parsed = premise_rank._parse_results(stdout)
            if rc:
                n_fail += 1
                tail = (stderr or stdout)[-1500:]
                print(
                    f"[community_aperture] cip={cip_index} B={budget} rc={rc}\n{tail}",
                    file=sys.stderr,
                )
            for name, chosen in sets:
                solved, confidence, missing_line = _lookup(parsed, jobs, chosen)
                if missing_line:
                    n_fail += 1
                    print(
                        f"[community_aperture] missing result {name} "
                        f"cip={cip_index} B={budget}",
                        file=sys.stderr,
                    )
                counts = side_counts(chosen, labels) if chosen else {s: 0 for s in SIDES}
                solved_cell, conf_cell = _blank(solved, confidence)
                if not anchor_ok(cip_index, int(budget), name, solved, confidence):
                    n_anchor += 1
                    print(
                        f"[community_aperture] anchor mismatch cip={cip_index} "
                        f"B={budget} {name} solved={solved} conf={confidence}",
                        file=sys.stderr,
                    )
                records.append(
                    {
                        "cip_index": cip_index,
                        "budget": int(budget),
                        "arm": name,
                        "n": len(chosen),
                        "n_intra": counts["intra"],
                        "n_inter": counts["inter"],
                        "n_bridge": counts["bridge"],
                        "solved": solved_cell,
                        "confidence": conf_cell,
                    }
                )
                shown = "skip" if solved is None else solved
                print(f"  {name:20} n={len(chosen):<4} solved={shown} conf={confidence}")

    csv_path = dest / csv_name
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FOLLOWUP_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    print(f"[community_aperture] wrote {csv_path}")
    if n_anchor:
        print(
            f"[community_aperture] {n_anchor} anchor(s) disagree with a reported cell",
            file=sys.stderr,
        )
        return 1
    return 0 if n_fail == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Community cut inside C_Q ∧ F")
    parser.add_argument("--probes-dir", default="output/mve/probes")
    parser.add_argument("--focus-cap", type=int, default=12)
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument(
        "--out", default="output/cognitive_synergy/b4_community_aperture"
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--cips", default=None, help="comma list of CIP indices")
    parser.add_argument(
        "--followup",
        action="store_true",
        help="CIP 4 budgets 5/10/20 and CIP 5 bridge check on saved banks",
    )
    parser.add_argument(
        "--cip5-budget",
        action="store_true",
        help="CIP 5 full, bridge, inter, and full-minus-bridge at budgets 5/10/20",
    )
    args = parser.parse_args(argv)
    cips = None
    if args.cips:
        cips = [int(part) for part in str(args.cips).split(",") if part.strip()]
    if args.followup and args.cip5_budget:
        print(
            "[community_aperture] pass only one of --followup and --cip5-budget",
            file=sys.stderr,
        )
        return 2
    if args.cip5_budget:
        out = args.out
        if out == "output/cognitive_synergy/b4_community_aperture":
            out = "output/cognitive_synergy/b4_community_cip5_budget"
        return run_followup(
            probes_root=args.probes_dir,
            focus_cap=args.focus_cap,
            out=out,
            timeout_s=args.timeout,
            specs=CIP5_BUDGET_SPECS,
            csv_name="cip5_budget.csv",
        )
    if args.followup:
        out = args.out
        if out == "output/cognitive_synergy/b4_community_aperture":
            out = "output/cognitive_synergy/b4_community_followup"
        return run_followup(
            probes_root=args.probes_dir,
            focus_cap=args.focus_cap,
            out=out,
            timeout_s=args.timeout,
        )
    return run_community_sweep(
        probes_root=args.probes_dir,
        focus_cap=args.focus_cap,
        budget=args.budget,
        out=args.out,
        timeout_s=args.timeout,
        cips=cips,
    )


if __name__ == "__main__":
    sys.exit(main())
