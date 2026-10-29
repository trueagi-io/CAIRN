"""Mid-run PLN probes during CIP (B3 schedule of the coupled workshop).

Same kernel as B2 end-of-run: snapshot → freeze-F three-arm steering
(see bridge/coupled.py). Called from MeTTa when CAIRN_PLN_PROBE=1.
Does not load lib_pln in the CIP process.

Env (set by mve_pln_probe.py):
  CAIRN_PLN_PROBE=1
  CAIRN_PLN_PROBE_EVERY=2
  CAIRN_PLN_PROBE_FOCUS_CAP=12
  CAIRN_PLN_PROBE_BUDGET=10
  CAIRN_PLN_PROBE_CLOSED_LOOP=0|1   # B4
  CAIRN_PLN_PROBE_WAGE=200
  CAIRN_PLN_PROBE_OUT=output/cognitive_synergy/mve_pln_probe
  CAIRN_PLN_PROBE_EXPORT_ONLY=0|1   # alias: CAIRN_PLN_PROBE_DUMP_ONLY
  CAIRN_PLN_PROBE_COMMUNITIES=0|1  # also write cip_N.hebbian.json
  CAIRN_PLN_PROBE_LINK=0|1          # priced link; probes live under CAIRN_PLN_PROBE_OUT
  CAIRN_PLN_ENCODER=Inheritance|Implication|Similarity  # binary form of a Hebbian edge
  CAIRN_LINK_ADMIT_FREE=0|1         # open pass admits the tail after the fund suspends
  CAIRN_LINK_INFLUENCED_ONLY=0|1    # unused; weighted and distracted stay on the cell
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

CAIRN = Path(__file__).resolve().parent.parent
BRIDGE = CAIRN / "bridge"
sys.path.insert(0, str(BRIDGE))

import coupled  # noqa: E402
import export_snapshot  # noqa: E402
import link_fund  # noqa: E402
import pln_encoding  # noqa: E402

PROBE_FIELDS = [
    "cip_index",
    "wall_ms",
    "skip_reason",
    "weighted_solved",
    "influenced_solved",
    "distracted_solved",
    "influenced_beats_distracted",
    "weighted_n_premises",
    "influenced_n_premises",
    "distracted_n_premises",
    "weighted_wall_ms",
    "influenced_wall_ms",
    "distracted_wall_ms",
    "influenced_faster_than_distracted",
    "query_af_overlap",
    "focus_size",
    "budget",
    "focus_cap",
    "query",
    "n_waged",
    "wage_applied",
    "wage_method",
    "snapshot_path",
    "summary_path",
    "written_at",
]


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def probe_enabled() -> bool:
    return _env_truthy("CAIRN_PLN_PROBE")


def communities_enabled() -> bool:
    """MeTTa gate: dump the whole Hebbian bank beside the capped probe."""
    return _env_truthy("CAIRN_PLN_PROBE_COMMUNITIES")


def record_hebbian(cip_index, edges) -> bool:
    """Write cip_{i}.hebbian.json. Louvain runs later, offline.

    The live PLN cell keeps reading cip_{i}.json. A dump error is printed
    and swallowed so the closed trajectory still finishes.
    """
    if not communities_enabled():
        return False
    try:
        i = int(float(cip_index))
    except (TypeError, ValueError):
        print(f"[cip_probe] hebbian skip bad cip {cip_index!r}", file=sys.stderr)
        return False
    try:
        triples = export_snapshot._edge_list(edges)
        path = probes_dir() / f"cip_{i}.hebbian.json"
        payload = {"cip_index": i, "n_edges": len(triples), "edges": triples}
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"[cip_probe] cip={cip_index} hebbian dump failed: {exc}", file=sys.stderr)
        return False
    print(f"[cip_probe] cip={i} hebbian n_edges={len(triples)} → {path.name}")
    return True


def every_n() -> int:
    return max(1, _env_int("CAIRN_PLN_PROBE_EVERY", 2))


def focus_cap() -> int:
    return max(2, _env_int("CAIRN_PLN_PROBE_FOCUS_CAP", coupled.DEFAULT_FOCUS_CAP))


def budget() -> int:
    return max(1, _env_int("CAIRN_PLN_PROBE_BUDGET", coupled.DEFAULT_BUDGET))


def closed_loop() -> bool:
    return _env_truthy("CAIRN_PLN_PROBE_CLOSED_LOOP")


def link_enabled() -> bool:
    return _env_truthy("CAIRN_PLN_PROBE_LINK")


def admit_free() -> bool:
    """Open pass: an exhausted link admits the remaining matches for free."""
    return _env_truthy("CAIRN_LINK_ADMIT_FREE")


def release_mode() -> str | None:
    raw = os.environ.get("CAIRN_LINK_RELEASE", "").strip().lower()
    if not raw:
        return None
    if raw not in link_fund.RELEASE_MODES:
        print(f"[cip_probe] ignoring unknown release mode {raw!r}", file=sys.stderr)
        return None
    return raw


def wage_amount() -> float:
    return _env_float("CAIRN_PLN_PROBE_WAGE", 200.0)


def export_only() -> bool:
    """Export attention snapshots only (no PLN). Same idea as B2 --export-only."""
    return _env_truthy("CAIRN_PLN_PROBE_EXPORT_ONLY") or _env_truthy(
        "CAIRN_PLN_PROBE_DUMP_ONLY"
    )


# Back-compat name
dump_only = export_only


def out_dir() -> Path:
    rel = os.environ.get("CAIRN_PLN_PROBE_OUT", "output/cognitive_synergy/mve_pln_probe")
    p = Path(rel)
    if not p.is_absolute():
        p = CAIRN / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def probes_dir() -> Path:
    # Link passes keep their own probes. The shared mve dir is the B4 export.
    p = (out_dir() / "probes") if link_enabled() else (CAIRN / "output" / "mve" / "probes")
    p.mkdir(parents=True, exist_ok=True)
    return p


def wage_dir() -> Path:
    p = (out_dir() / "wage") if link_enabled() else (CAIRN / "output" / "mve" / "wage")
    p.mkdir(parents=True, exist_ok=True)
    return p


def fund_path() -> Path:
    return out_dir() / "fund.json"


def probe_fields() -> list[str]:
    if link_enabled():
        return PROBE_FIELDS + link_fund.LINK_FIELDS
    return list(PROBE_FIELDS)


def should_probe(cip_index) -> bool:
    """MeTTa py-call: True if this CIP index should run a probe."""
    if not probe_enabled():
        return False
    try:
        i = int(float(cip_index))
    except (TypeError, ValueError):
        return False
    if i <= 0:
        return False
    return (i % every_n()) == 0


def _probe_snapshot_path(cip_index: int) -> Path:
    return Path(export_snapshot.midrun_snapshot_path(cip_index, probes_dir()))


def _append_probe_row(row: dict) -> None:
    path = out_dir() / "protocol_probes.csv"
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        fields = probe_fields()
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def _bool_cell(v) -> str:
    if v is True or v is False:
        return "true" if v else "false"
    if v is None or v == "":
        return ""
    return str(v)


def run_probe(cip_index, af, sti_pairs, edges) -> Any:
    """Dump snapshot; run shared workshop steering cell; return wage list or ().

    MeTTa: empty list → no wage; non-empty → stimulate those atoms (B4).
    """
    t0 = time.time()
    try:
        i = int(float(cip_index))
    except (TypeError, ValueError):
        return []

    k = focus_cap()
    b = budget()
    row = {
        "cip_index": i,
        "wall_ms": "",
        "skip_reason": "",
        "budget": b,
        "focus_cap": k,
        "n_waged": 0,
        "wage_applied": False,
        "written_at": datetime.now().isoformat(),
    }

    try:
        src = coupled.midrun_source("mve", i)
        # Shared with B2: export_snapshot.write_attention_snapshot
        path = export_snapshot.write_midrun(
            i,
            src,
            af,
            sti_pairs,
            edges,
            probes_dir=str(probes_dir()),
        )
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
        row["snapshot_path"] = coupled.relpath_cairn(path)

        n_af = snap.get("stats", {}).get("n_af", 0)
        n_edges = snap.get("stats", {}).get("n_edges", 0)
        if n_af < 2 or n_edges < 2:
            row["skip_reason"] = f"tiny_graph n_af={n_af} n_edges={n_edges}"
            row["wall_ms"] = int((time.time() - t0) * 1000)
            _append_probe_row(row)
            print(f"[cip_probe] cip={i} skip {row['skip_reason']}")
            return []

        if export_only():
            row["skip_reason"] = "export_only"
            row["wall_ms"] = int((time.time() - t0) * 1000)
            _append_probe_row(row)
            print(f"[cip_probe] cip={i} export-only → {row['snapshot_path']}")
            return []

        # Same kernel as B2: freeze-f cell with stable k/B name.
        # The priced link queries the influenced arm on the atoms it held.
        held: list[str] | None = None
        account: dict | None = None
        if link_enabled():
            query = [str(x) for x in ((snap.get("query") or {}).get("objects") or [])]
            ordered = link_fund.order_candidates(snap.get("af") or [], query, snap.get("sti") or {})
            doc = link_fund.load_fund(fund_path())
            if doc is None or doc.get("remainder") is None:
                opening = link_fund.focus_mass(snap.get("af") or [], snap.get("sti") or {})
                owned: list[str] = []
            else:
                opening = float(doc["remainder"])
                owned = [str(atom) for atom in (doc.get("owned") or [])]
            present = link_fund.importable_bank(snap)
            for atom in query:
                if atom not in present:
                    present.append(atom)
            account = link_fund.price_link(
                ordered,
                snap.get("sti") or {},
                opening,
                k,
                admit_free(),
                owned=owned,
                release=release_mode(),
                query=query,
                present=present,
            )
            held = list(account["held"])
            print(
                f"[cip_probe] cip={i} link open={opening:.4g} held={account['n_held']} "
                f"kept={account['n_retained']} bought={account['n_bought']} "
                f"released={account['n_released']} free={account['n_free']} "
                f"bound={account['bound']} suspended={account['suspended']}"
            )

        cname = coupled.midrun_cell_name(
            "mve", i, mode=coupled.DEFAULT_MODE, focus_cap=k, budget=b
        )
        cell_out = out_dir() / "cells" / f"cip_{i}"
        cell_out.mkdir(parents=True, exist_ok=True)

        summary: dict = {}
        if account is not None and account["forgotten"]:
            row["influenced_solved"] = "false"
            row["influenced_n_premises"] = 0
        else:
            rc = coupled.run_steering_cell(
                path,
                mode=coupled.DEFAULT_MODE,
                seed=coupled.DEFAULT_SEED,
                budget=b,
                focus_cap=k,
                name=cname,
                focus_atoms=held,
            )
            src_summary = CAIRN / "output" / "cognitive_synergy" / cname / "summary.json"
            dst_summary = cell_out / "summary.json"
            if src_summary.is_file():
                shutil.copy2(src_summary, dst_summary)
                row["summary_path"] = str(dst_summary.relative_to(CAIRN))
                with open(src_summary, encoding="utf-8") as f:
                    summary = json.load(f)
            else:
                row["skip_reason"] = f"worker_rc={rc}_no_summary"

        fields = coupled.arm_fields_from_summary(summary)
        row.update(
            {
                "weighted_solved": _bool_cell(fields.get("weighted_solved")),
                "influenced_solved": _bool_cell(fields.get("influenced_solved")),
                "distracted_solved": _bool_cell(fields.get("distracted_solved")),
                "influenced_beats_distracted": _bool_cell(
                    fields.get("influenced_beats_distracted")
                ),
                "weighted_n_premises": fields.get("weighted_n_premises", ""),
                "influenced_n_premises": fields.get("influenced_n_premises", ""),
                "distracted_n_premises": fields.get("distracted_n_premises", ""),
                "weighted_wall_ms": fields.get("weighted_wall_ms", ""),
                "influenced_wall_ms": fields.get("influenced_wall_ms", ""),
                "distracted_wall_ms": fields.get("distracted_wall_ms", ""),
                "influenced_faster_than_distracted": _bool_cell(
                    fields.get("influenced_faster_than_distracted")
                ),
                "query_af_overlap": fields.get("query_af_overlap", ""),
                "focus_size": fields.get("focus_size", ""),
                "query": fields.get("query", ""),
            }
        )
        if link_enabled():
            arms = summary.get("arms") or {}
            for arm_name in ("weighted", "influenced", "distracted"):
                row[f"{arm_name}_confidence"] = coupled.arm_dict(arms, arm_name).get(
                    "confidence", ""
                )
        if account is not None and account["forgotten"]:
            row["influenced_solved"] = "false"
            row["influenced_n_premises"] = 0

        wage_atoms: list[str] = []
        wage_meta: dict = {}
        if closed_loop() and fields.get("influenced_solved"):
            # Prefer original CIP names via probe snapshot + proof stamps (B4.1)
            wage_meta = coupled.wage_atoms_from_steering(summary, snap)
            wage_atoms = list(wage_meta.get("atoms") or [])
            wpath = wage_dir() / f"cip_{i}_wage.json"
            with open(wpath, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "cip_index": i,
                        "atoms": wage_atoms,
                        "wage": wage_amount(),
                        "method": wage_meta.get("method"),
                        "stamps": wage_meta.get("stamps"),
                        "cell": cname,
                    },
                    f,
                    indent=2,
                )
                f.write("\n")
            row["n_waged"] = len(wage_atoms)
            row["wage_applied"] = bool(wage_atoms)
            row["wage_method"] = wage_meta.get("method", "")

        if account is not None:
            added = link_fund.wage_credit(len(wage_atoms), wage_amount()) if wage_atoms else 0.0
            _record_link_period(i, account, added, bool(wage_atoms))
            row["credit_open"] = account["credit_open"]
            row["spent"] = account["spent"]
            row["remainder"] = account["remainder"]
            row["n_held"] = account["n_held"]
            row["bound"] = account["bound"]
            row["suspended"] = _bool_cell(account["suspended"])
            row["forgotten"] = _bool_cell(account["forgotten"])
            row["n_free"] = account["n_free"]
            row["n_retained"] = account["n_retained"]
            row["n_bought"] = account["n_bought"]
            row["n_released"] = account["n_released"]
            row["wage_credit"] = added

        row["wall_ms"] = int((time.time() - t0) * 1000)
        _append_probe_row(row)
        print(
            f"[cip_probe] cip={i} cell={cname} inf={row.get('influenced_solved')} "
            f"dist={row.get('distracted_solved')} "
            f"beat={row.get('influenced_beats_distracted')} "
            f"ms={row['wall_ms']} wage={len(wage_atoms)}"
            + (f" method={wage_meta.get('method')}" if wage_meta else "")
        )
        # MeTTa: empty → no stimulate; non-empty → original CIP atom names
        return wage_atoms if wage_atoms else []

    except Exception as e:
        row["skip_reason"] = f"error:{type(e).__name__}:{e}"
        row["wall_ms"] = int((time.time() - t0) * 1000)
        try:
            _append_probe_row(row)
        except OSError:
            pass
        print(f"[cip_probe] cip={i} ERROR {e}", file=sys.stderr)
        return []


def _record_link_period(cip_index: int, account: dict, added: float, paid: bool) -> None:
    """Carry the remainder, including the wage credit, into the next period."""
    path = fund_path()
    doc = link_fund.load_fund(path) or link_fund.fresh_fund(
        admit_free(), wage_amount(), focus_cap()
    )
    period = {
        "cip_index": cip_index,
        "credit_open": account["credit_open"],
        "spent": account["spent"],
        "remainder": account["remainder"],
        "held": account["held"],
        "n_held": account["n_held"],
        "bound": account["bound"],
        "suspended": account["suspended"],
        "forgotten": account["forgotten"],
        "n_free": account["n_free"],
        "n_retained": account["n_retained"],
        "n_bought": account["n_bought"],
        "n_released": account["n_released"],
        "released": account["released"],
        "owned": account["owned"],
        "wage_credit": added,
        "wage_applied": paid,
    }
    periods = [
        item
        for item in (doc.get("periods") or [])
        if int(item.get("cip_index", -1)) != cip_index
    ]
    periods.append(period)
    periods.sort(key=lambda item: int(item["cip_index"]))
    doc["periods"] = periods
    doc["remainder"] = float(account["remainder"]) + float(added)
    doc["owned"] = list(account["owned"])
    doc["release"] = release_mode() or ""
    doc["admit_free"] = admit_free()
    doc["wage"] = wage_amount()
    doc["k"] = focus_cap()
    link_fund.save_fund(path, doc)


def _true_cell(row: dict, *keys) -> bool:
    for k in keys:
        if str(row.get(k, "")).lower() == "true":
            return True
    return False


def finalize_run(
    *,
    focus_caps: Optional[list[int]] = None,
    budgets: Optional[list[int]] = None,
    mode: str = "live",
) -> str:
    """Write summary.json for the probe series (after mve or offline grid)."""
    csv_path = out_dir() / "protocol_probes.csv"
    rows = []
    if csv_path.is_file():
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    n = len(rows)
    inf = sum(1 for r in rows if _true_cell(r, "influenced_solved", "af_solved"))
    dist = sum(1 for r in rows if _true_cell(r, "distracted_solved", "random_solved"))
    wtd = sum(1 for r in rows if _true_cell(r, "weighted_solved", "full_solved"))
    beat = sum(
        1 for r in rows if _true_cell(r, "influenced_beats_distracted", "af_beats_random")
    )
    params = {
        "protocol": "cip_probe",
        "mode": mode,
        "every": every_n() if mode == "live" else None,
        "closed_loop": closed_loop() if mode == "live" else False,
        "n_rows": n,
    }
    if focus_caps is not None:
        params["focus_caps"] = focus_caps
    else:
        params["focus_cap"] = focus_cap()
    if budgets is not None:
        params["budgets"] = budgets
    else:
        params["budget"] = budget()
    summary = {
        "run_timestamp": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat(),
        "parameters": params,
        "rates": {
            "weighted_solve": wtd / n if n else None,
            "influenced_solve": inf / n if n else None,
            "distracted_solve": dist / n if n else None,
            "influenced_beats_distracted": beat / n if n else None,
        },
        "probes_csv": str(csv_path.relative_to(CAIRN)) if csv_path.is_file() else None,
    }
    path = out_dir() / "summary.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")
    print(f"[cip_probe] wrote {path} n_rows={n}")
    return str(path)


def list_probe_snapshots(probes_root: Optional[Path] = None) -> list[tuple[int, Path]]:
    """Return sorted (cip_index, path) for cip_*.json under probes dir."""
    root = Path(probes_root) if probes_root else probes_dir()
    if not root.is_dir():
        return []
    out: list[tuple[int, Path]] = []
    for p in root.glob("cip_*.json"):
        # cip_N.hebbian.json is the full bank, not a probe snapshot.
        if ".hebbian." in p.name or not p.stem.startswith("cip_"):
            continue
        stem = p.stem  # cip_12
        try:
            i = int(stem.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        out.append((i, p))
    out.sort(key=lambda t: t[0])
    return out


def _run_offline_cell(
    snap_path: Path,
    cip_index: int,
    focus_cap_k: int,
    budget_b: int,
    seed: int,
    mode: str,
    link: str | None = None,
) -> dict:
    """One offline workshop cell; return protocol_probes row."""
    t0 = time.time()
    row = {
        "cip_index": cip_index,
        "wall_ms": "",
        "skip_reason": "",
        "budget": budget_b,
        "focus_cap": focus_cap_k,
        "n_waged": 0,
        "wage_applied": False,
        "wage_method": "",
        "snapshot_path": coupled.relpath_cairn(snap_path),
        "written_at": datetime.now().isoformat(),
    }
    try:
        with open(snap_path, encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        row["skip_reason"] = f"bad_snapshot:{e}"
        row["wall_ms"] = int((time.time() - t0) * 1000)
        return row

    n_af = (snap.get("stats") or {}).get("n_af", len(snap.get("af") or []))
    n_edges = (snap.get("stats") or {}).get("n_edges", len(snap.get("edges") or []))
    if n_af < 2 or n_edges < 2:
        row["skip_reason"] = f"tiny_graph n_af={n_af} n_edges={n_edges}"
        row["wall_ms"] = int((time.time() - t0) * 1000)
        return row

    src = snap.get("source") or coupled.midrun_source("mve", cip_index)
    # Prefer mve as base for naming when source is mve_cipN
    base = "mve"
    cname = coupled.midrun_cell_name(
        base, cip_index, mode=mode, focus_cap=focus_cap_k, budget=budget_b
    )
    cell_out = out_dir() / "cells" / f"cip_{cip_index}_k{focus_cap_k}_b{budget_b}"
    cell_out.mkdir(parents=True, exist_ok=True)

    rc = coupled.run_steering_cell(
        str(snap_path),
        mode=mode,
        seed=seed,
        budget=budget_b,
        focus_cap=focus_cap_k,
        link=link,
        name=cname,
    )
    src_summary = CAIRN / "output" / "cognitive_synergy" / cname / "summary.json"
    dst_summary = cell_out / "summary.json"
    if src_summary.is_file():
        shutil.copy2(src_summary, dst_summary)
        row["summary_path"] = str(dst_summary.relative_to(CAIRN))
        with open(src_summary, encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = {}
        row["skip_reason"] = f"worker_rc={rc}_no_summary"

    fields = coupled.arm_fields_from_summary(summary)
    row.update(
        {
            "weighted_solved": _bool_cell(fields.get("weighted_solved")),
            "influenced_solved": _bool_cell(fields.get("influenced_solved")),
            "distracted_solved": _bool_cell(fields.get("distracted_solved")),
            "influenced_beats_distracted": _bool_cell(
                fields.get("influenced_beats_distracted")
            ),
            "weighted_n_premises": fields.get("weighted_n_premises", ""),
            "influenced_n_premises": fields.get("influenced_n_premises", ""),
            "distracted_n_premises": fields.get("distracted_n_premises", ""),
            "weighted_wall_ms": fields.get("weighted_wall_ms", ""),
            "influenced_wall_ms": fields.get("influenced_wall_ms", ""),
            "distracted_wall_ms": fields.get("distracted_wall_ms", ""),
            "influenced_faster_than_distracted": _bool_cell(
                fields.get("influenced_faster_than_distracted")
            ),
            "query_af_overlap": fields.get("query_af_overlap", ""),
            "focus_size": fields.get("focus_size", ""),
            "query": fields.get("query", ""),
        }
    )
    row["wall_ms"] = int((time.time() - t0) * 1000)
    if rc and not row.get("skip_reason"):
        row["skip_reason"] = f"worker_rc={rc}"
    return row


def run_offline_grid(
    probes_root: Optional[str | Path] = None,
    focus_caps: Optional[list[int]] = None,
    budgets: Optional[list[int]] = None,
    seed: int = coupled.DEFAULT_SEED,
    mode: str = coupled.DEFAULT_MODE,
    out: Optional[str] = None,
    link: str | None = None,
) -> int:
    """B3 offline: k×B grid on saved probe snapshots (after --export-only).

    One mve export → many workshop cells without replaying CIP.
    """
    if out:
        os.environ["CAIRN_PLN_PROBE_OUT"] = out
    os.environ.setdefault("CAIRN_PLN_PROBE", "1")

    caps = [max(2, int(k)) for k in (focus_caps or [coupled.DEFAULT_FOCUS_CAP])]
    bs = [max(1, int(b)) for b in (budgets or [coupled.DEFAULT_BUDGET])]
    mode = mode if mode in ("freeze-f", "re-dynamics") else coupled.DEFAULT_MODE

    root = Path(probes_root) if probes_root else probes_dir()
    if not root.is_absolute():
        root = CAIRN / root
    snaps = list_probe_snapshots(root)
    if not snaps:
        print(f"[cip_probe] no cip_*.json under {root}", file=sys.stderr)
        return 2

    total = len(snaps) * len(caps) * len(bs)
    print(
        f"[cip_probe] offline-grid probes={len(snaps)} k={caps} B={bs} "
        f"mode={mode} cells={total} → {out_dir()}"
    )

    rows: list[dict] = []
    i = 0
    n_fail = 0
    for cip_i, snap_path in snaps:
        for k in caps:
            for b in bs:
                i += 1
                print(
                    f"[cip_probe] offline ({i}/{total}) cip={cip_i} k={k} B={b}"
                )
                row = _run_offline_cell(snap_path, cip_i, k, b, seed, mode, link)
                rows.append(row)
                if row.get("skip_reason"):
                    n_fail += 1
                    print(f"  skip {row['skip_reason']}")
                else:
                    print(
                        f"  inf={row.get('influenced_solved')} "
                        f"dist={row.get('distracted_solved')} "
                        f"ms={row.get('wall_ms')}"
                    )

    # Rewrite clean CSV for this offline product
    csv_path = out_dir() / "protocol_probes.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PROBE_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in PROBE_FIELDS})
    print(f"[cip_probe] wrote {csv_path}")

    finalize_run(focus_caps=caps, budgets=bs, mode="offline_grid")
    index = {
        "run_timestamp": datetime.now().isoformat(),
        "probes_dir": coupled.relpath_cairn(root),
        "mode": mode,
        "focus_caps": caps,
        "budgets": bs,
        "seed": seed,
        "n_snapshots": len(snaps),
        "n_cells": len(rows),
        "n_ok": sum(1 for r in rows if not r.get("skip_reason")),
        "n_fail": n_fail,
        "table": str(csv_path.relative_to(CAIRN)),
    }
    ipath = out_dir() / "offline_grid_index.json"
    with open(ipath, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    print(f"[cip_probe] wrote {ipath}")
    return 0 if n_fail == 0 else 1


SEED_FIELDS = [
    "cip_index",
    "seed",
    "query",
    "influenced_solved",
    "distracted_solved",
    "influenced_beats_distracted",
    "influenced_n_premises",
    "distracted_n_premises",
    "influenced_confidence",
    "distracted_confidence",
    "s_equals_focus",
    "query_covered_by_s",
    "s_overlap_focus",
    "skip_reason",
]


def _sym_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value if str(x)]
    return [str(value)]


def _seed_row(cip_index: int, seed: int, summary: dict, skip: str) -> dict:
    """One distracted draw on a fixed snapshot. W and I do not use the seed."""
    params = summary.get("parameters") or {}
    arms = summary.get("arms") or {}
    att = summary.get("attention") or {}
    influenced = arms.get("influenced") or {}
    distracted = arms.get("distracted") or {}
    focus = set(_sym_list(att.get("focus")))
    drawn = set(_sym_list(att.get("distracted_S")))
    query_objs = _sym_list(att.get("query_objects"))
    if not query_objs:
        label = str(params.get("query") or "")
        query_objs = pln_encoding.objects_from_label(label)
    covered = bool(query_objs) and all(q in drawn for q in query_objs)
    fields = coupled.arm_fields_from_summary(summary) if summary else {}
    return {
        "cip_index": cip_index,
        "seed": seed,
        "query": params.get("query", ""),
        "influenced_solved": _bool_cell(fields.get("influenced_solved")),
        "distracted_solved": _bool_cell(fields.get("distracted_solved")),
        "influenced_beats_distracted": _bool_cell(
            fields.get("influenced_beats_distracted")
        ),
        "influenced_n_premises": influenced.get("n_premises", ""),
        "distracted_n_premises": distracted.get("n_premises", ""),
        "influenced_confidence": influenced.get("confidence", ""),
        "distracted_confidence": distracted.get("confidence", ""),
        "s_equals_focus": str(bool(focus) and focus == drawn),
        "query_covered_by_s": str(covered),
        "s_overlap_focus": len(focus & drawn),
        "skip_reason": skip,
    }


def run_seed_sweep(
    probes_root: Optional[str | Path] = None,
    seeds: Optional[list[int]] = None,
    focus_cap: int = coupled.DEFAULT_FOCUS_CAP,
    budget: int = coupled.DEFAULT_BUDGET,
    mode: str = coupled.DEFAULT_MODE,
    out: Optional[str] = None,
    link: str | None = None,
) -> int:
    """Re-draw distracted S on saved CIP snapshots. The export stays fixed.

    Each seed repeats freeze-F steering. Influenced does not depend on the
    seed; the distracted arm does. Seed 0 is the published single-draw cell.
    """
    if out:
        os.environ["CAIRN_PLN_PROBE_OUT"] = out
    os.environ.setdefault("CAIRN_PLN_PROBE", "1")

    seed_list = [int(s) for s in (seeds or [coupled.DEFAULT_SEED])]
    k = max(2, int(focus_cap))
    b = max(1, int(budget))
    mode = mode if mode in ("freeze-f", "re-dynamics") else coupled.DEFAULT_MODE

    root = Path(probes_root) if probes_root else probes_dir()
    if not root.is_absolute():
        root = CAIRN / root
    snaps = list_probe_snapshots(root)
    if not snaps:
        print(f"[cip_probe] no cip_*.json under {root}", file=sys.stderr)
        return 2

    dest = out_dir()
    dest.mkdir(parents=True, exist_ok=True)
    total = len(snaps) * len(seed_list)
    print(
        f"[cip_probe] seed-sweep probes={len(snaps)} seeds={seed_list} "
        f"k={k} B={b} mode={mode} cells={total} → {dest}"
    )

    rows: list[dict] = []
    n_fail = 0
    i = 0
    for cip_i, snap_path in snaps:
        for seed in seed_list:
            i += 1
            print(f"[cip_probe] seed ({i}/{total}) cip={cip_i} seed={seed}")
            cname = coupled.midrun_cell_name(
                "mve", cip_i, mode=mode, focus_cap=k, budget=b
            )
            rc = coupled.run_steering_cell(
                str(snap_path),
                mode=mode,
                seed=seed,
                budget=b,
                focus_cap=k,
                name=cname,
                link=link,
            )
            summary_path = CAIRN / "output" / "cognitive_synergy" / cname / "summary.json"
            summary: dict = {}
            skip = ""
            if summary_path.is_file():
                with open(summary_path, encoding="utf-8") as f:
                    summary = json.load(f)
            else:
                skip = f"worker_rc={rc}_no_summary"
            if rc and not skip:
                skip = f"worker_rc={rc}"
            row = _seed_row(cip_i, seed, summary, skip)
            rows.append(row)
            if skip:
                n_fail += 1
                print(f"  skip {skip}")
            else:
                print(
                    f"  I={row['influenced_solved']} nI={row['influenced_n_premises']} "
                    f"D={row['distracted_solved']} nD={row['distracted_n_premises']} "
                    f"cover={row['query_covered_by_s']} eqF={row['s_equals_focus']} "
                    f"overlap={row['s_overlap_focus']}"
                )

    csv_path = dest / "seed_sweep.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SEED_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({key: row.get(key, "") for key in SEED_FIELDS})
    print(f"[cip_probe] wrote {csv_path}")
    return 0 if n_fail == 0 else 1


def main(argv: Optional[list] = None) -> int:
    """CLI: single snapshot cell, or offline k×B grid over probes/."""
    import argparse

    ap = argparse.ArgumentParser(
        description="B3 offline: workshop cell(s) on probe snapshot(s)"
    )
    ap.add_argument("--snapshot", default=None, help="single probes/cip_N.json")
    ap.add_argument("--cip-index", type=int, default=None)
    ap.add_argument("--focus-cap", type=int, default=None)
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument(
        "--offline-grid",
        action="store_true",
        help="sweep k×B on all cip_*.json under --probes-dir",
    )
    ap.add_argument(
        "--probes-dir",
        default="output/mve/probes",
        help="probe snapshots directory (offline-grid)",
    )
    ap.add_argument(
        "--focus-caps",
        default=None,
        help="comma list of k (offline-grid; default single --focus-cap or 12)",
    )
    ap.add_argument(
        "--budgets",
        default=None,
        help="comma list of B (offline-grid; default single --budget or 10)",
    )
    ap.add_argument("--mode", choices=("freeze-f", "re-dynamics"), default="freeze-f")
    ap.add_argument("--seed", type=int, default=coupled.DEFAULT_SEED)
    ap.add_argument(
        "--seeds",
        default=None,
        help="comma list of distracted-arm seeds; sweeps saved snapshots",
    )
    ap.add_argument(
        "--premise-ranks",
        default=None,
        help="comma list of premise-rank widths inside C_Q and F; sweeps saved snapshots",
    )
    ap.add_argument(
        "--community-aperture",
        action="store_true",
        help="cut C_Q and F by the whole-bank Louvain sidecar; sweeps saved snapshots",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="protocol out dir (default output/cognitive_synergy/mve_pln_probe)",
    )
    args = ap.parse_args(argv)

    if args.out:
        os.environ["CAIRN_PLN_PROBE_OUT"] = args.out

    if args.seeds:
        k = coupled.resolve_axis(
            args.focus_cap, args.focus_caps, coupled.DEFAULT_FOCUS_CAP
        )[0]
        b = coupled.resolve_axis(
            args.budget, args.budgets, coupled.DEFAULT_BUDGET
        )[0]
        return run_seed_sweep(
            probes_root=args.probes_dir,
            seeds=coupled.parse_int_list(args.seeds, [coupled.DEFAULT_SEED]),
            focus_cap=k,
            budget=b,
            mode=args.mode,
            out=args.out,
        )

    if args.premise_ranks:
        import premise_rank

        k = coupled.resolve_axis(
            args.focus_cap, args.focus_caps, coupled.DEFAULT_FOCUS_CAP
        )[0]
        b = coupled.resolve_axis(
            args.budget, args.budgets, coupled.DEFAULT_BUDGET
        )[0]
        return premise_rank.run_premise_rank_sweep(
            probes_root=args.probes_dir,
            ranks=coupled.parse_int_list(args.premise_ranks, premise_rank.DEFAULT_RANKS),
            focus_cap=k,
            budget=b,
            out=args.out,
        )

    if args.community_aperture:
        import community_aperture

        k = coupled.resolve_axis(
            args.focus_cap, args.focus_caps, coupled.DEFAULT_FOCUS_CAP
        )[0]
        b = coupled.resolve_axis(
            args.budget, args.budgets, coupled.DEFAULT_BUDGET
        )[0]
        return community_aperture.run_community_sweep(
            probes_root=args.probes_dir,
            focus_cap=k,
            budget=b,
            out=args.out,
        )

    if args.offline_grid:
        return run_offline_grid(
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

    if not args.snapshot:
        print("need --snapshot PATH or --offline-grid", file=sys.stderr)
        return 2
    k = coupled.resolve_axis(
        args.focus_cap, None, coupled.DEFAULT_FOCUS_CAP
    )[0]
    b = coupled.resolve_axis(args.budget, None, coupled.DEFAULT_BUDGET)[0]
    os.environ["CAIRN_PLN_PROBE"] = "1"
    os.environ["CAIRN_PLN_PROBE_FOCUS_CAP"] = str(k)
    os.environ["CAIRN_PLN_PROBE_BUDGET"] = str(b)
    snap = Path(args.snapshot)
    if not snap.is_file():
        print(f"missing {snap}", file=sys.stderr)
        return 2
    with open(snap, encoding="utf-8") as f:
        data = json.load(f)
    i = args.cip_index if args.cip_index is not None else data.get("cip_index", 0)
    name = coupled.midrun_cell_name("mve", i, mode=args.mode, focus_cap=k, budget=b)
    return coupled.run_steering_cell(
        str(snap),
        mode=args.mode,
        seed=args.seed,
        budget=b,
        focus_cap=k,
        name=name,
    )


if __name__ == "__main__":
    sys.exit(main())
