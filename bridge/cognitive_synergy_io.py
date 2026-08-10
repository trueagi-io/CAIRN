"""Synergy I/O — CAIRN-shaped output under output/cognitive_synergy/<scenario>/.

Layout (same idea as output/mve/ and output/benchmark/):
  output/cognitive_synergy/<scenario>/
    summary.json   # run envelope (parameters + results)
    metrics.csv    # one row per protocol run (seed recorded, not swept)
"""

from __future__ import annotations

import csv
import json
import random
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Flat row schema for metrics.csv (steering + feedback share columns; unused = "")
# Arms: weighted (all premises) | influenced (Cq∧AF) | distracted (random |S|=|F|)
METRICS_FIELDS = [
    "seed",
    "protocol",
    "scenario",
    "budget",
    "ecan_cycles",
    "query",
    "weighted_solved",
    "weighted_confidence",
    "weighted_n_premises",
    "weighted_wall_ms",
    "influenced_solved",
    "influenced_confidence",
    "influenced_n_premises",
    "influenced_wall_ms",
    "distracted_solved",
    "distracted_confidence",
    "distracted_n_premises",
    "distracted_wall_ms",
    "query_af_overlap",
    "influenced_beats_distracted",
    "influenced_faster_than_distracted",
    "focus_seed_size",
    "focus_size",
    "pln_solved",
    "pln_confidence",
    "pln_wall_ms",
    "n_proof_objects",
    "n_newly_focused",
    "n_proof_in_focus0",
    "n_proof_in_focus1",
    "sti_gain_sum",
    "written_at",
]

# Canonical arm name → legacy aliases (read path only)
_ARM_KEYS = {
    "weighted": ("weighted", "full"),
    "influenced": ("influenced", "af"),
    "distracted": ("distracted", "random"),
}


def wall_ms():
    """Monotonic wall clock in milliseconds (for MeTTa py-call timers)."""
    return time.perf_counter() * 1000.0


def elapsed_ms(t0):
    """Milliseconds since t0 from wall_ms()."""
    try:
        return max(0.0, wall_ms() - float(t0))
    except (TypeError, ValueError):
        return 0.0


def sample_as_list(pool, k, seed=0):
    items = list(pool) if isinstance(pool, (list, tuple)) else [pool]
    flat = []
    for x in items:
        if isinstance(x, (list, tuple)):
            flat.extend(str(y) for y in x)
        else:
            flat.append(str(x))
    flat = [x for x in flat if x and x != "-"]
    k = min(int(float(k)), len(flat)) if flat else 0
    if k <= 0:
        return []
    return random.Random(int(float(seed))).sample(flat, k)


def _edge_pair(item):
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return None
    a, b = item[0], item[1]
    if str(a) in ("Table", "Inheritance"):
        return None
    return str(a), str(b)


def neighbors_from_edges(edges):
    """Undirected adjacency for AFImportanceDiffusion from table leg pairs."""
    raw = list(edges) if isinstance(edges, (list, tuple)) else [edges]
    g = defaultdict(set)
    for item in raw:
        pair = _edge_pair(item)
        if pair is None:
            if isinstance(item, (list, tuple)):
                for sub in item:
                    pair = _edge_pair(sub)
                    if pair:
                        a, b = pair
                        g[a].add(b)
                        g[b].add(a)
            continue
        a, b = pair
        g[a].add(b)
        g[b].add(a)
    return [[n, sorted(ns)] for n, ns in sorted(g.items())]


