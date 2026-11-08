#!/usr/bin/env python3
"""Deck Builder: the status-aware Arena simulator (deckbuilder/sim)."""
import collections
import csv
import random
import sqlite3
import statistics
import tempfile
import unittest
from pathlib import Path

from deckbuilder_testlib import BUILD, FIX, cli_invoke, needs_master, needs_stage, tables
from deckbuilder import model, sim, stage


def template(cid=1, elem="fire", gauge_full=False, hp=100000.0):
    from deckbuilder.sim import units
    passives = [dict(op="advance", which="cs", frac=1.0, scope="self_01")] if gauge_full else []
    return dict(cid=cid, name=f"unit {cid}", elem=elem, hp=hp, atk=1000.0, df=1000.0, agi=1000.0, crit=0.1, critdmg=1.5,
                cs=dict(name="cs", gauge=1000, timed=False, ops=[], hits=1, combo=True), wskills=[], comp=None,
                passives=passives, team=collections.Counter(), mods=units.merge_mods([]), na=(1.0, 1))


def status(type_, ben, **kw):
    return dict(op="status", scope="self_01", prob=1, st=dict(type=type_, ben=ben, life=("frames", 1800), **kw))


@needs_master
class MechanicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sim.use(tables())
        from deckbuilder.sim import battle, rules
        cls.battle, cls.rules = battle, rules

    def fight(self, att, dfn):
        return self.battle.Battle(att, dfn, random.Random(0))

    def test_base_damage_is_the_clients(self):
        """CalculatorMath.GetBaseDamage (0x324A8D0): DEF at most halves a hit, and the base tops out near 300,000."""
        base = self.rules.base_damage
        self.assertEqual(base(50000, 428400), 26041)
        self.assertEqual(base(50000, 50000), 44274)
        self.assertEqual(base(50000, 10000), 68520)
        self.assertLess(base(10 ** 7, 1), 300000)
        self.assertEqual(self.rules.P["DAMAGE"], "game")

    def test_a_hit_is_capped_at_1_5_million(self):
        """CalculateAttackSkillExec clamps a hit to 1,500,000 (0x34F6248)."""
        f = self.rules.DAMAGE_FORMULAS["game"]
        self.assertEqual(f(50000, 1000.0, 1.0, 50000, self.rules.P), 1_500_000)
        self.assertEqual(f(50000, 1.0, 1.0, 50000, self.rules.P), 44274)

    def test_element_coefficients(self):
        adv = self.rules.ADV
        self.assertEqual(adv[("fire", "wind")], 1.2)
        self.assertEqual(adv[("wind", "fire")], 0.8)
        self.assertEqual(adv[("light", "dark")], 1.2)
        self.assertEqual(adv[("dark", "light")], 1.2)
        self.assertNotIn(("fire", "fire"), adv)

    def test_compromise_does_not_remove_active_dauntless(self):
        b = self.fight({"L": template(1)}, {"L": template(2)})
        u = b.sides["D"][0]
        b.apply(u, status(44, True, dauntless=True), None)
        b.apply(u, status(43, False), None)
        self.assertTrue(b.has(u, "dauntless"))           # still on
        u.st = [s for s in u.st if s["p"]["type"] != 44]
        b.apply(u, status(44, True, dauntless=True), None)
        self.assertFalse(b.has(u, "dauntless"))          # a new one is blocked

    def test_crush_is_cleansable(self):
        b = self.fight({"L": template(1)}, {"L": template(2)})
        u = b.sides["D"][0]
        b.apply(u, status(30, False, attr=[(2, "taken", 1.3)]), None)
        b.apply(u, dict(op="cleanse", scope="self_01", kinds=2), None)
        self.assertFalse([s for s in u.st if s["p"]["type"] == 30])

    def test_opening_order_right_left_middle(self):
        att = {s: template(i, gauge_full=True) for i, s in enumerate("LMR", 1)}
        dfn = {s: template(10 + i, gauge_full=True) for i, s in enumerate("LMR", 1)}
        for manual, first in ((True, "A"), (False, "D")):
            b = self.battle.Battle(att, dfn, random.Random(0), attacker_manual=manual)
            seen = []
            orig = b.run_ops
            def spy(u, ops, hits, comp_atk=None, b=b, orig=orig):
                if ops is u.t["cs"]["ops"]:
                    seen.append((round(b.t / self.rules.P["FPS"], 2), u.side, u.slot))
                return orig(u, ops, hits, comp_atk)
            b.run_ops = spy
            b.run_opening()
            self.assertEqual(seen[0][0], 3.0)
            self.assertEqual([x[1:] for x in seen[:3]], [(first, "R"), (first, "L"), (first, "M")], manual)
        self.assertIs(self.rules.P["ATTACKER_MANUAL"], True)

    def test_a_prepared_side_fights_the_same(self):
        """A side prepared once (start passives, team stats, starting HP: prepare_side) and copied into each fight ends
        every fight exactly as one set up from its templates; both roles, and when the other side's start passives
        reach across (then the fight is set up as usual)."""
        buff = dict(op="buff", scope="alive_all_self_party_01", key="Attack", value=0.2, frames=900, prob=1.0)
        reach = dict(op="buff", scope="alive_all_enemy_01", key="Attack", value=-0.1, frames=900, prob=1.0)
        x = {s: dict(template(i, gauge_full=True), agi=1200.0 + 10 * i, passives=[buff] + template(i, gauge_full=True)["passives"])
             for i, s in enumerate("LMR", 1)}
        y = {s: dict(template(10 + i, gauge_full=True, hp=60000.0), agi=900.0 + 10 * i) for i, s in enumerate("LMR", 1)}
        y_reach = {s: dict(t, passives=[reach] + t["passives"]) for s, t in y.items()}
        for role in ("A", "D"):
            prepared = self.battle.prepare_side(x, role)
            self.assertIsNotNone(prepared)
            for other in (y, y_reach):
                att, dfn = (x, other) if role == "A" else (other, x)
                for manual in (True, False):
                    for seed in (0, 1):
                        plain = self.battle.Battle(att, dfn, random.Random(seed), manual); plain.logging = False
                        fast = self.battle.Battle(att, dfn, random.Random(seed), manual, prepared=prepared); fast.logging = False
                        self.assertEqual(fast.run(), plain.run(), (role, other is y_reach, manual, seed))
                        self.assertEqual((fast.mirror_safe, fast.chance_draws), (plain.mirror_safe, plain.chance_draws))
        self.assertIsNone(self.battle.prepare_side(y_reach, "D"))       # its passives reach the other side

    def test_a_mirror_safe_fight_ends_the_same_with_the_roles_swapped(self):
        """When nothing in a fight depended on which side attacks (no turn-order tie between the sides, no close
        time-out, no start passive reaching the other side) and no draw could change anything, the same fight with the
        roles and openings swapped ends the same, mirrored (the bake uses it for its defense fights)."""
        x = {s: dict(template(i, gauge_full=True), agi=1200.0 + 10 * i) for i, s in enumerate("LMR", 1)}
        y = {s: dict(template(10 + i, gauge_full=True, hp=60000.0), agi=900.0 + 10 * i) for i, s in enumerate("LMR", 1)}
        for manual in (True, False):
            a = self.battle.Battle(x, y, random.Random(0), manual); a.logging = False
            ra = a.run()
            self.assertTrue(a.mirror_safe and a.chance_draws == 0)
            d = self.battle.Battle(y, x, random.Random(0), not manual); d.logging = False
            self.assertEqual(d.run(), self.battle.mirror(ra))

    def test_an_agility_tie_between_the_sides_is_not_mirror_safe(self):
        x = {"L": dict(template(1), agi=1000.0)}
        y = {"L": dict(template(2), agi=1000.0)}
        b = self.battle.Battle(x, y, random.Random(0)); b.logging = False
        b.run()
        self.assertFalse(b.mirror_safe)

    def test_a_one_turn_stun_skips_one_turn(self):
        """A status measured in turns counts down at its holder's turns: stunned for 1 turn, a unit loses its next
        turn and acts in the round after (it was 10 s of real time: several turns, which over-rated every stun)."""
        def first_actions(stun):
            att = {"L": template(1, hp=10 ** 9)}
            dfn = {"L": template(2, hp=10 ** 9)}
            b = self.battle.Battle(att, dfn, random.Random(0))
            b.frames = 15 * self.rules.P["FPS"]
            if stun:
                op = dict(op="status", scope="alive_all_enemy_01", prob=1.0,
                          st=dict(type=6, ben=False, stun=True, life=("turns", 1)))
                b.apply(b.sides["A"][0], op, None)
            b.run()
            acts = [(float(line[:5]), line[7:9]) for line in b.log]
            return acts, b.sides["D"][0].st
        plain, _ = first_actions(False)
        stunned, left = first_actions(True)
        self.assertEqual(plain[0][1], "DL")                      # unstunned, the defender opens the round
        self.assertEqual(stunned[0][1], "AL")                    # stunned, it loses that turn
        self.assertEqual(stunned[1][1], "DL")                    # and acts in the next round
        self.assertLess(stunned[1][0], 6.0)                      # not after 10 s
        self.assertFalse(any(s["p"].get("stun") for s in left))  # the stun is over

    def test_attack_debuffs_never_heal_the_target(self):
        """Attack debuffs past -100% (-50%, -50%, -15%: seen in the bake) once made the attacker's Attack negative,
        so its hits healed the target past its max HP. Stats floor at the client's minimums (power.K_MIN: Attack 1,
        crit rate 0, crit damage x1): damage is never negative."""
        att = {"L": template(1)}
        dfn = {"L": template(2, hp=100000.0)}
        b = self.battle.Battle(att, dfn, random.Random(0))
        u, tgt = b.sides["A"][0], b.sides["D"][0]
        u.bf = [dict(key="Attack", v=-0.5, left=900, src=1), dict(key="Attack", v=-0.5, left=900, src=2),
                dict(key="Attack", v=-0.15, left=900, src=3), dict(key="CriticalRatio", v=-0.5, left=900, src=4)]
        tgt.hp = 50000.0
        b.hit(u, tgt, 1.0, 1)
        self.assertLessEqual(tgt.hp, 50000.0)
        self.assertGreater(tgt.hp, 49000.0)        # Attack 1: a scratch, not a heal and not a full hit

    def test_score_runs_one_seed_when_no_draw_can_matter(self):
        """A fight whose random draws cannot change anything (no chance below 1, no shuffle that matters) plays the
        same on every seed: score runs it once per opening and counts it for every seed, the same result."""
        from unittest import mock
        att = {s: template(i, gauge_full=True) for i, s in enumerate("LMR", 1)}
        dfn = {s: template(10 + i, gauge_full=True, hp=50000.0) for i, s in enumerate("LMR", 1)}
        every = []
        for manual in self.battle.OPENINGS:
            for seed in range(4):
                b = self.battle.Battle(att, dfn, random.Random(seed), manual); b.logging = False
                every.append(b.run())
        want = (round(sum(r["win"] == "A" for r in every) / 8, 4), round(sum(r["hpA"] - r["hpD"] for r in every) / 8, 4))
        ran = []
        real_run = self.battle.Battle.run
        def counted(b):
            ran.append(1)
            return real_run(b)
        with mock.patch.object(self.battle, "_side", lambda d, t: d), mock.patch.object(self.battle.Battle, "run", counted):
            self.assertEqual(self.battle.score(att, dfn, tables(), runs=4), want)
        self.assertEqual(len(ran), 2)

    def test_a_fight_without_its_log_ends_the_same(self):
        """The bake turns the log off (it formats a line per action); the fight itself must not change."""
        att = {s: template(i, gauge_full=True) for i, s in enumerate("LMR", 1)}
        dfn = {s: template(10 + i, gauge_full=True, hp=50000.0) for i, s in enumerate("LMR", 1)}
        on = self.battle.Battle(att, dfn, random.Random(0))
        off = self.battle.Battle(att, dfn, random.Random(0)); off.logging = False
        a, b = on.run(), off.run()
        self.assertTrue(on.log)
        self.assertEqual(off.log, [])
        self.assertEqual({k: v for k, v in a.items() if k != "log"}, {k: v for k, v in b.items() if k != "log"})

    def test_time_out_with_both_sides_nearly_out_is_the_defenders(self):
        """At the time limit a side wins on HP share only when clearly ahead: two units held at 1 HP by Dauntless
        are a draw (the defender's), not a win for the side whose 1 HP is a larger share of a smaller maximum."""
        att = {"L": template(1, hp=1000.0)}
        dfn = {"L": template(2, hp=100000.0)}
        for a_hp, d_hp, winner in ((1, 1, "D"), (600, 1, "A"), (1, 60000, "D")):
            b = self.battle.Battle(att, dfn, random.Random(0))
            b.frames = 0
            b.sides["A"][0].hp, b.sides["D"][0].hp = a_hp, d_hp
            self.assertEqual(b.run()["win"], winner, (a_hp, d_hp))

    def test_score_counts_both_openings(self):
        """Who opens decides many fights, and the player may tap start skills by hand or leave them on Auto:
        a match is scored over both openings. Here the side that opens wins, so the score is half; the margin
        is the attacker's remaining HP share minus the defender's, averaged over every fight."""
        from unittest import mock
        def run(b):
            return dict(win="A" if b.attacker_manual else "D", hpA=0.6 if b.attacker_manual else 0.0,
                        hpD=0.0 if b.attacker_manual else 0.2)
        with mock.patch.object(self.battle.Battle, "run", run), mock.patch.object(self.battle, "_side", lambda d, t: {}):
            self.assertEqual(self.battle.score("a", "d", tables(), runs=3), (0.5, 0.2))
            self.assertEqual(self.battle.win_rate("a", "d", tables(), runs=3), 0.5)

    def test_damage_cuts_do_not_stack(self):
        """Several Indomitable damage cuts on one unit: only the strongest applies
        (multiplying them made the stall defense take ~22x less damage). Each
        still uses up one of its hits."""
        b = self.fight({"L": template(1)}, {"L": template(2, hp=1e9)})
        u, tgt = b.sides["A"][0], b.sides["D"][0]
        def dmg():
            hp0 = tgt.hp
            b.hit(u, tgt, 1.0, 1)
            return hp0 - tgt.hp
        tgt.st = []
        base = dmg()
        for v in (0.5, 0.3):
            b.apply(tgt, status(18, True, taken_mult=v, **{}) | {}, None)
        tgt.st = [dict(s, cnt=3) for s in tgt.st]
        self.assertAlmostEqual(dmg() / base, 0.3, places=6)
        self.assertEqual(sorted(s["cnt"] for s in tgt.st), [2, 2])

    def test_combo_multiplier(self):
        c = self.rules.Combo()
        rows = dict(c.table)
        c.count["A"] = 20
        self.assertEqual(c.coef("A"), 2.0)
        c.count["A"] = 6                                  # on-screen COMBO 6 uses the row for 5
        self.assertEqual(c.coef("A"), max(v for lo, v in c.table if lo <= 5))
        c.count["A"] = 1
        self.assertEqual(c.coef("A"), rows.get(0, 1.0))

    def test_cooldown_and_buff_clocks(self):
        b = self.fight({"L": template(1)}, {"L": template(2)})
        u = b.sides["A"][0]
        u.w = [600.0]
        u.bf = [dict(key="Attack", v=0.1, left=300, src=1)]
        b.tick(30)                                        # one second
        self.assertEqual(u.w, [540.0])                    # weapon cooldown: 60 per second (60 fps logic)
        self.assertEqual(u.bf[0]["left"], 270)            # buffs: 30 per second


