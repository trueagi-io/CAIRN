"""Shared ECAN–PLN **coupled workshop**: CIP attention → three-arm budgeted PLN.

One measurement kernel; two schedules kept as distinct ladder rungs:

  B2  end-of-run / offline grid   — modes × k × B on a frozen snapshot
  B3  mid-run CIP probes         — same kernel at selected CIP indices

  B4  closed-loop CIP wage       — same mid-run schedule, wage into live CIP

Atomic step (both B2 and B3):
  snapshot AF+edges → generate dualed map → freeze-f|re-dynamics →
  weighted / influenced / distracted under fixed B → summary + wall_ms

Attention export (shared):
  export_snapshot.write_attention_snapshot  schedule=end|midrun
  B2/B3 --export-only → bridge_snapshot.json | probes/cip_{i}.json

Entry points:
  B2  python bridge/mve_bridge.py …
  B3  python bridge/mve_pln_probe.py …   (injects hooks; calls cip_probe → here)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, Union

from scenario_from_snapshot import DEFAULT_FOCUS_CAP, cell_name, safe_sym

# Shared defaults (B2 grid cells and B3 probes)
DEFAULT_BUDGET = 10
DEFAULT_MODE = "freeze-f"
DEFAULT_SEED = 0
DEFAULT_WORKER_TIMEOUT_S = 300.0

CAIRN_ROOT = Path(__file__).resolve().parent.parent

_LEGACY_ARMS = {"weighted": "full", "influenced": "af", "distracted": "random"}


def relpath_cairn(path: Union[str, Path], base: Optional[Path] = None) -> str:
    """Path relative to CAIRN root when possible; else absolute/str."""
    p = Path(path).resolve()
    root = (base or CAIRN_ROOT).resolve()
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def attention_snapshot_ok(path: Union[str, Path]) -> bool:
    """True if path is a usable attention snapshot (end or midrun)."""
    p = Path(path)
    if not p.is_file() or p.stat().st_size < 32:
        return False
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    af = data.get("af")
    edges = data.get("edges")
    return isinstance(af, list) and len(af) > 0 and isinstance(edges, list)


def petta_export_rc(returncode: int, artifact_ok: bool, label: str) -> int:
    """Map PeTTa exit code after an export-only / live mve run.

    Long mve runs sometimes exit non-zero on teardown (notably SIGALRM → rc 142)
    even after snapshots were written successfully. Treat those as success when
    artifacts validate; still fail hard when nothing usable was produced.
    """
    if returncode == 0:
        return 0
    if artifact_ok:
        print(
            f"[{label}] PeTTa rc={returncode} after successful export; "
            "treating as success (known teardown noise, e.g. SIGALRM/142)",
            file=sys.stderr,
        )
        return 0
    print(f"[{label}] failed rc={returncode} (no usable export artifact)", file=sys.stderr)
    return returncode


def parse_int_list(s: Optional[str], default: list[int]) -> list[int]:
    """Parse '5,10,20' → [5,10,20]; empty/None → default."""
    if not s or not str(s).strip():
        return list(default)
    out: list[int] = []
    for part in str(s).split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    return out or list(default)


def resolve_axis(
    single: Optional[int],
    multi: Optional[str],
    default: int,
) -> list[int]:
    """CLI helper: --foo X / --foos a,b,c → list of ints."""
    if multi and str(multi).strip():
        return parse_int_list(multi, [default])
    if single is not None:
        return [int(single)]
    return [default]


def midrun_source(source: str, cip_index: int) -> str:
    """Snapshot source tag for a mid-run probe (feeds cell_name)."""
    src = (source or "mve").strip() or "mve"
    return f"{src}_cip{int(cip_index)}"


def midrun_cell_name(
    source: str,
    cip_index: int,
    mode: str = DEFAULT_MODE,
    focus_cap: int = DEFAULT_FOCUS_CAP,
    budget: int = DEFAULT_BUDGET,
    protocol: str = "steering",
) -> str:
    """Stable dir name for a B3 probe cell — same scheme as B2, with cip index.

    Example: from_mve_cip4_ff_k12_b10
    """
    return cell_name(
        midrun_source(source, cip_index),
        mode,
        focus_cap,
        budget,
        protocol=protocol,
    )


def arm_dict(arms: dict, name: str) -> dict:
    """Resolve arm by canonical name with legacy full/af/random fallback."""
    if not isinstance(arms, dict):
        return {}
    return arms.get(name) or arms.get(_LEGACY_ARMS.get(name, ""), {}) or {}


def arm_fields_from_summary(summary: Optional[dict]) -> dict[str, Any]:
    """Flatten steering summary arms/contrast into probe-row / table fields."""
    summary = summary or {}
    arms = summary.get("arms") or {}
    contrast = summary.get("contrast") or {}
    att = summary.get("attention") or {}
    params = summary.get("parameters") or {}
    timing = summary.get("timing") or {}

    def solved(name: str):
        return arm_dict(arms, name).get("solved")

    def n_prem(name: str):
        return arm_dict(arms, name).get("n_premises", "")

    def wall_ms(name: str):
        a = arm_dict(arms, name)
        leg = _LEGACY_ARMS.get(name, name)
        return a.get(
            "wall_ms",
            timing.get(f"{name}_wall_ms", timing.get(f"{leg}_wall_ms", "")),
        )

    beat = contrast.get("influenced_beats_distracted")
    if beat is None:
        beat = contrast.get("af_beats_random_solve")
    faster = contrast.get("influenced_faster_than_distracted")
    if faster is None:
        faster = contrast.get("af_faster_than_random")

    return {
        "weighted_solved": solved("weighted"),
        "influenced_solved": solved("influenced"),
        "distracted_solved": solved("distracted"),
        "influenced_beats_distracted": beat,
        "weighted_n_premises": n_prem("weighted"),
        "influenced_n_premises": n_prem("influenced"),
        "distracted_n_premises": n_prem("distracted"),
        "weighted_wall_ms": wall_ms("weighted"),
        "influenced_wall_ms": wall_ms("influenced"),
        "distracted_wall_ms": wall_ms("distracted"),
        "influenced_faster_than_distracted": faster,
        "query_af_overlap": att.get("query_af_overlap", contrast.get("query_af_overlap", "")),
        "focus_size": len(att.get("focus") or []),
        "query": params.get("query", ""),
    }


def run_steering_cell(
    snapshot_path: str,
    *,
    mode: str = DEFAULT_MODE,
    budget: int = DEFAULT_BUDGET,
    focus_cap: int = DEFAULT_FOCUS_CAP,
    seed: Optional[int] = DEFAULT_SEED,
    name: Optional[str] = None,
    protocol: str = "steering",
) -> int:
    """One workshop cell — thin wrapper around run_from_snapshot (B2/B3 kernel)."""
    import run_bridge

    return run_bridge.run_from_snapshot(
        snapshot_path,
        mode=mode,
        seed=seed,
        protocol=protocol,
        budget=budget,
        focus_cap=focus_cap,
        name=name,
    )


# ---- B4 closed-loop wage extraction -----------------------------------------


def _as_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def stamps_from_answer(answer) -> list[int]:
    """PLN answer shape: ((stv f c) (stamp1 stamp2 …)) or nested list form."""
    if answer is None:
        return []
    if isinstance(answer, dict):
        if "stamps" in answer:
            raw = answer["stamps"]
        else:
            raw = answer.get("answer")
            return stamps_from_answer(raw)
    else:
        raw = answer
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return []
    stamps = raw[1]
    if not isinstance(stamps, (list, tuple)):
        try:
            return [int(float(stamps))]
        except (TypeError, ValueError):
            return []
    out = []
    for s in stamps:
        try:
            out.append(int(float(s)))
        except (TypeError, ValueError):
            continue
    return out


def original_nodes_from_snapshot(snap: dict) -> set[str]:
    nodes: set[str] = set()
    for a in snap.get("af") or []:
        nodes.add(str(a))
    for e in snap.get("edges") or []:
        if isinstance(e, (list, tuple)) and len(e) >= 2:
            nodes.add(str(e[0]))
            nodes.add(str(e[1]))
    q = (snap.get("query") or {}).get("objects") or []
    for a in q:
        nodes.add(str(a))
    for a in (snap.get("sti") or {}):
        nodes.add(str(a))
    return nodes


def reverse_symbol_map(snap: dict) -> dict[str, str]:
    """Safe PeTTa symbol → original CIP atom string."""
    return {safe_sym(n): n for n in original_nodes_from_snapshot(snap)}


def _to_original(name: str, rev: dict[str, str]) -> str:
    s = str(name)
    return rev.get(s, rev.get(safe_sym(s), s))


def originals_for_stamps(snap: dict, stamps: list[int]) -> list[str]:
    """Map PLN table stamps → original edge endpoint atoms.

    scenario_from_snapshot stamps edges with enumerate(edges, start=1) using
    the same edge list order as the probe snapshot.
    """
    edges = snap.get("edges") or []
    out: list[str] = []
    for sid in stamps:
        if not (1 <= int(sid) <= len(edges)):
            continue
        row = edges[int(sid) - 1]
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        out.append(str(row[0]))
        out.append(str(row[1]))
    return out


def wage_atoms_from_steering(
    summary: Optional[dict],
    snapshot: Optional[dict] = None,
) -> dict[str, Any]:
    """Build CIP wage list after influenced arm solves (B4).

    Priority:
      1. Original endpoints of tables used in the influenced proof (stamps)
      2. Snapshot query objects (original CIP names)
      3. Attention query ∩ focus, reverse-mapped to originals when possible

    Returns {atoms, stamps, method, n}.
    """
    summary = summary or {}
    snap = snapshot or {}
    influenced = arm_dict(summary.get("arms") or {}, "influenced")
    if not influenced.get("solved"):
        return {"atoms": [], "stamps": [], "method": "unsolved", "n": 0}

    rev = reverse_symbol_map(snap) if snap else {}
    stamps = stamps_from_answer(influenced.get("answer"))
    atoms: list[str] = []
    method = "none"

    if stamps and snap.get("edges"):
        atoms = originals_for_stamps(snap, stamps)
        if atoms:
            method = "proof_stamps"

    if not atoms:
        q_snap = _as_list((snap.get("query") or {}).get("objects"))
        if q_snap:
            atoms = [str(x) for x in q_snap]
            method = "snapshot_query"

    if not atoms:
        att = summary.get("attention") or {}
        q = [str(x) for x in _as_list(att.get("query_objects"))]
        focus = [str(x) for x in _as_list(att.get("focus"))]
        qset = set(q)
        candidates = [a for a in focus if a in qset] or q or focus[: min(4, len(focus))]
        atoms = [_to_original(a, rev) for a in candidates]
        method = "attention_fallback"

    # unique preserve order; drop empties
    seen: set[str] = set()
    uniq: list[str] = []
    for a in atoms:
        if a and a not in seen:
            seen.add(a)
            uniq.append(a)
    return {
        "atoms": uniq,
        "stamps": stamps,
        "method": method,
        "n": len(uniq),
    }
