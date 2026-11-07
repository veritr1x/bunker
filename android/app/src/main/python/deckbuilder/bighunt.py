"""Subjugation (the game's Big Hunt) bosses, from the master data.

Five bosses, one per element, each with five difficulties. A fight is three waves
(phases) of 3600 game frames (60 s); the player's three Subjugation decks fight one
phase each. The boss does not fall: the score is the damage dealt. Skill hits fill a
knock-down gauge (an amount per hit by its damage, for the skill's hit count); at the
phase's thresholds the boss is knocked down for some frames and takes DamageRatio‰
damage.

The boss is a battle NPC: battle group → wave → battle → NPC deck → its one
character → an enemy costume (1181 B 2 D 01: boss B, difficulty D) at a level, and
an NPC weapon.
"""
from __future__ import annotations

import uuid as uuid_mod
from typing import NamedTuple

GAME_FPS = 60
BOSS_HP = 1e15              # the boss does not fall in Subjugation
ELEMENTS = {1: "dark", 2: "fire", 3: "light", 5: "water", 6: "wind"}
# The game's own names (its Subjugation texts: "Manifestation: Fiery Cursed God", ...).
NAMES = {"fire": "Fiery Cursed God", "water": "Soggy Cursed God", "wind": "Windy Cursed God",
         "light": "Bright Cursed God", "dark": "Bleak Cursed God"}


class Threshold(NamedTuple):
    at: int             # cumulative gauge
    down: bool          # a knock-down (else a stagger the score ignores)
    frames: int         # game frames the boss stays down
    ratio: float        # damage multiplier while down (DamageRatio‰)


class Phase(NamedTuple):
    order: int
    frames: int                 # game frames (60 fps)
    thresholds: list            # [Threshold]
    gauge_rows: dict            # hit count (1..5) → [(damage lower limit, gauge lower limit, ‰)], ascending

    def gauge(self, hits: int, damage: float) -> float:
        rows = self.gauge_rows.get(max(1, min(hits, max(self.gauge_rows))), [])
        lo, base, permil = 0, 0, 0
        for d, g, p in rows:
            if damage >= d:
                lo, base, permil = d, g, p
        return base + (damage - lo) * permil / 1000


class Fight(NamedTuple):
    boss_id: int
    difficulty: int
    costume_id: int
    level: int
    weapon: tuple | None        # (weapon id, level, limit breaks)
    phases: list                # [Phase] in order


class Boss(NamedTuple):
    id: int
    element: str
    name: str
    fights: dict                # difficulty → Fight


_cache: dict = {}


def bosses(tables) -> list[Boss]:
    key = id(tables)
    if key not in _cache:
        _cache.clear()
        _cache[key] = _read(tables)
    return _cache[key]


def boss(tables, boss_id: int) -> Boss | None:
    return next((b for b in bosses(tables) if b.id == boss_id), None)


