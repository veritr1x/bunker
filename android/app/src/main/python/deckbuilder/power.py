"""Force (deck power) exactly as NieR Re[in]carnation 3.7.1's client computes it.

Port of Dark.Calculator.CalculatorPower and the stat pipeline it calls
(CalculatorStatusOutgame, CalculatorStatus, Subsystem.Serval.*); each step
names its RVA. POWER.md has the derivation. Verified against the power the
game stored in saves (android/tools/test_deckbuilder_power.py).

Inputs are a save (real or synthesized by deckbuilder.model): the user's
rows of the tables the client reads, through model.Save.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

# ---------------------------------------------------------------- int helpers

def i32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def tdiv(a, b):
    """C# integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def permil(value, p):
    """PermilServal.multiplyPermil / PowerServal.calc*: (int)((long)a*b/1000)."""
    return i32(tdiv(value * p, 1000))


AGI, ATK, CRIT_ATK, CRIT_RATIO, EVA, HP, VIT = range(1, 8)
KINDS = (AGI, ATK, CRIT_ATK, CRIT_RATIO, EVA, HP, VIT)
ADD, MUL = 1, 2
# CalculatorStatus.cctor 0x2A17A10: kMin{Agility,Attack,CriticalAttack,CriticalRatio,EvasionRatio,Hp,Vitality}
K_MIN = {AGI: 0, ATK: 1, CRIT_ATK: 1000, CRIT_RATIO: 0, EVA: 0, HP: 1, VIT: 1}


def clamp_min(st, kinds=KINDS):
    out = dict(st)
    for k in kinds:
        out[k] = max(out[k], K_MIN[k])
    return out


def sv(**kw):
    s = dict.fromkeys(KINDS, 0)
    s.update(kw)
    return s


def closest_lower(rows, key, value):
    """MasterMemory FindClosest...(selectLower: true) within one group."""
    best = None
    for r in rows:
        if r[key] <= value and (best is None or r[key] > best[key]):
            best = r
    return best


# ---------------------------------------------------------------- Serval

def calc_parameter(ftype, p, x, y=0):
    """FunctionsServal.calcParameter 0x29218BC (jump table 0x5A4EAFC)."""
    g = lambda i: p[i] if i < len(p) else 0
    if ftype == 1:   # LINEAR 0x29221CC
        return i32(g(0) * x + g(1))
    if ftype == 2:   # MONOMIAL 0x2922128: p0 * (x-1)^p1 (exponent 1 when p1<2)
        b = x - 1
        r = b
        for _ in range(max(g(1), 1) - 1):
            r = i32(r * b)
        return i32(r * g(0))
    if ftype == 3:   # DUPLEX_LINEAR 0x2922248
        return i32(g(0) * x + g(1) * y)
    if ftype == 4:   # LINEAR_PERMIL 0x29222CC
        return i32(permil(g(0), x) + g(1))
    if ftype == 5:   # POLYNOMIAL_THIRD 0x2922368
        return i32(i32(i32(g(0) * x + g(1)) * x + g(2)) * x + g(3))
    if ftype == 6:   # POLYNOMIAL_THIRD_PERMIL 0x292241C
        x2 = i32(x * x)
        x3 = i32(x2 * x)
        return i32(permil(g(0), x3) + permil(g(1), x2) + permil(g(2), x) + g(3))
    if ftype == 7:   # PARTS_MAIN_OPTION 0x2922518
        a = min(max(x - 1, 0), 13) if x - 1 < 14 else 13
        b = max(x - 14, 0) if x - 14 < 2 else 1
        return i32(tdiv(g(0) * a, 1000) + g(1) * b)
    return 0


def growth_status(m, base, fid, level, threshold, coef):
    """CostumeServal/WeaponServal.calcStatusValue 0x2921EB8 / 0x29230D8."""
    f = m.nf(fid)
    if f is None:
        return 0
    raw = lambda lv: i32(calc_parameter(f[0], f[1], lv) + base)
    cur = raw(level)
    if level > threshold:
        t = raw(threshold)
        cur = i32(t + permil(cur - t, coef))
    return cur


# ---------------------------------------------------------------- abilities and skills

