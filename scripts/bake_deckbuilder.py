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

import os as _os
BAKE = Path(_os.environ.get("BAKE_DIR") or BUILD / "bake")     # an experiment bakes into its own folder
META = int(_os.environ.get("BAKE_META") or 5)                  # expert meta decks the decks (and gear) are scored against
META_TOP = int(_os.environ.get("BAKE_META_TOP") or 0)          # plus this many of the strongest decks of an earlier bake
TOP_FROM = Path(_os.environ.get("BAKE_TOP_FROM") or BUILD / "bake")
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


def _worker_init(use_compiled=False):
    from deckbuilder import sim
    T = tables()
    sim.use(T)
    if use_compiled:
        compiled()
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
    gen = generate.Generator(T, ex, st, st, meta_size=META)
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


def _force_score(spec, costume_id) -> int:
    """The Force of the loadout's deck: the costume (left) with the first expert lineup's two teammates (team-wide
    statuses reach them, as in the game's Force)."""
    from deckbuilder import power
    st = _W["st"]
    keep = []
    if spec.karma:                                     # the spec's own karma (force-gear's), on the staged costume for now
        keep = st.db.execute("select slot_number, odds_number from user_costume_lottery_effects where user_id=? and user_costume_uuid=?",
                             (st.uid, spec.costume.uuid)).fetchall()
        for slot, odds in spec.karma.items():
            st.db.execute("update user_costume_lottery_effects set odds_number=? where user_id=? and user_costume_uuid=? and slot_number=?",
                          (int(odds), st.uid, spec.costume.uuid, int(slot)))
    try:
        return power.deck_power(_deck(_team_specs(costume_id, spec, _W["pairs"][0])), _W["T"]).total
    finally:
        for slot, odds in keep:
            st.db.execute("update user_costume_lottery_effects set odds_number=? where user_id=? and user_costume_uuid=? and slot_number=?",
                          (odds, st.uid, spec.costume.uuid, slot))


def _force_gear_one(costume_id):
    """The loadout with the most Force: every candidate of each slot in turn, the rest fixed (as _gear_one, by Force)."""
    T, ex, st = _W["T"], _W["ex"], _W["st"]
    R = lambda kind, u: model.PieceRef(kind, u, "stage") if u else None
    spec = equip.equip((costume_id,), equip.Mode("best"), st, st, T, ex).specs[0]
    if spec is None:
        return {"costume_id": costume_id, "error": "no default loadout"}
    best = default = _force_score(spec, costume_id)
    weapons, mains, comps, debris = _gear_candidates(costume_id)
    role = equip.role(costume_id, ex)

    def better(cand):
        nonlocal best
        f = _force_score(cand, costume_id)
        if f > best:
            best = f
            return True
        return False

    for w, u in mains.items():
        cand = spec._replace(main_weapon=R("weapon", u))
        if better(cand): spec = cand
    for i in range(2):
        for w, u in weapons.items():
            subs = list(spec.subs) + [None] * (2 - len(spec.subs))
            if spec.main_weapon and u == spec.main_weapon.uuid or any(x and x.uuid == u for j, x in enumerate(subs) if j != i):
                continue
            subs[i] = R("weapon", u)
            cand = spec._replace(subs=[x for x in subs if x])
            if better(cand): spec = cand
    for c, u in comps.items():
        cand = spec._replace(companion=R("companion", u))
        if better(cand): spec = cand
    memoir_role = role
    for s_ in sorted(int(x) for x in equip.rankings()["memoir_sets"]):
        for r_ in (role, "force"):                     # the role's memoirs, or the Force build (equip.ROLE_MEMOIRS)
            refs = equip._memoirs(equip._Picker(st, st, T, equip.Mode("best")), s_, r_, T)
            if len(refs) == 3:
                cand = spec._replace(memoirs=refs)
                if better(cand): spec, memoir_role = cand, r_
    for t, u in debris.items():
        cand = spec._replace(debris=R("debris", u))
        if better(cand): spec = cand
    for _ in range(2):                                 # karma for Force: each slot's top-tier options in turn
        for slot, options in sorted(karma_options(costume_id, T).items()):
            for o in options:
                cand = spec._replace(karma={**(spec.karma or {}), str(slot): o})
                if better(cand): spec = cand
    piece = lambda kind, ref: st.piece_id(kind, ref.uuid) if ref else None
    W = T.idx("Weapon", "WeaponId")
    main_id = piece("weapon", spec.main_weapon)
    memoir_set = None
    if spec.memoirs:
        g = T.idx("Parts", "PartsId")[piece("memoir", spec.memoirs[0])]["PartsGroupId"]
        memoir_set = T.idx("PartsGroup", "PartsGroupId")[g]["PartsSeriesId"]
    return {"costume_id": costume_id, "name": T.costume_name(costume_id), "role": role,
            "element": {v: k for k, v in equip.ELEM_ATTR.items()}.get(W.get(main_id, {}).get("AttributeType")),
            "main_weapon": main_id, "subs": [piece("weapon", x) for x in spec.subs], "companion": piece("companion", spec.companion),
            "memoir_set": memoir_set, "memoir_role": memoir_role if spec.memoirs else None, "force_karma": spec.karma,
            "debris": piece("debris", spec.debris), "default_force": default, "force": best}


