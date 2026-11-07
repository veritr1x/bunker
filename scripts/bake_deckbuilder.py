#!/usr/bin/env python3
"""Bake Deck Builder's All maxed search at build time, in checkpoints.

    python scripts/bake_deckbuilder.py stage      # 1: stage every costume and equippable item, fully raised
    python scripts/bake_deckbuilder.py gear       # 2: each costume's best loadout, every candidate per slot
    python scripts/bake_deckbuilder.py fighters   # 3: cached fighters, checked against building decks directly
    python scripts/bake_deckbuilder.py sample     # 4: a sample of decks, checked against the generator
    python scripts/bake_deckbuilder.py bake       # 5: every deck, in resumable chunks on every core

Each step writes its results and a readable report to .build/deckbuilder/bake/ (BAKE below) and reads the
earlier steps' results from there. Needs the master data and bunker-edit, as the Deck Builder tests do
(scripts/build_deckbuilder_fixtures.py --master --master-bin).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "android/tools"))
from deckbuilder_testlib import BUILD, cli_invoke, tables  # noqa: E402
from deckbuilder import equip, experts as experts_mod, model, stage as stage_mod  # noqa: E402

BAKE = BUILD / "bake"
CYTHON = BUILD / "cython"                      # the compiled simulator (scripts/bake_cython)


def compiled(check=True):
    """Swap in the Cython-compiled simulator (after sim.use): built from the current battle.py and
    scripts/bake_cython/battle_c.pxd when they are newer than the module. Needs Cython in the venv."""
    import shutil, subprocess
    src = ROOT / "android/app/src/main/python/deckbuilder/sim/battle.py"
    pxd = ROOT / "scripts/bake_cython/battle_c.pxd"
    CYTHON.mkdir(parents=True, exist_ok=True)
    built = sorted(CYTHON.glob("battle_c.*.so"))
    if not built or built[0].stat().st_mtime < max(src.stat().st_mtime, pxd.stat().st_mtime):
        for f in CYTHON.glob("battle_c.*"):
            f.unlink()
        shutil.copy(src, CYTHON / "battle_c.py"); shutil.copy(pxd, CYTHON / "battle_c.pxd")
        subprocess.run([str(Path(sys.executable).parent / "cythonize"), "-i", "-3", "-q", "battle_c.py"], cwd=CYTHON,
                       check=True, capture_output=True)
    if str(CYTHON) not in sys.path:
        sys.path.insert(0, str(CYTHON))
    import battle_c
    import deckbuilder.sim as simpkg
    sys.modules["deckbuilder.sim.battle"] = battle_c
    simpkg.battle = battle_c
    return battle_c


def report(name: str, data: dict) -> None:
    BAKE.mkdir(parents=True, exist_ok=True)
    (BAKE / f"{name}.json").write_text(json.dumps(data, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in data.items() if not isinstance(v, (list, dict)) or len(v) <= 12}, indent=1))
    print(f"→ {BAKE / (name + '.json')}")


def universe(T) -> dict:
    """Every fieldable costume and every equippable item the ranking data knows, with both roles' memoirs of
    every memoir set."""
    r = equip.rankings()
    known_w, known_c, known_t = T.idx("Weapon", "WeaponId"), T.idx("Companion", "CompanionId"), T.idx("Thought", "ThoughtId")
    costumes = sorted(c for c in T.idx("Costume", "CostumeId") if T.is_fieldable(c))
    sets = sorted(int(s) for s in r["memoir_sets"])
    memoirs = [m for s in sets for _, mains, subs in equip.ROLE_MEMOIRS.values() for m in equip.memoir_specs(s, mains, subs, T)]
    return dict(costume_ids=costumes,
                weapon_ids=sorted(int(w) for w in r["weapons"] if int(w) in known_w),
                companion_ids=sorted(int(c) for c in r["companions"] if int(c) in known_c),
                thought_ids=sorted(int(t) for t in r["debris"] if int(t) in known_t),
                memoirs=memoirs)


def cmd_stage(args) -> None:
    T = tables()
    plan = universe(T)
    path = BAKE / "stage.db"
    BAKE.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    t0 = time.time()
    stage_mod.Stager(cli_invoke(path), T).build(**plan)
    took = time.time() - t0
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    one = lambda sql: db.execute(sql).fetchone()
    costumes = {r[0]: r[1:] for r in db.execute("select costume_id, level, limit_break_count, awaken_count from user_costumes")}
    # each costume at its rarity's cap: the highest level any costume of that rarity reached
    rarity = {c: T.idx("Costume", "CostumeId")[c]["RarityType"] for c in costumes}
    cap = {}
    for c, (lv, lb, aw) in costumes.items():
        cap[rarity[c]] = max(cap.get(rarity[c], 0), lv)
    below = sorted(c for c, (lv, lb, aw) in costumes.items() if lv < cap[rarity[c]] or lb < 4)
    weapons = db.execute("select weapon_id, level, limit_break_count from user_weapons").fetchall()
    can_awaken = {r["WeaponId"] for r in T.T("WeaponAwaken")}
    awakened = {r[0] for r in db.execute("select w.weapon_id from user_weapons w join user_weapon_awakens a using (user_weapon_uuid)")}
    weapons_below = sorted(w for w, lv, lb in weapons if lb < 4 or (w in can_awaken and w not in awakened))
    data = {
        "took_s": round(took, 1),
        "asked": {k: len(v) for k, v in plan.items()},
        "staged": {"costumes": len(costumes), "weapons": len(weapons), "companions": one("select count(*) from user_companions")[0],
                   "debris": one("select count(*) from user_thoughts")[0], "memoirs": one("select count(*) from user_parts")[0],
                   "characters": one("select count(*) from user_characters")[0],
                   "mythic_slab_abilities": one("select count(*) from user_character_board_abilities")[0],
                   "awakening_rows": one("select count(*) from user_costume_awaken_status_ups")[0],
                   "karma_rows": one("select count(*) from user_costume_lottery_effects")[0]},
        "costume_level_caps_by_rarity": {str(k): v for k, v in sorted(cap.items())},
        "costumes_below_cap": below,
        "weapon_levels": sorted({lv for _, lv, _ in weapons}),
        "weapons_not_limit_broken_or_awakened": weapons_below,
        "companion_levels": sorted({r[0] for r in db.execute("select level from user_companions")}),
        "memoir_levels": sorted({r[0] for r in db.execute("select level from user_parts")}),
        "missing_costumes": sorted(set(plan["costume_ids"]) - set(costumes)),
    }
    report("1_stage", data)


# ---------------------------------------------------------------- 2: gear
_W = {}     # a worker's state: tables, experts, the stage in memory, the reference fighters


def _worker_init():
    from deckbuilder import sim
    T = tables()
    sim.use(T)
    ex = experts_mod.Experts.load(T)
    st = model.Save(model.snapshot(BAKE / "stage.db"), 1)
    _W.update(T=T, ex=ex, st=st, refs=_references(T, ex, st), **_team_context(T, ex, st))


PARTNER_LINEUPS = 4     # the experts' top lineups that lend a candidate its two teammates


def _team_context(T, ex, st):
    """Gear is judged in a team: the candidate with two teammates from each of the experts' top lineups (their own
    gear), against the meta decks (both openings). The deck is composed whole, so team-wide stats (a memoir set's
    team Attack, a support's party buffs) reach the teammates and theirs reach the candidate."""
    from deckbuilder import generate
    from deckbuilder.sim import battle
    gen = generate.Generator(T, ex, st, st)
    meta = [(name, battle._side(d, T)) for d, w, name in gen.meta()]
    lineups = sorted(ex.lineups(), key=lambda l: -l.weight)[:PARTNER_LINEUPS]
    pairs = []
    for l in lineups:
        eq = equip.equip(l.costumes, equip.Mode("best"), st, st, T, ex, expert=l, deck_number=80 + len(pairs))
        pairs.append([(c, s) for c, s in zip(l.costumes, eq.specs) if s is not None])
    return {"meta": meta, "pairs": pairs}


def _team_specs(costume_id, spec, pair):
    """The candidate (left) and two teammates from the lineup that are not its character (middle, right)."""
    T = _W["T"]
    char = lambda c: T.idx("Costume", "CostumeId")[c]["CharacterId"]
    mates = [s for c, s in pair if char(c) != char(costume_id)][:2]
    return [spec] + mates


def _references(T, ex, st):
    """The experts' strongest costume of each element, with the default loadout: what every candidate fights."""
    from deckbuilder.sim import battle
    out = []
    for e in ("fire", "water", "wind", "light", "dark"):
        best = max((c for c in ex.costumes() if T.is_fieldable(c) and equip.element_of(c, T) == e), key=ex.weight)
        eq = equip.equip((best,), equip.Mode("best"), st, st, T, ex, deck_number=90 + len(out))
        out.append((best, battle._side(eq.deck, T)))
    return out


def _deck(specs):
    """An Arena deck (deck 1) in the in-memory stage, holding these loadouts."""
    st = _W["st"]
    model._write_deck(st.db, st.uid, specs, 2, 1)
    return model.Deck(st, 2, 1)


def _score(spec, costume_id, beat=None):
    """(win share, margin) of the loadout in a team (_team_context): every teammate pair, every meta deck, both
    openings. With beat (the best so far): None as soon as the loadout cannot beat it even by winning every fight
    left (the same choice as running them all: a candidate is kept only when strictly better)."""
    import random
    from deckbuilder.sim import battle
    total = len(_W["pairs"]) * len(_W["meta"]) * 2
    wins = margin = 0.0
    n = 0
    for pair in _W["pairs"]:
        side = battle._side(_deck(_team_specs(costume_id, spec, pair)), _W["T"])
        for _, opp in _W["meta"]:
            for manual in (True, False):
                b = battle.Battle(side, opp, random.Random(0), manual); b.logging = False
                r = b.run()
                wins += r["win"] == "A"; margin += r["hpA"] - r["hpD"]; n += 1
                if beat is not None and round((wins + total - n) / total, 4) < beat[0]:
                    return None
    return round(wins / n, 4), round(margin / n, 4)


def _gear_candidates(costume_id):
    T, st = _W["T"], _W["st"]
    W = T.idx("Weapon", "WeaponId")
    pick = lambda kind, **w: st.pick(kind, **w)
    weapons = {}
    for w in (int(x) for x in equip.rankings()["weapons"]):
        u = pick("weapon", weapon_id=equip._final_id(w, T))
        if u:
            weapons[equip._final_id(w, T)] = u
    wt = equip._weapon_type(costume_id, T)
    mains = {w: u for w, u in weapons.items() if W.get(w, {}).get("WeaponType") == wt}
    comps = {c: u for c in (int(x) for x in equip.rankings()["companions"]) if (u := pick("companion", companion_id=c))}
    debris = {t: u for t in (int(x) for x in equip.rankings()["debris"]) if (u := pick("debris", thought_id=t))}
    return weapons, mains, comps, debris


def _gear_one(costume_id):
    """Coordinate search over the slots from the default loadout: each slot's every candidate with the rest
    fixed, keeping the best (win share, then margin)."""
    T, ex, st = _W["T"], _W["ex"], _W["st"]
    R = lambda kind, u: model.PieceRef(kind, u, "stage") if u else None
    try:
        eq = equip.equip((costume_id,), equip.Mode("best"), st, st, T, ex)
    except Exception as exc:  # noqa: BLE001 (reported, not hidden)
        return {"costume_id": costume_id, "error": f"default loadout: {exc}"}
    spec = eq.specs[0]
    if spec is None:
        return {"costume_id": costume_id, "error": "no default loadout"}
    default = _score(spec, costume_id)
    weapons, mains, comps, debris = _gear_candidates(costume_id)
    role = equip.role(costume_id, ex)
    sets = sorted(int(s) for s in equip.rankings()["memoir_sets"])
    best, evaluations = default, 1

    def better(cand):
        nonlocal best, evaluations
        sc = _score(cand, costume_id, beat=best); evaluations += 1
        if sc is not None and sc > best:
            best = sc
            return True
        return False

    for w, u in mains.items():
        cand = spec._replace(main_weapon=R("weapon", u))
        if better(cand):
            spec = cand
    for i in range(2):
        for w, u in weapons.items():
            subs = list(spec.subs) + [None] * (2 - len(spec.subs))
            if spec.main_weapon and u == spec.main_weapon.uuid or any(s and s.uuid == u for j, s in enumerate(subs) if j != i):
                continue
            subs[i] = R("weapon", u)
            cand = spec._replace(subs=[s for s in subs if s])
            if better(cand):
                spec = cand
    for c, u in comps.items():
        cand = spec._replace(companion=R("companion", u))
        if better(cand):
            spec = cand
    for s in sets:
        refs = equip._memoirs(equip._Picker(st, st, T, equip.Mode("best")), s, role, T)
        if len(refs) < 3:
            continue
        cand = spec._replace(memoirs=refs)
        if better(cand):
            spec = cand
    for t, u in debris.items():
        cand = spec._replace(debris=R("debris", u))
        if better(cand):
            spec = cand
    piece = lambda kind, ref: st.piece_id(kind, ref.uuid) if ref else None
    W = T.idx("Weapon", "WeaponId")
    main_id = piece("weapon", spec.main_weapon)
    memoir_set = None
    if spec.memoirs:
        g = T.idx("Parts", "PartsId")[piece("memoir", spec.memoirs[0])]["PartsGroupId"]
        memoir_set = T.idx("PartsGroup", "PartsGroupId")[g]["PartsSeriesId"]
    return {"costume_id": costume_id, "name": T.costume_name(costume_id), "role": role,
            "element": {v: k for k, v in equip.ELEM_ATTR.items()}.get(W.get(main_id, {}).get("AttributeType")),
            "main_weapon": main_id, "subs": [piece("weapon", s) for s in spec.subs],
            "companion": piece("companion", spec.companion), "memoir_set": memoir_set,
            "memoir_mains": list(equip.ROLE_MEMOIRS[role][1]), "debris": piece("debris", spec.debris),
            "default_score": default, "score": best, "evaluations": evaluations,
            "candidates": {"mains": len(mains), "weapons": len(weapons), "companions": len(comps), "memoir_sets": len(sets),
                           "debris": len(debris)}}


def cmd_gear(args) -> None:
    import multiprocessing as mp
    T = tables()
    costumes = sorted(c for c in T.idx("Costume", "CostumeId") if T.is_fieldable(c))
    if args.limit:
        costumes = costumes[:args.limit]
    t0 = time.time()
    with mp.get_context("spawn").Pool(args.workers, initializer=_worker_init) as pool:
        out = []
        for i, r in enumerate(pool.imap_unordered(_gear_one, costumes), 1):
            out.append(r)
            if i % 20 == 0 or i == len(costumes):
                print(f"  {i}/{len(costumes)} costumes, {time.time() - t0:.0f}s", flush=True)
    out.sort(key=lambda r: r["costume_id"])
    ok = [r for r in out if "error" not in r]
    name = lambda kind, i: T.name(kind, i) if i else None
    for r in ok:
        r["names"] = {"main_weapon": name("weapons", r["main_weapon"]), "subs": [name("weapons", s) for s in r["subs"]],
                      "companion": name("companions", r["companion"]), "debris": name("thoughts", r["debris"])}
    report("2_gear", {
        "took_s": round(time.time() - t0, 1), "costumes": len(out), "errors": [r for r in out if "error" in r],
        "improved_over_default": sum(1 for r in ok if tuple(r["score"]) > tuple(r["default_score"])),
        "evaluations": sum(r["evaluations"] for r in ok),
        "strongest": [(r["name"], r["score"]) for r in sorted(ok, key=lambda r: r["score"], reverse=True)[:10]],
        "loadouts": ok})


# ---------------------------------------------------------------- 3: fighters
def loadout_spec(r, st, T):
    """A baked loadout (2_gear.json) as a CharacterSpec of the bake stage's pieces."""
    P = lambda kind, col, i: model.PieceRef(kind, st.pick(kind, **{col: i}), "stage") if i else None
    memoirs = equip._memoirs(equip._Picker(st, st, T, equip.Mode("best")), r["memoir_set"], r["role"], T) if r["memoir_set"] else []
    return model.CharacterSpec(P("costume", "costume_id", r["costume_id"]), P("weapon", "weapon_id", r["main_weapon"]),
                               [P("weapon", "weapon_id", w) for w in r["subs"]], P("companion", "companion_id", r["companion"]),
                               memoirs, P("debris", "thought_id", r["debris"]))


def fighter_cache(T, st):
    from deckbuilder import fighters
    gear = json.loads((BAKE / "2_gear.json").read_text())["loadouts"]
    cache, specs = fighters.FighterCache(T, st), {}
    for r in gear:
        specs[r["costume_id"]] = loadout_spec(r, st, T)
        cache.add(r["costume_id"], specs[r["costume_id"]])
    return cache, specs


def cmd_fighters(args) -> None:
    """Cached fighters for every costume, checked on a small sample: equal to decks built whole, and fighting the same."""
    import random
    from deckbuilder import sim
    T = tables(); sim.use(T)
    from deckbuilder.sim import battle
    st = model.Save(model.snapshot(BAKE / "stage.db"), 1)
    t0 = time.time(); cache, specs = fighter_cache(T, st); fill = time.time() - t0
    rnd = random.Random(7); keys = sorted(specs)
    lineups = [tuple(rnd.sample(keys, 3)) for _ in range(args.decks)]
    t0 = time.time(); built = [battle._side(model.compose(st, st, [specs[c] for c in l], 2, 7, T), T) for l in lineups]; tb = time.time() - t0
    t0 = time.time(); cached = [cache.side(l) for l in lineups]; tc = time.time() - t0
    unequal = [list(l) for l, a, b in zip(lineups, built, cached) if a != b]
    fights_differ, n = [], 0
    for i in range(0, min(args.fights, len(lineups) - 1), 2):
        for manual in (True, False):
            x = battle.Battle(cached[i], cached[i + 1], random.Random(0), manual); x.logging = False
            y = battle.Battle(built[i], built[i + 1], random.Random(0), manual); y.logging = False
            n += 1
            if x.run() != y.run():
                fights_differ.append([list(lineups[i]), list(lineups[i + 1]), manual])
    report("3_fighters", {"costumes_cached": len(specs), "fill_s": round(fill, 2), "decks_checked": len(lineups),
                          "decks_unequal": unequal, "fights_checked": n, "fights_differ": fights_differ,
                          "ms_per_deck_built": round(1000 * tb / len(lineups), 2), "ms_per_deck_cached": round(1000 * tc / len(lineups), 3)})


# ---------------------------------------------------------------- 4/5: decks
def check_compiled(n=20) -> None:
    """The compiled simulator must score these decks exactly as the plain one: else stop."""
    import random
    _deck_worker_init()
    combos = random.Random(3).sample(all_combos(sorted(_W["specs"]), _W["char"]), n)
    plain = [bake_deck(c) for c in combos]
    compiled()
    _deck_worker_init(use_compiled=True)
    fast = [bake_deck(c) for c in combos]
    if plain != fast:
        raise SystemExit(f"the compiled simulator differs from battle.py on {sum(a != b for a, b in zip(plain, fast))} of {n} decks: not used")
    print(f"compiled simulator checked: identical on {n} decks", flush=True)

RUNS = 4                # seeds per matchup, as the app scores (generate.Generator runs=4)
SCALE = 10000           # win shares and margins are kept to 4 decimals, as the app rounds them


class _CountingRandom(__import__("random").Random):
    """A Random that counts its draws: a fight that never draws ends the same for every seed."""
    def __init__(self, seed):
        super().__init__(seed); self.draws = 0

    def random(self):
        self.draws += 1
        return super().random()

    def shuffle(self, x, *a, **kw):
        self.draws += 1
        return super().shuffle(x, *a, **kw)


def _matchup(att, dfn):
    """(win share, margin) of att against dfn, as battle.score gives it (RUNS seeds, both openings), running the
    other seeds only when the first drew a random number (else they end the same)."""
    from deckbuilder.sim import battle
    wins = margin = 0.0
    for manual in battle.OPENINGS:
        first = None
        for seed in range(RUNS):
            if first is not None and first[2] == 0:
                r = first[0]
            else:
                b = battle.Battle(att, dfn, __import__("random").Random(seed), manual); b.logging = False
                r = b.run()
                if first is None:
                    first = (r, None, b.chance_draws)
            wins += r["win"] == "A"
            margin += r["hpA"] - r["hpD"]
    k = RUNS * len(battle.OPENINGS)
    return round(wins / k, 4), round(margin / k, 4)


def _deck_worker_init(use_compiled=False):
    from deckbuilder import generate, sim
    T = tables(); sim.use(T)
    if use_compiled:
        compiled()
    from deckbuilder.sim import battle
    ex = experts_mod.Experts.load(T)
    st = model.Save(model.snapshot(BAKE / "stage.db"), 1)
    cache, specs = fighter_cache(T, st)
    gen = generate.Generator(T, ex, st, st)
    meta = [(battle._side(d, T), w, name) for d, w, name in gen.meta()]
    _W.update(T=T, ex=ex, st=st, cache=cache, specs=specs, gen=gen, meta=meta,
              char={c: T.idx("Costume", "CostumeId")[c]["CharacterId"] for c in specs})


def bake_deck(combo) -> tuple:
    """(lineup in slot order, attack win, attack margin, defense win, defense margin, Force) for a combination,
    scored as the app scores it against the general meta (Generator.outcome)."""
    gen, cache = _W["gen"], _W["cache"]
    lineup = gen.order(combo)
    side = cache.side(lineup)
    force = cache.force(lineup)
    aw = am = dw = dm = 0.0
    for opp, w, _ in _W["meta"]:
        win, margin = _matchup(side, opp)
        aw += w * win; am += w * margin
        win, margin = _matchup(opp, side)
        dw += w * (1 - win); dm -= w * margin
    return lineup, round(aw, 4), round(am, 4), round(dw, 4), round(dm, 4), force


def _app_deck(combo) -> tuple:
    """The same numbers the app's own way: the deck built whole, sim.score, power.deck_power."""
    from deckbuilder import power, sim
    T, st, gen, specs = _W["T"], _W["st"], _W["gen"], _W["specs"]
    lineup = gen.order(combo)
    deck = model.compose(st, st, [specs[c] for c in lineup], 2, 7, T)
    aw = am = dw = dm = 0.0
    for (d, w, _), (_, _, _) in zip(gen.meta(), _W["meta"]):
        win, margin = sim.score(deck, d, T, runs=RUNS)
        aw += w * win; am += w * margin
        win, margin = sim.score(d, deck, T, runs=RUNS)
        dw += w * (1 - win); dm -= w * margin
    return tuple(lineup), round(aw, 4), round(am, 4), round(dw, 4), round(dm, 4), power.deck_power(deck, T).total


def all_combos(costumes, char):
    import itertools
    return [c for c in itertools.combinations(costumes, 3) if len({char[x] for x in c}) == 3]


def cmd_sample(args) -> None:
    import random
    _deck_worker_init()                                  # the plain simulator first: the app's way of scoring
    combos = all_combos(sorted(_W["specs"]), _W["char"])
    rnd = random.Random(11)
    sample = rnd.sample(combos, args.decks)
    check = sample[:args.check]
    t0 = time.time(); app = [_app_deck(c) for c in check]; ta = time.time() - t0
    if args.compiled:                                    # then the bake's way, with the compiled simulator
        compiled(); _deck_worker_init(use_compiled=True)
    t0 = time.time(); baked = [bake_deck(c) for c in sample]; tb = time.time() - t0
    differ = [(list(b[0]), b[1:], a[1:]) for b, a in zip(baked, app) if tuple(b[0]) != a[0] or b[1:] != a[1:]]
    top = sorted(baked, key=lambda r: (-r[1], -r[2]))[:10]
    name = lambda l: " · ".join(_W["T"].character_name(c) for c in l)
    report("4_sample", {"combos_total": len(combos), "sampled": len(sample), "checked_against_app": len(check),
                        "differ_from_app": differ, "ms_per_deck_baked": round(1000 * tb / len(sample), 2), "compiled": args.compiled,
                        "ms_per_deck_app_way": round(1000 * ta / len(check), 1),
                        "estimate_full_bake_min_on_17_cores": round(len(combos) * tb / len(sample) / 17 / 60, 1),
                        "attack_win_spread": sorted(__import__("collections").Counter(round(r[1], 1) for r in baked).items()),
                        "top_attack_in_sample": [(name(r[0]), r[1], r[2], r[5]) for r in top]})


# ---------------------------------------------------------------- round-robin
def _rr_one(costume_id):
    """costume_id one-on-one against every other costume, as attacker and as defender (baked gear)."""
    cache = _W["cache"]
    me = cache.side((costume_id,))
    att = dfn = 0.0
    n = 0
    for other in sorted(_W["specs"]):
        if other == costume_id:
            continue
        them = cache.side((other,))
        att += _matchup(me, them)[0]
        dfn += 1 - _matchup(them, me)[0]
        n += 1
    return costume_id, round(att / n, 4), round(dfn / n, 4)


def cmd_roundrobin(args) -> None:
    import multiprocessing as mp
    from deckbuilder import screen
    T = tables()
    gear = json.loads((BAKE / "2_gear.json").read_text())["loadouts"]
    costumes = sorted(r["costume_id"] for r in gear)
    t0 = time.time()
    with mp.get_context("spawn").Pool(args.workers, initializer=_deck_worker_init) as pool:
        rows = list(pool.imap_unordered(_rr_one, costumes))
    took = time.time() - t0
    rows.sort(key=lambda r: -(r[1] + r[2]))
    rr_rank = {c: i for i, (c, a, d) in enumerate(rows)}
    team_rank = {r["costume_id"]: i for i, r in enumerate(sorted(gear, key=lambda r: tuple(r["score"]), reverse=True))}
    st = model.Save(model.snapshot(BAKE / "stage.db"), 1)
    ex = experts_mod.Experts.load(T)
    old_pool = screen.pool_by_strength(screen.strength(T, ex, st), T)
    def spearman(a, b):
        keys = [k for k in a if k in b]; n = len(keys)
        return round(1 - 6 * sum((a[k] - b[k]) ** 2 for k in keys) / (n * (n * n - 1)), 3)
    top60 = [c for c, _, _ in rows[:60]]
    name = T.costume_name
    report("rr_roundrobin", {"took_s": round(took, 1), "costumes": len(rows),
        "rank_agreement_with_team_gear_scores": spearman(rr_rank, team_rank),
        "top60_overlap_with_current_pool": len(set(top60) & set(old_pool)),
        "top20": [(name(c), a, d) for c, a, d in rows[:20]],
        "in_current_pool_but_rr_rank_over_120": [(name(c), rr_rank[c]) for c in old_pool if rr_rank[c] > 120],
        "rr_top60_not_in_current_pool": [(name(c), rr_rank[c]) for c in top60 if c not in old_pool],
        "ranking": [(c, name(c), a, d) for c, a, d in rows]})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stage").set_defaults(fn=cmd_stage)
    g = sub.add_parser("gear"); g.set_defaults(fn=cmd_gear)
    g.add_argument("--limit", type=int, default=0, help="only the first N costumes (a trial run)")
    g.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    f = sub.add_parser("fighters"); f.set_defaults(fn=cmd_fighters)
    f.add_argument("--decks", type=int, default=300); f.add_argument("--fights", type=int, default=100)
    rr = sub.add_parser("roundrobin"); rr.set_defaults(fn=cmd_roundrobin)
    rr.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    sp = sub.add_parser("sample"); sp.set_defaults(fn=cmd_sample)
    sp.add_argument("--decks", type=int, default=2000); sp.add_argument("--check", type=int, default=100)
    sp.add_argument("--plain", dest="compiled", action="store_false", help="the plain simulator, not the compiled one")
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