class Ability:
    """DataAbility (CalculatorAbility.CreateDataAbility 0x2801368)."""

    def __init__(self, m, ability_id, level, origin, force_unlocked=False):
        self.ability_id, self.level, self.origin = ability_id, level, origin
        self.locked = (level == 0) and not force_unlocked   # 0x28014A0: IsLocked = level == 0
        self.statuses = []      # DataAbilityStatus dicts
        self.passive_skills = []  # SkillDetail ids
        rows = m.grp("AbilityLevelGroup", "AbilityLevelGroupId").get(ability_id, [])
        row = closest_lower(rows, "LevelLowerLimit", level)
        self.valid = row is not None
        if not row:
            return
        detail = m.idx("AbilityDetail", "AbilityDetailId")[row["AbilityDetailId"]]
        beh = m.idx("AbilityBehaviour", "AbilityBehaviourId")
        for g in sorted(m.grp("AbilityBehaviourGroup", "AbilityBehaviourGroupId").get(detail["AbilityBehaviourGroupId"], []),
                        key=lambda r: r["AbilityBehaviourIndex"]):
            b = beh.get(g["AbilityBehaviourId"])
            if not b:
                continue
            t, aid = b["AbilityBehaviourType"], b["AbilityBehaviourActionId"]
            if t == 1:
                ps = m.idx("AbilityBehaviourActionPassiveSkill", "AbilityBehaviourActionId").get(aid)
                if ps:
                    self.passive_skills.append(ps["SkillDetailId"])
            elif t in (3, 5):
                tbl = "AbilityBehaviourActionStatus" if t == 3 else "AbilityBehaviourActionStatusDown"
                a = m.idx(tbl, "AbilityBehaviourActionId").get(aid)
                if not a:
                    continue
                st = m.idx("AbilityStatus", "AbilityStatusId").get(a["AbilityStatusId"], {})
                sign = 1 if t == 3 else -1   # StatusDown negates every value (0x280243C)
                vals = {AGI: st.get("Agility", 0), ATK: st.get("Attack", 0),
                        CRIT_ATK: st.get("CriticalAttackRatioPermil", 0), CRIT_RATIO: st.get("CriticalRatioPermil", 0),
                        EVA: st.get("EvasionRatioPermil", 0), HP: st.get("Hp", 0), VIT: st.get("Vitality", 0)}
                self.statuses.append({
                    "change": a["AbilityBehaviourStatusChangeType"],
                    "attr": a["AttributeConditionType"],
                    "scope": a["ApplyScopeType"],
                    "org": a["AbilityOrganizationConditionType"],
                    "value": {k: sign * v for k, v in vals.items()},
                    "src": (ability_id, level, origin),
                })


def skill_detail_id(m, skill_id, level):
    s = m.idx("Skill", "SkillId").get(skill_id)
    if not s:
        return None
    row = closest_lower(m.grp("SkillLevelGroup", "SkillLevelGroupId").get(s["SkillLevelGroupId"], []), "LevelLowerLimit", level)
    return row["SkillDetailId"] if row else None


def skill_power_def(m, detail_id):
    """CalculatorSkill.CreateDataSkillPower 0x2918C90."""
    d = m.idx("SkillDetail", "SkillDetailId").get(detail_id)
    if not d:
        return None
    refs = [r for r in m.grp("PowerReferenceStatusGroup", "PowerReferenceStatusGroupId").get(d["PowerReferenceStatusGroupId"], [])
            if 0 <= r["ReferenceStatusType"] <= 7]
    return {"base": d["SkillPowerBaseValue"], "ref_type": d["PowerCalculationReferenceStatusType"],
            "refs": [(r["ReferenceStatusType"], r["AttributeConditionType"], r["CoefficientValuePermil"]) for r in refs]}


# ---------------------------------------------------------------- attribute rules

def power_attr_match(attr, cond):
    """CalculatorPower.IsMatchAttributeCondition 0x2A11020 (jump table 0x5A6D620)."""
    return {1: attr == 1, 2: attr == 2, 3: attr == 3, 4: False, 5: attr == 5,
            6: attr == 6, 7: attr == 4, 8: True}.get(cond, False)


def status_attr_match(attr, cond):
    """CalculatorStatus.AbilityAttributeConditionTypeCheck 0x2A17648 (jump table 0x5A6D690)."""
    if cond == 8:
        return True
    return {1: 1, 2: 2, 3: 3, 4: 7, 5: 5, 6: 6}.get(attr) == cond


# ---------------------------------------------------------------- status diffs (CalculatorStatus)

def status_diff_lists(base, items):
    """Shared shape of the board / level bonus / awaken / lottery diffs (0x2A15CC4 etc.):
    ADD values summed; MULTIPLY permils summed, then multiplyPermil(base, sum) per stat."""
    add, mul = sv(), sv()
    for calc, vals in items:
        tgt = add if calc == ADD else mul if calc == MUL else None
        if tgt is None:
            continue
        for k in KINDS:
            tgt[k] += vals.get(k, 0)
    return {k: add[k] + permil(base[k], mul[k]) for k in KINDS}


def ability_diff(base, attr, org, statuses):
    """CalculatorStatus.GetAbilityStatusDiff 0x2A152C4."""
    sel = []
    for s in statuses:
        if s["org"] == 4:
            if org != 1 and s["change"] == ADD:
                continue
        elif s["org"] != org:
            continue
        if not status_attr_match(attr, s["attr"]):
            continue
        sel.append((s["change"], s["value"]))
    return status_diff_lists(base, sel)


def costume_status_settings(m, costume_id):
    c = m.idx("Costume", "CostumeId")[costume_id]
    base = m.idx("CostumeBaseStatus", "CostumeBaseStatusId")[c["CostumeBaseStatusId"]]
    calc = m.idx("CostumeStatusCalculation", "CostumeStatusCalculationId")[c["CostumeStatusCalculationId"]]
    keys = {AGI: ("Agility", "AgilityNumericalFunctionId"), ATK: ("Attack", "AttackNumericalFunctionId"),
            CRIT_ATK: ("CriticalAttackRatioPermil", "CriticalAttackRatioPermilNumericalFunctionId"),
            CRIT_RATIO: ("CriticalRatioPermil", "CriticalRatioPermilNumericalFunctionId"),
            EVA: ("EvasionRatioPermil", "EvasionRatioPermilNumericalFunctionId"),
            HP: ("Hp", "HpNumericalFunctionId"), VIT: ("Vitality", "VitalityNumericalFunctionId")}
    return {k: (base[b], calc[f]) for k, (b, f) in keys.items()}