def cmd_forcegear(args) -> None:
    """Each costume's loadout with the most Force (2f_force_gear.json): for the Force list."""
    import multiprocessing as mp
    T = tables()
    costumes = sorted(c for c in T.idx("Costume", "CostumeId") if T.is_fieldable(c))
    t0 = time.time()
    with mp.get_context("spawn").Pool(args.workers, initializer=_worker_init) as pool:
        out = sorted(pool.imap_unordered(_force_gear_one, costumes), key=lambda r: r["costume_id"])
    ok = [r for r in out if "error" not in r]
    report("2f_force_gear", {"took_s": round(time.time() - t0, 1), "costumes": len(out), "errors": [r for r in out if "error" in r],
                             "raised_over_default": sum(1 for r in ok if r["force"] > r["default_force"]),
                             "strongest": [(r["name"], r["force"]) for r in sorted(ok, key=lambda r: -r["force"])[:10]], "loadouts": ok})


def cmd_gear(args) -> None:
    import multiprocessing as mp
    T = tables()
    costumes = sorted(c for c in T.idx("Costume", "CostumeId") if T.is_fieldable(c))
    if args.limit:
        costumes = costumes[:args.limit]
    t0 = time.time()
    if args.compiled:
        check_compiled(20)
    with mp.get_context("spawn").Pool(args.workers, initializer=_worker_init, initargs=(args.compiled,)) as pool:
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


# ---------------------------------------------------------------- 2k: karma
def karma_options(costume_id, T) -> dict:
    """{slot: [odds numbers]}: each karma slot's top-tier options (the game's rarest roll of each effect)."""
    odds = T.grp("CostumeLotteryEffectOddsGroup", "CostumeLotteryEffectOddsGroupId")
    return {le["SlotNumber"]: sorted(o["OddsNumber"] for o in odds.get(le["CostumeLotteryEffectOddsGroupId"], []) if o["RarityType"] == 40)
            for le in T.T("CostumeLotteryEffect") if le["CostumeId"] == costume_id}


def _karma_one(costume_id):
    """The best karma for the costume in its baked loadout: every combination of its slots' top-tier options, scored
    in a team (_score) against the meta, kept only when strictly better (win share, then margin) than the stage's own."""
    import itertools
    from deckbuilder import baked
    T, st = _W["T"], _W["st"]
    lo = _W["gear"].get(costume_id)
    if lo is None:
        return {"costume_id": costume_id, "error": "no baked loadout"}
    spec = baked.loadout_spec(lo, st, T)
    uuid = spec.costume.uuid
    rows = {r["slot_number"]: r["odds_number"] for r in st.q("select slot_number, odds_number from user_costume_lottery_effects"
                                                               " where user_id=? and user_costume_uuid=?", uuid)}
    opts = {s: o for s, o in karma_options(costume_id, T).items() if s in rows and o}
    if not opts:
        return {"costume_id": costume_id, "name": T.costume_name(costume_id), "karma": {}, "evaluations": 0}
    slots = sorted(opts)
    def put(karma):
        for s, o in karma.items():
            st.db.execute("update user_costume_lottery_effects set odds_number=? where user_id=? and user_costume_uuid=? and slot_number=?",
                          (o, st.uid, uuid, s))
    default = {s: rows[s] for s in slots}
    best_k, best = default, _score(spec, costume_id)
    first = best
    n = 1
    for combo in itertools.product(*(opts[s] for s in slots)):
        k = dict(zip(slots, combo))
        if k == default:
            continue
        put(k)
        sc = _score(spec, costume_id, beat=best); n += 1
        if sc is not None and sc > best:
            best, best_k = sc, k
    put(default)
    return {"costume_id": costume_id, "name": T.costume_name(costume_id), "karma": {str(s): o for s, o in best_k.items()},
            "default": {str(s): o for s, o in default.items()}, "default_score": first, "score": best, "evaluations": n}