def _read(tables) -> list[Boss]:
    T = tables.T
    battle = {r["BattleId"]: r for r in T("Battle")}
    waves = {}
    for r in T("BattleGroup"):
        waves.setdefault(r["BattleGroupId"], []).append(r)
    decks = {(r["BattleNpcId"], r["DeckType"], r["BattleNpcDeckNumber"]): r for r in T("BattleNpcDeck")}
    chars = {(r["BattleNpcId"], r["BattleNpcDeckCharacterUuid"]): r for r in T("BattleNpcDeckCharacter")}
    costumes = {(r["BattleNpcId"], r["BattleNpcCostumeUuid"]): r for r in T("BattleNpcCostume")}
    weapons = {(r["BattleNpcId"], r["BattleNpcWeaponUuid"]): r for r in T("BattleNpcWeapon")}
    phase_rows = {}
    for r in T("BattleBigHuntPhaseGroup"):
        phase_rows.setdefault(r["BattleBigHuntPhaseGroupId"], []).append(r)
    thresholds = {}
    for r in T("BattleBigHuntDamageThresholdGroup"):
        thresholds.setdefault(r["KnockDownDamageThresholdGroupId"], []).append(r)
    gauges = {}
    for r in T("BattleBigHuntKnockDownGaugeValueConfigGroup"):
        gauges.setdefault(r["KnockDownGaugeValueConfigGroupId"], {}).setdefault(r["ActiveSkillHitCount"], []).append(
            (r["DamageValueLowerLimit"], r["GaugeValueLowerLimit"], r["CorrectionRatioPermil"]))
    for g in gauges.values():
        for rows in g.values():
            rows.sort()

    fights: dict[int, dict[int, Fight]] = {}
    for bh in T("BattleBigHunt"):
        first = min(waves.get(bh["BattleGroupId"], []), key=lambda w: w["WaveNumber"], default=None)
        if first is None:
            continue
        b = battle[first["BattleId"]]
        d = decks.get((b["BattleNpcId"], b["DeckType"], b["BattleNpcDeckNumber"]))
        ch = d and chars.get((b["BattleNpcId"], d["BattleNpcDeckCharacterUuid01"]))
        co = ch and costumes.get((b["BattleNpcId"], ch["BattleNpcCostumeUuid"]))
        if not co:
            continue
        digits = str(co["CostumeId"])
        if len(digits) != 9 or not digits.startswith("1181"):
            continue
        boss_id, difficulty = int(digits[4]), int(digits[6])
        w = weapons.get((b["BattleNpcId"], ch["MainBattleNpcWeaponUuid"]))
        phases = []
        for p in sorted(phase_rows.get(bh["BattleBigHuntPhaseGroupId"], []), key=lambda r: r["BattleBigHuntPhaseGroupOrder"]):
            th = [Threshold(t["KnockDownCumulativeDamageThreshold"], t["IsKnockDown"], t["KnockDownDurationFrameCount"],
                            t["DamageRatio"] / 1000)
                  for t in sorted(thresholds.get(p["KnockDownDamageThresholdGroupId"], []), key=lambda t: t["KnockDownDamageThresholdGroupOrder"])]
            phases.append(Phase(p["BattleBigHuntPhaseGroupOrder"], p["NormalPhaseFrameCount"], th,
                                gauges.get(bh["KnockDownGaugeValueConfigGroupId"], {})))
        fights.setdefault(boss_id, {})[difficulty] = Fight(
            boss_id, difficulty, co["CostumeId"], co["Level"],
            (w["WeaponId"], w["Level"], w["LimitBreakCount"]) if w else None, phases)

    out = []
    for r in sorted(T("BigHuntBoss"), key=lambda r: r["BigHuntBossId"]):
        e = ELEMENTS.get(r["AttributeType"], "dark")
        out.append(Boss(r["BigHuntBossId"], e, NAMES.get(e, f"Boss {r['BigHuntBossId']}"), fights.get(r["BigHuntBossId"], {})))
    return out


def boss_unit(fight: Fight, schema, tables) -> dict:
    """The boss as a simulator unit template: its costume at its level and its weapon, put in a one-character
    deck of an empty save with schema's tables (any save, e.g. the stage), its HP made endless."""
    from deckbuilder import model
    from deckbuilder.sim import units
    import sqlite3
    con = sqlite3.connect(":memory:", check_same_thread=False)
    for t in model.TABLES:
        sql = schema.table_sql(t)
        if sql:
            con.execute(sql)
    uid = schema.uid
    save = model.Save(con, uid)
    template = lambda t: schema.one(f"select * from {t} where user_id=? limit 1")
    c = dict(template("user_costumes"))
    c.update(user_costume_uuid=str(uuid_mod.uuid4()), costume_id=fight.costume_id, level=fight.level,
             limit_break_count=0, awaken_count=0)
    model._insert(con, "user_costumes", [c])
    weapon = None
    if fight.weapon:
        w = dict(template("user_weapons"))
        w.update(user_weapon_uuid=str(uuid_mod.uuid4()), weapon_id=fight.weapon[0], level=fight.weapon[1],
                 limit_break_count=fight.weapon[2])
        model._insert(con, "user_weapons", [w])
        weapon = model.PieceRef("weapon", w["user_weapon_uuid"], "save")
    spec = model.CharacterSpec(model.PieceRef("costume", c["user_costume_uuid"], "save"), weapon, [], None, [], None)
    model._write_deck(con, uid, [spec], 2, 1)
    t = dict(units.units_for(model.Deck(save, 2, 1), tables))["L"]
    t["hp"] = BOSS_HP
    return t