def costume_base_status(m, costume_id, level):
    """GetCostumeBaseStatus 0x2A1518C -> CalcCostumeStatus 0x2A16AF0."""
    thr = m.config("COSTUME_STATUS_FUNCTION_THRESHOLD_LEVEL")
    coef = m.config("COSTUME_STATUS_FUNCTION_THRESHOLD_OVER_COEFFICIENT")
    return {k: growth_status(m, b, f, level, thr, coef) for k, (b, f) in costume_status_settings(m, costume_id).items()}


def weapon_base_status(m, weapon_id, level):
    """GetWeaponBaseStatus 0x2A16BF4 -> CalcWeaponStatus 0x2A171FC."""
    w = m.idx("Weapon", "WeaponId")[weapon_id]
    base = m.idx("WeaponBaseStatus", "WeaponBaseStatusId")[w["WeaponBaseStatusId"]]
    calc = m.idx("WeaponStatusCalculation", "WeaponStatusCalculationId")[w["WeaponStatusCalculationId"]]
    thr = m.config("WEAPON_STATUS_FUNCTION_THRESHOLD_LEVEL")
    coef = m.config("WEAPON_STATUS_FUNCTION_THRESHOLD_OVER_COEFFICIENT")
    return sv() | {
        ATK: growth_status(m, base["Attack"], calc["AttackNumericalFunctionId"], level, thr, coef),
        HP: growth_status(m, base["Hp"], calc["HpNumericalFunctionId"], level, thr, coef),
        VIT: growth_status(m, base["Vitality"], calc["VitalityNumericalFunctionId"], level, thr, coef)}


def companion_base_status(m, companion_id, level):
    """GetCompanionBaseStatus 0x2A17490 -> CompanionServal.calcStatusValue 0x2921AD8 (no growth curve)."""
    c = m.idx("Companion", "CompanionId")[companion_id]
    base = m.idx("CompanionBaseStatus", "CompanionBaseStatusId")[c["CompanionBaseStatusId"]]
    calc = m.idx("CompanionStatusCalculation", "CompanionStatusCalculationId")[c["CompanionStatusCalculationId"]]

    def one(b, fid):
        f = m.nf(fid)
        return 0 if f is None else i32(calc_parameter(f[0], f[1], level) + b)
    return sv() | {ATK: one(base["Attack"], calc["AttackNumericalFunctionId"]),
                   HP: one(base["Hp"], calc["HpNumericalFunctionId"]),
                   VIT: one(base["Vitality"], calc["VitalityNumericalFunctionId"])}


def build_weapon(m, s, uuid):
    if not uuid:
        return None
    uw = s.one("select * from user_weapons where user_id=? and user_weapon_uuid=?", uuid)
    if not uw:
        return None
    w = m.idx("Weapon", "WeaponId")[uw["weapon_id"]]
    awakened = s.one("select 1 from user_weapon_awakens where user_id=? and user_weapon_uuid=?", uuid) is not None
    skills, abilities = [], []
    sk_lv = {r["slot_number"]: r["level"] for r in s.q("select * from user_weapon_skills where user_id=? and user_weapon_uuid=?", uuid)}
    ab_lv = {r["slot_number"]: r["level"] for r in s.q("select * from user_weapon_abilities where user_id=? and user_weapon_uuid=?", uuid)}
    for r in sorted(m.grp("WeaponSkillGroup", "WeaponSkillGroupId").get(w["WeaponSkillGroupId"], []), key=lambda r: r["SlotNumber"]):
        lv = sk_lv.get(r["SlotNumber"], 0)
        d = skill_detail_id(m, r["SkillId"], lv)
        if d is not None:
            skills.append((r["SkillId"], lv, d))
    for r in sorted(m.grp("WeaponAbilityGroup", "WeaponAbilityGroupId").get(w["WeaponAbilityGroupId"], []), key=lambda r: r["SlotNumber"]):
        abilities.append(Ability(m, r["AbilityId"], ab_lv.get(r["SlotNumber"], 0), "weapon %d slot %d" % (uw["weapon_id"], r["SlotNumber"])))
    awaken_status = []
    wa = m.idx("WeaponAwaken", "WeaponId").get(uw["weapon_id"])
    if awakened and wa:
        for e in m.grp("WeaponAwakenEffectGroup", "WeaponAwakenEffectGroupId").get(wa["WeaponAwakenEffectGroupId"], []):
            if e["WeaponAwakenEffectType"] == 1:
                for st in m.grp("WeaponAwakenStatusUpGroup", "WeaponAwakenStatusUpGroupId").get(e["WeaponAwakenEffectId"], []):
                    awaken_status.append((st["StatusCalculationType"], {st["StatusKindType"]: st["EffectValue"]}))
            elif e["WeaponAwakenEffectType"] == 2:
                a = m.idx("WeaponAwakenAbility", "WeaponAwakenAbilityId").get(e["WeaponAwakenEffectId"])
                if a:
                    abilities.append(Ability(m, a["AbilityId"], a["AbilityLevel"], "weapon %d awaken" % uw["weapon_id"], force_unlocked=True))
    return {"uuid": uuid, "id": uw["weapon_id"], "level": uw["level"], "attr": w["AttributeType"], "type": w["WeaponType"],
            "skills": skills, "abilities": abilities, "awaken_status": awaken_status, "awakened": awakened}


