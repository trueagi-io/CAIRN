"""Labeler checks for the community aperture. No PeTTa."""

import json
import tempfile
import unittest
from pathlib import Path

import community_aperture as ca
from utils import identify_modules


def _row(stamp, src, tgt):
    return {"stamp": stamp, "src": src, "tgt": tgt, "score": 1.0}


class LabelTests(unittest.TestCase):
    def test_one_community_intra_inter_and_direct(self):
        membership = {"a": 0, "b": 0, "c": 0, "x": 1}
        query = ["a", "b"]
        self.assertEqual(
            ca.label_premise("a", "c", query, membership, ""), "intra"
        )
        self.assertEqual(
            ca.label_premise("a", "x", query, membership, ""), "inter"
        )
        self.assertEqual(
            ca.label_premise("a", "b", query, membership, ""), "intra"
        )

    def test_split_query(self):
        membership = {"a": 0, "b": 0, "x": 1, "y": 1, "z": 2}
        query = ["a", "x"]
        self.assertEqual(
            ca.label_premise("a", "b", query, membership, ""), "intra"
        )
        self.assertEqual(
            ca.label_premise("a", "z", query, membership, ""), "inter"
        )
        self.assertEqual(
            ca.label_premise("a", "x", query, membership, ""), "bridge"
        )

    def test_outside_leg_absent(self):
        membership = {"a": 0, "b": 0}
        self.assertEqual(
            ca.label_premise("a", "z", ["a", "b"], membership, ""), "unassigned"
        )

    def test_query_atom_absent_skips_the_cut(self):
        membership = {"a": 0, "c": 0}
        rows = [_row(1, "a", "c"), _row(2, "a", "b")]
        labels, indices, one, reason = ca.label_rows(rows, ["a", "b"], membership)
        self.assertEqual(reason, "query_unassigned")
        self.assertFalse(one)
        self.assertEqual(indices, [0, None])
        self.assertEqual(set(labels.values()), {"unassigned"})
        counts = ca.side_counts(rows, labels)
        self.assertEqual(sum(counts.values()), len(rows))
        self.assertEqual(counts["unassigned"], 2)

    def test_accounting_identity(self):
        membership = {"a": 0, "b": 0, "c": 0, "x": 1, "z": 2}
        query = ["a", "x"]
        rows = [
            _row(1, "a", "b"),
            _row(2, "a", "z"),
            _row(3, "a", "x"),
            _row(4, "a", "missing"),
        ]
        labels, _, one, reason = ca.label_rows(rows, query, membership)
        self.assertFalse(one)
        self.assertEqual(reason, "")
        counts = ca.side_counts(rows, labels)
        self.assertEqual(
            counts,
            {"intra": 1, "inter": 1, "bridge": 1, "unassigned": 1},
        )
        self.assertEqual(sum(counts.values()), len(rows))

    def test_empty_arm_is_not_queried_and_shared_sets_collapse(self):
        full = [_row(1, "a", "b"), _row(2, "a", "c")]
        jobs = ca.query_jobs(
            {"full": full, "intra": [], "inter": full, "band": list(full)}
        )
        self.assertEqual([name for name, _rows in jobs], ["full"])

    def test_louvain_two_triangles(self):
        edges = [
            ("a", "b", 0.5),
            ("b", "c", 0.5),
            ("a", "c", 0.5),
            ("x", "y", 0.5),
            ("y", "z", 0.5),
            ("x", "z", 0.5),
        ]
        modules = identify_modules(edges)
        self.assertEqual(len(modules), 2)
        membership = ca.membership_from_modules(modules)
        self.assertEqual(membership["a"], membership["b"])
        self.assertNotEqual(membership["a"], membership["x"])
        query = ["a", "b"]
        self.assertEqual(
            ca.label_premise("a", "c", query, membership, ""), "intra"
        )
        self.assertEqual(
            ca.label_premise("a", "x", query, membership, ""), "inter"
        )

    def test_missing_sidecar_stops_before_pln(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cip_1.json").write_text(
                json.dumps({"cip_index": 1, "edges": [], "af": [], "sti": {}, "query": {}})
                + "\n",
                encoding="utf-8",
            )
            code = ca.run_community_sweep(probes_root=root, out=str(root / "out"))
            self.assertEqual(code, 2)
            self.assertFalse((root / "out" / "community_sweep.csv").exists())


def _scored(stamp, src, tgt, score):
    return {"stamp": stamp, "src": src, "tgt": tgt, "score": score, "weight": 0.5}


