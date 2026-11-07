#!/usr/bin/env python3
"""Deck Builder: the generator (deckbuilder/generate.py)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, cli_invoke, needs_stage, tables
from deckbuilder import equip, experts, generate, model, stage

SARAFA, RION, MARIE, NY_YUDIL, SARYU, SUMMER_YURIE, PHANTASMAL_YUDIL, FESTIVE_FIO, FESTIVE_YURIE, LARS = (
    35036, 33029, 31032, 32035, 34048, 32028, 34040, 31029, 34047, 35035)
POOL = [SARAFA, RION, MARIE, NY_YUDIL, SARYU, SUMMER_YURIE, PHANTASMAL_YUDIL, FESTIVE_FIO, FESTIVE_YURIE, LARS]
TOP_DEFENSE = (MARIE, SARAFA, RION)


@needs_stage
class GenerateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        lineups = [tuple(POOL[i:i + 3]) for i in range(0, len(POOL), 3)] + [TOP_DEFENSE]
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan(lineups + [tuple(POOL[-3:])], tables(), cls.experts))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        cls.gen = generate.Generator(tables(), cls.experts, cls.stage, cls.stage, pool=POOL, meta_size=2, runs=2)
        cls.top_defense = equip.equip(TOP_DEFENSE, equip.Mode("best"), cls.stage, cls.stage, tables(), cls.experts, deck_number=99).deck

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def criteria(self, **kw):
        return generate.Criteria(**dict(dict(deck_for="attack", mode=equip.Mode("best"), against=self.top_defense), **kw))

    def test_generate_ranks_by_win_rate(self):
        page = self.gen.page(self.criteria(), 0, 6)
        self.assertEqual(len(page.items), 6)
        keys = [(r.win_rate, r.margin) for r in page.items]
        self.assertEqual(keys, sorted(keys, reverse=True))   # equal win rates: the wider margin first
        self.assertTrue(all(-1 <= r.margin <= 1 for r in page.items))
        self.assertEqual([r.rank for r in page.items], list(range(1, 7)))
        self.assertTrue(all(r.force > 0 for r in page.items))

    def test_data_pick_reason(self):
        items = self.gen.page(self.criteria(), 0, 30).items
        expert_ranks = [r.rank for r in items if r.expert]
        for r in items:
            below = [x for x in items if x.expert and x.rank > r.rank]
            if not r.expert and below and r.win_rate > below[0].win_rate:   # above it on margin alone: no badge
                self.assertIsNotNone(r.data_pick, r.lineup)
                self.assertEqual(r.data_pick.beats, below[0].name)
                self.assertGreater(r.data_pick.by, 0)
            elif not r.expert:
                self.assertIsNone(r.data_pick, r.lineup)
            if r.expert:
                self.assertIsNone(r.data_pick)

    def test_decks_are_named_by_their_characters(self):
        """A deck's name is its three characters, left to right; no source names ("Video …")."""
        items = self.gen.page(self.criteria(), 0, 30).items
        self.assertTrue(any(r.expert for r in items))
        for r in items:
            self.assertEqual(r.name, " · ".join(tables().character_name(c) for c in r.lineup))
            self.assertNotIn("Video", r.name)
            self.assertIn(r.strategy, generate.STRATEGY_NAME)

    def test_all_maxed_combines_the_pool_chosen_by_strength(self):
        """The pool prepare chose (screen.pool_by_strength), kept to the costumes the stage holds."""
        gen = generate.Generator(tables(), self.experts, self.stage, self.stage, best_pool=[LARS, SARAFA, 31001, RION])
        self.assertEqual(gen.pool(equip.Mode("best")), [LARS, SARAFA, RION])

    def test_a_required_costume_outside_the_pool_is_combined(self):
        """The picker lists every costume: one required from outside the pool joins it for that search."""
        gen = generate.Generator(tables(), self.experts, self.stage, self.stage, pool=POOL[:5], meta_size=1, runs=1)
        outsider = POOL[8]
        self.assertNotIn(outsider, gen.pool(equip.Mode("best")))
        page = gen.page(self.criteria(include=frozenset({outsider})), 0, 6)
        self.assertTrue(page.items)
        self.assertTrue(all(outsider in r.lineup for r in page.items))

    def test_filters(self):
        c = self.criteria(elements=(None, None, "water"), must_have=frozenset({"compromise"}), exclude=frozenset({SARAFA}),
                          min_stats={"agi": 1000})
        page = self.gen.page(c, 0, 10)
        self.assertTrue(page.items)
        for r in page.items:
            self.assertNotIn(SARAFA, r.lineup)
            self.assertIn("compromise", r.effects)
            self.assertEqual(r.elements[2], "water")
            self.assertTrue(all(s["agi"] >= 1000 for s in r.stats))

    def test_variants_fold(self):
        items = self.gen.page(self.criteria(), 0, 40).items
        sets = [frozenset(r.lineup) for r in items]
        self.assertEqual(len(sets), len(set(sets)))
        top = [r for r in items if frozenset(r.lineup) == frozenset(TOP_DEFENSE)]
        self.assertTrue(top and top[0].variants)

    def test_paging_stable(self):
        c = self.criteria()
        a = self.gen.page(c, 0, 6).items + self.gen.page(c, 6, 6).items
        b = self.gen.page(c, 0, 12).items
        self.assertEqual([r.lineup for r in a], [r.lineup for r in b])

    def test_to_add_skips_what_the_player_owns(self):
        """All maxed on a player who owns the costumes: the write uses the
        owned costumes and debris, so they are not counted as added."""
        import json
        from deckbuilder_testlib import FIX
        con = model.rows_to_db(json.loads((FIX / "saves" / "2d981f327817.json").read_text()))
        base = model.Save(con, 1)
        gen = generate.Generator(tables(), self.experts, base, self.stage, pool=POOL, meta_size=1, runs=1)
        r = gen.evaluate(TOP_DEFENSE, self.criteria())
        staged = len(r.equipped.to_add)
        owned_costumes = sum(1 for s in r.equipped.specs if base.pick("costume", costume_id=self.stage.piece_id("costume", s.costume.uuid)))
        self.assertEqual(owned_costumes, 3)
        self.assertLessEqual(r.to_add, staged - owned_costumes)

    def assert_valid_decks(self, items, base):
        costume_char = tables().idx("Costume", "CostumeId")
        for r in items:
            chars = [costume_char[c]["CharacterId"] for c in r.lineup]
            self.assertEqual(len(set(chars)), len(chars), f"{r.lineup}: a character twice")
            used = {}
            for c in r.deck.characters():
                self.assertIsNotNone(c.main_weapon, f"{r.lineup}: a character with no main weapon")
                for kind, p in [("costume", c.costume), ("debris", c.debris)]:
                    if p:
                        self.assertNotIn((kind, p.uuid), used, f"{r.lineup}: one {kind} on two characters")
                        used[(kind, p.uuid)] = 1

    def test_decks_are_valid_in_best_mode(self):
        self.assert_valid_decks(self.gen.page(self.criteria(), 0, 30).items, self.stage)

    def test_decks_are_valid_in_owned_mode(self):
        import json
        from deckbuilder_testlib import FIX
        base = model.Save(model.rows_to_db(json.loads((FIX / "saves" / "129f58f58f43.json").read_text())), 1)
        gen = generate.Generator(tables(), self.experts, base, self.stage, meta_size=1, runs=1)
        for allow in (0, 2):
            items = gen.page(self.criteria(mode=equip.Mode("owned", allow)), 0, 6).items
            self.assertTrue(items)
            self.assert_valid_decks(items, base)

    def test_owned_mode_scales_to_a_late_game_save(self):
        import json, time
        from deckbuilder_testlib import FIX
        base = model.Save(model.rows_to_db(json.loads((FIX / "saves" / "2d981f327817.json").read_text())), 1)
        gen = generate.Generator(tables(), self.experts, base, self.stage, meta_size=1, runs=1)
        self.assertLessEqual(len(gen.pool(equip.Mode("owned"))), generate.DEFAULT_POOL)
        t0 = time.time()
        page = gen.page(self.criteria(mode=equip.Mode("owned", 2)), 0, 6)
        self.assertTrue(page.items)
        self.assertLess(time.time() - t0, 20)

    def test_min_stats_leaving_nothing_says_so(self):
        page = self.gen.page(self.criteria(min_stats={"agi": 10 ** 9}), 0, 6)
        self.assertEqual((page.total, page.items, page.exhausted, page.relax), (0, [], True, "min_stats"))

    def test_generate_no_match(self):
        c = self.criteria(must_have=frozenset({"compromise"}), exclude=frozenset({NY_YUDIL}), elements=("fire", "fire", "fire"))
        page = self.gen.page(c, 0, 6)
        self.assertEqual((page.total, page.items, page.exhausted), (0, [], True))
        self.assertIn(page.relax, ("must_have", "exclude", "elements"))


if __name__ == "__main__":
    unittest.main()
