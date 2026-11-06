"""Mods › Challenges: harder battles that pay a reward bonus.

The game works battles out on the device from its game data, so these change
the game data the game loads (the server only reads the settings for the
bonus, internal/mods):

- Hard enemies: enemy levels. An enemy costume's HP, attack and vitality are
  slope × level / 1000 (NumericalFunctionType 4, no offset) for almost every
  enemy, so ×N level is ×N stats; the few on another curve get the level that
  comes closest. Enemy costumes have ids from 1,000,000 up; lower ids are the
  player's costumes (story guests, mirror fights), which stay. Subjugation
  (Big Hunt) battles stay: their rewards follow score.
- Weakness only: the player's element damage table for normal battles
  (BattleSchemeType 1, group 1): every hit that isn't super-effective
  (≤ 1000‰) does half. The Arena (scheme 2, group 3, shared by both sides)
  and the enemies' table stay.
- Slow skills: the cooldown each of the player's skills has
  (m_skill_detail.SkillCooltimeValue) ×1.5. The tables for how fast cooldowns
  fill are shared with enemies and stay.

Stat curves are shared with the player's costumes and are never changed.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import msgpack

PLAYER_ID_LIMIT = 1_000_000  # costume and weapon ids below this are the player's
INT32_MAX = 2**31 - 1
# Element damage: normal battles' player table. The Arena's (scheme 2) is its own.
PLAYER_DAMAGE_GROUP = 1
SLOW = 1.5


def _schemas():
    from tools import dump_masterdata
    return {t: [name for _, _, name in cols] for t, (_, cols) in dump_masterdata.load_schemas().items()}


_columns = None


def columns(table):
    global _columns
    if _columns is None:
        _columns = _schemas()
    return _columns[table]


def records(toc, blob, changed, table):
    """A table's rows as dicts by column name (from changed when touched)."""
    from android_calendar import _rows
    from patcher import patch_masterdata as pm
    names, out = columns(table), []

    def collect(b):
        for _, cells in _rows(b):
            out.append({names[i]: msgpack.unpackb(c, raw=False) for i, c in enumerate(cells) if i < len(names)})
        return 0
    pm.apply_to_table(toc, blob, dict(changed), table, collect)  # a copy: reading changes nothing
    return out


def _rewrite(toc, blob, changed, table, change):
    """Rewrites rows in place: change(row dict) returns {column: value} for a
    changed row, or None. Returns how many rows changed."""
    from android_calendar import _rows, _table
    from patcher import patch_masterdata as pm
    names = columns(table)
    count = 0

    def mutate(b):
        nonlocal count
        out = []
        for header, cells in _rows(b):
            row = {names[i]: msgpack.unpackb(c, raw=False) for i, c in enumerate(cells) if i < len(names)}
            new = change(row)
            if new:
                cells = list(cells)
                for name, value in new.items():
                    cells[names.index(name)] = msgpack.packb(value)
                count += 1
            out.append(header + b"".join(cells))
        return _table(out)
    pm.apply_to_table(toc, blob, changed, table, mutate)
    return count


def evaluate(function_type, p, value):
    """A numerical function, as the game works it out (64-bit)."""
    if function_type == 1:
        return p[1] + p[0] * value
    if function_type == 2:
        return (value - 1) ** max(p[1], 1) * p[0]
    if function_type in (4, 7):
        return int(p[0] * value / 1000) + p[1]
    if function_type == 5:
        return p[3] + (p[2] + (p[1] + p[0] * value) * value) * value
    if function_type == 6:
        return int(p[0] * value**3 / 1000) + int(p[1] * value**2 / 1000) + int(p[2] * value / 1000) + p[3]
    return 0


def _functions(toc, blob, changed):
    params = {}
    for r in records(toc, blob, changed, "m_numerical_function_parameter_group"):
        params.setdefault(r["NumericalFunctionParameterGroupId"], []).append((r["ParameterIndex"], r["ParameterValue"]))
    return {r["NumericalFunctionId"]: (r["NumericalFunctionType"], [v for _, v in sorted(params.get(r["NumericalFunctionParameterGroupId"], []))])
            for r in records(toc, blob, changed, "m_numerical_function")}


