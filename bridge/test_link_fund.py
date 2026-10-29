"""Account checks for the priced link. No PeTTa."""

import json
import tempfile
import unittest
from pathlib import Path

import link_fund as lf
import scenario_from_snapshot as scn


class PriceTests(unittest.TestCase):
    def test_query_atoms_match_before_richer_atoms(self):
        ordered = lf.order_candidates(
            ["rich", "quiet", "ask"],
            ["ask"],
            {"rich": 9, "quiet": 3, "ask": 1},
        )
        self.assertEqual(ordered, ["ask", "rich", "quiet"])

    def test_cap_binds_while_credit_remains(self):
        account = lf.price_link(
            ["a", "b", "c"],
            {"a": 1, "b": 1, "c": 1},
            credit=100,
            k=2,
            admit_free=False,
        )
        self.assertEqual(account["held"], ["a", "b"])
        self.assertEqual(account["bound"], "cap")
        self.assertFalse(account["suspended"])
        self.assertEqual(account["remainder"], 98)
        self.assertFalse(account["forgotten"])

    def test_closed_suspension_drops_the_tail(self):
        account = lf.price_link(
            ["a", "b", "c"],
            {"a": 4, "b": 4, "c": 4},
            credit=5,
            k=12,
            admit_free=False,
        )
        self.assertEqual(account["held"], ["a"])
        self.assertEqual(account["bound"], "fund")
        self.assertTrue(account["suspended"])
        self.assertEqual(account["remainder"], 1)
        self.assertEqual(account["n_free"], 0)

    def test_open_suspension_admits_the_tail_free(self):
        account = lf.price_link(
            ["a", "b", "c"],
            {"a": 4, "b": 4, "c": 4},
            credit=5,
            k=12,
            admit_free=True,
        )
        self.assertEqual(account["held"], ["a", "b", "c"])
        self.assertEqual(account["bound"], "fund")
        self.assertTrue(account["suspended"])
        self.assertEqual(account["spent"], 4)
        self.assertEqual(account["remainder"], 1)
        self.assertEqual(account["n_free"], 2)

    def test_open_free_tail_stops_at_the_cap(self):
        account = lf.price_link(
            ["a", "b", "c"],
            {"a": 4, "b": 4, "c": 4},
            credit=5,
            k=2,
            admit_free=True,
        )
        self.assertEqual(account["held"], ["a", "b"])
        self.assertEqual(account["n_free"], 1)
        self.assertEqual(account["owned"], ["a"])
        self.assertEqual(account["bound"], "fund")
        self.assertNotIn("c", account["held"])

    def test_bought_atoms_stay_without_a_second_charge(self):
        first = lf.price_link(
            ["a", "b", "c"],
            {"a": 5, "b": 5, "c": 5},
            credit=12,
            k=2,
            admit_free=False,
        )
        self.assertEqual(first["owned"], ["a", "b"])
        second = lf.price_link(
            ["c", "a", "b"],
            {"a": 100, "b": 100, "c": 5},
            credit=first["remainder"],
            k=2,
            admit_free=False,
            owned=first["owned"],
        )
        self.assertEqual(second["held"], ["a", "b"])
        self.assertEqual(second["spent"], 0)
        self.assertEqual(second["n_retained"], 2)
        self.assertEqual(second["n_bought"], 0)
        self.assertEqual(second["remainder"], first["remainder"])
        self.assertEqual(second["bound"], "cap")
        self.assertEqual(second["owned"], ["a", "b"])

    def test_a_kept_atom_leaves_room_for_one_new_purchase(self):
        account = lf.price_link(
            ["b", "a"],
            {"a": 100, "b": 3},
            credit=6,
            k=2,
            admit_free=False,
            owned=["a"],
        )
        self.assertEqual(account["held"], ["a", "b"])
        self.assertEqual(account["spent"], 3)
        self.assertEqual(account["owned"], ["a", "b"])
        self.assertEqual(account["n_retained"], 1)
        self.assertEqual(account["n_bought"], 1)

    def test_absent_release_drops_only_atoms_missing_from_the_snapshot(self):
        kept, released = lf.release_owned(
            ["gone", "quiet", "ask"],
            ["ask"],
            {"quiet": 0.0, "ask": 4},
            ["quiet", "ask"],
            lf.RELEASE_ABSENT,
        )
        self.assertEqual(released, ["gone"])
        self.assertEqual(kept, ["quiet", "ask"])

    def test_dead_release_drops_absent_and_zero_sti(self):
        kept, released = lf.release_owned(
            ["gone", "quiet", "rich", "ask"],
            ["ask"],
            {"quiet": 0.0, "rich": 5, "ask": 0.0},
            ["quiet", "rich", "ask"],
            lf.RELEASE_DEAD,
        )
        self.assertEqual(released, ["gone", "quiet"])
        self.assertEqual(kept, ["rich", "ask"])

    def test_one_release_frees_the_cheapest_when_nothing_is_dead(self):
        kept, released = lf.release_owned(
            ["rich", "quiet", "mid"],
            ["rich"],
            {"rich": 9, "quiet": 1, "mid": 4},
            ["rich", "quiet", "mid"],
            lf.RELEASE_ONE,
        )
        self.assertEqual(released, ["quiet"])
        self.assertEqual(kept, ["rich", "mid"])

    def test_one_release_does_not_add_a_second_drop_when_a_slot_is_dead(self):
        kept, released = lf.release_owned(
            ["gone", "quiet", "rich"],
            [],
            {"quiet": 1, "rich": 5},
            ["quiet", "rich"],
            lf.RELEASE_ONE,
        )
        self.assertEqual(released, ["gone"])
        self.assertEqual(kept, ["quiet", "rich"])

    def test_released_slot_is_sold_to_the_query_atom(self):
        account = lf.price_link(
            ["ask", "rich", "quiet"],
            {"ask": 3, "rich": 9, "quiet": 1, "gone": 4},
            credit=10,
            k=2,
            admit_free=False,
            owned=["gone", "rich"],
            release=lf.RELEASE_ABSENT,
            query=["ask"],
            present=["ask", "rich", "quiet"],
        )
        self.assertEqual(account["released"], ["gone"])
        self.assertEqual(account["held"], ["rich", "ask"])
        self.assertEqual(account["spent"], 3)
        self.assertEqual(account["owned"], ["rich", "ask"])

    def test_empty_remainder_on_the_open_pass_is_all_free(self):
        account = lf.price_link(
            ["a", "b"],
            {"a": 3, "b": 3},
            credit=0,
            k=12,
            admit_free=True,
        )
        self.assertEqual(account["held"], ["a", "b"])
        self.assertEqual(account["spent"], 0)
        self.assertEqual(account["bound"], "fund")

    def test_wage_opens_the_next_period(self):
        first = lf.price_link(["a"], {"a": 10, "b": 1}, 10, k=12, admit_free=False)
        added = lf.wage_credit(2, wage=200)
        self.assertEqual(added, 400)
        second = lf.price_link(
            ["b"],
            {"b": 50},
            credit=first["remainder"] + added,
            k=12,
            admit_free=False,
        )
        self.assertEqual(second["credit_open"], 400)
        self.assertEqual(second["held"], ["b"])
        self.assertEqual(first["remainder"], 0)

    def test_offline_account_does_not_change_the_carried_credit(self):
        carried = {"remainder": 40.0}
        opening = carried["remainder"]
        offline = lf.price_link(
            ["a", "b"],
            {"a": 30, "b": 30},
            credit=opening,
            k=12,
            admit_free=False,
        )
        self.assertEqual(carried["remainder"], 40.0)
        self.assertEqual(offline["held"], ["a"])
        again = lf.price_link(
            ["a", "b"],
            {"a": 30, "b": 30},
            credit=opening,
            k=12,
            admit_free=False,
        )
        self.assertEqual(again, offline)

    def test_no_held_atom_is_forgotten(self):
        account = lf.price_link([], {}, credit=5, k=12, admit_free=False)
        self.assertTrue(account["forgotten"])
        self.assertEqual(account["bound"], "none")

    def test_focus_mass_ignores_atoms_outside_the_focus(self):
        self.assertEqual(lf.focus_mass(["a", "b"], {"a": 1.5, "b": 2, "c": 100}), 3.5)


class FocusOverrideTests(unittest.TestCase):
    def test_priced_focus_is_not_rebuilt_as_top_k(self):
        snap = {
            "source": "unit",
            "af": ["rich", "quiet", "ask"],
            "sti": {"rich": 50, "quiet": 40, "ask": 1, "other": 99},
            "edges": [["rich", "quiet", 0.5], ["ask", "quiet", 0.5], ["other", "rich", 0.5]],
            "query": {"objects": ["ask", "quiet"]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cip.json"
            path.write_text(json.dumps(snap), encoding="utf-8")
            meta = scn.generate(
                path,
                out_dir=tmp,
                name="priced_unit",
                focus_cap=2,
                focus_atoms=["ask"],
            )
            text = Path(meta["map_path"]).read_text(encoding="utf-8")
        focus_line = next(line for line in text.splitlines() if "(fx-focus)" in line)
        self.assertEqual(meta["focus"], ["ask"])
        self.assertIn("cons ask", focus_line)
        self.assertNotIn("rich", focus_line)


if __name__ == "__main__":
    unittest.main()