def build_companion(m, s, uuid):
    if not uuid:
        return None
    uc = s.one("select * from user_companions where user_id=? and user_companion_uuid=?", uuid)
    if not uc:
        return None
    c = m.idx("Companion", "CompanionId")[uc["companion_id"]]
    lv = uc["level"]
    sl = closest_lower(m.T("CompanionSkillLevel"), "CompanionLevelLowerLimit", lv)
    al = closest_lower(m.T("CompanionAbilityLevel"), "CompanionLevelLowerLimit", lv)
    skill_lv = sl["SkillLevel"] if sl else 0
    ab_lv = al["AbilityLevel"] if al else 0
    d = skill_detail_id(m, c["SkillId"], skill_lv)
    ag = sorted(m.grp("CompanionAbilityGroup", "CompanionAbilityGroupId").get(c["CompanionAbilityGroupId"], []), key=lambda r: r["SlotNumber"])
    ability = Ability(m, ag[0]["AbilityId"], ab_lv, "companion %d" % uc["companion_id"]) if ag else None
    return {"uuid": uuid, "id": uc["companion_id"], "level": lv, "attr": c["AttributeType"],
            "skill": (c["SkillId"], skill_lv, d) if d is not None else None, "ability": ability}


def build_memory(m, s, uuid):
    up = s.one("select * from user_parts where user_id=? and user_parts_uuid=?", uuid)
    if not up:
        return None
    p = m.idx("Parts", "PartsId")[up["parts_id"]]
    series = m.idx("PartsGroup", "PartsGroupId")[p["PartsGroupId"]]["PartsSeriesId"]
    main = m.idx("PartsStatusMain", "PartsStatusMainId").get(up["parts_status_main_id"])
    subs = s.q("select * from user_parts_status_subs where user_id=? and user_parts_uuid=? order by status_index", uuid)
    return {"uuid": uuid, "id": up["parts_id"], "level": up["level"], "series": series, "main": main,
            "subs": [(r["status_kind_type"], r["status_calculation_type"], r["status_change_value"]) for r in subs]}


def memory_series_bonus(m, memories):
    """CalculatorMemory.CreateMemorySeriesBonusDataAbility(memories) 0x29A3780.
    One group per series; every bonus row is created, locked unless SetCount == pieces of that series."""
    out = []
    counts = collections.Counter(x["series"] for x in memories if x)
    for series, n in counts.items():
        if n < 2:
            continue
        gid = m.idx("PartsSeries", "PartsSeriesId")[series]["PartsSeriesBonusAbilityGroupId"]
        for r in m.grp("PartsSeriesBonusAbilityGroup", "PartsSeriesBonusAbilityGroupId").get(gid, []):
            a = Ability(m, r["AbilityId"], r["AbilityLevel"], "memoir series %d x%d" % (series, r["SetCount"]))
            a.locked = (n != r["SetCount"])
            out.append(a)
    return out


def build_costume(m, s, uuid):
    uc = s.one("select * from user_costumes where user_id=? and user_costume_uuid=?", uuid)
    c = m.idx("Costume", "CostumeId")[uc["costume_id"]]
    lb, aw = uc["limit_break_count"], uc["awaken_count"]
    # active skill: CostumeActiveSkillGroup closest LB lower limit, level from IUserCostumeActiveSkill
    asg = closest_lower(m.grp("CostumeActiveSkillGroup", "CostumeActiveSkillGroupId").get(c["CostumeActiveSkillGroupId"], []),
                        "CostumeLimitBreakCountLowerLimit", lb)
    sk = s.one("select * from user_costume_active_skills where user_id=? and user_costume_uuid=?", uuid)
    sk_lv = sk["level"] if sk else 1
    active = None
    if asg:
        d = skill_detail_id(m, asg["CostumeActiveSkillId"], sk_lv)
        if d is not None:
            active = (asg["CostumeActiveSkillId"], sk_lv, d)
    # abilities: CreateCostumeDataAbilityList 0x2878328
    abilities = []
    for r in sorted(m.grp("CostumeAbilityGroup", "CostumeAbilityGroupId").get(c["CostumeAbilityGroupId"], []), key=lambda r: r["SlotNumber"]):
        lvr = closest_lower(m.grp("CostumeAbilityLevelGroup", "CostumeAbilityLevelGroupId").get(r["CostumeAbilityLevelGroupId"], []),
                            "CostumeLimitBreakCountLowerLimit", lb)
        abilities.append(Ability(m, r["AbilityId"], lvr["AbilityLevel"] if lvr else 0, "costume slot %d" % r["SlotNumber"]))
    eff = m.grp("CostumeAwakenEffectGroup", "CostumeAwakenEffectGroupId")
    aw_row = m.idx("CostumeAwaken", "CostumeId").get(uc["costume_id"])
    if aw_row:
        for e in eff.get(aw_row["CostumeAwakenEffectGroupId"], []):
            if e["CostumeAwakenEffectType"] == 2 and e["AwakenStep"] <= aw:
                a = m.idx("CostumeAwakenAbility", "CostumeAwakenAbilityId").get(e["CostumeAwakenEffectId"])
                if a:
                    abilities.append(Ability(m, a["AbilityId"], a["AbilityLevel"], "costume awaken step %d" % e["AwakenStep"]))
    # karma (lottery effect): abilities and status ups, as the server derives IUserCostumeLotteryEffect*
    lot_abilities, lot_status = [], collections.defaultdict(lambda: sv())
    for r in s.q("select * from user_costume_lottery_effects where user_id=? and user_costume_uuid=? order by slot_number", uuid):
        if not r["odds_number"]:
            continue
        le = [x for x in m.T("CostumeLotteryEffect") if x["CostumeId"] == uc["costume_id"] and x["SlotNumber"] == r["slot_number"]]
        if not le:
            continue
        odds = [x for x in m.grp("CostumeLotteryEffectOddsGroup", "CostumeLotteryEffectOddsGroupId").get(le[0]["CostumeLotteryEffectOddsGroupId"], [])
                if x["OddsNumber"] == r["odds_number"]]
        if not odds:
            continue
        o = odds[0]
        if o["CostumeLotteryEffectType"] == 1:
            t = m.idx("CostumeLotteryEffectTargetAbility", "CostumeLotteryEffectTargetAbilityId").get(o["CostumeLotteryEffectTargetId"])
            if t:
                lot_abilities.append(Ability(m, t["AbilityId"], t["AbilityLevel"], "karma slot %d" % r["slot_number"]))
        elif o["CostumeLotteryEffectType"] == 2:
            for t in m.grp("CostumeLotteryEffectTargetStatusUp", "CostumeLotteryEffectTargetStatusUpId").get(o["CostumeLotteryEffectTargetId"], []):
                lot_status[t["StatusCalculationType"]][t["StatusKindType"]] += t["EffectValue"]
    return {"uuid": uuid, "id": uc["costume_id"], "character": c["CharacterId"], "level": uc["level"], "lb": lb, "awaken": aw,
            "skillful": c["SkillfulWeaponType"], "active_skill": active, "abilities": abilities,
            "lottery_abilities": lot_abilities, "lottery_status": [(k, dict(v)) for k, v in lot_status.items()]}


