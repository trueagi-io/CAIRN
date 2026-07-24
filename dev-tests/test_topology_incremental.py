#!/usr/bin/env python3
"""Property tests: inductive TopoState matches full recompute.

Run from CAIRN/:
  source venv/bin/activate
  python dev-tests/test_topology_incremental.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.utils as u


def full(edges):
    return u._clique_complex_report(edges)


def assert_eq(label, expected, actual):
    if expected != actual:
        raise AssertionError(f"FAIL {label}: expected {expected}, got {actual}")
    print(f"PASS {label}: {actual}")


def test_static_cases():
    u.reset_topology_state()
    # empty
    assert_eq("empty", [0, 0, 0, 0], u.topology_invariants([]))
    # cache hit
    assert_eq("empty-cache", [0, 0, 0, 0], u.topology_invariants([]))

    u.reset_topology_state()
    tri = [("a", "b"), ("b", "c"), ("a", "c")]
    assert_eq("filled-triangle", [1, 1, 0, 0], u.topology_invariants(tri))
    assert_eq("filled-triangle-cache", [1, 1, 0, 0], u.topology_invariants(tri))

    octa = [
        ("a", "b"), ("a", "c"), ("a", "e"), ("a", "f"),
        ("b", "c"), ("b", "d"), ("b", "f"),
        ("c", "d"), ("c", "e"),
        ("d", "e"), ("d", "f"),
        ("e", "f"),
    ]
    u.reset_topology_state()
    assert_eq("octahedron", list(full(octa)), u.topology_invariants(octa))


def test_incremental_matches_full_stream():
    """Add edges one-by-one via topology_invariants; compare to full each step."""
    random.seed(0)
    n = 25
    all_edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    random.shuffle(all_edges)

    u.reset_topology_state()
    live = []
    for k, e in enumerate(all_edges):
        live.append(e)
        got = u.topology_invariants(live)
        exp = list(full(live))
        if got != exp:
            raise AssertionError(
                f"FAIL stream step {k} edge={e}: expected {exp}, got {got}"
            )
    print(f"PASS stream-vs-full n={n} edges={len(all_edges)} final={got}")


def test_batch_adds_match_full():
    """Grow in batches (CIP-like); each batch is pure adds."""
    random.seed(1)
    n = 30
    pool = [(i, j) for i in range(n) for j in range(i + 1, n)]
    random.shuffle(pool)

    u.reset_topology_state()
    live = []
    for batch_i in range(0, len(pool), 17):
        live.extend(pool[batch_i:batch_i + 17])
        got = u.topology_invariants(live)
        exp = list(full(live))
        if got != exp:
            raise AssertionError(
                f"FAIL batch {batch_i}: expected {exp}, got {got}"
            )
    print(f"PASS batch-adds final={got}")


def test_delete_triggers_rebuild():
    u.reset_topology_state()
    edges = [("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")]
    u.topology_invariants(edges)
    # remove one edge
    smaller = [("a", "b"), ("b", "c"), ("a", "c")]
    got = u.topology_invariants(smaller)
    exp = list(full(smaller))
    assert_eq("delete-rebuild", exp, got)


def test_add_edge_local_api():
    st = u.TopoState()
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d"), ("d", "b")]
    for e in edges:
        st.add_edge(*e)
    assert_eq("local-add-api", list(full(edges)), list(st.report()))


if __name__ == "__main__":
    test_static_cases()
    test_add_edge_local_api()
    test_incremental_matches_full_stream()
    test_batch_adds_match_full()
    test_delete_triggers_rebuild()
    print("ALL PASS")