def _karma_worker_init(use_compiled=False):
    _worker_init(use_compiled)
    _W["gear"] = {c: lo for c, lo in gear_loadouts(with_karma=False).items()}


def cmd_karma(args) -> None:
    """Each costume's best karma in its baked loadout (2k_karma.json); setkarma writes it into the stage."""
    import multiprocessing as mp
    T = tables()
    costumes = sorted(gear_loadouts(with_karma=False))
    if args.limit:
        costumes = costumes[:args.limit]
    t0 = time.time()
    if args.compiled:
        check_compiled(20)
    with mp.get_context("spawn").Pool(args.workers, initializer=_karma_worker_init, initargs=(args.compiled,)) as pool:
        out = []
        for i, r in enumerate(pool.imap_unordered(_karma_one, costumes), 1):
            out.append(r)
            if i % 20 == 0 or i == len(costumes):
                print(f"  {i}/{len(costumes)} costumes, {time.time() - t0:.0f}s", flush=True)
    out.sort(key=lambda r: r["costume_id"])
    ok = [r for r in out if "error" not in r]
    report("2k_karma", {"took_s": round(time.time() - t0, 1), "costumes": len(out), "errors": [r for r in out if "error" in r],
                        "changed": sum(1 for r in ok if r["karma"] != r.get("default", r["karma"])),
                        "improved": sum(1 for r in ok if r.get("score") and tuple(r["score"]) > tuple(r["default_score"])),
                        "evaluations": sum(r["evaluations"] for r in ok), "karma": ok})


def baked_karma() -> dict:
    """{costume id: {slot: odds number}} from 2k_karma.json ({} before the karma step)."""
    path = BAKE / "2k_karma.json"
    if not path.exists():
        return {}
    return {r["costume_id"]: r["karma"] for r in json.loads(path.read_text())["karma"] if r.get("karma")}


def cmd_setkarma(args) -> None:
    """The baked karma written into the bake's stage (the server's own set_costume_karma_batch)."""
    T = tables()
    k = baked_karma()
    stage_mod.Stager(cli_invoke(BAKE / "stage.db"), T).set_karma(k)
    db = sqlite3.connect(f"file:{BAKE / 'stage.db'}?mode=ro", uri=True)
    got = {}
    for c, s, o in db.execute("select c.costume_id, e.slot_number, e.odds_number from user_costume_lottery_effects e"
                              " join user_costumes c using (user_costume_uuid)"):
        got.setdefault(c, {})[str(s)] = o
    report("2k_setkarma", {"costumes": len(k), "mismatched": sorted(c for c, v in k.items() if got.get(c) != v)})


# ---------------------------------------------------------------- 3: fighters
def gear_loadouts(with_karma=True):
    """Each costume's baked loadout (2_gear.json), with its element and (after the karma step) its karma:
    {costume id: loadout}."""
    keys = ("costume_id", "role", "element", "main_weapon", "subs", "companion", "memoir_set", "debris")
    los = {r["costume_id"]: {k: r[k] for k in keys} for r in json.loads((BAKE / "2_gear.json").read_text())["loadouts"]}
    return _with_karma(los) if with_karma else los


def _with_karma(los: dict) -> dict:
    k = baked_karma()
    return {c: dict(lo, karma=k[c]) if c in k else lo for c, lo in los.items()}