def _stat_functions(toc, blob, changed):
    """costume id -> its HP, attack and vitality functions."""
    functions = _functions(toc, blob, changed)
    calcs = {r["CostumeStatusCalculationId"]: r for r in records(toc, blob, changed, "m_costume_status_calculation")}
    out = {}
    for c in records(toc, blob, changed, "m_costume"):
        calc = calcs.get(c["CostumeStatusCalculationId"])
        if calc:
            out[c["CostumeId"]] = [functions.get(calc[k], (0, [])) for k in
                                   ("HpNumericalFunctionId", "AttackNumericalFunctionId", "VitalityNumericalFunctionId")]
    return out


def stat_sum(toc, blob, changed):
    """A function (costume id, level) -> HP + attack + vitality."""
    stats = _stat_functions(toc, blob, changed)
    return lambda costume, level: sum(evaluate(t, p, level) for t, p in stats.get(costume, []))


def linear_enemy_costumes(toc, blob, changed):
    """Enemy costumes whose stats are slope × level / 1000 with no offset."""
    return {c for c, fs in _stat_functions(toc, blob, changed).items()
            if c >= PLAYER_ID_LIMIT and fs and all(t == 4 and len(p) >= 2 and p[1] == 0 for t, p in fs)}


def big_hunt_costumes(toc, blob, changed):
    """The enemy costumes of subjugation (Big Hunt) battles, as (BattleNpcId,
    BattleNpcCostumeUuid): battle → its npc deck → the deck's characters →
    their costumes. (Most enemies share BattleNpcId 1, so the id alone won't do.)"""
    rec = lambda t: records(toc, blob, changed, t)
    groups = {r["BattleGroupId"] for r in rec("m_battle_big_hunt")}
    battles = {r["BattleId"] for r in rec("m_battle_group") if r["BattleGroupId"] in groups}
    decks = {(r["BattleNpcId"], r["DeckType"], r["BattleNpcDeckNumber"]) for r in rec("m_battle") if r["BattleId"] in battles}
    characters = {(d["BattleNpcId"], d[f"BattleNpcDeckCharacterUuid0{i}"]) for d in rec("m_battle_npc_deck")
                  if (d["BattleNpcId"], d["DeckType"], d["BattleNpcDeckNumber"]) in decks for i in (1, 2, 3)}
    return {(c["BattleNpcId"], c["BattleNpcCostumeUuid"]) for c in rec("m_battle_npc_deck_character")
            if (c["BattleNpcId"], c["BattleNpcDeckCharacterUuid"]) in characters}


def _peak(stats, costume, lo, hi):
    """The level in lo..hi with the most stats, for a curve that rises then falls."""
    while hi - lo > 2:
        a, b = lo + (hi - lo) // 3, hi - (hi - lo) // 3
        if stats(costume, a) < stats(costume, b):
            lo = a + 1
        else:
            hi = b
    return max(range(lo, hi + 1), key=lambda level: stats(costume, level))


def _level_for(stats, costume, level, factor):
    """The level whose stats come closest to factor × those at level. Some
    curves rise and then fall: when the target is past their peak, the peak."""
    target = factor * stats(costume, level)
    lo, hi = level, max(level + 1, int(level * factor) + 1)
    while stats(costume, hi) < target:
        if hi >= INT32_MAX or stats(costume, min(hi * 2, INT32_MAX)) <= stats(costume, hi):
            return _peak(stats, costume, lo, min(hi * 2, INT32_MAX))  # past the peak: out of reach
        lo, hi = hi, min(hi * 2, INT32_MAX)
    while lo < hi:  # the first level at or above the target (the rising side)
        mid = (lo + hi) // 2
        if stats(costume, mid) < target:
            lo = mid + 1
        else:
            hi = mid
    below = max(lo - 1, level)
    return below if abs(stats(costume, below) - target) < abs(stats(costume, lo) - target) else lo


def hard_enemies(toc, blob, changed, factor):
    """Enemy levels ×factor (see the module notes). Returns rows changed."""
    if factor in (0, 1):
        return 0
    linear = linear_enemy_costumes(toc, blob, changed)
    big_hunt = big_hunt_costumes(toc, blob, changed)
    stats = stat_sum(toc, blob, changed)

    def change(row):
        if row["CostumeId"] < PLAYER_ID_LIMIT or (row["BattleNpcId"], row["BattleNpcCostumeUuid"]) in big_hunt or row["Level"] <= 0:
            return None
        if row["CostumeId"] in linear:
            level = int(row["Level"] * factor + 0.5)
        elif stats(row["CostumeId"], row["Level"]) <= 0:
            return None  # its stats don't come from these curves
        else:
            level = _level_for(stats, row["CostumeId"], row["Level"], factor)
        return {"Level": min(level, INT32_MAX)}
    return _rewrite(toc, blob, changed, "m_battle_npc_costume", change)


