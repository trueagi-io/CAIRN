"""Generate bridge fx-* scenario files from a bridge_snapshot.json.

Hebbian edges are dualed as Inheritance premises (PeTTa lib_pln syllogism
is Inheritance-only). This is an operational encoding, not taxonomy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Freeze-F: do not use full CIP AF as F — |S|=|F| would nearly equal V.
# Top-STI focus keeps a scarce Cq∧AF control; weighted arm still sees all tables.
DEFAULT_FOCUS_CAP = 12
DEFAULT_RE_DYNAMICS_CYCLES = 3
MIN_EDGES = 2
MIN_AF = 2


def _safe_sym(s: str) -> str:
    """PeTTa-friendly atom: alnum/underscore; prefix if starts with digit."""
    t = re.sub(r"[^A-Za-z0-9_]", "_", str(s))
    if not t:
        t = "x"
    if t[0].isdigit():
        t = "n_" + t
    return t


# Public alias for reverse-map / wage extraction (B4)
safe_sym = _safe_sym


def _cons_atoms(atoms: list) -> str:
    """Build nested cons chain ending in ()."""
    if not atoms:
        return "()"
    inner = "()"
    for a in reversed(atoms):
        inner = f"(cons {a} {inner})"
    return inner


def _stv_from_sti(sti: float, lo: float, hi: float) -> tuple:
    """Map STI to (strength, confidence) in (0,1]."""
    if hi > lo:
        x = (float(sti) - lo) / (hi - lo)
    else:
        x = 0.5
    x = max(0.05, min(0.95, x))
    return (round(0.3 + 0.5 * x, 4), 0.9)


def validate_snapshot(snap: dict) -> str | None:
    """Return skip reason or None if usable."""
    edges = snap.get("edges") or []
    af = snap.get("af") or []
    if len(edges) < MIN_EDGES:
        return f"too few edges ({len(edges)} < {MIN_EDGES})"
    if len(af) < MIN_AF and len(edges) < MIN_EDGES:
        return f"too few AF atoms ({len(af)} < {MIN_AF})"
    return None


def _top_focus(af: list, sti: dict, cap: int) -> list:
    """Highest-STI AF atoms, capped; preserves order by STI desc."""
    ranked = sorted(
        (str(a) for a in af),
        key=lambda a: float(sti.get(a, 0.0)),
        reverse=True,
    )
    # unique preserve order
    seen = set()
    out = []
    for a in ranked:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
        if len(out) >= cap:
            break
    return out


def cell_name(
    source: str,
    mode: str,
    focus_cap: int,
    budget: int,
    protocol: str = "steering",
) -> str:
    """Stable coupled / ablation scenario dir name (always includes mode, k, B).

    Examples:
      from_mve_ff_k12_b10
      feedback_from_mve_ff_k12_b10
    """
    m = "ff" if mode == "freeze-f" else "rd"
    base = f"from_{_safe_sym(source)}_{m}_k{int(focus_cap)}_b{int(budget)}"
    if protocol == "feedback":
        return f"feedback_{base}"
    return base


def resolve_focus_cap(snap: dict, focus_cap: int | None) -> int:
    caps = snap.get("caps") or {}
    if focus_cap is None:
        focus_cap = int(caps.get("focus_cap") or DEFAULT_FOCUS_CAP)
    return max(2, int(focus_cap))


def generate(
    snapshot_path: str | Path,
    out_dir: str | Path | None = None,
    name: str | None = None,
    mode: str = "freeze-f",
    focus_cap: int | None = None,
    re_dynamics_cycles: int = DEFAULT_RE_DYNAMICS_CYCLES,
    budget: int = 10,
    protocol: str = "steering",
) -> dict:
    """Write <name>_map.metta and <name>_pln.metta. Returns paths + meta.

    Default name is cell_name(source, mode, k, B[, protocol]).
    Raises ValueError if snapshot is too small to run a protocol.
    """
    snap_path = Path(snapshot_path)
    with open(snap_path, encoding="utf-8") as f:
        snap = json.load(f)

    reason = validate_snapshot(snap)
    if reason:
        raise ValueError(f"snapshot unusable: {reason}")

    source = snap.get("source") or "snapshot"
    mode = mode if mode in ("freeze-f", "re-dynamics") else "freeze-f"
    focus_cap = resolve_focus_cap(snap, focus_cap)
    budget = max(1, int(budget))
    proto = protocol if protocol in ("steering", "feedback") else "steering"
    name = name or cell_name(source, mode, focus_cap, budget, protocol=proto)
    out_dir = Path(out_dir or (Path(__file__).resolve().parent / "scenarios" / "generated"))
    out_dir.mkdir(parents=True, exist_ok=True)

    sti = {str(k): float(v) for k, v in (snap.get("sti") or {}).items()}
    edges = snap.get("edges") or []
    af_all = [str(a) for a in (snap.get("af") or [])]
    query = snap.get("query") or {}
    q_objs = [str(x) for x in (query.get("objects") or [])][:2]
    if len(q_objs) < 2:
        ranked = sorted(sti.keys(), key=lambda a: sti.get(a, 0.0), reverse=True)
        q_objs = (ranked + ["_a", "_b"])[:2]

    # Ensure query atoms stay in focus for freeze-F (Cq needs Q∩F).
    af_ranked = _top_focus(af_all, sti, focus_cap)
    for q in q_objs:
        if q not in af_ranked and q in set(af_all) | set(sti):
            # replace lowest-STI slot if full
            if len(af_ranked) >= focus_cap and af_ranked:
                af_ranked = af_ranked[:-1]
            if q not in af_ranked:
                af_ranked.append(q)
    if len(af_ranked) < 2:
        af_ranked = list(dict.fromkeys(q_objs + af_ranked))[: max(2, focus_cap)]

    # symbol map over AF + edge endpoints + query
    nodes: set[str] = set()
    for a, b, _w in edges:
        nodes.add(str(a))
        nodes.add(str(b))
    for a in af_all:
        nodes.add(str(a))
    for a in q_objs:
        nodes.add(str(a))
    nodes_list = sorted(nodes)
    sym = {n: _safe_sym(n) for n in nodes_list}

    stis = [sti.get(n, 0.0) for n in nodes_list] or [0.0]
    lo, hi = min(stis), max(stis)

    tables = []
    sentences = []
    for i, row in enumerate(edges, start=1):
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        a, b = str(row[0]), str(row[1])
        w = float(row[2]) if len(row) >= 3 else 0.5
        sa, sb = sym[a], sym[b]
        strength = max(0.05, min(0.95, w))
        conf = 0.9
        stamp = i
        tables.append(
            f"(Table {i} Inheritance (cons {sa} (cons {sb} ())) (stv {strength} {conf}) ({stamp}))"
        )
        sentences.append(
            f"(Sentence ((Inheritance {sa} {sb}) (stv {strength} {conf})) ({stamp}))"
        )

    if len(tables) < MIN_EDGES:
        raise ValueError(f"snapshot unusable: too few valid edges ({len(tables)})")

    af_syms = [sym[a] for a in af_ranked if a in sym]
    if len(af_syms) < 2:
        af_syms = [sym[q_objs[0]], sym[q_objs[1]]]
    q_syms = [sym[q_objs[0]], sym[q_objs[1]]]
    pool = [f'"{sym[n]}"' for n in nodes_list]
    obj_cons = _cons_atoms([sym[n] for n in nodes_list])
    seed_cons = _cons_atoms(q_syms)
    focus_cons = _cons_atoms(af_syms)
    qobj_cons = _cons_atoms(q_syms)

    table_chain = "()"
    for t in reversed(tables):
        table_chain = f"(cons {t} {table_chain})"

    kb_full = "()\n" if not sentences else "(\n    " + "\n    ".join(sentences) + "\n   )"

    cycles = 0 if mode == "freeze-f" else max(1, int(re_dynamics_cycles))
    af_size = float(max(2, len(af_syms)))
    out_base = f"output/cognitive_synergy/{name}"

    # Do not bake fx-out / fx-out-feedback here — driver_src always sets them
    # (avoids PeTTa multi-equality double-writes to wrong paths).
    map_body = f"""; Auto-generated from {snap_path.name} — do not edit by hand.