def fighter_cache(T, st):
    """The fighter cache with every costume's baked fighter, keyed (costume id, debris): a deck that gives a character
    another debris (baked.deck_loadouts) adds its fighter as it comes (deck_keys)."""
    from deckbuilder import baked, fighters
    los = gear_loadouts()
    cache = fighters.FighterCache(T, st)
    for c, lo in los.items():
        cache.add((c, lo["debris"]), baked.loadout_spec(lo, st, T))
    return cache, los


def deck_keys(lineup):
    """(fighter keys, loadouts) of a deck in slot order: a debris taken twice goes to the next (baked.deck_loadouts),
    as Deck Builder writes the deck."""
    from deckbuilder import baked
    los = baked.deck_loadouts(lineup, _W["los"], _W["order"])
    keys = []
    for lo in los:
        k = (lo["costume_id"], lo["debris"])
        if k not in _W["cache"]:
            _W["cache"].add(k, baked.loadout_spec(lo, _W["st"], _W["T"]))
        keys.append(k)
    return tuple(keys), los


def cmd_fighters(args) -> None:
    """Cached fighters for every costume, checked on a small sample: equal to decks built whole, and fighting the same."""
    import random
    from deckbuilder import baked
    t0 = time.time(); _deck_worker_init(); fill = time.time() - t0
    from deckbuilder.sim import battle
    T, st = _W["T"], _W["st"]
    rnd = random.Random(7); keys = sorted(_W["los"])
    lineups = [tuple(rnd.sample(keys, 3)) for _ in range(args.decks)]
    t0 = time.time()
    built = [battle._side(model.compose(st, st, [baked.loadout_spec(lo, st, T) for lo in deck_keys(l)[1]], 2, 7, T), T) for l in lineups]
    tb = time.time() - t0
    t0 = time.time(); cached = [_W["cache"].side(deck_keys(l)[0]) for l in lineups]; tc = time.time() - t0
    unequal = [list(l) for l, a, b in zip(lineups, built, cached) if a != b]
    fights_differ, n = [], 0
    for i in range(0, min(args.fights, len(lineups) - 1), 2):
        for manual in (True, False):
            x = battle.Battle(cached[i], cached[i + 1], random.Random(0), manual); x.logging = False
            y = battle.Battle(built[i], built[i + 1], random.Random(0), manual); y.logging = False
            n += 1
            if x.run() != y.run():
                fights_differ.append([list(lineups[i]), list(lineups[i + 1]), manual])
    report("3_fighters", {"costumes_cached": len(_W["los"]), "fill_s": round(fill, 2), "decks_checked": len(lineups),
                          "decks_unequal": unequal, "fights_checked": n, "fights_differ": fights_differ,
                          "ms_per_deck_built": round(1000 * tb / len(lineups), 2), "ms_per_deck_cached": round(1000 * tc / len(lineups), 3)})


# ---------------------------------------------------------------- 4/5: decks
def check_compiled(n=20) -> None:
    """The compiled simulator must score these decks exactly as the plain one: else stop."""
    import random
    _deck_worker_init()
    combos = random.Random(3).sample(all_combos(sorted(_W["los"]), _W["char"]), n)
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


def _pair(side, opp, prep_d=None, prep_a=None):
    """(_matchup(side, opp), _matchup(opp, side)) with each defense fight taken from its attack fight mirrored when
    nothing in it depended on the roles (Battle.mirror_safe, no chance draws): the same sums, in the same order."""
    import random
    from deckbuilder.sim import battle
    k = RUNS * len(battle.OPENINGS)
    first = {}
    wins = margin = 0.0
    for manual in battle.OPENINGS:
        once = None
        for seed in range(RUNS):
            if once is not None:
                r = once
            else:
                b = battle.Battle(side, opp, random.Random(seed), manual, prepared=prep_d); b.logging = False
                r = b.run()
                if seed == 0:
                    first[manual] = (r, b.chance_draws == 0 and b.mirror_safe)
                    if b.chance_draws == 0:
                        once = r
            wins += r["win"] == "A"; margin += r["hpA"] - r["hpD"]
    attack = (round(wins / k, 4), round(margin / k, 4))
    wins = margin = 0.0
    for manual in battle.OPENINGS:
        src, safe = first[not manual]
        once = battle.mirror(src) if safe else None
        for seed in range(RUNS):
            if once is not None:
                r = once
            else:
                b = battle.Battle(opp, side, random.Random(seed), manual, prepared=prep_a); b.logging = False
                r = b.run()
                if seed == 0 and b.chance_draws == 0:
                    once = r
            wins += r["win"] == "A"; margin += r["hpA"] - r["hpD"]
    return attack, (round(wins / k, 4), round(margin / k, 4))


