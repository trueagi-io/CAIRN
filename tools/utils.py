import csv
import re
from itertools import combinations

import networkx as nx


def _collides_with_prolog_predicate(word):
    import janus
    r = janus.query_once("atom_string(A, S), current_predicate(A/_)", {"S": word})
    return r["truth"]


def _prolog_collision_set(words):
    seen = {}
    for w in words:
        if w not in seen:
            seen[w] = _collides_with_prolog_predicate(w)
    return {w for w, bad in seen.items() if bad}


def filter_prolog_collisions(words):
    """Words with any Prolog-predicate-colliding entries removed (order
    preserved). Collisions are checked live via janus against the actual
    running PeTTa/SWI-Prolog process, not a hardcoded list -- common English
    words like "is", "not", "member", "between" double as core/library
    predicates, and stimulating them as bare atoms makes PeTTa's
    specialization compiler emit a call to the real builtin instead of
    treating the atom as a data value, which crashes with an
    under-instantiated-arguments error partway through a run.
    """
    bad = _prolog_collision_set(words)
    return [w for w in words if w not in bad]


def find_prolog_collisions(words):
    """Deduplicated, sorted words that would be dropped by
    filter_prolog_collisions -- for reporting what was excluded and why."""
    return sorted(_prolog_collision_set(words))


from networkx.algorithms.community import louvain_communities
from scipy.stats import pearsonr, entropy


# ---- MeTTa edge-list → networkx Graph glue ----------------------------

def _node_key(n):
    """Canonical node id for graphs. Always str so sorted() never mixes str/int
    (PeTTa/Janus may hand through bare ints, floats, or nested lists)."""
    if isinstance(n, list):
        return str(tuple(_node_key(x) for x in n))
    return str(n)


def _build_graph(edges):
    G = nx.DiGraph()
    for edge in edges:
        G.add_edge(_node_key(edge[0]), _node_key(edge[1]))
    return G


def _build_weighted_graph(edges_with_weights):
    G = nx.DiGraph()
    for item in edges_with_weights:
        G.add_edge(item[0], item[1], weight=item[2])
    return G


# ---- Statistics (thin wrappers around scipy/stdlib) --------------------

def pearson_correlation(xs, ys):
    if len(xs) < 2:
        return 0.0
    return float(pearsonr(xs, ys).statistic)


def shannon_entropy(dist):
    return float(entropy(dist, base=2))


# ---- Graph topology (undirected — for simplicial/Betti analysis) -------

import time as _time


def count_triangles(edges):
    G = _build_graph(edges).to_undirected()
    return sum(nx.triangles(G).values()) // 3


# ---- Clique-complex Betti numbers (mod-2 boundary-matrix rank) --------
# Mirrors synapse attention-bank/synapse/topology_metrics.py.
# Expands cliques up to tetrahedra only (min=3, max=4).
#
# topology_invariants maintains a live TopoState:
#   * unchanged edge set  → free cache hit
#   * pure edge additions → inductive update (local new simplices + GF(2)
#                           column inserts into d1/d2/d3 bases)
#   * any edge deletion   → full rebuild (delete-rank is deferred)


def _normalize_edge_set(edges):
    """Undirected edge set with string node keys; loops dropped."""
    out = set()
    for edge in edges or []:
        if not edge or len(edge) < 2:
            continue
        a, b = _node_key(edge[0]), _node_key(edge[1])
        if a == b:
            continue
        out.add(tuple(sorted((a, b))))
    return out


def _sorted_simplex(nodes):
    return tuple(sorted(nodes, key=_node_key))


def _rank_mod2(columns):
    """Rank over GF(2) of columns, each encoded as a bitmask int."""
    basis = {}
    for column in columns:
        _insert_column_mod2(basis, column)
    return len(basis)


def _insert_column_mod2(basis, column):
    """Reduce `column` against `basis` and insert if independent.
    Returns True iff rank increased. Mutates `basis`."""
    vector = column
    while vector:
        pivot = vector.bit_length() - 1
        if pivot not in basis:
            basis[pivot] = vector
            return True
        vector ^= basis[pivot]
    return False


def _boundary_column(simplex, face_to_index):
    column = 0
    for face in combinations(simplex, len(simplex) - 1):
        face_key = _sorted_simplex(face)
        column ^= 1 << face_to_index[face_key]
    return column


