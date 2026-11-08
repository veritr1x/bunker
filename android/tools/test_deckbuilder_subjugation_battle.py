#!/usr/bin/env python3
"""Deck Builder: a Subjugation wave as the game plays it on Auto (deckbuilder/sim/subjugation_battle.py), against
fights recorded on the emulator (D5 Fiery Cursed God; the game's Battle Report and result screens), with the very
decks they used (fixtures/deckbuilder/fights/fire_d5.json: the save's Subjugation decks 101-103):

  wave 1  Fio · Yuzuki · Sarafa      36.7M and 30.7M, knocked down about 1:45 into the wave
  wave 2  Yurie · Marie · 063y        1.1M and 1.0M, never knocked down
  wave 3  Levania · Saryu · Akeha    21.5M and about 28M
  a whole fight                       59.4M and 56.9M"""
import json
import random
import statistics
import unittest

from deckbuilder_testlib import FIX, needs_master, tables
from deckbuilder import bighunt, model, sim

FIGHT = FIX / "fights" / "fire_d5.json"


@needs_master
class RulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sim.use(tables())
        from deckbuilder.sim import subjugation_battle
        cls.sb = subjugation_battle

    def test_each_boss_is_weak_to_one_element(self):
        self.assertEqual({e: self.sb.weakness(e) for e in ("fire", "water", "wind", "light", "dark")},
                         {"fire": "water", "water": "wind", "wind": "fire", "light": "dark", "dark": "light"})

    def test_pve_elements(self):
        c = self.sb.pve_coefficient
        self.assertEqual((c("water", "fire"), c("fire", "water"), c("fire", "fire"), c("dark", "light")), (1.5, 0.75, 1.0, 1.5))


@needs_master
class RecordedFightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fight = json.loads(FIGHT.read_text())
        save_inputs = lambda n: dict(tables=cls.fight["tables"], user_id=1, deck_type=5, deck_number=n)
        sim.use(tables())
        from deckbuilder.sim import battle, subjugation_battle
        cls.sb = subjugation_battle
        decks = [model.Deck.from_inputs(save_inputs(w["deck_number"])) for w in cls.fight["waves"]]
        cls.parties = [battle._side(d, tables()) for d in decks]
        cls.f = bighunt.boss(tables(), cls.fight["boss_id"]).fights[cls.fight["difficulty"]]
        cls.unit = bighunt.boss_unit(cls.f, decks[0].save, tables())
        cls.runs = []
        for seed in range(5):
            g, waves = 0.0, []
            for i, party in enumerate(cls.parties):
                r = subjugation_battle.wave(party, cls.unit, cls.f.phases[i], gauge=g, seed=seed); g = r["gauge"]; waves.append(r)
            cls.runs.append(waves)

    def median(self, wave):
        return statistics.median(r[wave]["damage"] for r in self.runs)

    def test_the_water_deck_knocks_the_boss_down_late_in_wave_1(self):
        kd = [r[0]["kd_at"] for r in self.runs]
        self.assertTrue(all(k is not None for k in kd), kd)
        self.assertTrue(70 <= statistics.median(kd) <= 120, kd)

    def test_the_fire_deck_never_knocks_it_down_and_barely_scratches_it(self):
        self.assertTrue(all(r[1]["knockdowns"] == 0 for r in self.runs))
        self.assertLess(self.median(1), 3e6)

    def test_knocked_down_waves_within_twice_the_game(self):
        for wave in (0, 2):
            game = [f["damage"] for f in self.fight["waves"][wave]["fights"]]
            m = self.median(wave)
            self.assertTrue(min(game) / 2 <= m <= max(game) * 2, f"wave {wave + 1}: {m / 1e6:.1f}M, game {game}")

    def test_a_whole_fight_within_half_again_of_the_game(self):
        game = [t["damage"] for t in self.fight["totals"]]
        total = statistics.median(sum(w["damage"] for w in r) for r in self.runs)
        self.assertTrue(min(game) / 1.5 <= total <= max(game) * 1.5, f"{total / 1e6:.1f}M, game {game}")

    def test_character_skills_never_fire_on_auto(self):
        b = self.sb.SubjugationBattle(self.parties[0], self.unit, self.f.phases[0], random.Random(0))
        b.run()
        self.assertFalse([l for l in b.log if " A" in l[:10] and " CS " in l], "a character skill on Auto")
        self.assertFalse([l for l in b.log if " A" in l[:10] and "companion" in l], "a companion skill on Auto")


if __name__ == "__main__":
    unittest.main()