def meta_top(ex) -> list:
    """The META_TOP strongest attack decks of the bake in TOP_FROM that are not expert meta decks (slot order)."""
    if not META_TOP:
        return []
    known = {frozenset(l.costumes) for l in ex.meta_pool()}
    top = []
    for r in sorted(read_decks(TOP_FROM / "decks"), key=lambda r: (-r[3], -r[4])):
        if frozenset(r[:3]) not in known and len(top) < META_TOP:
            known.add(frozenset(r[:3])); top.append(tuple(r[:3]))
    return top


def _deck_worker_init(use_compiled=False):
    from deckbuilder import generate, sim
    T = tables(); sim.use(T)
    if use_compiled:
        compiled()
    from deckbuilder.sim import battle
    ex = experts_mod.Experts.load(T)
    st = model.Save(model.snapshot(BAKE / "stage.db"), 1)
    from deckbuilder import baked
    cache, los = fighter_cache(T, st)
    gen = generate.Generator(T, ex, st, st, meta_size=META)
    _W.update(T=T, st=st, cache=cache, los=los, order=baked.debris_order(los), gen=gen)
    meta = [(battle._side(d, T), w, name) for d, w, name in gen.meta()]
    top = meta_top(ex)
    _W["meta_top"] = top
    if top:
        # the strongest decks of an earlier bake join the expert meta as opponents, every opponent weighted alike
        # (as the app scores a baked deck: generate.Generator.baked_opponents)
        meta = meta + [(cache.side(deck_keys(l)[0]), 0.0, "Bake top " + " · ".join(T.character_name(c) for c in l)) for l in top]
        meta = [(m, 1 / len(meta), n) for m, _, n in meta]
    # each meta deck set up once per role (battle.prepare_side; None where that cannot stand in for setting it up)
    prepared = [(battle.prepare_side(m, "D"), battle.prepare_side(m, "A")) for m, _, _ in meta]
    _W.update(T=T, ex=ex, st=st, cache=cache, los=los, order=baked.debris_order(los), gen=gen, meta=meta, prepared=prepared,
              char={c: T.idx("Costume", "CostumeId")[c]["CharacterId"] for c in los})


def bake_deck(combo) -> tuple:
    """(lineup in slot order, attack win, attack margin, defense win, defense margin, Force) for a combination,
    scored as the app scores it against the general meta (Generator.outcome)."""
    gen, cache = _W["gen"], _W["cache"]
    lineup = gen.order(combo)
    side, force = cache.side_force(deck_keys(lineup)[0])
    aw = am = dw = dm = 0.0
    for (opp, w, _), (prep_d, prep_a) in zip(_W["meta"], _W.get("prepared") or [(None, None)] * len(_W["meta"])):
        (win, margin), (dwin, dmargin) = _pair(side, opp, prep_d, prep_a)
        aw += w * win; am += w * margin
        dw += w * (1 - dwin); dm -= w * dmargin
    return lineup, round(aw, 4), round(am, 4), round(dw, 4), round(dm, 4), force


def _app_deck(combo) -> tuple:
    """The same numbers the app's own way: the deck built whole, sim.score, power.deck_power."""
    from deckbuilder import power, sim
    from deckbuilder import baked
    T, st, gen = _W["T"], _W["st"], _W["gen"]
    lineup = gen.order(combo)
    deck = model.compose(st, st, [baked.loadout_spec(lo, st, T) for lo in deck_keys(lineup)[1]], 2, 7, T)
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
    combos = all_combos(sorted(_W["los"]), _W["char"])
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