class FollowupSetTests(unittest.TestCase):
    def test_cip4_band_splits_by_stamp_and_arms_are_sides(self):
        rows = [
            _scored(1, "a", "b", 0.5),
            _scored(2, "a", "c", 0.9),
            _scored(3, "a", "d", 0.4),
            _scored(4, "a", "y", 0.3),
            _scored(5, "a", "z", 0.9),
            _scored(6, "a", "w", 0.2),
        ]
        membership = {
            "a": 0,
            "x": 1,
            "b": 0,
            "c": 0,
            "d": 0,
            "y": 2,
            "z": 2,
            "w": 2,
        }
        labels, _, _, reason = ca.label_rows(rows, ["a", "x"], membership)
        self.assertEqual(reason, "")
        sets = dict(ca.cip4_followup_sets(rows, labels))
        self.assertEqual([row["stamp"] for row in sets["intra"]], [1, 2, 3])
        self.assertEqual([row["stamp"] for row in sets["inter"]], [4, 5, 6])
        self.assertEqual({row["stamp"] for row in sets["band"]}, {2, 5})
        self.assertEqual(sets["band_a"][0]["stamp"], 2)
        self.assertEqual(sets["band_b"][0]["stamp"], 5)
        self.assertEqual(labels[sets["band_a"][0]["stamp"]], "intra")
        self.assertEqual(labels[sets["band_b"][0]["stamp"]], "inter")
        self.assertNotIn("-", "".join(sets))

    def test_cip5_drops_only_the_bridge_and_keeps_the_inter_tie(self):
        rows = [
            _scored(1, "a", "b", 0.4),
            _scored(2, "a", "x", 0.99),
            _scored(3, "a", "y", 0.8),
            _scored(4, "a", "z", 0.8),
            _scored(5, "a", "w", 0.1),
        ]
        membership = {"a": 0, "x": 1, "b": 0, "y": 2, "z": 2, "w": 2}
        labels, _, _, reason = ca.label_rows(rows, ["a", "x"], membership)
        self.assertEqual(reason, "")
        self.assertEqual(labels[2], "bridge")
        sets = dict(ca.cip5_followup_sets(rows, labels))
        self.assertEqual([row["stamp"] for row in sets["bridge"]], [2])
        self.assertEqual(
            [row["stamp"] for row in sets["full_minus_bridge"]], [1, 3, 4, 5]
        )
        self.assertEqual({row["stamp"] for row in sets["inter_band"]}, {3, 4})
        self.assertEqual([row["stamp"] for row in sets["intra"]], [1])

    def test_cip5_budget_sets_keep_inter_and_drop_only_the_bridge(self):
        rows = [
            _scored(1, "a", "b", 0.4),
            _scored(2, "a", "x", 0.99),
            _scored(3, "a", "y", 0.8),
            _scored(4, "a", "z", 0.8),
            _scored(5, "a", "w", 0.1),
        ]
        membership = {"a": 0, "x": 1, "b": 0, "y": 2, "z": 2, "w": 2}
        labels, _, _, reason = ca.label_rows(rows, ["a", "x"], membership)
        self.assertEqual(reason, "")
        sets = dict(ca.cip5_budget_sets(rows, labels))
        self.assertEqual(list(sets), ["full", "bridge", "inter", "full_minus_bridge"])
        self.assertEqual([row["stamp"] for row in sets["bridge"]], [2])
        self.assertEqual([row["stamp"] for row in sets["inter"]], [3, 4, 5])
        self.assertEqual(
            [row["stamp"] for row in sets["full_minus_bridge"]], [1, 3, 4, 5]
        )
        self.assertTrue(ca.anchor_ok(5, 10, "inter", True, 0.4736842105263158))
        self.assertTrue(ca.anchor_ok(5, 10, "full_minus_bridge", False, 0.0))
        self.assertFalse(ca.anchor_ok(5, 10, "full_minus_bridge", True, 0.47))

    def test_named_jobs_skip_empty_and_shared_sets(self):
        one = [_scored(1, "a", "b", 0.1)]
        two = [_scored(2, "a", "c", 0.2)]
        jobs = ca.named_jobs(
            [("full", one + two), ("empty", []), ("same", list(one + two)), ("only", one)]
        )
        self.assertEqual([name for name, _rows in jobs], ["full", "only"])

    def test_anchor_ok(self):
        conf = 0.4736842105263158
        self.assertTrue(ca.anchor_ok(4, 10, "full", True, conf))
        self.assertTrue(ca.anchor_ok(5, 10, "bridge", True, 0.9))
        self.assertTrue(ca.anchor_ok(5, 10, "intra", False, 0.0))
        self.assertFalse(ca.anchor_ok(4, 10, "intra", True, 0.0))
        self.assertFalse(ca.anchor_ok(4, 10, "full", True, conf + 1e-6))
        self.assertFalse(ca.anchor_ok(5, 10, "full", None, 0.9))
        self.assertTrue(ca.anchor_ok(4, 5, "band_a", False, 0.0))


if __name__ == "__main__":
    unittest.main()