# The video openings (opening_check.py of the research): attacker deck (L, M, R),
# the observed attacker skill order and the first skill's delay after the battle start.
OBS = [
    ((33032, 32035, 35018), ["R", "M"], 2.0), ((32035, 34048, 35036), ["R"], 1.75), ((32022, 32028, 34048), ["R", "L", "M"], 4.5),
    ((32022, 32028, 34048), ["R", "L", "M"], None), ((32035, 35036, 34039), ["L", "M"], 1.0), ((32035, 34048, 35036), ["L", "M", "R"], 4.0),
    ((32035, 35036, 34039), ["L", "M"], 1.0), ((32035, 35036, 34039), ["L", "M"], 1.0), ((32035, 34048, 35036), ["R", "L", "M"], 0.5),
    ((32035, 34048, 35036), ["R", "L"], 3.0), ((53002, 31032, 31030), ["M"], 5.5), ((53002, 31032, 31030), ["M"], 3.0),
    ((53002, 31032, 31030), ["M"], 3.5), ((31031, 53002, 31032), ["R"], 5.5), ((53002, 33030, 31032), ["M", "R"], 6.0),
    ((31030, 31032, 53002), ["M"], 3.5), ((31030, 31032, 53002), ["M"], 3.0), ((31030, 31032, 53002), ["M"], 2.0),
    ((31030, 31032, 53002), ["M"], 3.0), ((31030, 31032, 53002), ["M"], 3.0), ((53002, 33032, 33030), ["R"], 3.0),
]
DEFENSE = (31032, 35036, 33029)