def _boundary_columns(simplices, face_to_index):
    for simplex in simplices:
        yield _boundary_column(simplex, face_to_index)


def _triangles_and_tetrahedra_from_adj(adj):
    """Enumerate 3- and 4-cliques from an adjacency-dict graph.

    Do NOT use networkx.enumerate_all_cliques: it walks every clique size
    and explodes on dense AF graphs (k~70).
    """
    triangles = []
    tetrahedra = []
    nodes = sorted(adj.keys(), key=_node_key)
    for u in nodes:
        nbrs_u = [v for v in adj[u] if _node_key(v) > _node_key(u)]
        nbrs_u.sort(key=_node_key)
        for i, v in enumerate(nbrs_u):
            nbrs_v = adj[v]
            common = [w for w in nbrs_u[i + 1:] if w in nbrs_v]
            for j, w in enumerate(common):
                triangles.append(_sorted_simplex((u, v, w)))
                nbrs_w = adj[w]
                for x in common[j + 1:]:
                    if x in nbrs_w:
                        tetrahedra.append(_sorted_simplex((u, v, w, x)))
    return triangles, tetrahedra


def _triangles_and_tetrahedra(G):
    adj = {n: set(G.neighbors(n)) for n in G.nodes()}
    return _triangles_and_tetrahedra_from_adj(adj)


