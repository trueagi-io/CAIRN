"""Canonical AF + Hebbian → JSON attention snapshots for the coupled workshop.

Shared by:
  B2 end-of-run  — output/mve/bridge_snapshot.json   (schedule=end)
  B3 mid-run     — output/mve/probes/cip_{i}.json    (schedule=midrun)

Entry points call write_attention_snapshot (or thin wrappers).
Does not import PeTTa; pure Python JSON writer.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

DEFAULT_MAX_NODES = 80
DEFAULT_MAX_EDGES = 200
DEFAULT_END_DIR = "output/mve"
DEFAULT_PROBES_DIR = "output/mve/probes"


def _as_list(x):
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return list(x)
    return [x]


def _atom(x) -> str:
    if isinstance(x, (list, tuple)):
        return str(tuple(_atom(y) for y in x))
    return str(x)


def _float(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _sti_map(sti_pairs) -> dict:
    """Accept ((atom sti) ...) or {atom: sti}."""
    out = {}
    if isinstance(sti_pairs, dict):
        for k, v in sti_pairs.items():
            out[_atom(k)] = _float(v)
        return out
    for item in _as_list(sti_pairs):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out[_atom(item[0])] = _float(item[1])
    return out


def _edge_list(edges) -> list:
    """Accept ((src tgt [w]) ...) → [[src, tgt, w], ...]."""
    out = []
    for e in _as_list(edges):
        if not isinstance(e, (list, tuple)) or len(e) < 2:
            continue
        w = _float(e[2], 0.5) if len(e) >= 3 else 0.5
        a, b = _atom(e[0]), _atom(e[1])
        if a == b:
            continue
        if a > b:
            a, b = b, a
        out.append([a, b, max(0.0, min(1.0, w))])
    # dedupe keep max weight
    best = {}
    for a, b, w in out:
        key = (a, b)
        best[key] = max(w, best.get(key, 0.0))
    return [[a, b, w] for (a, b), w in best.items()]


def _grow_nodes(af, edges, sti, max_nodes: int) -> list:
    """AF-first BFS by edge strength / STI, capped."""
    af_list = [_atom(a) for a in _as_list(af)]
    adj = defaultdict(list)
    for a, b, w in edges:
        adj[a].append((b, w))
        adj[b].append((a, w))

    chosen = []
    seen = set()
    # seed with AF ordered by STI desc
    seed = sorted(af_list, key=lambda a: sti.get(a, 0.0), reverse=True)
    queue = list(seed)
    for a in seed:
        if a not in seen:
            seen.add(a)
            chosen.append(a)

    # expand neighbors preferred by weight * sti
    i = 0
    while i < len(chosen) and len(chosen) < max_nodes:
        u = chosen[i]
        i += 1
        nbrs = sorted(
            adj.get(u, []),
            key=lambda tw: (tw[1], sti.get(tw[0], 0.0)),
            reverse=True,
        )
        for v, _w in nbrs:
            if v in seen:
                continue
            seen.add(v)
            chosen.append(v)
            if len(chosen) >= max_nodes:
                break
    return chosen


def _pick_query(nodes: list, edges: list, sti: dict, explicit=None) -> dict:
    if explicit and len(_as_list(explicit)) >= 2:
        objs = [_atom(x) for x in _as_list(explicit)[:2]]
        return {
            "objects": objs,
            "term_label": f"Inheritance {objs[0]} {objs[1]}",
        }

    # undirected adjacency for path check
    adj = defaultdict(set)
    for a, b, _w in edges:
        if a in nodes and b in nodes:
            adj[a].add(b)
            adj[b].add(a)

    ranked = sorted(nodes, key=lambda a: sti.get(a, 0.0), reverse=True)

    def reachable(s, t):
        if s == t:
            return True
        seen = {s}
        stack = [s]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v in seen:
                    continue
                if v == t:
                    return True
                seen.add(v)
                stack.append(v)
        return False

    for i, a in enumerate(ranked):
        for b in ranked[i + 1 :]:
            if reachable(a, b):
                return {
                    "objects": [a, b],
                    "term_label": f"Inheritance {a} {b}",
                }
    # fallback top-2 STI even if disconnected
    objs = ranked[:2] if len(ranked) >= 2 else ranked + ranked
    objs = objs[:2]
    if len(objs) < 2:
        objs = (objs + ["_pad", "_pad"])[:2]
    return {"objects": objs, "term_label": f"Inheritance {objs[0]} {objs[1]}"}


def build_snapshot(
    source: str,
    af,
    sti_pairs,
    edges,
    max_nodes: int = 80,
    max_edges: int = 200,
    query_objects=None,
) -> dict:
    sti = _sti_map(sti_pairs)
    raw_edges = _edge_list(edges)
    # seed STI for edge endpoints missing from AF export
    for a, b, _w in raw_edges:
        sti.setdefault(a, 0.0)
        sti.setdefault(b, 0.0)
    for a in _as_list(af):
        sti.setdefault(_atom(a), 0.0)

    nodes = _grow_nodes(af, raw_edges, sti, int(max_nodes))
    node_set = set(nodes)
    kept_edges = [[a, b, w] for a, b, w in raw_edges if a in node_set and b in node_set]
    kept_edges.sort(key=lambda e: e[2], reverse=True)
    kept_edges = kept_edges[: int(max_edges)]

    # drop nodes with no edge if we have edges
    if kept_edges:
        used = set()
        for a, b, _w in kept_edges:
            used.add(a)
            used.add(b)
        # keep AF nodes even if isolated
        af_set = {_atom(a) for a in _as_list(af)}
        nodes = [n for n in nodes if n in used or n in af_set]

    af_out = [_atom(a) for a in _as_list(af) if _atom(a) in set(nodes)]
    if not af_out:
        af_out = nodes[: min(10, len(nodes))]

    query = _pick_query(nodes, kept_edges, sti, explicit=query_objects)

    return {
        "source": str(source),
        "exported_at": datetime.now().isoformat(),
        "af": af_out,
        "sti": {n: sti.get(n, 0.0) for n in nodes},
        "edges": kept_edges,
        "query": query,
        # focus_cap: scenario generator trims freeze-F to top-STI AF for fair |S|=|F|
        "caps": {
            "max_nodes": int(max_nodes),
            "max_edges": int(max_edges),
            "focus_cap": 12,
        },
        "stats": {
            "n_nodes": len(nodes),
            "n_edges": len(kept_edges),
            "n_af": len(af_out),
        },
    }


def end_snapshot_path(out_dir: Union[str, Path] = DEFAULT_END_DIR) -> str:
    """B2 path: <out_dir>/bridge_snapshot.json"""
    return str(Path(str(out_dir)) / "bridge_snapshot.json")


def midrun_snapshot_path(
    cip_index,
    probes_dir: Union[str, Path] = DEFAULT_PROBES_DIR,
) -> str:
    """B3 path: <probes_dir>/cip_{i}.json"""
    return str(Path(str(probes_dir)) / f"cip_{int(float(cip_index))}.json")


# Back-compat alias used by MeTTa export-bridge-snapshot-force!
snapshot_path = end_snapshot_path


def _norm_cip_index(cip_index) -> Optional[int]:
    if cip_index is None or cip_index is False:
        return None
    if isinstance(cip_index, (list, tuple)) and len(cip_index) == 0:
        return None
    s = str(cip_index).strip()
    if s in ("", "None", "()", "nil"):
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def write_attention_snapshot(
    path,
    source,
    af,
    sti_pairs,
    edges,
    schedule="end",
    cip_index=None,
    max_nodes=DEFAULT_MAX_NODES,
    max_edges=DEFAULT_MAX_EDGES,
    query_objects=None,
):
    """Canonical AF→JSON export for B2 (end) and B3 (midrun).

    Parameters are positional-friendly for PeTTa py-call.
    Returns path string. Annotates schedule + optional cip_index on the JSON.

    schedule: "end" | "midrun"
    """
    path = Path(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    sched = str(schedule or "end").strip().lower()
    if sched not in ("end", "midrun"):
        sched = "end"
    ci = _norm_cip_index(cip_index)

    snap = build_snapshot(
        source,
        af,
        sti_pairs,
        edges,
        max_nodes=int(float(max_nodes)),
        max_edges=int(float(max_edges)),
        query_objects=query_objects,
    )
    snap["schedule"] = sched
    snap["source"] = str(source)
    if ci is not None:
        snap["cip_index"] = ci

    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)
        f.write("\n")
    print(
        f"[export_snapshot] wrote {path} schedule={sched}"
        + (f" cip={ci}" if ci is not None else "")
        + f" nodes={snap['stats']['n_nodes']} edges={snap['stats']['n_edges']}"
    )
    return str(path)


def write(
    path,
    source,
    af,
    sti_pairs,
    edges,
    max_nodes=DEFAULT_MAX_NODES,
    max_edges=DEFAULT_MAX_EDGES,
    query_objects=None,
):
    """Back-compat thin wrapper → write_attention_snapshot (schedule=end)."""
    return write_attention_snapshot(
        path,
        source,
        af,
        sti_pairs,
        edges,
        "end",
        None,
        max_nodes,
        max_edges,
        query_objects,
    )


def write_midrun(
    cip_index,
    source,
    af,
    sti_pairs,
    edges,
    probes_dir=DEFAULT_PROBES_DIR,
    max_nodes=DEFAULT_MAX_NODES,
    max_edges=DEFAULT_MAX_EDGES,
):
    """B3 convenience: write probes/cip_{i}.json with schedule=midrun."""
    ci = _norm_cip_index(cip_index)
    if ci is None:
        raise ValueError("write_midrun requires cip_index")
    path = midrun_snapshot_path(ci, probes_dir)
    return write_attention_snapshot(
        path,
        source,
        af,
        sti_pairs,
        edges,
        "midrun",
        ci,
        max_nodes,
        max_edges,
        None,
    )