@needs_stage
class VideoOpeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        costumes = sorted({c for deck, _, _ in OBS for c in deck} | set(DEFENSE))
        stage.Stager(cli_invoke(path), tables()).build(costume_ids=costumes)
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)
        sim.use(tables())

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def deck(self, costumes, number):
        specs = [model.CharacterSpec(model.PieceRef("costume", self.stage.pick("costume", costume_id=c), "stage"), None, [], None, [], None)
                 for c in costumes]
        return model.compose(self.stage, self.stage, specs, 2, number, tables())

    def test_opening_matches_video(self):
        from deckbuilder.sim import battle, rules, units
        P = rules.P
        dfn = dict(units.units_for(self.deck(DEFENSE, 2), tables()))
        first_ok, terr = 0, []
        for costumes, seq, t0 in OBS:
            att = dict(units.units_for(self.deck(costumes, 1), tables()))
            b = battle.Battle(att, dfn, random.Random(P["SEED"]))
            events = []
            orig = b.run_ops
            def spy(u, ops, hits, comp_atk=None, b=b, orig=orig):
                if ops is u.t["cs"]["ops"]:
                    events.append((b.t / P["FPS"], u.side, u.slot))
                return orig(u, ops, hits, comp_atk)
            b.run_ops = spy
            b.run_opening()
            a = [(t, s) for t, side, s in events if side == "A"]
            first_ok += bool(a) and a[0][1] == seq[0]
            if t0 is not None and a:
                terr.append(abs(a[0][0] - t0))
        self.assertGreaterEqual(first_ok, 19, f"first attacker skill right in {first_ok}/21")
        self.assertLessEqual(statistics.mean(terr), 1.2 + 0.05, f"mean first-skill timing error {statistics.mean(terr):.2f} s")