class TopoState:
    """Live clique complex (≤ tetrahedra) + GF(2) boundary ranks.

    Add-only updates insert columns into d1/d2/d3. Removals are handled
    by discarding the state and rebuilding (see topology_invariants).
    """

    __slots__ = (
        "adj", "edges",
        "vertex_index", "edge_index", "triangle_index", "tetra_index",
        "basis_d1", "basis_d2", "basis_d3",
        "rank_d1", "rank_d2", "rank_d3",
        "_next_v", "_next_e", "_next_t", "_next_tet",
    )

    def __init__(self):
        self.adj = {}
        self.edges = set()
        self.vertex_index = {}
        self.edge_index = {}
        self.triangle_index = {}
        self.tetra_index = {}
        self.basis_d1 = {}
        self.basis_d2 = {}
        self.basis_d3 = {}
        self.rank_d1 = 0
        self.rank_d2 = 0
        self.rank_d3 = 0
        self._next_v = 0
        self._next_e = 0
        self._next_t = 0
        self._next_tet = 0

    # ---- construction -------------------------------------------------

    @classmethod
    def from_edge_set(cls, edge_set):
        """Full rebuild from an undirected edge set (canonical path)."""
        st = cls()
        if not edge_set:
            return st

        st.edges = {tuple(sorted(e)) for e in edge_set}
        for a, b in st.edges:
            st._ensure_vertex(a)
            st._ensure_vertex(b)
            st.adj[a].add(b)
            st.adj[b].add(a)
            st.edge_index[(a, b)] = st._next_e  # edges already sorted
            st._next_e += 1

        triangles, tetrahedra = _triangles_and_tetrahedra_from_adj(st.adj)
        for tri in triangles:
            st.triangle_index[tri] = st._next_t
            st._next_t += 1
        for tet in tetrahedra:
            st.tetra_index[tet] = st._next_tet
            st._next_tet += 1

        # d1 columns: edges → vertices
        for e in st.edge_index:
            col = (1 << st.vertex_index[(e[0],)]) ^ (1 << st.vertex_index[(e[1],)])
            if _insert_column_mod2(st.basis_d1, col):
                st.rank_d1 += 1
        # d2 columns: triangles → edges
        for tri in st.triangle_index:
            col = _boundary_column(tri, st.edge_index)
            if _insert_column_mod2(st.basis_d2, col):
                st.rank_d2 += 1
        # d3 columns: tetras → triangles
        for tet in st.tetra_index:
            col = _boundary_column(tet, st.triangle_index)
            if _insert_column_mod2(st.basis_d3, col):
                st.rank_d3 += 1
        return st

    # ---- report -------------------------------------------------------

    def report(self):
        n_v = len(self.vertex_index)
        n_e = len(self.edge_index)
        n_t = len(self.triangle_index)
        if n_v == 0:
            return (0, 0, 0, 0)
        triangles = n_t
        betti_0 = max(0, n_v - self.rank_d1)
        betti_1 = max(0, n_e - self.rank_d1 - self.rank_d2)
        betti_2 = max(0, n_t - self.rank_d2 - self.rank_d3)
        return (triangles, betti_0, betti_1, betti_2)

    # ---- vertex / simplex registration --------------------------------

    def _ensure_vertex(self, v):
        key = (v,)
        if key not in self.vertex_index:
            self.vertex_index[key] = self._next_v
            self._next_v += 1
            self.adj.setdefault(v, set())

    def _register_edge(self, e):
        """Register edge simplex; return True if newly created."""
        e = tuple(sorted(e))
        if e in self.edge_index:
            return False
        self.edge_index[e] = self._next_e
        self._next_e += 1
        self.edges.add(e)
        a, b = e
        self.adj.setdefault(a, set()).add(b)
        self.adj.setdefault(b, set()).add(a)
        return True

    def _register_triangle(self, tri):
        tri = _sorted_simplex(tri)
        if tri in self.triangle_index:
            return False
        self.triangle_index[tri] = self._next_t
        self._next_t += 1
        return True

    def _register_tetra(self, tet):
        tet = _sorted_simplex(tet)
        if tet in self.tetra_index:
            return False
        self.tetra_index[tet] = self._next_tet
        self._next_tet += 1
        return True

    # ---- inductive edge addition --------------------------------------

    def add_edge(self, a, b):
        """Add undirected edge {a,b} and all newly completed simplices.
        Returns (n_new_edges, n_new_tris, n_new_tetras)."""
        a, b = _node_key(a), _node_key(b)
        if a == b:
            return (0, 0, 0)
        e = tuple(sorted((a, b)))
        if e in self.edge_index:
            return (0, 0, 0)

        self._ensure_vertex(a)
        self._ensure_vertex(b)
        common = self.adj.get(a, set()) & self.adj.get(b, set())

        # 1-simplex + d1 column
        self._register_edge(e)
        col_d1 = (1 << self.vertex_index[(a,)]) ^ (1 << self.vertex_index[(b,)])
        if _insert_column_mod2(self.basis_d1, col_d1):
            self.rank_d1 += 1
        n_e, n_t, n_tet = 1, 0, 0

        # New triangles {a,b,w} for each common neighbour w
        new_tris = []
        for w in common:
            tri = _sorted_simplex((a, b, w))
            if not self._register_triangle(tri):
                continue
            n_t += 1
            new_tris.append(tri)
            col_d2 = _boundary_column(tri, self.edge_index)
            if _insert_column_mod2(self.basis_d2, col_d2):
                self.rank_d2 += 1

        # New tetras {a,b,w,x}: pairs of common neighbours that are linked
        common_list = sorted(common, key=_node_key)
        for i, w in enumerate(common_list):
            nbrs_w = self.adj[w]
            for x in common_list[i + 1:]:
                if x not in nbrs_w:
                    continue
                tet = _sorted_simplex((a, b, w, x))
                if not self._register_tetra(tet):
                    continue
                n_tet += 1
                # faces: abw, abx must exist (just created); awx, bwx pre-exist
                col_d3 = _boundary_column(tet, self.triangle_index)
                if _insert_column_mod2(self.basis_d3, col_d3):
                    self.rank_d3 += 1

        return (n_e, n_t, n_tet)

    def add_edges(self, edge_iter):
        totals = [0, 0, 0]
        for a, b in edge_iter:
            de, dt, dtet = self.add_edge(a, b)
            totals[0] += de
            totals[1] += dt
            totals[2] += dtet
        return tuple(totals)


# Module-level live state for CIP-to-CIP inductive updates.
_topo_state = {"state": None}


def _clique_complex_report(edges):
    """Single-pass (triangles, betti_0, betti_1, betti_2) — full recompute,
    does not touch the live TopoState (used by helpers / tests)."""
    edge_set = _normalize_edge_set(edges)
    if not edge_set:
        return 0, 0, 0, 0
    return TopoState.from_edge_set(edge_set).report()


def _clique_complex_betti_1_2(edges):
    """(betti_1, betti_2) -- thin wrapper over the single-pass report."""
    _, _, b1, b2 = _clique_complex_report(edges)
    return b1, b2