# ---------------------------------------------------------------- 5: the full bake
DECKS = BAKE / "decks"
FIELDS = ("left", "middle", "right", "attack_win", "attack_margin", "defense_win", "defense_margin", "force")


def _chunk_path(i: int) -> Path:
    return DECKS / f"chunk_{i:03d}.bin"


def _bake_chunk(job):
    """Every deck whose lowest costume is costumes[i]: 8 int32 per deck (FIELDS; shares and margins x SCALE),
    written whole to its chunk file (a temp file renamed: a stopped bake leaves no half chunk)."""
    from array import array
    i, combos = job
    rows = array("i")
    for c in combos:
        lineup, aw, am, dw, dm, force = bake_deck(c)
        rows.extend(list(lineup) + [round(aw * SCALE), round(am * SCALE), round(dw * SCALE), round(dm * SCALE), force])
    tmp = _chunk_path(i).with_suffix(".tmp")
    with open(tmp, "wb") as f:
        rows.tofile(f)
    tmp.rename(_chunk_path(i))
    return i, len(combos)


def read_decks(folder=None):
    """All baked decks as tuples of FIELDS (shares and margins back as fractions)."""
    from array import array
    for path in sorted((folder or DECKS).glob("chunk_*.bin")):
        a = array("i")
        with open(path, "rb") as f:
            a.frombytes(f.read())
        for k in range(0, len(a), len(FIELDS)):
            r = a[k:k + len(FIELDS)]
            yield (r[0], r[1], r[2], r[3] / SCALE, r[4] / SCALE, r[5] / SCALE, r[6] / SCALE, r[7])


def cmd_bake(args) -> None:
    import collections
    import multiprocessing as mp
    if args.compiled:
        check_compiled(20)
    T = tables()
    gear = json.loads((BAKE / "2_gear.json").read_text())["loadouts"]
    costumes = sorted(r["costume_id"] for r in gear)
    char = {c: T.idx("Costume", "CostumeId")[c]["CharacterId"] for c in costumes}
    groups = collections.defaultdict(list)
    for c in all_combos(costumes, char):
        groups[costumes.index(c[0])].append(c)
    DECKS.mkdir(parents=True, exist_ok=True)
    for t in DECKS.glob("*.tmp"):
        t.unlink()
    pending = sorted((i for i in groups if not _chunk_path(i).exists()), key=lambda i: -len(groups[i]))
    total = sum(len(v) for v in groups.values())
    left = sum(len(groups[i]) for i in pending)
    print(f"{total:,} decks in {len(groups)} chunks; {left:,} to bake in {len(pending)} chunks", flush=True)
    t0 = time.time(); done = 0
    if pending:
        with mp.get_context("spawn").Pool(args.workers, initializer=_deck_worker_init, initargs=(args.compiled,)) as pool:
            for i, n in pool.imap_unordered(_bake_chunk, [(i, groups[i]) for i in pending]):
                done += n
                el = time.time() - t0
                print(f"  {done:,}/{left:,} decks ({100 * done / left:.1f}%), {el / 60:.1f} min, about {el * (left - done) / max(done, 1) / 60:.1f} min left",
                      flush=True)
    took = time.time() - t0
    rows = list(read_decks())
    name = lambda r: " · ".join(T.character_name(c) for c in r[:3])
    top = lambda key, n=15: [(name(r), list(r[:3]), r[3], r[4], r[5], r[6], r[7]) for r in sorted(rows, key=key)[:n]]
    spread = lambda k: sorted(collections.Counter(round(r[k], 1) for r in rows).items())
    report("5_bake", {
        "decks": len(rows), "expected": total, "missing_chunks": [i for i in groups if not _chunk_path(i).exists()],
        "took_min": round(took / 60, 1), "compiled": args.compiled,
        "size_mb": round(sum(p.stat().st_size for p in DECKS.glob("chunk_*.bin")) / 1e6, 1),
        "attack_win_spread": spread(3), "defense_win_spread": spread(5),
        "top_attack": top(lambda r: (-r[3], -r[4], -r[7])), "top_defense": top(lambda r: (-r[5], -r[6], -r[7])),
        "top_force": top(lambda r: -r[7], 10), "fields": FIELDS})


