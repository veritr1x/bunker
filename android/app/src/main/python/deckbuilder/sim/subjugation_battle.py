"""A Subjugation (Big Hunt) wave as the game plays it on Auto.

Every rule here comes from the game client (decoded from libil2cpp and the battle assets) or, where the client's
rule lives in an asset not decoded, from measurements of recorded fights (marked "measured"):

- Damage: the client's formula (rules.dmg_game: base damage, the 1,500,000 cap per hit). Against the boss the PvE
  element table applies (x1.5 advantage, x0.75 disadvantage; the Arena's is x1.2 / x0.8), and the boss takes x0.5
  from every element but its weakness (each boss's battle groups attach an "except element X" resist ability).
  While the boss is knocked down a hit is multiplied by the threshold's DamageRatio after the cap, at most
  45,000,000 (CalculatorActorStatusBigHunt.CalculateDamageValue), and the skill combo counts as 0.
- Knock-down: skill hits (not normal attacks) fill the gauge (bighunt.Phase.gauge); one skill adds at most 20% of
  the knock-down threshold; one knock-down per wave; a wave without one hands its gauge to the next wave. A
  knock-down lasts its threshold's frames, the boss does nothing meanwhile, and the wave's clock stops.
- A wave: the phase's NormalPhaseFrameCount at 30 frames per second (3,600 = 2:00 on the game's clock). It does not
  end inside a knock-down.
- Weapon skill cooldowns gain 1 per frame (the Arena's tuning ran them at the game's 2x speed).
- The turn order (gameplay/bt/gameflow): one unit acts at a time and the next starts at the previous action's
  handover; rounds run back to back, each one every unit, the boss included, by agility x random 950-1050 permil
  (a new round is queued when fewer than two units are left); a unit's requested skill is what it does on its turn
  (measured: each unit acts once a round, the recorded hit counts). The boss's turn holds the chain (measured: BOSS_TURN_S; what holds it lives in the skill act flow, not
  decoded); its casts still go off meanwhile. While it is knocked down the boss has no turns.
- The party on Auto (skill AI 1): weapon skills only, one drawn at random among those ready, each time any action
  finishes, the boss's included. Character skills and companion skills are never used on Auto (skill AI 1 leaves
  them out; player guides agree).
- The boss (skill AI 909, the same for all five bosses): at most one skill at a time, by fixed priority and action
  counters, each with its cast time; its main attack never targets a unit it hits at a disadvantage; never its
  character skill; nothing on its first AI run of a wave or while knocked down.
"""
from __future__ import annotations

import contextlib
import random
import threading

from deckbuilder.sim import battle, rules

P = rules.P
HIT_CAP_DOWN = 45_000_000
GAUGE_SKILL_SHARE = 0.20            # one skill fills at most this share of the knock-down threshold (guide)
PVE_ADV, PVE_DISADV = 1.5, 0.75     # AttributeDamageCoefficientGroup 1 (player) and 2 (NPC), BattleSchemeType 1
BOSS_RESIST = 0.5                   # the boss's "except its weakness" receive correction (CorrectionValuePermil 500)

# The game's pace. The client's rules (decoded) with one measured number: how long the boss's turn holds the chain.
SUBJUGATION = dict(
    CD_RATE=1.0,         # cooldown units per 30-fps frame (data: +1 per battle frame; the clock is 30 fps)
    BLIGHTED=0.0,        # the Arena assumes every unit starts with Blighted Flowers' head start
    ANIM_SCALE=3.5,      # action animations, x the Arena-calibrated frames (measured: fitted with BOSS_TURN_S on recorded fights)
    BOSS_TURN_S=12.0,    # seconds the boss's turn holds the chain (measured: fitted on recorded fights)
    OPEN_S=3.0,          # wave intro before the first action
    CHARACTER_SKILLS=False,  # played by hand: character skills too, when nothing else is ready (skill AI 2's order)
)
# The boss's skills by slot (weapon 9030511, skill_ai_0909): cast frames; slots 3 and 4 have no cooldown in the data.
BOSS_CAST = {0: 150, 1: 150, 2: 1800, 3: 0, 4: 90}
BOSS_NO_COOLDOWN = (2, 3)