LEVEL_BONUS = {1: (AGI, ADD), 2: (AGI, MUL), 3: (ATK, ADD), 4: (ATK, MUL), 5: (CRIT_ATK, ADD), 6: (CRIT_RATIO, ADD),
               7: (HP, ADD), 8: (HP, MUL), 9: (VIT, ADD), 10: (VIT, MUL)}


def character_level_bonus(m, s, character_id):
    """IUserCharacterCostumeLevelBonus as the bunker server projects it (zz_bunker_costume.go)."""
    lv = {}
    for r in s.q("select costume_id, level from user_costumes where user_id=?"):
        lv[r["costume_id"]] = max(lv.get(r["costume_id"], 0), r["level"])
    sums = collections.defaultdict(lambda: sv())
    cost = m.idx("Costume", "CostumeId")
    for cid, level in lv.items():
        c = cost.get(cid)
        if not c or c["CharacterId"] != character_id:
            continue
        for b in m.grp("CostumeLevelBonus", "CostumeLevelBonusId").get(c["CostumeLevelBonusId"], []):
            k = LEVEL_BONUS.get(b["CostumeLevelBonusType"])
            if k and b["Level"] <= level:
                sums[k[1]][k[0]] += b["EffectValue"]
    return [(calc, dict(v)) for calc, v in sums.items()]


def stained_glass_status(m, s, character_id, skillful):
    """CalculatorDataStainedGlassStatus.CreateStainedGlassStatusList 0x2A0F218 (ADD rows only)."""
    owned = {r["important_item_id"] for r in s.q("select * from user_important_items where user_id=? and count>0")}
    total = sv()
    glass = m.idx("StainedGlass", "StainedGlassId")
    for it in m.T("ImportantItem"):
        if it["ImportantItemType"] != 5 or it["ImportantItemId"] not in owned:
            continue
        g = glass.get(it["ExternalReferenceId"])
        if not g:
            continue
        hit = False
        for t in m.grp("StainedGlassStatusUpTargetGroup", "StainedGlassStatusUpTargetGroupId").get(g["StainedGlassStatusUpTargetGroupId"], []):
            if (t["StatusUpTargetType"] == 1 and t["TargetValue"] == character_id) or \
               (t["StatusUpTargetType"] == 2 and t["TargetValue"] == skillful):
                hit = True
        if not hit:
            continue
        for r in m.grp("StainedGlassStatusUpGroup", "StainedGlassStatusUpGroupId").get(g["StainedGlassStatusUpGroupId"], []):
            if r["StatusCalculationType"] == ADD:
                total[r["StatusKindType"]] += r["EffectValue"]
    return [(ADD, total)]


def character_abilities(m, s, character_id):
    """CollectCharacterAbility 0x2A19240: rank abilities (CharacterLevelBonusAbilityGroup up to the
    character's rank = IUserCharacter.level) + character board abilities."""
    out = []
    ch = m.idx("Character", "CharacterId").get(character_id)
    uc = s.one("select * from user_characters where user_id=? and character_id=?", character_id)
    rank = uc["level"] if uc else 0
    if ch:
        for r in m.grp("CharacterLevelBonusAbilityGroup", "CharacterLevelBonusAbilityGroupId").get(ch["CharacterLevelBonusAbilityGroupId"], []):
            if r["ActivationCharacterLevel"] <= rank:
                out.append(Ability(m, r["AbilityId"], r["AbilityLevel"], "rank %d" % r["ActivationCharacterLevel"]))
    for r in s.q("select * from user_character_board_abilities where user_id=? and character_id=?", character_id):
        out.append(Ability(m, r["ability_id"], r["level"], "board"))
    return out