; mode={mode} focus_cap={focus_cap} (AF export may be larger; F is top-STI)
; Output paths (fx-name / fx-out / fx-out-feedback) are set by run_bridge driver.
(= (fx-query-label) "Inheritance {q_syms[0]} {q_syms[1]}")
(= (fx-af-size) {af_size})
(= (fx-cycles) {cycles})
(= (fx-n-tables) {len(tables)})
(= (fx-mode) "{mode}")
(= (fx-seeds) {seed_cons})
(= (fx-focus) {focus_cons})
(= (fx-objects) {obj_cons})
(= (fx-pool) ({' '.join(pool)}))
(= (fx-tables) {table_chain})
(= (fx-query-term) (Inheritance {q_syms[0]} {q_syms[1]}))
(= (fx-query-objects) {qobj_cons})
(= (fx-kb-full) {kb_full})
"""

    pln_lines = [
        "; Auto-generated node STV priors — late-import after ECAN seed.",
        "!(import! &self (library lib_pln))",
    ]
    for n in nodes_list:
        s, c = _stv_from_sti(sti.get(n, 0.0), lo, hi)
        pln_lines.append(f"(= (STV {sym[n]}) (stv {s} {c}))")
    pln_body = "\n".join(pln_lines) + "\n"

    map_path = out_dir / f"{name}_map.metta"
    pln_path = out_dir / f"{name}_pln.metta"
    map_path.write_text(map_body, encoding="utf-8")
    pln_path.write_text(pln_body, encoding="utf-8")

    meta = {
        "name": name,
        "map_path": str(map_path),
        "pln_path": str(pln_path),
        "n_tables": len(tables),
        "n_nodes": len(nodes_list),
        "n_focus": len(af_syms),
        "n_af_export": len(af_all),
        "focus_cap": focus_cap,
        "budget": budget,
        "mode": mode,
        "protocol": proto,
        "source": source,
        "query": [q_syms[0], q_syms[1]],
        "focus": af_syms,
        "out_base": out_base,
    }
    print(
        f"[scenario_from_snapshot] wrote {map_path.name} "
        f"tables={len(tables)} focus={len(af_syms)}/{len(af_all)} "
        f"mode={mode} k={focus_cap} B={budget}"
    )
    return meta
