#!/usr/bin/env python3
"""Deck Builder: All maxed results baked at build time (deckbuilder/baked.py): the shipped format, its ranked
lists, the fighter fingerprint."""
import itertools
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_stage, tables
from deckbuilder import baked


def rec(l, aw, am, dw, dm, f):
    return baked.Record(tuple(l), aw, am, dw, dm, f)


ROWS = [rec((1, 2, 3), 1.0, 0.25, 0.8, 0.1, 400000), rec((1, 2, 4), 0.6, -0.1, 1.0, 0.5, 350000),
        rec((2, 3, 4), 0.6, 0.2, 0.0, -0.4, 500000), rec((4, 3, 1), 0.0, -0.9, 0.4, 0.05, 300000)]
LOADOUTS = {c: {"costume_id": c, "element": e, "role": "attacker", "main_weapon": 100 + c, "subs": [], "companion": None,
                "memoir_set": None, "debris": None} for c, e in ((1, "fire"), (2, "water"), (3, "wind"), (4, "dark"))}


class FormatTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name)
        baked.write(self.path, LOADOUTS, "abc123", ROWS, extra={"bake": "test"})
        self.b = baked.Baked.load(self.path)

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip_in_rank_order(self):
        """Attack ranks by attack win then margin (and Force), defense by defense win then margin; values kept to
        4 decimals, lineups in slot order."""
        self.assertEqual([r.lineup for r in self.b.records("attack")], [(1, 2, 3), (2, 3, 4), (1, 2, 4), (4, 3, 1)])
        self.assertEqual([r.lineup for r in self.b.records("defense")], [(1, 2, 4), (1, 2, 3), (4, 3, 1), (2, 3, 4)])
        self.assertEqual(self.b.records("attack")[0], ROWS[0])
        self.assertEqual(self.b.fingerprint, "abc123")
        self.assertEqual(self.b.element(2), "water")
        self.assertEqual(self.b.meta["bake"], "test")

    def test_keeps_only_the_top(self):
        b = baked.write(self.path, LOADOUTS, "x", ROWS, keep=2)
        b = baked.Baked.load(self.path)
        self.assertEqual([r.lineup for r in b.records("attack")], [(1, 2, 3), (2, 3, 4)])
        self.assertEqual([r.lineup for r in b.records("defense")], [(1, 2, 4), (1, 2, 3)])

    def test_missing_data_is_none(self):
        self.assertIsNone(baked.Baked.load(self.path / "nowhere"))


class DebrisTest(unittest.TestCase):
    """The game holds one of each debris: in a deck, a debris an earlier character already has is replaced on the
    later one by its next in order (first not taken)."""
    def test_a_debris_twice_goes_to_the_next(self):
        lo = {c: dict(LOADOUTS[c], debris=d) for c, d in ((1, 900), (2, 900), (3, 901))}
        order = lambda element: [900, 901, 902]
        out = baked.deck_loadouts((1, 2, 3), lo, order)
        self.assertEqual([x["debris"] for x in out], [900, 902, 901])
        self.assertEqual([x["costume_id"] for x in out], [1, 2, 3])
        self.assertEqual(lo[2]["debris"], 900)                  # the shared loadouts are not changed

    def test_no_debris_or_none_left(self):
        lo = {c: dict(LOADOUTS[c], debris=d) for c, d in ((1, 900), (2, 900), (3, None))}
        out = baked.deck_loadouts((1, 2, 3), lo, lambda e: [900])
        self.assertEqual([x["debris"] for x in out], [900, None, None])