# ---------------------------------------------------------------- the Force list
DECKS_FORCE = BAKE / "decks_force"


def force_loadouts():
    keys = ("costume_id", "role", "element", "main_weapon", "subs", "companion", "memoir_set", "memoir_role", "force_karma", "debris")
    return _with_karma({r["costume_id"]: {k: r.get(k) for k in keys} for r in json.loads((BAKE / "2f_force_gear.json").read_text())["loadouts"]})


def _force_worker_init():
    """A worker for the Force list: the same state as the decks' (_deck_worker_init), with the Force loadouts."""
    from deckbuilder import baked, fighters, generate, sim
    T = tables(); sim.use(T)
    ex = experts_mod.Experts.load(T)
    st = model.Save(model.snapshot(BAKE / "stage.db"), 1)
    los = force_loadouts()
    cache = fighters.FighterCache(T, st)
    for c, lo in los.items():
        cache.add((c, lo["debris"]), baked.loadout_spec(lo, st, T))
    _W.update(T=T, ex=ex, st=st, cache=cache, los=los, order=baked.debris_order(los),
              gen=generate.Generator(T, ex, st, st), char={c: T.idx("Costume", "CostumeId")[c]["CharacterId"] for c in los})


def _force_chunk(job):
    from array import array
    i, combos = job
    rows = array("i")
    for c in combos:
        lineup = _W["gen"].order(c)
        rows.extend(list(lineup) + [_W["cache"].force(deck_keys(lineup)[0])])
    tmp = (DECKS_FORCE / f"chunk_{i:03d}.bin").with_suffix(".tmp")
    with open(tmp, "wb") as f:
        rows.tofile(f)
    tmp.rename(DECKS_FORCE / f"chunk_{i:03d}.bin")
    return i, len(combos)


def read_force(folder=None):
    from array import array
    for path in sorted((folder or DECKS_FORCE).glob("chunk_*.bin")):
        a = array("i")
        with open(path, "rb") as f:
            a.frombytes(f.read())
        for k in range(0, len(a), 4):
            yield tuple(a[k:k + 3]), a[k + 3]


def cmd_forcebake(args) -> None:
    """Every deck's Force with each costume's Force loadout (a debris taken twice goes to the next), for the Force list."""
    import collections
    import multiprocessing as mp
    T = tables()
    los = force_loadouts()
    costumes = sorted(los)
    char = {c: T.idx("Costume", "CostumeId")[c]["CharacterId"] for c in costumes}
    groups = collections.defaultdict(list)
    for c in all_combos(costumes, char):
        groups[costumes.index(c[0])].append(c)
    DECKS_FORCE.mkdir(parents=True, exist_ok=True)
    pending = sorted((i for i in groups if not (DECKS_FORCE / f"chunk_{i:03d}.bin").exists()), key=lambda i: -len(groups[i]))
    t0 = time.time()
    with mp.get_context("spawn").Pool(args.workers, initializer=_force_worker_init) as pool:
        for _ in pool.imap_unordered(_force_chunk, [(i, groups[i]) for i in pending]):
            pass
    rows = list(read_force())
    top = sorted(rows, key=lambda r: -r[1])[:10]
    report("5f_force", {"decks": len(rows), "took_min": round((time.time() - t0) / 60, 1),
                        "top": [(" · ".join(T.character_name(c) for c in l), f) for l, f in top]})