def board_status(s, character_id):
    out = []
    for r in s.q("select * from user_character_board_status_ups where user_id=? and character_id=?", character_id):
        out.append((r["status_calculation_type"], {HP: r["hp"], ATK: r["attack"], VIT: r["vitality"], AGI: r["agility"],
                                                   CRIT_RATIO: r["critical_ratio"], CRIT_ATK: r["critical_attack"]}))
    return out


def awaken_status(s, uuid):
    out = []
    for r in s.q("select * from user_costume_awaken_status_ups where user_id=? and user_costume_uuid=?", uuid):
        out.append((r["status_calculation_type"], {HP: r["hp"], ATK: r["attack"], VIT: r["vitality"], AGI: r["agility"],
                                                   CRIT_RATIO: r["critical_ratio"], CRIT_ATK: r["critical_attack"]}))
    return out


class Actor:
    def __init__(self, m, s, dc_uuid):
        dc = s.one("select * from user_deck_characters where user_id=? and user_deck_character_uuid=?", dc_uuid)
        self.uuid = dc_uuid
        self.stored = dc["power"] if dc else None
        self.empty = not dc or not dc["user_costume_uuid"] or not s.one(
            "select 1 x from user_costumes where user_id=? and user_costume_uuid=?", dc["user_costume_uuid"])  # a costume no longer owned
        if self.empty:
            return
        self.costume = build_costume(m, s, dc["user_costume_uuid"])
        self.main = build_weapon(m, s, dc["main_user_weapon_uuid"])
        subs = {r["ordinal"]: r["user_weapon_uuid"] for r in s.q("select * from user_deck_sub_weapons where user_id=? and user_deck_character_uuid=?", dc_uuid)}
        so = sorted(subs)
        self.sub1 = build_weapon(m, s, subs[so[0]]) if len(so) > 0 else None
        self.sub2 = build_weapon(m, s, subs[so[1]]) if len(so) > 1 else None
        self.companion = build_companion(m, s, dc["user_companion_uuid"])
        parts = {r["ordinal"]: r["user_parts_uuid"] for r in s.q("select * from user_deck_parts where user_id=? and user_deck_character_uuid=?", dc_uuid)}
        self.memories = [x for x in (build_memory(m, s, parts[k]) for k in sorted(parts)) if x]
        self.series_bonus = memory_series_bonus(m, self.memories)
        self.thought = None
        if dc["user_thought_uuid"]:
            ut = s.one("select * from user_thoughts where user_id=? and user_thought_uuid=?", dc["user_thought_uuid"])
            th = m.idx("Thought", "ThoughtId").get(ut["thought_id"]) if ut else None
            if th:
                self.thought = Ability(m, th["AbilityId"], th["AbilityLevel"], "debris %d" % th["ThoughtId"])
        cid = self.costume["character"]
        self.char_abilities = character_abilities(m, s, cid)
        self.board_status = board_status(s, cid)
        self.level_bonus = character_level_bonus(m, s, cid)
        self.awaken_status = awaken_status(s, self.costume["uuid"])
        self.stained = stained_glass_status(m, s, cid, self.costume["skillful"])
        # CollectAbilityStatus 0x2A19060
        st = []
        for a in self.costume["abilities"] + self.costume["lottery_abilities"]:
            if not a.locked:
                st += a.statuses
        for a in self.char_abilities:
            st += a.statuses
        if self.companion and self.companion["ability"]:
            st += self.companion["ability"].statuses   # no IsLocked check here
        for w in (self.main, self.sub1, self.sub2):
            if w:
                for a in w["abilities"]:
                    if not a.locked:
                        st += a.statuses
        for a in self.series_bonus:
            if not a.locked:
                st += a.statuses
        if self.thought:
            st += self.thought.statuses
        self.ability_status = st
        self.other_status = []

    # ------------------------------------------------------------ statuses
    def statuses(self):
        return self.ability_status + self.other_status

    def costume_status(self, m):
        """GetDeckActorCostumeStatus 0x2A11F08 -> CalculatorStatus.GetCostumeStatus 0x2A142A4 (no parts)."""
        c = self.costume
        base = costume_base_status(m, c["id"], c["level"])
        diffs = [
            ability_diff(base, 0, 1, self.statuses()),
            status_diff_lists(base, self.board_status),
            status_diff_lists(base, self.level_bonus),
            status_diff_lists(base, self.awaken_status),
            {k: sum(v.get(k, 0) for calc, v in self.stained if calc == ADD) for k in KINDS},
            status_diff_lists(base, c["lottery_status"]),
        ]
        out = {k: base[k] + sum(d[k] for d in diffs) for k in KINDS}
        out[HP] += self.proper_attr_hp(m)
        self.costume_breakdown = {"base": base, "diffs": diffs}
        return clamp_min(out)

    def proper_attr_hp(self, m):
        """GetCostumeProperAttributeHpAdditionalValue 0x2A0F064."""
        r = m.idx("CostumeProperAttributeHpBonus", "CostumeId").get(self.costume["id"])
        if not r:
            return 0
        v = 0
        if self.main and self.main["attr"] == r["CostumeProperAttributeType"]:
            v += r["MainWeaponHpAdditionalValue"]
        for w in (self.sub1, self.sub2):
            if w and w["attr"] == r["CostumeProperAttributeType"]:
                v += r["SubWeaponHpAdditionalValue"]
        return v

    def weapon_status(self, m, w, is_main):
        """GetDeckActorWeaponStatus 0x2A120AC -> GetWeaponStatus 0x2A14C58."""
        is_skillful = w["type"] == self.costume["skillful"]
        base = weapon_base_status(m, w["id"], w["level"])
        for k in (ATK, HP, VIT):
            if not is_skillful:
                base[k] = tdiv(base[k], 2)
            if not is_main:
                base[k] = tdiv(base[k], 2)
        ad = ability_diff(base, w["attr"], 2, self.statuses())
        awd = status_diff_lists(base, w["awaken_status"])
        out = sv() | {k: base[k] + ad[k] + awd[k] for k in (ATK, HP, VIT)}
        return clamp_min(out, (ATK, HP, VIT))

    def companion_status(self, m):
        """GetDeckActorCompanionStatus 0x2A1218C -> GetCompanionStatus 0x2A14F7C."""
        c = self.companion
        base = companion_base_status(m, c["id"], c["level"])
        ad = ability_diff(base, c["attr"], 3, self.statuses())
        out = sv() | {k: base[k] + ad[k] for k in (ATK, HP, VIT)}
        return clamp_min(out, (ATK, HP, VIT))

    # ------------------------------------------------------------ powers
    def base_power(self, m):
        """CalculateDeckActorBasePower 0x2A110B0."""
        K = m.power_consts()
        comp = collections.OrderedDict()
        cs = self.costume_status(m)
        comp["costume"] = (permil(cs[HP], K[2]), permil(cs[ATK], K[1]), permil(cs[VIT], K[3]))
        self.stats = {"costume": cs}
        for name, w, main in (("main_weapon", self.main, True), ("sub_weapon1", self.sub1, False), ("sub_weapon2", self.sub2, False)):
            if w:
                ws = self.weapon_status(m, w, main)
                self.stats[name] = ws
                comp[name] = (permil(ws[HP], K[5]), permil(ws[ATK], K[4]), permil(ws[VIT], K[6]))
        if self.companion:
            ps = self.companion_status(m)
            self.stats["companion"] = ps
            comp["companion"] = (permil(ps[HP], K[8]), permil(ps[ATK], K[7]), permil(ps[VIT], K[9]))
        if self.memories:
            comp["memoirs"] = parts_power(m, self.memories)
        self.components = comp
        self.hp_power = sum(v[0] for v in comp.values())
        self.atk_power = sum(v[1] for v in comp.values())
        self.vit_power = sum(v[2] for v in comp.values())