@needs_stage
class GeneratorTest(unittest.TestCase):
    """All maxed against the general meta answered from the baked lists: their order, the same filters, the baked
    gear in the deck; the live search for what the bake does not cover."""
    POOL = [35036, 33029, 31032, 32035, 34048, 32028]

    @classmethod
    def setUpClass(cls):
        from deckbuilder import equip, experts, generate, model, stage
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.ex = experts.Experts.load(tables())
        meta = [l.costumes for l in sorted(cls.ex.meta_pool(), key=lambda l: -l.weight)[:1]]
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan([(c,) for c in cls.POOL] + meta, tables(), cls.ex))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        los = {}
        for c in cls.POOL:
            spec = equip.equip((c,), equip.Mode("best"), cls.stage, cls.stage, tables(), cls.ex).specs[0]
            pid = lambda kind, ref: cls.stage.piece_id(kind, ref.uuid) if ref else None
            los[c] = {"costume_id": c, "role": equip.role(c, cls.ex), "element": equip.element_of(c, tables()),
                      "main_weapon": pid("weapon", spec.main_weapon), "subs": [pid("weapon", w) for w in spec.subs],
                      "companion": pid("companion", spec.companion), "memoir_set": None, "debris": pid("debris", spec.debris)}
        cls.los = los
        char = {c: tables().idx("Costume", "CostumeId")[c]["CharacterId"] for c in cls.POOL}
        combos = [c for c in itertools.combinations(cls.POOL, 3) if len({char[x] for x in c}) == 3]
        cls.rows = [baked.Record(c, round(1 - i / 40, 4), 0.0, round(i / 40, 4), 0.0, 300000 + 1000 * i) for i, c in enumerate(combos)]
        cls.bdir = Path(cls.dir.name) / "baked"
        baked.write(cls.bdir, los, "fp", cls.rows)
        cls.gen = generate.Generator(tables(), cls.ex, cls.stage, cls.stage, baked=baked.Baked.load(cls.bdir), meta_size=1, runs=1)

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def criteria(self, **kw):
        from deckbuilder import equip, generate
        return generate.Criteria(**dict(dict(deck_for="attack", mode=equip.Mode("best")), **kw))

    def test_attack_and_defense_in_baked_order(self):
        page = self.gen.page(self.criteria(), 0, 4)
        self.assertEqual([r.lineup for r in page.items], [r.lineup for r in self.rows[:4]])
        self.assertEqual([r.rank for r in page.items], [1, 2, 3, 4])
        self.assertEqual(page.total, len(self.rows))
        r = page.items[0]
        self.assertEqual((r.win_rate, r.margin), self.gen.outcome(r.deck, self.criteria()))   # the written deck's own
        d = self.gen.page(self.criteria(deck_for="defense"), 0, 2)
        self.assertEqual([r.lineup for r in d.items], [r.lineup for r in sorted(self.rows, key=lambda r: -r.defense_win)[:2]])

    def test_filters_and_force_sort(self):
        page = self.gen.page(self.criteria(exclude=frozenset({35036})), 0, 50)
        self.assertTrue(page.items and all(35036 not in r.lineup for r in page.items))
        forced = self.gen.page(self.criteria(sort="force"), 0, 3)
        self.assertEqual([r.lineup for r in forced.items], [r.lineup for r in sorted(self.rows, key=lambda r: -r.force)[:3]])

    def test_the_deck_holds_the_baked_gear(self):
        r = self.gen.page(self.criteria(), 0, 1).items[0]
        for c, spec in zip(r.lineup, r.equipped.specs):
            self.assertEqual(self.stage.piece_id("weapon", spec.main_weapon.uuid), self.los[c]["main_weapon"])
        self.assertEqual(r.elements, tuple(self.los[c]["element"] for c in r.lineup))
        self.assertTrue(r.deck.characters()[0])

    def test_what_the_bake_does_not_cover_searches_live(self):
        """What I own, an opponent, minimum stats or Fewest to add depend on the player's save or the opponent: the live
        search answers them."""
        from deckbuilder import equip
        self.assertTrue(self.gen.baked_applies(self.criteria()))
        self.assertTrue(self.gen.baked_applies(self.criteria(deck_for="defense", sort="force")))
        for c in (self.criteria(mode=equip.Mode("owned", 2)), self.criteria(against=object()), self.criteria(min_stats={"agi": 1000}),
                  self.criteria(sort="fewest")):
            self.assertFalse(self.gen.baked_applies(c))

class StagePlanTest(unittest.TestCase):
    """The phone's stage holds every baked costume and piece (the baked decks are written from it)."""
    def test_plan_holds_the_baked_pieces_and_merges(self):
        import android_deckbuilder as db
        from deckbuilder_testlib import HAVE_MASTER
        if not HAVE_MASTER:
            self.skipTest("no master data")
        los = {c: dict(LOADOUTS[c], subs=[200 + c], companion=7 if c < 3 else None, memoir_set=10 if c == 1 else None,
                       debris=900 + (c % 2)) for c in LOADOUTS}
        b = baked.Baked(Path("."), {"costumes": sorted(los), "loadouts": {str(c): lo for c, lo in los.items()}, "fingerprint": "x"})
        plan = db._baked_plan(b, tables())
        self.assertEqual(plan["costume_ids"], [1, 2, 3, 4])
        self.assertEqual(plan["weapon_ids"], [101, 102, 103, 104, 201, 202, 203, 204])
        self.assertEqual((plan["companion_ids"], plan["thought_ids"]), ([7], [900, 901]))
        self.assertEqual(len(plan["memoirs"]), 6)                  # set 10: three pieces for each role
        merged = db._merge_plans({"costume_ids": [4, 9], "weapon_ids": [101], "companion_ids": [], "thought_ids": [], "memoirs": plan["memoirs"][:1]}, plan)
        self.assertEqual(merged["costume_ids"], [1, 2, 3, 4, 9])
        self.assertEqual(len(merged["memoirs"]), 6)


if __name__ == "__main__":
    unittest.main()
