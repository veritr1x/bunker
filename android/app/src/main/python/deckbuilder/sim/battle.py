"""The battle engine (ported from the research prototype's sim.py; logic
unchanged). Units are templates from deckbuilder.sim.units, built from a deck's
real pieces and stats."""
import collections
import random

from deckbuilder.sim import rules
from deckbuilder.sim.rules import P, ADV, ELEMN, ABN_SHORT

def _bsum(x, k):
    """The sum of x's buffs of kind k, in order from 0 (as sum() over them). A plain loop, not a closure: the
    bake compiles this module with Cython, which cannot type methods holding closures."""
    total = 0
    for b in x.bf:
        if b["key"] == k:
            total += b["v"]
    return total


class U:
    def __init__(self, tmpl, side, slot):
        self.t = tmpl; self.side = side; self.slot = slot; self.cid = tmpl["cid"]; self.elem = tmpl["elem"]
        self.maxhp = tmpl["hp"]; self.atk = tmpl["atk"]; self.df = tmpl["df"]
        self.hp = self.maxhp; self.alive = True
        if P["AGI_BUILD"] and (P["AGI_BUILD_FOR"] == "all" or any(o["op"] == "buff" and o["key"] == "Agility" and o["value"] > 0 for o in tmpl["passives"]) or tmpl["agi"] > 1000):
            self.agi_bonus = P["AGI_BUILD"]
        else: self.agi_bonus = 0
        self.st = []          # statuses: dict(p=params, left=frames|None, cnt=count|None, src)
        self.bf = []          # buffs: dict(key, v, left)
        self.team_atk = self.team_def = self.team_crit = self.team_cdmg = 0.0
        self.gauge = 0.0; self.gmult = 1.0; self.wmult = P["HASTE_MULT"]
        self.w = [ws["cd"] * (1 - P["BLIGHTED"]) for ws in tmpl["wskills"]]
        self.comp = (tmpl["comp"]["cd"] if tmpl["comp"] else None)
        self.na = None; self.lock = 0; self.first_act = None; self.died_at = None; self.cs_ready = None

    def clone(self):
        """A copy for another fight: the same state, its own statuses, buffs and cooldowns (fights change them);
        the template is shared (fights do not)."""
        c = U.__new__(U)
        c.t = self.t; c.side = self.side; c.slot = self.slot; c.cid = self.cid; c.elem = self.elem
        c.maxhp = self.maxhp; c.atk = self.atk; c.df = self.df; c.hp = self.hp; c.alive = self.alive
        c.agi_bonus = self.agi_bonus
        c.st = [dict(x) for x in self.st]; c.bf = [dict(x) for x in self.bf]
        c.team_atk = self.team_atk; c.team_def = self.team_def; c.team_crit = self.team_crit; c.team_cdmg = self.team_cdmg
        c.gauge = self.gauge; c.gmult = self.gmult; c.wmult = self.wmult
        c.w = list(self.w); c.comp = self.comp
        c.na = self.na; c.lock = self.lock; c.first_act = self.first_act; c.died_at = self.died_at; c.cs_ready = self.cs_ready
        return c


def reaches_enemy(templates):
    """Whether any of these units' start passives acts on the other side (a cooldown change, a buff or a status)."""
    for t in templates:
        for o in t["passives"]:
            if o["op"] in ("cdmult", "status", "buff") and "enemy" in o.get("scope", ""):
                return True
    return False


class _RecordingRandom(random.Random):
    """A Random that records its calls, to replay them on another (the same consumption of its state)."""
    def __init__(self, seed=0):
        super().__init__(seed); self.calls = []

    def random(self):
        self.calls.append(("random", 0))
        return super().random()

    def shuffle(self, x, *a, **kw):
        self.calls.append(("shuffle", len(x)))
        return super().shuffle(x, *a, **kw)


class PreparedSide:
    """A side set up once (start passives, team stats, starting HP and timing) to copy into fights: prepare_side."""
    def __init__(self, side, units, calls):
        self.side, self.units, self.calls = side, units, calls

    def replay(self, rng):
        for kind, n in self.calls:
            if kind == "random": rng.random()
            else: rng.shuffle(list(range(n)))


def prepare_side(templates, side):
    """The side ("A" or "D") of these unit templates set up once, or None when that cannot stand in for setting it up
    in each fight: its start passives reach the other side, or a draw in them could change something."""
    if reaches_enemy(templates.values()):
        return None
    rng = _RecordingRandom(0)
    b = Battle(templates if side == "A" else {}, {} if side == "A" else templates, rng)
    if b.chance_draws:
        return None
    return PreparedSide(side, b.sides[side], rng.calls)