def _bool(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, str) and v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def _norm(obj, key=None):
    if isinstance(obj, dict):
        return {str(k): _norm(v, str(k)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        if obj and all(isinstance(x, (list, tuple)) and len(x) == 2 for x in obj):
            return {str(k): _norm(v, str(k)) for k, v in obj}
        return [_norm(x) for x in obj]
    if key == "solved":
        return _bool(obj)
    if isinstance(obj, str) and obj.lower() in ("true", "false"):
        return _bool(obj)
    return obj


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def _sti_map(raw):
    """Normalize (($a $sti) ...) or {a: sti} to {str: float}."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        out = {}
        for k, v in raw.items():
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                pass
        return out
    out = {}
    for item in _as_list(raw):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                out[str(item[0])] = float(item[1])
            except (TypeError, ValueError):
                pass
    return out


def _arm(data, name):
    """Resolve arm dict by canonical name (weighted|influenced|distracted) or legacy."""
    if not isinstance(data, dict):
        return {}
    keys = _ARM_KEYS.get(name, (name,))
    for k in keys:
        a = data.get(k)
        if isinstance(a, dict) and a:
            return a
    arms = data.get("arms")
    if isinstance(arms, dict):
        for k in keys:
            a = arms.get(k)
            if isinstance(a, dict) and a:
                return a
    return {}


def _envelope(data: dict) -> dict:
    """CAIRN-style summary: parameters + results (not a flat bag of keys)."""
    now = datetime.now().isoformat()
    protocol = data.get("protocol") or "steering"
    params = {
        "scenario": data.get("scenario"),
        "protocol": protocol,
        "budget": data.get("budget"),
        "ecan_cycles": data.get("ecan_cycles"),
        "query": data.get("query"),
        "random_seed": data.get("random_seed", 0),
    }
    attention = {
        "focus_seed": data.get("focus_seed"),
        "focus": data.get("focus"),
        "query_objects": data.get("query_objects"),
        "query_af_overlap": data.get("query_af_overlap"),
        "distracted_S": data.get("distracted_S") or data.get("random_S"),
    }
    out = {
        "run_timestamp": data.get("run_timestamp") or now,
        "completed_at": now,
        "parameters": params,
        "attention": attention,
    }

    def _ms(arm_or_data, *keys):
        for k in keys:
            if isinstance(arm_or_data, dict) and k in arm_or_data and arm_or_data[k] is not None:
                try:
                    return float(arm_or_data[k])
                except (TypeError, ValueError):
                    pass
        return None

    if protocol == "feedback":
        out["parameters"]["protocol"] = "feedback"
        pln = data.get("pln") if isinstance(data.get("pln"), dict) else {}
        # allow top-level pln_wall_ms from MeTTa
        if pln is not None and data.get("pln_wall_ms") is not None:
            pln = dict(pln)
            pln["wall_ms"] = _ms(data, "pln_wall_ms")
        out["pln"] = pln
        sti0 = _sti_map(data.get("sti_before"))
        sti1 = _sti_map(data.get("sti_after"))
        gains = {k: sti1.get(k, 0.0) - sti0.get(k, 0.0) for k in set(sti0) | set(sti1)}
        proof = _as_list(data.get("proof_objects"))
        pin0 = set(map(str, _as_list(data.get("proof_in_focus0"))))
        pin1 = set(map(str, _as_list(data.get("proof_in_focus1"))))
        out["feedback"] = {
            "proof_objects": proof,
            "proof_in_focus0": sorted(pin0),
            "proof_in_focus1": sorted(pin1),
            "newly_focused": data.get("newly_focused"),
            "focus0": data.get("focus0"),
            "focus1": data.get("focus1"),
            "sti_before": sti0,
            "sti_after": sti1,
            "sti_gain": gains,
            "sti_gain_sum": sum(gains.values()),
            "proof_retained_in_af": bool(pin0) and pin0.issubset(pin1) if pin0 else bool(pin1),
        }
        out["attention"] = {
            "focus_seed": data.get("focus0"),
            "focus": data.get("focus1"),
            "query_objects": data.get("query_objects"),
            "query_af_overlap": None,
            "distracted_S": None,
        }
        out["timing"] = {
            "pln_wall_ms": _ms(pln or {}, "wall_ms") if pln else _ms(data, "pln_wall_ms"),
        }
    else:
        weighted = _arm(data, "weighted")
        influenced = _arm(data, "influenced")
        distracted = _arm(data, "distracted")
        for arm, key in (
            (weighted, "weighted_wall_ms"),
            (influenced, "influenced_wall_ms"),
            (distracted, "distracted_wall_ms"),
            # legacy flat keys
            (weighted, "full_wall_ms"),
            (influenced, "af_wall_ms"),
            (distracted, "random_wall_ms"),
        ):
            if arm is not None and data.get(key) is not None and "wall_ms" not in arm:
                try:
                    arm["wall_ms"] = float(data[key])
                except (TypeError, ValueError):
                    pass
        for arm in (weighted, influenced, distracted):
            if "solved" in arm:
                arm["solved"] = _bool(arm["solved"])
            if "wall_ms" in arm:
                try:
                    arm["wall_ms"] = float(arm["wall_ms"])
                except (TypeError, ValueError):
                    pass
        out["arms"] = {
            "weighted": weighted,
            "influenced": influenced,
            "distracted": distracted,
        }
        q = data.get("query_objects") or data.get("focus_seed")
        f = data.get("focus")
        overlap = data.get("query_af_overlap")
        if overlap is None and isinstance(q, list) and isinstance(f, list) and q:
            overlap = len(set(map(str, q)) & set(map(str, f))) / len(q)
        w_ms = _ms(weighted, "wall_ms")
        i_ms = _ms(influenced, "wall_ms")
        d_ms = _ms(distracted, "wall_ms")
        i_faster = None
        if i_ms is not None and d_ms is not None and i_ms > 0 and d_ms > 0:
            i_faster = i_ms < d_ms
        out["contrast"] = {
            "influenced_beats_distracted": bool(influenced.get("solved"))
            and not bool(distracted.get("solved")),
            "influenced_premises": influenced.get("n_premises"),
            "distracted_premises": distracted.get("n_premises"),
            "weighted_premises": weighted.get("n_premises"),
            "query_af_overlap": overlap,
            "influenced_faster_than_distracted": i_faster,
            "influenced_wall_ms": i_ms,
            "distracted_wall_ms": d_ms,
            "weighted_wall_ms": w_ms,
        }
        out["timing"] = {
            "weighted_wall_ms": w_ms,
            "influenced_wall_ms": i_ms,
            "distracted_wall_ms": d_ms,
            "budget": data.get("budget"),
        }
    return out


def _metrics_row(data: dict, completed_at: str) -> dict:
    protocol = (data.get("parameters") or {}).get("protocol") or data.get("protocol") or "steering"
    params = data.get("parameters") or {}
    att = data.get("attention") or {}
    arms = data.get("arms") or {}
    weighted = arms.get("weighted") or arms.get("full") or {}
    influenced = arms.get("influenced") or arms.get("af") or {}
    distracted = arms.get("distracted") or arms.get("random") or {}
    fb = data.get("feedback") or {}
    pln = data.get("pln") or {}
    contrast = data.get("contrast") or {}

    def solved(a):
        return _bool(a.get("solved")) if a else ""

    fs = _as_list(att.get("focus_seed") or fb.get("focus0"))
    fo = _as_list(att.get("focus") or fb.get("focus1"))
    proof = _as_list(fb.get("proof_objects"))
    newly = _as_list(fb.get("newly_focused"))
    pin0 = _as_list(fb.get("proof_in_focus0"))
    pin1 = _as_list(fb.get("proof_in_focus1"))
    sti_gain = fb.get("sti_gain_sum")
    if sti_gain is None and isinstance(fb.get("sti_gain"), dict):
        sti_gain = sum(fb["sti_gain"].values())

    timing = data.get("timing") or {}
    beat = contrast.get("influenced_beats_distracted")
    if beat is None:
        beat = contrast.get("af_beats_random_solve")
    faster = contrast.get("influenced_faster_than_distracted")
    if faster is None:
        faster = contrast.get("af_faster_than_random")

    return {
        "seed": params.get("random_seed", data.get("random_seed", 0)),
        "protocol": protocol,
        "scenario": params.get("scenario", data.get("scenario")),
        "budget": params.get("budget", data.get("budget")),
        "ecan_cycles": params.get("ecan_cycles", data.get("ecan_cycles")),
        "query": params.get("query", data.get("query")),
        "weighted_solved": solved(weighted),
        "weighted_confidence": weighted.get("confidence", ""),
        "weighted_n_premises": weighted.get("n_premises", ""),
        "weighted_wall_ms": weighted.get(
            "wall_ms", timing.get("weighted_wall_ms", timing.get("full_wall_ms", ""))
        ),
        "influenced_solved": solved(influenced),
        "influenced_confidence": influenced.get("confidence", ""),
        "influenced_n_premises": influenced.get("n_premises", ""),
        "influenced_wall_ms": influenced.get(
            "wall_ms", timing.get("influenced_wall_ms", timing.get("af_wall_ms", ""))
        ),
        "distracted_solved": solved(distracted),
        "distracted_confidence": distracted.get("confidence", ""),
        "distracted_n_premises": distracted.get("n_premises", ""),
        "distracted_wall_ms": distracted.get(
            "wall_ms", timing.get("distracted_wall_ms", timing.get("random_wall_ms", ""))
        ),
        "query_af_overlap": contrast.get("query_af_overlap", att.get("query_af_overlap", "")),
        "influenced_beats_distracted": beat if beat is not None else "",
        "influenced_faster_than_distracted": faster if faster is not None else "",
        "focus_seed_size": len(fs) if fs else "",
        "focus_size": len(fo) if fo else "",
        "pln_solved": solved(pln) if pln else "",
        "pln_confidence": pln.get("confidence", ""),
        "pln_wall_ms": pln.get("wall_ms", timing.get("pln_wall_ms", "")),
        "n_proof_objects": len(proof),
        "n_newly_focused": len(set(map(str, newly))),
        "n_proof_in_focus0": len(set(map(str, pin0))),
        "n_proof_in_focus1": len(set(map(str, pin1))),
        "sti_gain_sum": sti_gain if sti_gain is not None else "",
        "written_at": completed_at,
    }


def _write_metrics_csv(dir_path: Path, row: dict):
    """Write a single-row metrics.csv for this scenario run."""
    path = dir_path / "metrics.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=METRICS_FIELDS)
        w.writeheader()
        w.writerow({k: row.get(k, "") for k in METRICS_FIELDS})
    return path


def write_summary(path, summary):
    """Write CAIRN-style summary.json + metrics.csv in the same directory."""
    path = Path(str(path))
    # Normalize: always land as .../summary.json in a scenario dir
    if path.suffix != ".json":
        path = path / "summary.json"
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    raw = _norm(summary)
    if not isinstance(raw, dict):
        raw = {"raw": raw}

    env = _envelope(raw)
    # metrics first, summary last so dashboard summary_is_current (summary mtime >= metrics)
    _write_metrics_csv(dir_path, _metrics_row(env, env["completed_at"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(env, f, indent=2, default=str)
        f.write("\n")
    print(f"[cognitive_synergy_io] wrote {path}")
    print(f"[cognitive_synergy_io] updated {dir_path / 'metrics.csv'}")
    return str(path)