# Fights whose end the videos show: attacker (L, M, R), the defender, and the
# video's win time in seconds. DFMQmpJxA-A's Farplane attacks a stall team (the
# one the same video shows as its stall defense). Fo5jCU4TIxc's rank-1 deck
# (33032, 32035, 35018; won in 13 s) is left out: its opponent was unreadable,
# and the top defense is no stand-in for a rank-4 player's deck.
WIN_TIMES = [((32035, 34048, 35036), (32028, 34048, 31032), 32.0)]
# DFMQmpJxA-A 10:52.75: New Year's Belle Sarafa at 1% HP, Treason's Void Boon, a crit: 306,573.
VIDEO_HIT = 306573


@needs_stage
class WinTimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from deckbuilder import equip, experts
        cls.dir = tempfile.TemporaryDirectory(dir=BUILD)
        path = Path(cls.dir.name) / "stage.db"
        cls.experts = experts.Experts.load(tables())
        lineups = [l for a, d, _ in WIN_TIMES for l in (a, d)]
        stage.Stager(cli_invoke(path), tables()).build(**equip.stage_plan(lineups, tables(), cls.experts))
        cls.stage = model.Save(sqlite3.connect(f"file:{path}?mode=ro", uri=True), 1)

    @classmethod
    def tearDownClass(cls):
        cls.stage.db.close()
        cls.dir.cleanup()

    def deck(self, lineup, number):
        from deckbuilder import equip
        return equip.equip(lineup, equip.Mode("best"), self.stage, self.stage, tables(), self.experts, deck_number=number).deck

    def test_team_stat_passives_not_counted_twice(self):
        """The stats already hold every ability status, the party-wide ones
        included (power.character_stats); battle start must not add them again."""
        from deckbuilder.sim import battle, units
        sim.use(tables())
        side = dict(units.units_for(self.deck(WIN_TIMES[0][1], 2), tables()))
        b = battle.Battle(side, side, random.Random(0))
        for u in b.sides["A"]:
            self.assertEqual(u.maxhp, u.t["hp"], u.t["name"])
            self.assertEqual((u.team_atk, u.team_def), (0.0, 0.0), u.t["name"])

    def test_hit_matches_video(self):
        """Sarafa's Void Boon crit at 1% HP on the stall team's Saryu: within 10%
        of the 306,573 the video shows, with the client's damage formula (it fixed the old DEF_K guess)."""
        from deckbuilder.sim import battle, units
        sim.use(tables())
        att, dfn, _ = WIN_TIMES[0]
        b = battle.Battle(dict(units.units_for(self.deck(att, 1), tables())), dict(units.units_for(self.deck(dfn, 2), tables())), random.Random(0))
        sarafa = [u for u in b.sides["A"] if u.cid == 35036][0]
        saryu = [u for u in b.sides["D"] if u.cid == 34048][0]
        sarafa.hp, saryu.st, sarafa.t = sarafa.maxhp * 0.01, [], dict(sarafa.t, crit=1.0)
        ws = sarafa.t["wskills"][0]
        hp0 = saryu.hp
        b.hit(sarafa, saryu, [o for o in ws["ops"] if o["op"] == "dmg"][0]["power"], ws["hits"])
        self.assertLess(abs((hp0 - saryu.hp) / VIDEO_HIT - 1), 0.10, f"hit {hp0 - saryu.hp:.0f}, video {VIDEO_HIT}")

    def test_video_win_times_in_range(self):
        """The video's attack wins somewhere in the range a fight can take (seeds and both openings, as the bake scores
        decks: sim.score), and its wins land within half to twice the video's time. The video player's own memoirs and
        opening are unknown; this matchup turns on who fires their start-of-battle skills first (a revive decides it)."""
        for att, dfn, video in WIN_TIMES:
            a, d = self.deck(att, 1), self.deck(dfn, 2)
            fights = [sim.simulate(a, d, tables(), seed=s, attacker_manual=m) for s in range(8) for m in (True, False)]
            won = sorted(f["t"] for f in fights if f["win"] == "A")
            self.assertTrue(won, f"{att} never wins in {len(fights)} fights (video: a win in {video} s)")
            median = statistics.median(won)
            self.assertTrue(video / 2 <= median <= video * 2, f"{att}: median win {median:.1f} s, video {video} s")

if __name__ == "__main__":
    unittest.main()