def parts_status_power(m, kind, value, calc):
    """CalculatePartsStatusPower 0x2A1225C -> PowerServal.calcStatusPower(14 args) 0x2922814."""
    K = m.power_consts()
    if calc == ADD:
        coef = {AGI: K[10], ATK: K[11], CRIT_ATK: K[12], CRIT_RATIO: K[13], EVA: K[14], HP: K[15], VIT: K[16]}
    elif calc == MUL:
        coef = {AGI: K[17], ATK: K[18], CRIT_ATK: K[19], CRIT_RATIO: K[20], EVA: K[21], HP: K[22], VIT: K[23]}
    else:
        return 0
    if value == 0 or coef[kind] == 0:
        return 0
    return permil(value, coef[kind])


def parts_power(m, memories):
    """CalculateDeckPartsStatusPower 0x2A11A74: main + each sub status, bucketed hp / attack(agi..eva) / vitality."""
    hp = atk = vit = 0
    for x in memories:
        items = []
        mn = x["main"]
        if mn:
            f = m.nf(mn["StatusNumericalFunctionId"])
            val = i32(calc_parameter(f[0], f[1], x["level"]) + mn["StatusChangeInitialValue"]) if f else mn["StatusChangeInitialValue"]
            items.append((mn["StatusKindType"], mn["StatusCalculationType"], val))
        items += x["subs"]
        for kind, calc, val in items:
            if kind not in KINDS:
                continue
            p = parts_status_power(m, kind, val, calc)
            if kind == HP:
                hp += p
            elif kind == VIT:
                vit += p
            else:
                atk += p
    return hp, atk, vit


# ---------------------------------------------------------------- skill power

def skill_power(m, owner, actors, detail_id):
    """CalculateSkillPower(actor, deck, skill) 0x2A12410 + CalculateStatusReferenceValue 0x2A1267C."""
    d = skill_power_def(m, detail_id)
    if not d:
        return 0
    total = 0
    if d["ref_type"] in (1, 2):
        for kind, cond, coef in d["refs"]:
            for a in actors:
                if a.empty:
                    continue
                if d["ref_type"] == 1 and a.uuid != owner.uuid:
                    continue
                attr = a.main["attr"] if a.main else 0
                if not power_attr_match(attr, cond):
                    continue
                if 1 <= kind <= 5:
                    v = a.atk_power
                elif kind == 6:
                    v = a.hp_power
                elif kind == 7:
                    v = a.vit_power
                else:
                    v = 0
                total += permil(v, coef)
    return i32(d["base"] + total)


def ability_power(m, owner, actors, ab):
    """CalculateAbilityPower 0x2A124EC: 0 when locked, else the passive skills' power."""
    if ab is None or ab.locked:
        return 0
    return sum(skill_power(m, owner, actors, sd) for sd in ab.passive_skills)