def topology_invariants(edges):
    """[triangles, betti0, betti1, betti2] with inductive CIP updates.

    * Same edge set as last call → free hit.
    * Only new edges vs last state → patch local simplices + GF(2) columns.
    * Any removed edges → full rebuild (delete path deferred).

    Logs mode / delta / wall time for stall diagnosis.
    """
    edge_set = _normalize_edge_set(edges)
    st = _topo_state["state"]
    t0 = _time.perf_counter()

    if st is not None and edge_set == st.edges:
        report = st.report()
        print(f"[topo] cache hit edges={len(edge_set)}", flush=True)
        return list(report)

    if st is not None and edge_set.issuperset(st.edges):
        added = edge_set - st.edges
        n_e, n_t, n_tet = st.add_edges(added)
        report = st.report()
        dt = _time.perf_counter() - t0
        print(
            f"[topo] incremental +edges={len(added)} "
            f"new_e={n_e} new_tri={n_t} new_tet={n_tet} "
            f"edges={len(edge_set)} tri={report[0]} "
            f"b0={report[1]} b1={report[2]} b2={report[3]} "
            f"ms={dt * 1000:.1f}",
            flush=True,
        )
        return list(report)

    # Full rebuild: cold start, or edge deletions present.
    removed = 0 if st is None else len(st.edges - edge_set)
    st = TopoState.from_edge_set(edge_set)
    _topo_state["state"] = st
    report = st.report()
    dt = _time.perf_counter() - t0
    mode = "rebuild" if removed else "full"
    print(
        f"[topo] {mode} removed={removed} edges={len(edge_set)} "
        f"tri={report[0]} b0={report[1]} b1={report[2]} b2={report[3]} "
        f"ms={dt * 1000:.1f}",
        flush=True,
    )
    return list(report)


def reset_topology_state():
    """Drop live TopoState (tests / fresh runs)."""
    _topo_state["state"] = None


def count_voids(edges):
    _, betti_2 = _clique_complex_betti_1_2(edges)
    return betti_2


def connected_components(edges):
    G = _build_graph(edges)
    return nx.number_weakly_connected_components(G)


def count_undirected_cycles(edges):
    betti_1, _ = _clique_complex_betti_1_2(edges)
    return betti_1


def identify_modules(edges):
    """Weighted Louvain on undirected Hebbian graph. Edges (src,tgt) or
    (src,tgt,w); missing/nonpositive w → 0.5. resolution=1.01, seed=42."""
    G = nx.Graph()
    for item in edges or []:
        if not item or len(item) < 2:
            continue
        u, v = _node_key(item[0]), _node_key(item[1])
        if u == v:
            continue
        w = 0.5
        if len(item) >= 3:
            try:
                w = float(item[2])
            except (TypeError, ValueError):
                w = 0.5
            if w <= 0.0:
                w = 0.5
        if G.has_edge(u, v):
            G[u][v]['weight'] = max(G[u][v].get('weight', 0.0), w)
        else:
            G.add_edge(u, v, weight=w)
    if G.number_of_nodes() == 0:
        return []
    return [list(c) for c in louvain_communities(
        G, weight='weight', resolution=1.01, seed=42)]


# ---- Benchmark helpers -------------------------------------------------

def load_sentences(paths):
    """Read one or more .sent files (one sentence per line); return a single flat
    list of lowercase word atoms, in file order then line order -- so passing
    e.g. [insects.sent, poisons.sent] preserves a topic-switch stimulation order.

    Strips punctuation so each token is a clean symbol that PeTTa's stimulate can handle.
    Janus automatically converts the returned Python list to a Prolog/PeTTa cons-list.
    """
    if isinstance(paths, str):
        paths = [paths]
    words = []
    for path in paths:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    for tok in line.split():
                        w = re.sub(r"[^\w]", "", tok).lower()
                        if w:
                            words.append(w)
    return words


def read_avg_effectiveness(path):
    """Mean of all non-N/A 'effectiveness' values across a run's metrics.csv.

    Used to compare two already-completed runs over their full CIP history --
    calculate-effectiveness itself needs live &typeSpace state (via
    total-resource-cost), which no longer exists once a run has finished, so
    cross-run comparison uses each run's already-computed per-CIP numbers
    instead of recomputing anything. See evaluation/benchmark.metta's
    measure-gained-efficiency-from-eff, which takes the two resulting
    averages directly.
    """
    with open(path) as f:
        rows = list(csv.DictReader(f))
    vals = [float(row["effectiveness"]) for row in rows
            if row.get("effectiveness", "N/A") not in ("N/A", "")]
    return sum(vals) / len(vals) if vals else 0.0