_lock = threading.Lock()


@contextlib.contextmanager
def _params(over):
    """The simulator's parameters as Subjugation needs them, for the duration of one wave (P is shared with the Arena)."""
    with _lock:
        keep = {k: P[k] for k in ("CD_RATE", "BLIGHTED", "ANIM_CS", "ANIM_WS", "ANIM_NA", "ANIM_COMP")}
        P["CD_RATE"], P["BLIGHTED"] = over["CD_RATE"], over["BLIGHTED"]
        for k in ("ANIM_CS", "ANIM_WS", "ANIM_NA", "ANIM_COMP"):
            P[k] = keep[k] * over["ANIM_SCALE"]
        try:
            yield
        finally:
            P.update(keep)


def pve_coefficient(att_elem, tgt_elem) -> float:
    """The PvE element coefficient (the Arena table says which pairs are advantages)."""
    a = rules.ADV.get((att_elem, tgt_elem), 1.0)
    return PVE_ADV if a > 1 else PVE_DISADV if a < 1 else 1.0


def weakness(boss_elem) -> str | None:
    """The element the boss does not resist: the one with the advantage over it."""
    return next((a for (a, d), v in rules.ADV.items() if d == boss_elem and v > 1), None)


class SubjugationBattle(battle.Battle):
    def __init__(self, party, boss, phase, rng=None, gauge=0.0, params=None):
        """party: dict slot -> unit template; boss: the boss unit template (bighunt.boss_unit); phase: bighunt.Phase;
        gauge: knock-down gauge carried over from the previous wave."""
        self.par = dict(SUBJUGATION, **(params or {}))
        with _params(self.par):
            super().__init__(party, {"M": boss}, rng or random.Random(0), True)
        self.boss = self.sides["D"][0]
        self.phase = phase
        self.normal = phase.frames * P["FPS"] / 30            # the wave's clock in simulator frames
        self.kd_th = next((x for x in phase.thresholds if x.down), None)
        self.gauge_value = float(gauge); self.skill_gauge = 0.0
        self.down_until = -1.0; self.ratio = 1.0; self.knockdowns = 0; self.kd_frames = 0.0; self.kd_at = None
        self.dealt = 0.0; self.per = {}
        self.queue = []                                         # requested party skills: (unit, slot)
        b = self.boss; b.gmult = 1e9
        b.w = [0.0 if i in BOSS_NO_COOLDOWN else ws["cd"] * b.wmult for i, ws in enumerate(b.t["wskills"])]
        self.ai_init = False; self.ctr = dict(s1=0, s2=0, s4=0, l3=0, l4=0); self.cast = None; self.boss_casts = []

    # ---------------------------------------------------------------- state
    def down(self):
        return self.t < self.down_until

    def clock(self):
        """Seconds of the wave's clock used (it stops during a knock-down)."""
        return (self.t - self.kd_frames) / P["FPS"]

    def bad(self, e):
        """The boss hits e at a disadvantage."""
        return rules.ADV.get((self.boss.elem, e.elem), 1.0) < 1

    def taken_mult(self, tgt):
        return 1.0          # the knock-down ratio applies after the cap (on_hit)

    # ---------------------------------------------------------------- damage
    def hit(self, u, tgt, power, hits_in_skill, normal=False, pierce=False, comp_atk=None):
        k = pve_coefficient(u.elem, tgt.elem) / rules.ADV.get((u.elem, tgt.elem), 1.0)
        if tgt is self.boss and u.elem != weakness(self.boss.elem):
            k *= BOSS_RESIST
        if self.down():
            self._combo_target = False                          # no skill combo while the boss is down
        return super().hit(u, tgt, power * k, hits_in_skill, normal, pierce, comp_atk)

    def run_ops(self, u, ops, hits_in_skill, comp_atk=None):
        self.skill_gauge = 0.0
        return super().run_ops(u, ops, hits_in_skill, comp_atk)

    def on_hit(self, u, tgt, dmg, hits_in_skill, normal):
        if tgt is not self.boss:
            return
        dealt = min(dmg * (self.ratio if self.down() else 1.0), HIT_CAP_DOWN)
        self.dealt += dealt
        rec = self.per.setdefault(u.t["name"], [0.0, 0])
        rec[0] += dealt; rec[1] += 1
        if normal or self.down() or self.kd_th is None or self.knockdowns:
            return
        cap = GAUGE_SKILL_SHARE * self.kd_th.at
        add = min(self.phase.gauge(hits_in_skill, dmg), max(0.0, cap - self.skill_gauge))
        self.skill_gauge += add
        self.gauge_value = min(self.gauge_value + add, self.kd_th.at)
        if self.gauge_value >= self.kd_th.at:
            self.knockdowns = 1; self.ratio = self.kd_th.ratio; self.kd_at = round(self.clock(), 1)
            self.down_until = self.t + self.kd_th.frames * P["FPS"] / 30
            self.cast = None                                    # the boss's cast does not survive the knock-down

    # ---------------------------------------------------------------- time
    def advance(self, frames, acting=False):
        """frames pass (cooldowns run throughout: the client never pauses them in a battle)."""
        if self.down():
            self.kd_frames += min(frames, self.down_until - self.t)
        self.tick(frames)
        if self.cast is not None and not self.down():
            self.cast[1] -= frames

    def over(self):
        if not any(u.alive for u in self.sides["A"]):
            return True
        return (self.t - self.kd_frames) >= self.normal and not self.down()

    # ---------------------------------------------------------------- AIs
    def party_ai(self):
        """Skill AI 1 for every living party unit not already waiting: one ready weapon skill, drawn at random."""
        waiting = {id(u) for u, _ in self.queue}
        for u in self.sides["A"]:
            if not u.alive or id(u) in waiting:
                continue
            ready = [i for i, x in enumerate(u.w) if x <= 0]
            if ready:
                self.queue.append((u, ready[0] if len(ready) == 1 else self.rng.choice(ready)))
            elif self.par["CHARACTER_SKILLS"] and u.gauge >= u.t["cs"]["gauge"] * u.gmult:
                self.queue.append((u, "cs"))

    def boss_ai(self):
        """Skill AI 909: at most one skill, by priority; counters count AI runs."""
        b = self.boss
        if not b.alive or self.cast is not None:
            return
        if not self.ai_init:
            self.ai_init = True
            return
        if self.down():
            return
        c = self.ctr; c["s1"] += 1; c["s2"] += 1; c["s4"] += 1
        wave = self.phase.order
        ready = lambda i: b.w[i] <= 0
        pick = None
        if ready(4) and any(not self.bad(e) for e in self.enemies(b)):
            pick = 4
        elif wave == 2 and c["l3"] == 0 and ready(2):
            pick = 2; c["l3"] += 1
        elif wave == 3 and c["l4"] == 0 and c["s4"] >= 20 and self.knockdowns == 0 and ready(3):
            pick = 3; c["l4"] = 1
        elif c["s1"] >= 12 and ready(0):
            pick = 0; c["s1"] = 0
        elif c["s2"] >= 18 and ready(1):
            pick = 1; c["s2"] = 0
        if pick is not None:
            self.cast = [pick, BOSS_CAST[pick]]

    def pick(self, u, sc="alive_single_enemy_01"):
        if u is self.boss and "not_bad" in sc:
            es = [e for e in self.enemies(u) if not self.bad(e)]
            if es:
                return min(es, key=lambda e: e.hp / e.maxhp)
        return super().pick(u, sc)

    def enemies(self, u):
        if u is self.boss and self.down():
            return []
        return super().enemies(u)

    # ---------------------------------------------------------------- actions
    def finished(self, by_boss=False):
        """An action ended (anyone's): the AIs run."""
        self.boss_ai()
        self.party_ai()

    def party_skill(self, u, i):
        ws = u.t["wskills"][i]
        u.w[i] = ws["cd"] * u.wmult
        self.run_ops(u, ws["ops"], ws["hits"])
        if u.first_act is None:
            u.first_act = self.t
        self.advance(P["ANIM_WS"], acting=True)
        self.finished()

    def character_skill(self, u):
        if u.gauge < u.t["cs"]["gauge"] * u.gmult:
            return
        u.gauge = 0
        self.run_ops(u, u.t["cs"]["ops"], u.t["cs"]["hits"])
        self.advance(P["ANIM_CS"], acting=True)
        self.finished()

    def normal_attack(self, u):
        if not self.enemies(u):
            return
        pw, hits = u.t["na"]; tgt = self.pick(u); n = max(1, round(hits))
        for _ in range(n):
            self.hit(u, tgt, pw / n, n, normal=True)
        self.combo.on_action(u.side, True, normal=True)
        self.advance(P["ANIM_NA"], acting=True)
        self.finished()

    def boss_skill(self):
        i = self.cast[0]; self.cast = None
        b = self.boss; ws = b.t["wskills"][i]
        if i not in BOSS_NO_COOLDOWN:
            b.w[i] = ws["cd"] * b.wmult
        self.boss_casts.append((round(self.clock()), i + 1))
        self.run_ops(b, ws["ops"], ws["hits"])
        self.advance(P["ANIM_WS"], acting=True)
        self.finished(by_boss=True)

    def next_round(self):
        """Every living unit, the boss included, by agility x random 950-1050 permil, fastest first."""
        units = [u for s in ("A", "D") for u in self.sides[s] if u.alive]
        keyed = [((u.t["agi"] + u.agi_bonus) * self.rng.randint(950, 1050), i, u) for i, u in enumerate(units)]
        return [u for _, _, u in sorted(keyed, key=lambda x: (-x[0], x[1]))]

    def run(self):
        with _params(self.par):
            self.logging = getattr(self, "logging", True)
            self.advance(self.par["OPEN_S"] * P["FPS"])
            order, held_until = [], -1.0
            while not self.over():
                if self.cast is not None and self.cast[1] <= 0 and not self.down():
                    self.boss_skill()                           # a cast goes off as an interrupt, even mid-turn
                elif self.t < held_until and not self.down():
                    self.advance(P["STEP"])                     # the boss's turn holds the chain
                else:
                    if len(order) < 2:
                        order += self.next_round()
                    u = order.pop(0)
                    if not u.alive:
                        continue
                    if u is self.boss:
                        if not self.down():
                            held_until = self.t + self.par["BOSS_TURN_S"] * P["FPS"]
                            self.finished(by_boss=True)
                        continue
                    req = next((r for r in self.queue if r[0] is u), None)
                    if req is not None:
                        self.queue.remove(req)
                        if req[1] == "cs":
                            self.character_skill(u)
                        elif u.w[req[1]] <= 0:
                            self.party_skill(u, req[1])
                        else:
                            self.normal_attack(u)
                    else:
                        self.normal_attack(u)

    def result(self):
        return dict(damage=round(self.dealt), knockdowns=self.knockdowns, kd_at=self.kd_at,
                    gauge=0.0 if self.knockdowns else self.gauge_value, t=round(self.clock(), 1),
                    standing=sum(u.alive for u in self.sides["A"]),
                    per={k: (round(v[0]), v[1]) for k, v in self.per.items()}, boss_casts=self.boss_casts)


def wave(party, boss, phase, gauge=0.0, seed=0, params=None):
    """One wave: the result (damage, knock-downs, the gauge it hands on, ...)."""
    b = SubjugationBattle(party, boss, phase, random.Random(seed), gauge, params)
    b.logging = False
    b.run()
    return b.result()
