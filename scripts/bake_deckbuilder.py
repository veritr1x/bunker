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


PARTNER_LINEUPS = 2     # the experts' top lineups that lend a candidate its two teammates


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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stage").set_defaults(fn=cmd_stage)
    g = sub.add_parser("gear"); g.set_defaults(fn=cmd_gear)
    g.add_argument("--limit", type=int, default=0, help="only the first N costumes (a trial run)")
    g.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 1))
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
