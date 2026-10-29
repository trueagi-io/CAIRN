"""Binary PLN encoder. Inheritance stays the default. No PeTTa."""

import json
import os
import tempfile
import unittest
from pathlib import Path

import cognitive_synergy_io as io
import export_snapshot
import pln_encoding as enc
import premise_rank
import scenario_from_snapshot as scn


def _snap(**extra):
    base = {
        "source": "unit",
        "af": ["rich", "quiet", "ask"],
        "sti": {"rich": 50, "quiet": 40, "ask": 1, "other": 99},
        "edges": [["rich", "quiet", 0.5], ["ask", "quiet", 0.5], ["other", "rich", 0.5]],
        "query": {"objects": ["ask", "quiet"]},
    }
    base.update(extra)
    return base


class EncoderTests(unittest.TestCase):
    def test_default_is_inheritance(self):
        self.assertEqual(enc.link_of({}), "Inheritance")
        self.assertEqual(enc.link_of({"query": {"term_label": "Inheritance a b"}}), "Inheritance")
        self.assertEqual(enc.objects_from_label("Inheritance pressure millipedes"), ["pressure", "millipedes"])

    def test_passed_term_selects_implication(self):
        snap = {"query": {"term": ["Implication", "rain", "wet"]}}
        self.assertEqual(enc.link_of(snap), "Implication")
        self.assertEqual(enc.query_objects(snap), ["rain", "wet"])
        self.assertEqual(enc.objects_from_label("Implication rain wet"), ["rain", "wet"])

    def test_similarity_is_a_binary_encoder(self):
        self.assertEqual(enc.normalize("similarity"), "Similarity")
        self.assertEqual(enc.objects_from_label("Similarity alachlor peaweevil"), ["alachlor", "peaweevil"])

    def test_unknown_encoder_is_rejected(self):
        with self.assertRaises(ValueError):
            enc.normalize("Evaluation")

    def test_export_records_the_encoder(self):
        previous = os.environ.pop(enc.ENV_NAME, None)
        try:
            snap = export_snapshot.build_snapshot(
                "unit",
                ["ask", "quiet"],
                [["ask", 3], ["quiet", 1]],
                [["ask", "quiet", 0.4]],
            )
            self.assertEqual(snap["link"], "Inheritance")
            self.assertEqual(snap["query"]["term_label"], "Inheritance ask quiet")
            implied = export_snapshot.build_snapshot(
                "unit",
                ["ask", "quiet"],
                [["ask", 3], ["quiet", 1]],
                [["ask", "quiet", 0.4]],
                link="Implication",
            )
            self.assertEqual(implied["link"], "Implication")
            self.assertEqual(implied["query"]["term"], ["Implication", "ask", "quiet"])
        finally:
            if previous is not None:
                os.environ[enc.ENV_NAME] = previous

    def test_generate_keeps_inheritance_until_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cip.json"
            path.write_text(json.dumps(_snap()), encoding="utf-8")
            inherited = scn.generate(path, out_dir=tmp, name="inherited", focus_cap=2)
            implied = scn.generate(
                path, out_dir=tmp, name="implied", focus_cap=2, link="Implication"
            )
            inherited_text = Path(inherited["map_path"]).read_text(encoding="utf-8")
            implied_text = Path(implied["map_path"]).read_text(encoding="utf-8")
        self.assertEqual(inherited["link"], "Inheritance")
        self.assertIn('(= (fx-link) "Inheritance")', inherited_text)
        self.assertIn("(Inheritance ask quiet)", inherited_text)
        self.assertNotIn("Implication", inherited_text)
        self.assertEqual(implied["link"], "Implication")
        self.assertIn("(Table 1 Implication", implied_text)
        self.assertIn("(Implication ask quiet)", implied_text)
        self.assertNotIn("Inheritance", implied_text)

    def test_rank_query_uses_the_snapshot_encoder(self):
        snap = _snap(link="Implication", query={"objects": ["ask", "quiet"], "link": "Implication"})
        rows = [{"src": "ask", "tgt": "quiet", "weight": 0.5, "stamp": 1}]
        src = premise_rank._metta_src(snap, [("full", 1, rows)], 10)
        self.assertIn("(Implication ask quiet)", src)
        self.assertNotIn("Inheritance", src)
        self.assertEqual(premise_rank.query_label(snap), "Implication ask quiet")

    def test_neighbor_pairs_skip_both_encoders(self):
        self.assertIsNone(io._edge_pair(("Inheritance", "a")))
        self.assertIsNone(io._edge_pair(("Implication", "a")))
        self.assertIsNone(io._edge_pair(("Similarity", "a")))
        self.assertEqual(io._edge_pair(("ask", "quiet")), ("ask", "quiet"))


if __name__ == "__main__":
    unittest.main()