# ---------------------------------------------------------------- ship
def cmd_ship(args) -> None:
    """The baked results into the app (deckbuilder/data/baked): the top decks per role, every costume's loadout, the
    fighter fingerprint the phone compares after preparing its stage."""
    from deckbuilder import baked
    from deckbuilder import fighters
    _deck_worker_init()
    los, flos, T, st = _W["los"], force_loadouts(), _W["T"], _W["st"]
    # the fingerprint over both loadout sets, built as the phone builds them (android_deckbuilder._baked_check)
    cache, keys = fighters.FighterCache(T, st), {}
    for label, set_ in (("fight", los), ("force", flos)):
        for c, lo in set_.items():
            keys[(label, c)] = (label, c, lo["debris"])
            cache.add(keys[(label, c)], baked.loadout_spec(lo, st, T))
    from deckbuilder.sim import battle
    # the experts' meta decks in the loadouts the bake equipped them with, shipped so the phone builds the same ones
    # (its stage may hold other pieces); checked to rebuild the opponents the bake fought
    md = baked.meta_decks(_W["gen"], _W["ex"], st, T)
    sides = [battle._side(baked.meta_deck(d, i, st, T), T) for i, d in enumerate(md)]
    if sides != [m for m, _, _ in _W["meta"][:len(md)]]:
        raise SystemExit("the shipped meta loadouts do not rebuild the bake's opponents")
    fp = baked.fingerprint(cache, keys, sides)
    rows = (baked.Record(tuple(r[:3]), r[3], r[4], r[5], r[6], r[7]) for r in read_decks())
    src = ROOT / "android/app/src/main/python/deckbuilder/sim/battle.py"
    path = baked.write(args.out, los, fp, rows, keep=args.keep,
                       extra={"bake": json.loads((BAKE / "5_bake.json").read_text())["decks"], "simulator": _code_hash()},
                       force_rows=read_force(), force_loadouts=flos, meta_decks=md, meta_top=_W["meta_top"])
    size = sum(p.stat().st_size for p in path.iterdir())
    report("6_ship", {"out": str(path), "fingerprint": fp, "size_mb": round(size / 1e6, 2), "keep": args.keep,
                      "decks": json.loads((path / "meta.json").read_text())["decks"]})


def _code_hash() -> str:
    """The simulator and Force code the bake ran (a stale bake shows as a different hash)."""
    import hashlib
    h = hashlib.sha256()
    base = ROOT / "android/app/src/main/python/deckbuilder"
    for p in sorted(list((base / "sim").glob("*.py")) + [base / f for f in ("power.py", "fighters.py", "baked.py", "equip.py", "model.py")]):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- round-robin
def _rr_one(costume_id):
    """costume_id one-on-one against every other costume, as attacker and as defender (baked gear)."""
    cache = _W["cache"]
    me = cache.side(((costume_id, _W["los"][costume_id]["debris"]),))
    att = dfn = 0.0
    n = 0
    for other in sorted(_W["los"]):
        if other == costume_id:
            continue
        them = cache.side(((other, _W["los"][other]["debris"]),))
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
    g.add_argument("--plain", dest="compiled", action="store_false", help="the plain simulator, not the compiled one")
    g.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    fg = sub.add_parser("forcegear"); fg.set_defaults(fn=cmd_forcegear)
    fg.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    kk = sub.add_parser("karma"); kk.set_defaults(fn=cmd_karma)
    kk.add_argument("--limit", type=int, default=0, help="only the first N costumes (a trial run)")
    kk.add_argument("--plain", dest="compiled", action="store_false", help="the plain simulator, not the compiled one")
    kk.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    sub.add_parser("setkarma").set_defaults(fn=cmd_setkarma)
    f = sub.add_parser("fighters"); f.set_defaults(fn=cmd_fighters)
    f.add_argument("--decks", type=int, default=300); f.add_argument("--fights", type=int, default=100)
    fb = sub.add_parser("forcebake"); fb.set_defaults(fn=cmd_forcebake)
    fb.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    sh = sub.add_parser("ship"); sh.set_defaults(fn=cmd_ship)
    sh.add_argument("--out", type=Path, default=ROOT / "android/app/src/main/python/deckbuilder/data/baked")
    sh.add_argument("--keep", type=int, default=300000)
    rr = sub.add_parser("roundrobin"); rr.set_defaults(fn=cmd_roundrobin)
    rr.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    bk = sub.add_parser("bake"); bk.set_defaults(fn=cmd_bake)
    bk.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    bk.add_argument("--plain", dest="compiled", action="store_false", help="the plain simulator, not the compiled one")
    sp = sub.add_parser("sample"); sp.set_defaults(fn=cmd_sample)
    sp.add_argument("--decks", type=int, default=2000); sp.add_argument("--check", type=int, default=100)
    sp.add_argument("--plain", dest="compiled", action="store_false", help="the plain simulator, not the compiled one")
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
