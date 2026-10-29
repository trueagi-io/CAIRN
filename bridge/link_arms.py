#!/usr/bin/env python3
"""Price weighted and distracted on a finished link pass, then query PLN.

The live mve already spent the fund on the influenced arm. These two arms
open at that period's credit and are not carried forward.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

CAIRN = Path(__file__).resolve().parent.parent
BRIDGE = CAIRN / "bridge"
sys.path.insert(0, str(BRIDGE))

import coupled  # noqa: E402
import link_fund  # noqa: E402


def _bool_cell(value) -> str:
    if value is True or value is False:
        return "true" if value else "false"
    if value is None or value == "":
        return ""
    return str(value)


def _load(path: Path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _account_columns(prefix: str, account: dict, confidence, solved, n_premises, wall_ms) -> dict:
    return {
        f"{prefix}_credit_open": account["credit_open"],
        f"{prefix}_spent": account["spent"],
        f"{prefix}_remainder": account["remainder"],
        f"{prefix}_n_held": account["n_held"],
        f"{prefix}_bound": account["bound"],
        f"{prefix}_suspended": _bool_cell(account["suspended"]),
        f"{prefix}_forgotten": _bool_cell(account["forgotten"]),
        f"{prefix}_confidence": confidence,
        f"{prefix}_solved": solved,
        f"{prefix}_n_premises": n_premises,
        f"{prefix}_wall_ms": wall_ms,
    }


def _query_arm(snap_path: Path, held: list[str], cip: int, arm: str, budget: int, k: int) -> dict:
    """One influenced-only cell whose F is the atoms this arm held."""
    if not held:
        return {"solved": "false", "confidence": "", "n_premises": 0, "wall_ms": ""}
    os.environ["CAIRN_LINK_INFLUENCED_ONLY"] = "1"
    name = f"link_{arm}_cip{cip}"
    rc = coupled.run_steering_cell(
        str(snap_path),
        mode=coupled.DEFAULT_MODE,
        seed=coupled.DEFAULT_SEED,
        budget=budget,
        focus_cap=k,
        name=name,
        focus_atoms=held,
    )
    summary_path = CAIRN / "output" / "cognitive_synergy" / name / "summary.json"
    if not summary_path.is_file():
        return {
            "solved": "",
            "confidence": "",
            "n_premises": "",
            "wall_ms": "",
            "error": f"worker_rc={rc}_no_summary",
        }
    summary = _load(summary_path)
    arm_row = coupled.arm_dict(summary.get("arms") or {}, "influenced")
    fields = coupled.arm_fields_from_summary(summary)
    return {
        "solved": _bool_cell(fields.get("influenced_solved")),
        "confidence": arm_row.get("confidence", ""),
        "n_premises": fields.get("influenced_n_premises", ""),
        "wall_ms": fields.get("influenced_wall_ms", ""),
    }


def price_pass(pass_dir: Path) -> int:
    fund_path = pass_dir / "fund.json"
    table_path = pass_dir / "protocol_probes.csv"
    if not fund_path.is_file() or not table_path.is_file():
        print(f"[link_arms] missing fund or protocol table in {pass_dir}", file=sys.stderr)
        return 2
    fund = _load(fund_path)
    periods = {int(item["cip_index"]): item for item in fund.get("periods") or []}
    admit = bool(fund.get("admit_free"))
    k = int(fund.get("k") or 12)
    with open(table_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for name in link_fund.LINK_FIELDS:
        if name not in fieldnames:
            fieldnames.append(name)

    accounts = pass_dir / "accounts"
    accounts.mkdir(parents=True, exist_ok=True)
    probes = pass_dir / "probes"

    for row in rows:
        try:
            cip = int(float(row.get("cip_index") or 0))
        except (TypeError, ValueError):
            continue
        period = periods.get(cip)
        snap_path = probes / f"cip_{cip}.json"
        if period is None or not snap_path.is_file():
            print(f"[link_arms] cip={cip} missing period or snapshot", file=sys.stderr)
            continue
        snap = _load(snap_path)
        sti = snap.get("sti") or {}
        query = [str(x) for x in ((snap.get("query") or {}).get("objects") or [])]
        opening = float(period["credit_open"])
        budget = int(float(row.get("budget") or 10))
        bank = link_fund.importable_bank(snap)

        weighted = link_fund.price_link(
            link_fund.order_candidates(bank, query, sti),
            sti,
            opening,
            k,
            admit,
        )
        draw = link_fund.distracted_draw(bank, int(period["n_held"]), seed=0, skip=query)
        distracted = link_fund.price_link(
            link_fund.order_candidates(draw, [], sti),
            sti,
            opening,
            k,
            admit,
        )
        weighted_q = _query_arm(snap_path, weighted["held"], cip, "weighted", budget, k)
        distracted_q = _query_arm(snap_path, distracted["held"], cip, "distracted", budget, k)
        row.update(_account_columns(
            "weighted", weighted, weighted_q["confidence"],
            weighted_q["solved"], weighted_q["n_premises"], weighted_q["wall_ms"],
        ))
        row.update(_account_columns(
            "distracted", distracted, distracted_q["confidence"],
            distracted_q["solved"], distracted_q["n_premises"], distracted_q["wall_ms"],
        ))
        inf = str(row.get("influenced_solved") or "").lower()
        dist = str(distracted_q["solved"] or "").lower()
        if inf in ("true", "false") and dist in ("true", "false"):
            row["influenced_beats_distracted"] = "true" if inf == "true" and dist == "false" else "false"
        (accounts / f"cip_{cip}.json").write_text(
            json.dumps(
                {"cip_index": cip, "weighted": {**weighted, **weighted_q}, "distracted": {**distracted, **distracted_q}},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            f"[link_arms] cip={cip} W held={weighted['n_held']} solved={weighted_q['solved']} "
            f"D held={distracted['n_held']} solved={distracted_q['solved']}"
        )

    with open(table_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[link_arms] wrote {table_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline weighted and distracted arms for a link pass")
    parser.add_argument("--pass", dest="pass_dir", required=True, help="link pass directory")
    args = parser.parse_args()
    root = Path(args.pass_dir)
    if not root.is_absolute():
        root = CAIRN / root
    return price_pass(root)


if __name__ == "__main__":
    sys.exit(main())