class Battle:
    def __init__(self, att, dfn, rng, attacker_manual=None, prepared=None):
        """att, dfn: dict slot -> unit template (units.build_unit). attacker_manual: whose start-of-battle skills
        go first (True: the attacker's, tapped by hand; False: the defender's, Auto); None = P["ATTACKER_MANUAL"].
        prepared (prepare_side): that side copied, set up already, unless the other side's start passives reach it
        (then it is set up from its templates as usual); the same fight either way."""
        self.attacker_manual = P["ATTACKER_MANUAL"] if attacker_manual is None else attacker_manual
        self.frames = P["DURATION_S"] * P["FPS"]     # the time limit
        self.rng = rng; self.t = 0; self.log = []
        self.logging = True      # a line per action in self.log (the bake turns it off: it only needs the result)
        self.chance_draws = 0    # random draws that could change something (a chance below 1, a shuffle that matters):
                                 # with none, every seed plays the same fight (the bake runs one seed then)
        # mirror_safe: nothing here depended on which side attacks (no turn-order tie between the sides, no close
        # time-out, no start passive reaching the other side; with chance_draws == 0 as well, the same fight with the
        # roles and openings swapped ends the same, mirrored: mirror()). Only the queue/hybrid engine is checked.
        self.mirror_safe = P["ENGINE"] == "queue" and P["ACTION_MODEL"] == "hybrid"
        use = prepared
        if use is not None and reaches_enemy((dfn if use.side == "A" else att).values()):
            use = None
        self.sides = {"A": [u.clone() for u in use.units] if use is not None and use.side == "A" else [U(t, "A", s) for s, t in att.items()],
                      "D": [u.clone() for u in use.units] if use is not None and use.side == "D" else [U(t, "D", s) for s, t in dfn.items()]}
        self.combo = rules.Combo(P["COMBO"] != "off", P["COMBO_COUNT_NA"], P["COMBO_RESET"]); self._combo_target = False
        self.first_kill = None; self.na_done = 0; self.batch_left = None; self.comp_events = []; self.blocked = collections.Counter(); self.first_ben = {}
        for side in ("A", "D"):
            if use is not None and side == use.side:
                use.replay(self.rng)          # the draws its setup took, at the same point
                continue
            for u in self.sides[side]: self.start_passives(u)
        for side in ("A", "D"):
            if use is not None and side == use.side:
                continue
            for u in self.sides[side]:
                u.hp = u.maxhp
                u.na = self.na_interval(u) * P["FIRST_NA_FRAC"]

    # ---------- helpers ----------
    def allies(self, u): return [x for x in self.sides[u.side] if x.alive]
    def enemies(self, u): return [x for x in self.sides["D" if u.side == "A" else "A"] if x.alive]
    def has(self, u, key):
        for s in u.st:
            if s["p"].get(key):
                return True
        return False
    def agility(self, u): return (u.t["agi"] + u.agi_bonus) * (1 + _bsum(u, "Agility"))
    def na_interval(self, u): return P["NA_BASE_FRAMES"] * 1000 / max(self.agility(u), 100)

    def start_passives(self, u):
        for (stat, kind, cond), v in u.t["team"].items():
            for a in self.sides[u.side]:
                if cond and a.elem != cond: continue
                share = P["WEAPON_SHARE"] if cond else 1.0
                if stat == "atk": a.team_atk += v * share
                elif stat == "def": a.team_def += v * share
                elif stat == "hp": a.maxhp *= 1 + v * share
                elif stat == "critrate": a.team_crit += v
                elif stat == "critdmg": a.team_cdmg += v
        for o in u.t["passives"]:
            if o["op"] == "advance":
                if o["which"] == "cs": u.gauge += o["frac"] * u.t["cs"]["gauge"]
                else: u.w = [max(0, x - o["frac"] * ws["cd"]) for x, ws in zip(u.w, u.t["wskills"])]
            elif o["op"] == "cdmult":
                if "enemy" in o.get("scope", "self_01"): self.mirror_safe = False
                tg = self.scope(u, o.get("scope", "self_01"))
                for a in tg:
                    if o["which"] == "cs": a.gmult *= o["mult"]
                    else: a.wmult *= o["mult"]
            elif o["op"] in ("status", "buff"):
                if "enemy" in o.get("scope", ""): self.mirror_safe = False
                self.apply(u, o, None, at_start=True)

    def scope(self, u, sc, target=None):
        if sc in ("self_01",): return [u]
        if sc.startswith("alive_all_self_party"):
            al = self.allies(u)
            if "without_self" in sc: al = [a for a in al if a is not u]
            if "match_attribute" in sc: al = [a for a in al if a.elem == u.elem]
            return al
        if sc.startswith("alive_single_ally"): return [max(self.allies(u), key=lambda a: a.atk)] if self.allies(u) else []
        if sc.startswith("dead"): return [x for x in self.sides[u.side] if not x.alive][:1]
        if sc == "alive_all_enemy_01": return self.enemies(u)
        if "enemy" in sc: return [target] if target and target.alive else ([self.pick(u, sc)] if self.enemies(u) else [])
        return [u]

    def pick(self, u, sc="alive_single_enemy_01"):
        es = self.enemies(u)
        prov = [e for e in es if self.has(e, "provoke")]
        if prov: return prov[0]
        if P.get("FOCUS_CID") and u.side == "A":   # Lisy's rule test: attackers focus this costume when it is not under Dauntless
            f = [e for e in es if e.cid == P["FOCUS_CID"] and not self.has(e, "dauntless")]
            if f: return f[0]
        if "highest_attack" in sc or P["TARGET_RULE"] == "highest_atk": return max(es, key=lambda e: e.atk)
        if P["TARGET_RULE"] == "slot":
            order = {s: i for i, s in enumerate(P["SLOT_ORDER"])}
            same = [e for e in es if e.slot == u.slot]
            return same[0] if same else min(es, key=lambda e: order[e.slot])
        if P["TARGET_RULE"] == "smart":
            live = [e for e in es if not self.has(e, "dauntless")] or es
            return min(live, key=lambda e: e.hp / e.maxhp)
        return min(es, key=lambda e: e.hp)

    # ---------- effects ----------
    def apply(self, src, o, target, at_start=False):
        op = o["op"]
        if op == "buff":
            if o.get("prob", 1) < 1: self.chance_draws += 1
            if self.rng.random() > o.get("prob", 1): return
            for a in self.scope(src, o["scope"], target):
                a.bf = [b for b in a.bf if not (b["key"] == o["key"] and b["src"] == id(o))]
                a.bf.append(dict(key=o["key"], v=o["value"], left=o["frames"], src=id(o)))
        elif op == "status":
            if o.get("prob", 1) < 1: self.chance_draws += 1
            if self.rng.random() > o.get("prob", 1): return
            p = o["st"]
            for a in self.scope(src, o["scope"], target):
                if p["ben"]:
                    if any(s["p"].get("type") == 43 for s in a.st):
                        self.blocked[(a.side, a.cid, p["type"])] += 1; continue
                else:
                    res = [r for s in a.st for r in s["p"].get("resist", []) if (r[0] == 3 and r[1] in (0, p["type"]))]
                    for r in res:
                        if 0 < r[2] < 1: self.chance_draws += 1; break
                    if any(self.rng.random() < r[2] for r in res): continue
                kind, v = p["life"]
                rec = dict(p=p, left=None, cnt=None, src=id(o))
                if kind == "frames": rec["left"] = v if v < 54000 else 10 ** 9
                elif kind == "turns": rec["turns"] = v if v < 999 else None    # counted at its holder's turns (count_turn)
                elif kind == "ticks": rec["left"] = v * P["TICK_FRAMES"]
                elif kind == "hits": rec["cnt"] = v
                a.st = [s for s in a.st if not (s["p"]["type"] == p["type"] and s["src"] == id(o))]
                a.st.append(rec)
                if p["type"] == 43:
                    self.comp_events.append(dict(t=self.t / P["FPS"], by=src.cid, target=a.cid, side=a.side, target_had_ben=sorted({s["p"]["type"] for s in a.st if s["p"]["ben"]})))
                if p["ben"] and not at_start and (a.side, a.cid) not in self.first_ben: self.first_ben[(a.side, a.cid)] = self.t / P["FPS"]
        elif op == "heal":
            for a in self.scope(src, o["scope"], target): a.hp = min(a.maxhp, a.hp + o["ratio"] * a.maxhp)
        elif op == "revive":
            for a in self.scope(src, o["scope"], target):
                a.alive = True; a.hp = o["ratio"] * a.maxhp; a.st = []; a.bf = []
        elif op == "hpcost":
            src.hp = max(1, src.hp * (1 - o["ratio"]))
        elif op == "advance":
            for a in self.scope(src, o["scope"], target):
                if o["which"] == "cs": a.gauge += o["frac"] * a.t["cs"]["gauge"]
                else: a.w = [max(0, x - o["frac"] * ws["cd"]) for x, ws in zip(a.w, a.t["wskills"])]
        elif op == "cleanse":
            for a in self.scope(src, o["scope"], target):
                kinds = sorted({s["p"]["type"] for s in a.st if not s["p"]["ben"]})
                if len(kinds) > o["kinds"]: self.chance_draws += 1     # which ones are removed depends on the shuffle
                self.rng.shuffle(kinds)
                for k in kinds[:o["kinds"]]: a.st = [s for s in a.st if s["p"]["type"] != k]
        elif op == "purge":
            for a in self.scope(src, o["scope"], target):
                kinds = sorted({s["p"]["type"] for s in a.st if s["p"]["ben"]})
                if len(kinds) > o["kinds"]: self.chance_draws += 1
                self.rng.shuffle(kinds)
                for k in kinds[:o["kinds"]]: a.st = [s for s in a.st if s["p"]["type"] != k]
        elif op == "removebuff":
            for a in self.scope(src, o["scope"], target):
                pos = [b for b in a.bf if (b["v"] > 0) == o["positive"]]
                for b in pos[-o["n"]:]: a.bf.remove(b)

    def hit(self, u, tgt, power, hits_in_skill, normal=False, pierce=False, comp_atk=None):
        if not tgt.alive: return
        if normal and self.has(tgt, "defiance"): return
        # Stats floor at the client's minimums (power.K_MIN: Attack 1, crit rate 0, crit damage x1, DEF 1): debuffs
        # past -100% must not turn a hit into a heal.
        atk = max(1.0, (comp_atk or u.atk) * (1 + _bsum(u, "Attack") + u.team_atk))
        crit = max(0.0, min(1, u.t["crit"] + _bsum(u, "CriticalRatio") + u.team_crit))
        cd = max(1.0, u.t["critdmg"] + _bsum(u, "CriticalAttack") + u.team_cdmg)
        m = 1 + crit * (cd - 1)
        m *= ADV.get((u.elem, tgt.elem), 1.0)
        m *= 1 + P["BOARD_ELEM_DMG"]   # character board: own-element damage +9% (every character)
        add = 0.0
        for s in u.st:
            p = s["p"]
            for el, kind, v in p.get("attr", []):
                if kind == "dealt" and ELEMN.get(el) == u.elem: m *= v
            add += p.get("dealt_add", 0) if p.get("ben") else 0
            if p.get("chain") and hits_in_skill >= p["chain"][0]: add += (p["chain"][1] - 1) * P["CHAIN_WEIGHT"]
            if p.get("hit_mult"): m *= p["hit_mult"]
        mods = u.t["mods"]; r = u.hp / u.maxhp
        for x, th in mods["low_static"]:
            if r < th: add += x
        if mods["low_dyn"] and r <= 0.7: add += mods["low_dyn"] * (0.7 - r) / 0.7
        for x, th in mods["high_static"]:
            if r > th: add += x
        if mods["high_dyn"] and r >= 0.7: add += mods["high_dyn"] * (r - 0.7) / 0.3
        if mods["full_hp"] and r >= 0.999: add += mods["full_hp"]
        if not normal:
            for x, k in mods["pursuit"]:
                if hits_in_skill >= k: add += x
        m *= 1 + add
        for s in tgt.st:
            for el, kind, v in s["p"].get("attr", []):
                if kind == "taken" and ELEMN.get(el) == u.elem: m *= v
        dfv = max(1.0, tgt.df * (1 + _bsum(tgt, "Vitality") + tgt.team_def))
        if self._combo_target and not normal: m *= self.combo.coef(u.side)
        # Damage cuts (Indomitable) do not multiply together: the strongest one
        # applies; every active one still uses up a hit.
        cuts = [s for s in tgt.st if s["p"].get("taken_mult") is not None and (s["cnt"] is None or s["cnt"] > 0)]
        if cuts:
            least = None
            for s in cuts:        # the strongest cut (min() keeps the first of equals: so does this)
                if least is None or s["p"]["taken_mult"] < least:
                    least = s["p"]["taken_mult"]
            m *= least
            for s in cuts:
                if s["cnt"] is not None: s["cnt"] -= 1
        tgt.st = [s for s in tgt.st if s["cnt"] is None or s["cnt"] > 0]
        m *= self.taken_mult(tgt)
        dmg = max(0.0, rules.DAMAGE_FORMULAS[P["DAMAGE"]](atk, power, m, dfv, P, pierce))   # never a heal
        floor = 1 if self.has(tgt, "dauntless") else 0
        tgt.hp = max(floor, tgt.hp - dmg)
        self.on_hit(u, tgt, dmg, hits_in_skill, normal)
        tgt.gauge += P["GAUGE_HIT_TAKEN"]
        if tgt.hp <= 0:
            tgt.alive = False; tgt.died_at = self.t; tgt.st = []; tgt.bf = []
            if self.first_kill is None:
                self.first_kill = dict(t=self.t / P["FPS"], side=u.side, killer=u.cid, victim=tgt.cid, victim_acted=tgt.first_act is not None)

    def taken_mult(self, tgt):
        """A multiplier on damage the target takes (a knocked-down Subjugation boss)."""
        return 1.0

    def on_hit(self, u, tgt, dmg, hits_in_skill, normal):
        """After each hit (Subjugation scoring)."""

    def count_turn(self, u):
        """u's turn: each status it holds measured in turns loses one, and those at 0 end. A unit stunned for one
        turn so loses exactly its next turn."""
        if any(s.get("turns") is not None for s in u.st):
            for s in u.st:
                if s.get("turns") is not None:
                    s["turns"] -= 1
            u.st = [s for s in u.st if s.get("turns") is None or s["turns"] > 0]

    def reliance(self, e):
        s = 0
        for o in e.t["cs"]["ops"]:
            if o["op"] == "status" and o["st"]["ben"] and "enemy" not in o["scope"]:
                s += {44: 3, 45: 2, 24: 1, 18: 1}.get(o["st"]["type"], 0.5)
            if o["op"] == "hpcost": s += 2
        return s

    def run_ops(self, u, ops, hits_in_skill, comp_atk=None):
        target = None
        if P["COMP_TARGET"] == "reliance" and any(o["op"] == "status" and o["st"]["type"] == 43 and "single" in o["scope"] for o in ops):
            es = self.enemies(u)
            prov = [e for e in es if self.has(e, "provoke")]
            if es: target = prov[0] if prov else max(es, key=lambda e: (self.reliance(e), -e.hp / e.maxhp))
        sk = u.t["cs"] if ops is u.t["cs"]["ops"] else next((w for w in u.t["wskills"] if w["ops"] is ops), None)
        self._combo_target = bool(sk and sk.get("combo", True))
        if self.logging:
            if ops is u.t["cs"]["ops"]: lab = "CS " + u.t["cs"]["name"]
            elif u.t["comp"] and ops is u.t["comp"]["ops"]: lab = "companion"
            else: lab = "WS " + next((w["name"] for w in u.t["wskills"] if w["ops"] is ops), "?")
            hp0 = {id(x): x.hp for s in ("A", "D") for x in self.sides[s]}
            self._pending = (self.t, u, lab, hp0)
        for o in ops:
            if o["op"] == "dmg":
                tg = self.scope(u, o["scope"], target)
                if len(tg) == 1 and "enemy" in o["scope"]: target = tg[0]
                for t_ in tg:
                    for _ in range(o["hits"]): self.hit(u, t_, o["power"], hits_in_skill, pierce=o["pierce"], comp_atk=comp_atk)
            else:
                self.apply(u, o, target)
        self.combo.on_action(u.side, any(o["op"] == "dmg" for o in ops))
        self._log_action()

    def _log_action(self):
        if not self.logging:
            return
        t0, u, lab, hp0 = self._pending
        dmg = []
        for s in ("A", "D"):
            for x in self.sides[s]:
                d = hp0[id(x)] - x.hp
                if abs(d) > 1: dmg.append("%s%s %s %+d%s" % (x.side, x.slot, x.t["name"].split()[0], -d, " KO" if not x.alive else ""))
        sts = ",".join(sorted({ABN_SHORT.get(s["p"]["type"], str(s["p"]["type"])) for s in u.st}))
        self.log.append("%5.1fs %s%s %-28s %-34s %s" % (t0 / P["FPS"], u.side, u.slot, u.t["name"][:28], lab[:34], "; ".join(dmg)))

    # ---------- actions ----------
    def act(self, u):
        t = u.t
        if u.gauge >= t["cs"]["gauge"] * u.gmult:
            u.gauge = 0; self.run_ops(u, t["cs"]["ops"], t["cs"]["hits"]); u.lock = P["LOCK_CS"]; return "cs"
        for i, ws in enumerate(t["wskills"]):
            if u.w[i] <= 0:
                u.w[i] = ws["cd"] * u.wmult; self.run_ops(u, ws["ops"], ws["hits"]); u.gauge += P["GAUGE_WS"]; u.lock = P["LOCK_WS"]; return "ws"
        if u.na <= 0:
            pw, hits = t["na"]; es = self.enemies(u)
            if es:
                tgt = self.pick(u); n = max(1, round(hits))
                for _ in range(n): self.hit(u, tgt, pw / n, n, normal=True)
                u.gauge += P["GAUGE_NA"].get(min(5, n), 50)
            u.na = self.na_interval(u); u.lock = P["LOCK_NA"]; return "na"
        return None

    def step(self):
        S = P["STEP"]
        order = ("D", "A") if P["TIE_ORDER"] == "defender_first" else ("A", "D")
        for side in order:
            units = {u.slot: u for u in self.sides[side]}
            for sl in P["SLOT_ORDER"]:
                u = units.get(sl)
                if not u or not u.alive: continue
                if u.comp is not None and u.comp <= 0 and self.enemies(u):
                    self.run_ops(u, u.t["comp"]["ops"], 1, comp_atk=u.t["comp"]["atk"]); u.gauge += P["GAUGE_COMP"]; u.comp = u.t["comp"]["cd"]
                if u.lock > 0 or self.has(u, "stun") or not self.enemies(u): continue
                a = self.act(u)
                if a and u.first_act is None: u.first_act = self.t
        for side in ("A", "D"):
            for u in self.sides[side]:
                if not u.alive: continue
                u.lock = max(0, u.lock - S); u.na -= S
                u.w = [x - S for x in u.w]
                if u.comp is not None: u.comp -= S
                if u.t["cs"]["timed"]: u.gauge += S
                for b in u.bf: b["left"] -= S
                u.bf = [b for b in u.bf if b["left"] > 0]
                for s in u.st:
                    if s["left"] is not None:
                        before = s["left"]; s["left"] -= S
                        if s["p"].get("regen") and int(before // P["TICK_FRAMES"]) != int(s["left"] // P["TICK_FRAMES"]):
                            u.hp = min(u.maxhp, u.hp + s["p"]["regen"] * u.maxhp)
                u.st = [s for s in u.st if s["left"] is None or s["left"] > 0]
        self.t += S

    def tick(self, S):
        C = S * P["CD_RATE"]
        for side in ("A", "D"):
            for u in self.sides[side]:
                if not u.alive: continue
                u.w = [x - C for x in u.w]
                if u.comp is not None: u.comp -= C
                if u.t["cs"]["timed"]: u.gauge += C
                for b in u.bf: b["left"] -= S
                u.bf = [b for b in u.bf if b["left"] > 0]
                for s in u.st:
                    if s["left"] is not None:
                        before = s["left"]; s["left"] -= S
                        if s["p"].get("regen") and int(before // P["TICK_FRAMES"]) != int(s["left"] // P["TICK_FRAMES"]):
                            u.hp = min(u.maxhp, u.hp + s["p"]["regen"] * u.maxhp)
                u.st = [s for s in u.st if s["left"] is None or s["left"] > 0]
        self.t += S

    def ready_skill(self):
        """Earliest-ready skill first (FIFO by the moment it became ready); same moment -> tie order, then slot order."""
        tie = {"D": 0, "A": 1} if P["TIE_ORDER"] == "defender_first" else {"A": 0, "D": 1}
        if P["ATTACKER_FIRST_AT_START"] and self.t <= P["START_WINDOW"]: tie = {"A": 0, "D": 1}
        so = {s: i for i, s in enumerate(P["SLOT_ORDER"])}
        best = None
        for side in ("A", "D"):
            for u in self.sides[side]:
                if not u.alive or self.has(u, "stun") or not self.enemies(u): continue
                cands = []
                need = u.t["cs"]["gauge"] * u.gmult
                if u.gauge >= need:
                    if u.cs_ready is None: u.cs_ready = self.t
                    cands.append((u.cs_ready, 0, "cs", None))
                hold = P["HOLD_VS_DAUNTLESS"] and self.all_dauntless(u)
                if hold and cands and any(o["op"] == "dmg" for o in u.t["cs"]["ops"]): cands = []
                for i, x in enumerate(u.w):
                    if x <= 0 and not (hold and any(o["op"] == "dmg" for o in u.t["wskills"][i]["ops"])): cands.append((self.t + x, 1 + i, "ws", i))
                if u.comp is not None and u.comp <= 0: cands.append((self.t + u.comp, 5, "comp", None))
                for c in cands:
                    key = (round(c[0] / P["READY_GRANULE"]), tie[u.side], so[u.slot], c[1])
                    if best is None or key < best[0]: best = (key, u, c[2], c[3])
        return (best[1], best[2], best[3]) if best else (None, None, None)

    def all_dauntless(self, u):
        es = self.enemies(u)
        if not es: return False
        for e in es:
            d = [s for s in e.st if s["p"].get("dauntless")]
            if not d or all((s["left"] or 0) <= P["HOLD_MARGIN"] for s in d): return False
        return True

    def batch_size(self):
        """How many skills were ready at this boundary (they resolve before the next normal attack)."""
        n = 0
        for s in ("A", "D"):
            for u in self.sides[s]:
                if not u.alive or self.has(u, "stun"): continue
                n += (u.gauge >= u.t["cs"]["gauge"] * u.gmult) + sum(1 for x in u.w if x <= 0) + (u.comp is not None and u.comp <= 0)
        return n

    def turn_order(self):
        al = [u for s in ("A", "D") for u in self.sides[s] if u.alive]
        if not al: return []
        slowest = min(self.agility(u) for u in al)
        tie = {"D": 0, "A": 1} if P["TIE_ORDER"] == "defender_first" else {"A": 0, "D": 1}
        so = {s: i for i, s in enumerate(P["SLOT_ORDER"])}
        q = sorted(al, key=lambda u: (-self.agility(u), tie[u.side], so[u.slot]))
        if self.mirror_safe:
            agi_a = {self.agility(u) for u in al if u.side == "A"}
            if any(self.agility(u) in agi_a for u in al if u.side == "D"): self.mirror_safe = False   # a tie between sides
        doubles = [u for u in q if self.agility(u) >= P["AGI_DOUBLE_RATIO"] * slowest]
        return q + doubles

    def run_opening(self):
        """Hybrid: every character skill ready at battle start resolves right after the wave intro (OPEN_DELAY),
        sides alternating when OPEN_INTERLEAVE (rules.opening_order)."""
        if P["OPEN_DELAY"]: self.tick(int(P["OPEN_DELAY"] * P["FPS"]))
        units = [u for s in ("A", "D") for u in self.sides[s] if u.alive and u.gauge >= u.t["cs"]["gauge"] * u.gmult]
        for u in rules.opening_order(units, self.attacker_manual, P["SLOT_ORDER"], P["OPEN_INTERLEAVE"]):
            if not u.alive or not self.enemies(u) or self.has(u, "stun"): continue
            u.gauge = 0; u.cs_ready = None; self.run_ops(u, u.t["cs"]["ops"], u.t["cs"]["hits"])
            if u.first_act is None: u.first_act = self.t
            self.tick(int(P["OPEN_ANIM"] * P["FPS"]))

    def run_queue(self):
        end = self.frames; turn = []
        if P["ACTION_MODEL"] == "hybrid": self.run_opening()
        while self.t < end:
            if not any(u.alive for u in self.sides["A"]) or not any(u.alive for u in self.sides["D"]): break
            opening = P["OPENING_NA"] > self.na_done
            u, kind, i = self.ready_skill() if (P["SKILLS_FIRST"] and P["ACTION_MODEL"] == "queue" and not opening) else (None, None, None)
            if u is not None and P["INTERLEAVE"]:
                if self.batch_left is None: self.batch_left = self.batch_size()
                if self.batch_left <= 0: u = None; self.batch_left = None
                else: self.batch_left -= 1
            if u is not None:
                if kind == "cs":
                    u.gauge = 0; u.cs_ready = None; self.run_ops(u, u.t["cs"]["ops"], u.t["cs"]["hits"]); dur = P["ANIM_CS"]
                elif kind == "ws":
                    ws = u.t["wskills"][i]; u.w[i] = ws["cd"] * u.wmult; self.run_ops(u, ws["ops"], ws["hits"]); u.gauge += P["GAUGE_WS"]; dur = P["ANIM_WS"]
                else:
                    self.run_ops(u, u.t["comp"]["ops"], 1, comp_atk=u.t["comp"]["atk"]); u.gauge += P["GAUGE_COMP"]; u.comp = u.t["comp"]["cd"]; dur = P["ANIM_COMP"]
                if u.first_act is None: u.first_act = self.t
                self.tick(dur); continue
            if not turn: turn = self.turn_order()
            u = None
            while turn:
                c = turn.pop(0)
                if not c.alive: continue
                stunned = self.has(c, "stun")
                self.count_turn(c)            # its turn passes: statuses measured in turns count down (a stun ends)
                if not stunned and self.enemies(c): u = c; break
            if u is None: self.tick(P["STEP"]); continue
            if P["ACTION_MODEL"] in ("turn", "hybrid"):
                dur = 0
                if u.comp is not None and u.comp <= 0:
                    self.run_ops(u, u.t["comp"]["ops"], 1, comp_atk=u.t["comp"]["atk"]); u.gauge += P["GAUGE_COMP"]; u.comp = u.t["comp"]["cd"]; dur += P["ANIM_COMP"]
                if u.gauge >= u.t["cs"]["gauge"] * u.gmult:
                    u.gauge = 0; self.run_ops(u, u.t["cs"]["ops"], u.t["cs"]["hits"]); dur += P["ANIM_CS"]
                    if u.first_act is None: u.first_act = self.t
                    self.tick(dur); continue
                ready = [i for i, x in enumerate(u.w) if x <= 0]
                if ready:
                    i = ready[0]; ws = u.t["wskills"][i]; u.w[i] = ws["cd"] * u.wmult; self.run_ops(u, ws["ops"], ws["hits"]); u.gauge += P["GAUGE_WS"]
                    if u.first_act is None: u.first_act = self.t
                    self.tick(dur + P["ANIM_WS"]); continue
                if dur: self.tick(dur)
            if not self.enemies(u): continue
            pw, hits = u.t["na"]; tgt = self.pick(u); n = max(1, round(hits))
            hp_before = tgt.hp
            for _ in range(n): self.hit(u, tgt, pw / n, n, normal=True)
            if self.logging: self.log.append("%5.1fs %s%s %-28s %-34s %s%s %s %+d%s" % (self.t / P["FPS"], u.side, u.slot, u.t["name"][:28], "normal attack", tgt.side, tgt.slot, tgt.t["name"].split()[0], -(hp_before - tgt.hp), " KO" if not tgt.alive else ""))
            u.gauge += P["GAUGE_NA"].get(min(5, n), 50); self.na_done += 1
            self.combo.on_action(u.side, True, normal=True)
            if u.first_act is None: u.first_act = self.t
            self.tick(P["ANIM_NA"])

    def run(self):
        end = self.frames
        if P["ENGINE"] == "queue":
            self.run_queue()
        while P["ENGINE"] != "queue" and self.t < end:
            self.step()
            if not any(u.alive for u in self.sides["A"]) or not any(u.alive for u in self.sides["D"]): break
        aA = any(u.alive for u in self.sides["A"]); aD = any(u.alive for u in self.sides["D"])
        share = lambda s: sum(max(0, u.hp) / u.maxhp for u in self.sides[s] if u.alive) / 3
        if aA and not aD: win = "A"; how = "KO"
        elif aD and not aA: win = "D"; how = "KO"
        else:
            how = "timeout"
            if abs(share("A") - share("D")) <= P["TIMEOUT_MARGIN"]: self.mirror_safe = False    # a draw: the defender's
            # clearly ahead only: two sides held near 0 (Dauntless at 1 HP) are a draw, not a win for the smaller maximum HP
            win = "A" if (P["TIMEOUT_RULE"] == "hp_ratio" and share("A") > share("D") + P["TIMEOUT_MARGIN"]) else "D"
        # did Compromise land before the target's first beneficial status from a skill?
        comp = []
        for e in self.comp_events:
            fb = self.first_ben.get((e["side"], e["target"]))
            comp.append(dict(e, before_target_buff=(fb is None or e["t"] < fb), blocked=sum(v for k, v in self.blocked.items() if k[1] == e["target"])))
        return dict(win=win, how=how, t=self.t / P["FPS"], hpA=share("A"), hpD=share("D"), first_kill=self.first_kill, compromise=comp,
                    kills_A=sum(not u.alive for u in self.sides["D"]), kills_D=sum(not u.alive for u in self.sides["A"]))




class BossBattle(Battle):
    """A Subjugation phase: the party (A) against the boss (D, middle), which does not fall; the score is the damage
    dealt. Skill hits fill the knock-down gauge (bighunt.Phase.gauge); at a knock-down threshold the boss is down for
    its frames and takes the threshold's ratio times the damage."""
    def __init__(self, party, boss, phase, rng, attacker_manual=True):
        super().__init__(party, {"M": boss}, rng, attacker_manual)
        self.boss = self.sides["D"][0]
        self.phase = phase
        self.frames = int(phase.frames * P["FPS"] / 60)
        self.dealt = 0.0; self.gauge_value = 0.0; self.next_threshold = 0
        self.down_until = -1; self.ratio = 1.0; self.knockdowns = 0

    def taken_mult(self, tgt):
        return self.ratio if tgt is self.boss and self.t < self.down_until else 1.0

    def on_hit(self, u, tgt, dmg, hits_in_skill, normal):
        if tgt is not self.boss:
            return
        self.dealt += dmg
        if normal or self.t < self.down_until:
            return
        self.gauge_value += self.phase.gauge(hits_in_skill, dmg)
        th = self.phase.thresholds
        while self.next_threshold < len(th) and self.gauge_value >= th[self.next_threshold].at:
            x = th[self.next_threshold]; self.next_threshold += 1
            if x.down:
                self.down_until = self.t + x.frames * P["FPS"] / 60; self.ratio = x.ratio; self.knockdowns += 1


def boss_phase(party, boss, phase, tables, seed=0):
    """One Subjugation phase of the party deck against the boss unit template: damage dealt, knock-downs, and the
    time the party lasted (the phase's length when it stands to the end)."""
    b = BossBattle(_side(party, tables), boss, phase, random.Random(seed)); b.logging = False
    b.run()
    return dict(damage=round(b.dealt), knockdowns=b.knockdowns, t=round(min(b.t, b.frames) / P["FPS"], 1),
                standing=sum(u.alive for u in b.sides["A"]))


def mirror(r):
    """The result of the same fight with the roles swapped (see Battle.mirror_safe): the other side wins, the HP
    shares change places."""
    return dict(r, win="D" if r["win"] == "A" else "A", hpA=r["hpD"], hpD=r["hpA"])


def _side(deck, tables):
    from deckbuilder.sim import units
    return {slot: t for slot, t in units.units_for(deck, tables) if t is not None}


def simulate(attacker, defender, tables, seed=0, attacker_manual=True):
    """One fight; the dict the prototype returned (win "A"/"D", how, t, ...) plus the log."""
    b = Battle(_side(attacker, tables), _side(defender, tables), random.Random(seed), attacker_manual)
    r = b.run()
    r["log"] = b.log
    return r


# Whose start-of-battle skills go first decides many fights outright, and the player may tap them by hand (the
# attacker's first) or leave them on Auto (the defender's first): a match is scored over both openings.
OPENINGS = (True, False)


def score(attacker, defender, tables, runs=None):
    """(win share, margin) for the attacker over `runs` seeds and both openings. margin: the attacker's remaining
    HP share minus the defender's, averaged over the fights (-1..1); it tells apart decks with the same win share."""
    n = runs or P["runs"]
    att, dfn = _side(attacker, tables), _side(defender, tables)
    wins = margin = 0.0
    for manual in OPENINGS:
        once = None              # seed 0's fight, when no draw in it could change anything: every seed plays it
        for seed in range(n):
            if once is not None:
                r = once
            else:
                b = Battle(att, dfn, random.Random(seed), manual); b.logging = False
                r = b.run()
                if seed == 0 and b.chance_draws == 0:
                    once = r
            wins += r["win"] == "A"
            margin += r["hpA"] - r["hpD"]
    k = n * len(OPENINGS)
    return round(wins / k, 4), round(margin / k, 4)


def win_rate(attacker, defender, tables, runs=None):
    """Share of fights the attacker wins over `runs` seeds and both openings."""
    return score(attacker, defender, tables, runs)[0]
