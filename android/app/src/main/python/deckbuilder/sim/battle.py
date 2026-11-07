"""The battle engine (ported from the research prototype's sim.py; logic
unchanged). Units are templates from deckbuilder.sim.units, built from a deck's
real pieces and stats."""
import collections
import random

from deckbuilder.sim import rules
from deckbuilder.sim.rules import P, ADV, ELEMN, ABN_SHORT

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


class Battle:
    def __init__(self, att, dfn, rng):
        """att, dfn: dict slot -> unit template (units.build_unit)."""
        self.rng = rng; self.t = 0; self.log = []
        self.sides = {"A": [U(t, "A", s) for s, t in att.items()], "D": [U(t, "D", s) for s, t in dfn.items()]}
        self.combo = rules.Combo(P["COMBO"] != "off", P["COMBO_COUNT_NA"], P["COMBO_RESET"]); self._combo_target = False
        self.first_kill = None; self.na_done = 0; self.batch_left = None; self.comp_events = []; self.blocked = collections.Counter(); self.first_ben = {}
        for side in ("A", "D"):
            for u in self.sides[side]: self.start_passives(u)
        for side in ("A", "D"):
            for u in self.sides[side]:
                u.hp = u.maxhp
                u.na = self.na_interval(u) * P["FIRST_NA_FRAC"]

    # ---------- helpers ----------
    def allies(self, u): return [x for x in self.sides[u.side] if x.alive]
    def enemies(self, u): return [x for x in self.sides["D" if u.side == "A" else "A"] if x.alive]
    def has(self, u, key): return any(s["p"].get(key) for s in u.st)
    def agility(self, u): return (u.t["agi"] + u.agi_bonus) * (1 + sum(b["v"] for b in u.bf if b["key"] == "Agility"))
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
                tg = self.scope(u, o.get("scope", "self_01"))
                for a in tg:
                    if o["which"] == "cs": a.gmult *= o["mult"]
                    else: a.wmult *= o["mult"]
            elif o["op"] in ("status", "buff"):
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
            if self.rng.random() > o.get("prob", 1): return
            for a in self.scope(src, o["scope"], target):
                a.bf = [b for b in a.bf if not (b["key"] == o["key"] and b["src"] == id(o))]
                a.bf.append(dict(key=o["key"], v=o["value"], left=o["frames"], src=id(o)))
        elif op == "status":
            if self.rng.random() > o.get("prob", 1): return
            p = o["st"]
            for a in self.scope(src, o["scope"], target):
                if p["ben"]:
                    if any(s["p"].get("type") == 43 for s in a.st):
                        self.blocked[(a.side, a.cid, p["type"])] += 1; continue
                else:
                    res = [r for s in a.st for r in s["p"].get("resist", []) if (r[0] == 3 and r[1] in (0, p["type"]))]
                    if any(self.rng.random() < r[2] for r in res): continue
                kind, v = p["life"]
                rec = dict(p=p, left=None, cnt=None, src=id(o))
                if kind == "frames": rec["left"] = v if v < 54000 else 10 ** 9
                elif kind == "turns": rec["left"] = v * P["TURN_FRAMES"] if v < 999 else 10 ** 9
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
                self.rng.shuffle(kinds)
                for k in kinds[:o["kinds"]]: a.st = [s for s in a.st if s["p"]["type"] != k]
        elif op == "purge":
            for a in self.scope(src, o["scope"], target):
                kinds = sorted({s["p"]["type"] for s in a.st if s["p"]["ben"]}); self.rng.shuffle(kinds)
                for k in kinds[:o["kinds"]]: a.st = [s for s in a.st if s["p"]["type"] != k]
        elif op == "removebuff":
            for a in self.scope(src, o["scope"], target):
                pos = [b for b in a.bf if (b["v"] > 0) == o["positive"]]
                for b in pos[-o["n"]:]: a.bf.remove(b)

    def hit(self, u, tgt, power, hits_in_skill, normal=False, pierce=False, comp_atk=None):
        if not tgt.alive: return
        if normal and self.has(tgt, "defiance"): return
        bsum = lambda x, k: sum(b["v"] for b in x.bf if b["key"] == k)
        atk = (comp_atk or u.atk) * (1 + bsum(u, "Attack") + u.team_atk)
        crit = min(1, u.t["crit"] + bsum(u, "CriticalRatio") + u.team_crit); cd = u.t["critdmg"] + bsum(u, "CriticalAttack") + u.team_cdmg
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
        dfv = tgt.df * (1 + bsum(tgt, "Vitality") + tgt.team_def)
        if self._combo_target and not normal: m *= self.combo.coef(u.side)
        # Damage cuts (Indomitable) do not multiply together: the strongest one
        # applies; every active one still uses up a hit.
        cuts = [s for s in tgt.st if s["p"].get("taken_mult") is not None and (s["cnt"] is None or s["cnt"] > 0)]
        if cuts:
            m *= min(s["p"]["taken_mult"] for s in cuts)
            for s in cuts:
                if s["cnt"] is not None: s["cnt"] -= 1
        tgt.st = [s for s in tgt.st if s["cnt"] is None or s["cnt"] > 0]
        dmg = rules.DAMAGE_FORMULAS[P["DAMAGE"]](atk, power, m, dfv, P, pierce)
        floor = 1 if self.has(tgt, "dauntless") else 0
        tgt.hp = max(floor, tgt.hp - dmg)
        tgt.gauge += P["GAUGE_HIT_TAKEN"]
        if tgt.hp <= 0:
            tgt.alive = False; tgt.died_at = self.t; tgt.st = []; tgt.bf = []
            if self.first_kill is None:
                self.first_kill = dict(t=self.t / P["FPS"], side=u.side, killer=u.cid, victim=tgt.cid, victim_acted=tgt.first_act is not None)

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
        doubles = [u for u in q if self.agility(u) >= P["AGI_DOUBLE_RATIO"] * slowest]
        return q + doubles

    def run_opening(self):
        """Hybrid: every character skill ready at battle start resolves right after the wave intro (OPEN_DELAY),
        sides alternating when OPEN_INTERLEAVE (rules.opening_order)."""
        if P["OPEN_DELAY"]: self.tick(int(P["OPEN_DELAY"] * P["FPS"]))
        units = [u for s in ("A", "D") for u in self.sides[s] if u.alive and u.gauge >= u.t["cs"]["gauge"] * u.gmult]
        for u in rules.opening_order(units, P["ATTACKER_MANUAL"], P["SLOT_ORDER"], P["OPEN_INTERLEAVE"]):
            if not u.alive or not self.enemies(u) or self.has(u, "stun"): continue
            u.gauge = 0; u.cs_ready = None; self.run_ops(u, u.t["cs"]["ops"], u.t["cs"]["hits"])
            if u.first_act is None: u.first_act = self.t
            self.tick(int(P["OPEN_ANIM"] * P["FPS"]))

    def run_queue(self):
        end = P["DURATION_S"] * P["FPS"]; turn = []
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
                if c.alive and not self.has(c, "stun") and self.enemies(c): u = c; break
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
            self.log.append("%5.1fs %s%s %-28s %-34s %s%s %s %+d%s" % (self.t / P["FPS"], u.side, u.slot, u.t["name"][:28], "normal attack", tgt.side, tgt.slot, tgt.t["name"].split()[0], -(hp_before - tgt.hp), " KO" if not tgt.alive else ""))
            u.gauge += P["GAUGE_NA"].get(min(5, n), 50); self.na_done += 1
            self.combo.on_action(u.side, True, normal=True)
            if u.first_act is None: u.first_act = self.t
            self.tick(P["ANIM_NA"])

    def run(self):
        end = P["DURATION_S"] * P["FPS"]
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
            win = "A" if (P["TIMEOUT_RULE"] == "hp_ratio" and share("A") > share("D")) else "D"
        # did Compromise land before the target's first beneficial status from a skill?
        comp = []
        for e in self.comp_events:
            fb = self.first_ben.get((e["side"], e["target"]))
            comp.append(dict(e, before_target_buff=(fb is None or e["t"] < fb), blocked=sum(v for k, v in self.blocked.items() if k[1] == e["target"])))
        return dict(win=win, how=how, t=self.t / P["FPS"], hpA=share("A"), hpD=share("D"), first_kill=self.first_kill, compromise=comp,
                    kills_A=sum(not u.alive for u in self.sides["D"]), kills_D=sum(not u.alive for u in self.sides["A"]))




def _side(deck, tables):
    from deckbuilder.sim import units
    return {slot: t for slot, t in units.units_for(deck, tables) if t is not None}


def simulate(attacker, defender, tables, seed=0, attacker_manual=True):
    """One fight; the dict the prototype returned (win "A"/"D", how, t, ...) plus the log."""
    saved = P["ATTACKER_MANUAL"]
    P["ATTACKER_MANUAL"] = attacker_manual
    try:
        b = Battle(_side(attacker, tables), _side(defender, tables), random.Random(seed))
        r = b.run()
    finally:
        P["ATTACKER_MANUAL"] = saved
    r["log"] = b.log
    return r


def win_rate(attacker, defender, tables, runs=None):
    """Share of fights the attacker wins over `runs` seeds."""
    n = runs or P["runs"]
    att, dfn = _side(attacker, tables), _side(defender, tables)
    wins = 0
    for seed in range(n):
        b = Battle(att, dfn, random.Random(seed))
        wins += b.run()["win"] == "A"
    return wins / n