def actor_skill_power(m, a, actors):
    """CalculateSkillPower(userId, actor, deck) 0x2A11308."""
    parts = collections.OrderedDict()
    c = a.costume
    parts["costume_skill"] = skill_power(m, a, actors, c["active_skill"][2]) if c["active_skill"] else 0
    parts["main_weapon_skills"] = sum(skill_power(m, a, actors, sk[2]) for sk in a.main["skills"]) if a.main else 0
    parts["companion_skill"] = skill_power(m, a, actors, a.companion["skill"][2]) if a.companion and a.companion["skill"] else 0
    parts["costume_abilities"] = sum(ability_power(m, a, actors, x) for x in c["abilities"] + c["lottery_abilities"])
    parts["weapon_abilities"] = sum(ability_power(m, a, actors, x) for w in (a.main, a.sub1, a.sub2) if w for x in w["abilities"])
    parts["companion_ability"] = ability_power(m, a, actors, a.companion["ability"]) if a.companion else 0
    parts["memoir_series"] = sum(ability_power(m, a, actors, x) for x in a.series_bonus)
    parts["debris"] = ability_power(m, a, actors, a.thought)
    parts["character"] = sum(ability_power(m, a, actors, x) for x in a.char_abilities)
    return parts


# ---------------------------------------------------------------- deck

# ---------------------------------------------------------------- public API

@dataclass
class CharacterPower:
    costume_id: int
    character_id: int
    total: int
    hp: int
    atk: int
    vit: int
    skill: int
    parts: dict = field(default_factory=dict)          # component -> (hp, atk, vit)
    skill_parts: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)          # component -> {kind: value}
    stored: int | None = None


@dataclass
class PowerResult:
    total: int
    characters: list
    stored: int | None = None


def constants(tables) -> dict:
    """The PowerCalculationConstantValue types the client reads (1-23)."""
    return {k: v for k, v in tables.power_consts().items() if 1 <= k <= 23}


def actors_for(deck, tables):
    """The deck's actors with base power computed (CalculateDeckPower 0x2A102EC)."""
    m, s = tables, deck.save
    d = s.one("select * from user_decks where user_id=? and deck_type=? and user_deck_number=?", deck.deck_type, deck.deck_number)
    if not d:
        raise KeyError("no deck %s/%s" % (deck.deck_type, deck.deck_number))
    # One entry per slot, left to right; None for a slot with no character.
    actors = [Actor(m, s, d["user_deck_character_uuid%02d" % i]) if d["user_deck_character_uuid%02d" % i] else None
              for i in (1, 2, 3)]
    live = [a for a in actors if a is not None and not a.empty]
    # ApplyDeckAbilityStatusList 0x2A1039C: every PARTY-scope status of another actor reaches this one
    for dst in live:
        dst.other_status = [st for src in live if src is not dst for st in src.ability_status if st["scope"] == 2]
    for a in live:
        a.base_power(m)
    return d, actors, live


def deck_power(deck, tables) -> PowerResult:
    m = tables
    d, actors, live = actors_for(deck, tables)
    chars, total = [], 0
    for a in actors:
        if a is None or a.empty:
            chars.append(CharacterPower(0, 0, 0, 0, 0, 0, 0, stored=a.stored if a else None))
            continue
        sp = actor_skill_power(m, a, live)
        p = i32(a.hp_power + a.atk_power + a.vit_power + sum(sp.values()))
        total = i32(total + p)
        chars.append(CharacterPower(
            costume_id=a.costume["id"], character_id=a.costume["character"], total=p,
            hp=a.hp_power, atk=a.atk_power, vit=a.vit_power, skill=sum(sp.values()),
            parts=dict(a.components), skill_parts=dict(sp), stats=dict(a.stats), stored=a.stored))
    return PowerResult(total=total, characters=chars, stored=d["power"])


def character_stats(actor, tables) -> dict:
    """A character's battle stats from the same pipeline as Force: the costume's
    status (abilities, board, awakening, karma, level bonus) plus its weapons'
    and companion's HP/ATK/DEF, plus its memoirs' main and sub stats (flat
    values added, percentages of the costume's). Ratios in permil.
    Keys: hp, atk, df, agi, crit, critdmg, eva, comp_atk."""
    if actor is None or actor.empty:
        return None
    s = actor.stats
    c = s["costume"]
    tot = {k: c[k] for k in KINDS}
    for name in ("main_weapon", "sub_weapon1", "sub_weapon2", "companion"):
        if name in s:
            for k in (ATK, HP, VIT):
                tot[k] += s[name][k]
    for x in actor.memories:
        items = list(x["subs"])
        mn = x["main"]
        if mn:
            f = tables.nf(mn["StatusNumericalFunctionId"])
            val = i32(calc_parameter(f[0], f[1], x["level"]) + mn["StatusChangeInitialValue"]) if f else mn["StatusChangeInitialValue"]
            items.append((mn["StatusKindType"], mn["StatusCalculationType"], val))
        for kind, calc, val in items:
            if kind not in KINDS:
                continue
            tot[kind] += val if calc == ADD else permil(c[kind], val)
    return {"hp": tot[HP], "atk": tot[ATK], "df": tot[VIT], "agi": tot[AGI], "crit": tot[CRIT_RATIO],
            "critdmg": tot[CRIT_ATK], "eva": tot[EVA], "comp_atk": s["companion"][ATK] if "companion" in s else 0}


def deck_power_from_save(db_path, user_id, deck_type, deck_number, tables) -> PowerResult:
    from deckbuilder import model
    return deck_power(model.Deck.from_save(db_path, user_id, deck_type, deck_number, tables), tables)