def weakness_only(toc, blob, changed):
    """Half damage for the player's hits that aren't super-effective."""
    def change(row):
        if row["AttributeDamageCoefficientGroupId"] == PLAYER_DAMAGE_GROUP and row["DamageCoefficientPermil"] <= 1000:
            return {"DamageCoefficientPermil": row["DamageCoefficientPermil"] // 2}
        return None
    return _rewrite(toc, blob, changed, "m_battle_attribute_damage_coefficient_group", change)


def player_skill_details(toc, blob, changed):
    """The skill details the player's costumes, weapons and companions use."""
    rec = lambda t: records(toc, blob, changed, t)
    level_groups = {}
    for r in rec("m_skill_level_group"):
        level_groups.setdefault(r["SkillLevelGroupId"], set()).add(r["SkillDetailId"])
    skill = {r["SkillId"]: level_groups.get(r["SkillLevelGroupId"], set()) for r in rec("m_skill")}
    active = {}
    for r in rec("m_costume_active_skill_group"):
        active.setdefault(r["CostumeActiveSkillGroupId"], set()).add(r["CostumeActiveSkillId"])
    lotteries = {}
    for r in rec("m_costume_default_skill_group"):
        lotteries.setdefault(r["CostumeDefaultSkillGroupId"], set()).add(r["CostumeDefaultSkillLotteryGroupId"])
    lottery = {}
    for r in rec("m_costume_default_skill_lottery_group"):
        lottery.setdefault(r["CostumeDefaultSkillLotteryGroupId"], set()).add(r["SkillDetailId"])
    weapon_skills = {}
    for r in rec("m_weapon_skill_group"):
        weapon_skills.setdefault(r["WeaponSkillGroupId"], set()).add(r["SkillId"])
    out = set()
    for c in rec("m_costume"):
        if c["CostumeId"] >= PLAYER_ID_LIMIT:
            continue
        for s in active.get(c["CostumeActiveSkillGroupId"], ()):
            out |= skill.get(s, set())
        if c["CounterSkillDetailId"]:
            out.add(c["CounterSkillDetailId"])
        for g in lotteries.get(c["CostumeDefaultSkillGroupId"], ()):
            out |= lottery.get(g, set())
    for w in rec("m_weapon"):
        if w["WeaponId"] < PLAYER_ID_LIMIT:
            for s in weapon_skills.get(w["WeaponSkillGroupId"], ()):
                out |= skill.get(s, set())
    for r in rec("m_weapon_enhanced_skill"):
        out |= skill.get(r["SkillId"], set())
    for r in rec("m_companion"):
        out |= skill.get(r["SkillId"], set())
    return out


def slow_skills(toc, blob, changed):
    """The player's skill cooldowns ×1.5, rounded up."""
    player = player_skill_details(toc, blob, changed)

    def change(row):
        v = row["SkillCooltimeValue"]
        if row["SkillDetailId"] in player and v > 0:
            return {"SkillCooltimeValue": min(math.ceil(v * SLOW), INT32_MAX)}
        return None
    return _rewrite(toc, blob, changed, "m_skill_detail", change)


def active(settings):
    """Whether any challenge is on."""
    return settings.get("hardEnemies", 1) not in (0, 1) or bool(settings.get("weaknessOnly")) or bool(settings.get("slowSkills"))


def transform(source, output, settings):
    """Writes source's game data with the challenges in settings to output.
    False, writing nothing, when no challenge is on."""
    if not active(settings):
        return False
    import android_calendar as cal
    toc, blob = cal.read_master(source)
    changed = {}
    hard_enemies(toc, blob, changed, settings.get("hardEnemies", 1))
    if settings.get("weaknessOnly"):
        weakness_only(toc, blob, changed)
    if settings.get("slowSkills"):
        slow_skills(toc, blob, changed)
    cal.write_master(toc, blob, changed, Path(output))
    return True


# --- Every game data the game loads -----------------------------------------
#
# Content presets, calendar loops, restored snapshots and the gift text all
# reach the game through android_patcher.activate, which calls on_activate
# first; the calendar's next-loop and original-dates files, which the server
# loads by itself, go through finish. Each challenged file keeps its
# unchallenged copy (challenges.json: {"copies": {challenged sha: file}}), so
# game data built from the game's own file (the gift text, a restore, an
# export) starts unchallenged and is never challenged twice, and turning the
# challenges off gives back the game data exactly.

def _folder():
    import android_patcher
    return android_patcher.folder()


def _state_file():
    return _folder() / "challenges.json"


CHALLENGES = ("hardEnemies", "weaknessOnly", "slowSkills")
NONE_APPLIED = {"hardEnemies": 1, "weaknessOnly": False, "slowSkills": False}


def _state():
    import android_runtime as runtime
    state = runtime.read_json(_state_file())
    return state if isinstance(state, dict) else {}


def _copies():
    copies = _state().get("copies") or {}
    return {sha: _folder() / name for sha, name in copies.items() if (_folder() / name).is_file()}


def _save_copies(copies, applied=None):
    import android_runtime as runtime
    state = {"copies": {sha: path.name for sha, path in copies.items()}, "applied": applied or applied_challenges()}
    runtime.write_json(_state_file(), state)


def applied_challenges():
    """The challenges in the game data in use (as last applied), whatever
    mods.json says: a save that failed part-way leaves them apart."""
    applied = _state().get("applied")
    return {**NONE_APPLIED, **applied} if isinstance(applied, dict) else dict(NONE_APPLIED)


def wanted(settings):
    return {k: settings.get(k, NONE_APPLIED[k]) for k in CHALLENGES}


def _settings():
    import android_mods
    return android_mods.read_settings()


def _loaded_files():
    """The game data files the game may load: the master, and the calendar's
    next loop and original dates when they exist."""
    from web import config
    import android_calendar as cal
    return [p for p in (config.find_master_data_bin(), cal.next_file(), cal.view_file()) if p.is_file()]


def _prune(copies):
    import android_runtime as runtime
    keep = {runtime.fingerprint(p) for p in _loaded_files()}
    for sha in [sha for sha in copies if sha not in keep]:
        gone = copies.pop(sha)
        if gone not in copies.values():  # two challenged files can share one copy
            gone.unlink(missing_ok=True)
    for stray in _folder().glob("unchallenged-*.bin.e"):
        if stray not in copies.values():
            stray.unlink()
    _save_copies(copies)


def unchallenged(path):
    """path's game data without the challenges: its kept copy when path is a
    challenged file this module wrote, else path itself."""
    import android_runtime as runtime
    return _copies().get(runtime.fingerprint(path), Path(path))


def unchallenged_master():
    """The game's own game data without the challenges."""
    from web import config
    return unchallenged(config.find_master_data_bin())


def finish(path, settings=None):
    """Puts the challenges that are on into a game data file in place (it must
    be unchallenged; a file this module challenged is first put back)."""
    import shutil
    import android_runtime as runtime
    path = Path(path)
    copies = _copies()
    source = copies.get(runtime.fingerprint(path))
    if source:
        shutil.copyfile(source, path)
    settings = _settings() if settings is None else settings
    if active(settings):
        sha = runtime.fingerprint(path)
        keep = _folder() / f"unchallenged-{sha[:16]}.bin.e"
        shutil.copyfile(path, keep)
        pending = path.with_name(path.name + ".challenged")
        transform(keep, pending, settings)
        os.replace(pending, path)
        copies[runtime.fingerprint(path)] = keep
    _save_copies(copies)


def on_activate(candidate):
    """android_patcher.activate's first step: the candidate with the challenges."""
    settings = _settings()
    finish(candidate, settings)
    _save_copies(_copies(), wanted(settings))


def after_activate():
    """android_patcher.activate's last step: drops copies nothing uses."""
    _prune(_copies())


def reapply():
    """After the challenges change: the game data in use, the calendar's next
    loop and original dates built again from their unchallenged copies."""
    import shutil
    import android_calendar as cal
    import android_patcher as patcher
    import android_runtime as runtime
    from web import config
    active_label = runtime.read_json(patcher.folder() / "active.json")
    label = active_label.get("label") if isinstance(active_label, dict) else None
    candidate = patcher.folder() / "candidate.bin.e"
    try:
        shutil.copyfile(unchallenged_master(), candidate)
        patcher.activate(candidate, label or "Imported master data")
    finally:
        candidate.unlink(missing_ok=True)
    for extra in (cal.next_file(), cal.view_file()):
        if extra.is_file() and extra != config.find_master_data_bin():
            finish(extra)
    _prune(_copies())
