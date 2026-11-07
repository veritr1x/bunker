"""Battle units built from a deck's real pieces (ported from the research
prototype's sim_units.py: skills and passives compiled into simple ops).
Stats come from deckbuilder.power.character_stats, so they are the game's."""
import collections

from deckbuilder.sim.status import *   # tables + status decoders
from deckbuilder.sim.rules import P, ELEMN

COSTUME = idx("Costume", "CostumeId"); CASG = grp("CostumeActiveSkillGroup", "CostumeActiveSkillGroupId")
CABG = grp("CostumeAbilityGroup", "CostumeAbilityGroupId"); CALG = grp("CostumeAbilityLevelGroup", "CostumeAbilityLevelGroupId")
CAW = idx("CostumeAwaken", "CostumeId"); CAWE = grp("CostumeAwakenEffectGroup", "CostumeAwakenEffectGroupId")
CAWA = idx("CostumeAwakenAbility", "CostumeAwakenAbilityId"); CBASE = idx("CostumeBaseStatus", "CostumeBaseStatusId")
WEAPON = idx("Weapon", "WeaponId"); WSG = grp("WeaponSkillGroup", "WeaponSkillGroupId"); WAG = grp("WeaponAbilityGroup", "WeaponAbilityGroupId")
COMP = idx("Companion", "CompanionId")
DEFSKILL = grp("CostumeDefaultSkillGroup", "CostumeDefaultSkillGroupId"); DEFLOT = grp("CostumeDefaultSkillLotteryGroup", "CostumeDefaultSkillLotteryGroupId")
DMA_ALW = idx("SkillDamageMultiplyDetailAlways", "SkillDamageMultiplyDetailId")
ATTACK_TYPES = {"Attack", "AttackIgnoreVitality", "AttackVitality", "AttackClampHp", "AttackMainWeaponAttribute", "AttackFixedDamage"}


def abn_params(abn_id):
    """Executable parameters of one status."""
    a = ABN.get(abn_id)
    if not a: return None
    p = dict(type=a["SkillAbnormalTypeId"], ben=a["AbnormalPolarityType"] == 1)
    for g in ABN_BG.get(a["SkillAbnormalBehaviourGroupId"], []):
        b = ABN_B.get(g["SkillAbnormalBehaviourId"])
        if not b: continue
        t, aid = b["AbnormalBehaviourActionType"], b["SkillAbnormalBehaviourActionId"]
        if t == 2: p["stun"] = True
        elif t == 3 and aid in ABN_ADC:
            x = ABN_ADC[aid]; p.setdefault("attr", []).append((x["AttributeType"], "dealt" if x["CorrectionTargetDamageType"] == 1 else "taken", x["CorrectionValuePermil"] / 1000))
        elif t == 4 and aid in ABN_REC: p["regen"] = ABN_REC[aid]["Value"] / 1000
        elif t == 5 and aid in ABN_HITDOWN: p["hit_mult"] = ABN_HITDOWN[aid]["Value"] / 1000
        elif t == 7 and aid in ABN_DM:
            dm = ABN_DM[aid]; did = dm["DamageMultiplyAbnormalDetailId"]
            if did in ABN_DM_ALW:
                v = ABN_DM_ALW[did]["DamageMultiplyCoefficientValuePermil"] / 1000
                if dm["DamageMultiplyTargetType"] == 1: p["taken_mult"] = v
                else: p["dealt_add"] = v if v < 1 else v - 1
            elif did in ABN_DM_HIT:
                rows = HITVAL.get(ABN_DM_HIT[did]["SkillDamageMultiplyHitIndexValueGroupId"], [])
                if rows: p["chain"] = (min(r["TotalHitCountConditionLower"] for r in rows), max(r["DamageMultiplyCoefficientValuePermil"] for r in rows) / 1000)
        elif t == 8 and aid in ABN_RES:
            r = ABN_RES[aid]; p.setdefault("resist", []).append((r["AbnormalResistancePolarityType"], r["AbnormalResistanceSkillAbnormalTypeId"], r["BlockProbabilityPermil"] / 1000))
        elif t == 11: p["provoke"] = True
        elif t == 12: p["dauntless"] = True
        elif t == 13: p["defiance"] = True
    lt = ABN_LT.get(a["SkillAbnormalLifetimeId"]); life = ("frames", 1800)
    if lt:
        for g in ABN_LTG.get(lt["SkillAbnormalLifetimeBehaviourGroupId"], []):
            m, lid = g["AbnormalLifetimeMethodType"], g["SkillAbnormalLifetimeBehaviourId"]
            v = LT_TAB.get(m, {}).get(lid)
            if v is None: continue
            life = {1: ("frames", v), 2: ("turns", v), 4: ("ticks", v), 5: ("hits", v)}[m]
    p["life"] = life
    return p


def compile_skill(d, owner_elem, passive=False):
    """List of ops. For passive skills only battle-start / always behaviours are kept."""
    ops = []
    if not d: return ops
    mult = 1.0
    for g in SBG.get(d["SkillBehaviourGroupId"], []):
        b = SB.get(g["SkillBehaviourId"])
        if not b: continue
        mid = b["SkillBehaviourActivationMethodId"]
        if mid in AFFINITY_METHOD:
            if AFFINITY_METHOD[mid] != owner_elem: continue
            start = False
        else:
            am = ACTMETH.get(mid); mt = am["ActivationMethodType"] if am else 1
            if passive and mt not in (6, 3): continue
            if not passive and mt not in (1,): continue  # conditional in-skill multipliers etc. are skipped
            start = mt == 6
        bt = BTYPE.get(b["SkillBehaviourType"], str(b["SkillBehaviourType"]))
        aid = b["SkillBehaviourActionId"]; scope = SCOPE.get(b["SkillTargetScopeAssetCalculatorId"], "self_01")
        nh = max(1, g["SkillHitEndIndex"] - g["SkillHitStartIndex"] + 1); prob = b["HitRatioPermil"] / 1000
        if bt in ATTACK_TYPES:
            a = ACT.get(bt, {}).get(aid, {})
            em = a.get("MagnificationRate", 1000) / 1000 if bt == "AttackMainWeaponAttribute" and ELEM.get(a.get("AttributeType")) == owner_elem else 1.0
            ops.append(dict(op="dmg", scope=scope, power=a.get("SkillPower", 0) / 1000 * em, hits=nh, pierce=bt == "AttackIgnoreVitality"))
        elif bt == "Buff":
            s = BUFF.get(ACT["Buff"].get(aid, {}).get("SkillBuffId"))
            if s: ops.append(dict(op="buff", scope=scope, key=s["BuffKey"], value=(s["Power"] if s["BuffType"] == 1 else -s["Power"]) / 1000, frames=s["CooltimeFrameCount"], prob=prob))
        elif bt == "Abnormal":
            x = ACT["Abnormal"].get(aid); p = abn_params(x["SkillBehaviourAbnormalId"]) if x else None
            if p: ops.append(dict(op="status", scope=scope, st=p, prob=prob))
        elif bt == "Recovery":
            x = ACT["Recovery"].get(aid, {})
            ops.append(dict(op="revive" if scope.startswith("dead") else "heal", scope=scope, ratio=x.get("HpRatioRecoveryPointPermil", 0) / 1000))
        elif bt in ("AdvanceActiveSkillCooltime", "AdvanceActiveSkillCooltimeImmediate"):
            x = (ADV if bt == "AdvanceActiveSkillCooltime" else ADVI).get(aid, {})
            ops.append(dict(op="advance", scope=scope, which="cs" if x.get("ActiveSkillType") == 3 else "weapon", frac=x.get("AdvanceValue", 0) / 1000, start=start))
        elif bt == "ShortenActiveSkillCooltime":
            x = SHORT.get(aid, {}); ops.append(dict(op="cdmult", scope=scope, which="cs" if x.get("ActiveSkillType") == 3 else "weapon", mult=x.get("ShortenValuePermil", 1000) / 1000))
        elif bt == "RemoveAbnormal":
            r = REMOVE_ABN.get(aid, {}); ops.append(dict(op="cleanse" if r.get("TargetPolarityType") == 2 else "purge", scope=scope, kinds=r.get("RemoveKindCountUpper", 0) or 9))
        elif bt == "RemoveBuff":
            r = REMOVE_BUFF.get(aid, {}); ops.append(dict(op="removebuff", scope=scope, n=r.get("RemoveCount", 1), positive=r.get("BuffType") == 1))
        elif bt == "HpRatioDamage":
            pw = ACT["HpRatioDamage"].get(aid, {}).get("DamageRatioPermil", aid * 10) / 10
            ops.append(dict(op="hpcost", ratio=min(pw, 100) / 100))
        elif bt == "DamageMultiply":
            dm = ACT["DamageMultiply"].get(aid, {}).get("SkillDamageMultiplyDetailId")
            if dm in DMA_ALW: mult *= DMA_ALW[dm]["DamageMultiplyCoefficientValuePermil"] / 1000
    for o in ops:
        if o["op"] == "dmg": o["power"] *= mult
    return ops


def ability_list(cid):
    c = COSTUME[cid]; out = []
    for a in CABG.get(c["CostumeAbilityGroupId"], []):
        lv = max((r["AbilityLevel"] for r in CALG.get(a["CostumeAbilityLevelGroupId"], []) if r["CostumeLimitBreakCountLowerLimit"] <= 4), default=1)
        out.append((a["AbilityId"], lv))
    if cid in CAW:
        for e in CAWE[CAW[cid]["CostumeAwakenEffectGroupId"]]:
            if e["CostumeAwakenEffectType"] == 2 and e["CostumeAwakenEffectId"] in CAWA:
                x = CAWA[e["CostumeAwakenEffectId"]]; out.append((x["AbilityId"], x["AbilityLevel"]))
    return out


def passive_ops(abil, elem):
    """Battle-start ops and team stat passives from a list of (ability id, level)."""
    ops = []; team = collections.Counter(); mods = []
    for aid, lv in abil:
        d = ability_detail(aid, lv)
        if not d: continue
        for g in ABG.get(d["AbilityBehaviourGroupId"], []):
            b = ABH.get(g["AbilityBehaviourId"])
            if not b: continue
            if b["AbilityBehaviourType"] == 1:
                p = AB_PASSIVE.get(b["AbilityBehaviourActionId"])
                if p: ops += compile_skill(SD.get(p["SkillDetailId"]), elem, passive=True)
        f, _ = describe_ability(aid, lv)
        mods.append(ability_mods(aid, lv))
        for k, v in f.items():
            m = re.match(r"stat_(atk|hp|def|critrate|critdmg|agi)_(pct|flat)_team(?:_if(\w+))?$", k)
            if m: team[(m.group(1), m.group(2), m.group(3))] += v / 1000
    return ops, team, merge_mods(mods)


def default_attack(cid, elem):
    """Expected normal attack: (expected power per action, expected hits)."""
    gid = COSTUME[cid]["CostumeDefaultSkillGroupId"]; rows = []
    for g in DEFSKILL.get(gid, []):
        rows += DEFLOT.get(g["CostumeDefaultSkillLotteryGroupId"], [])
    tot = sum(r["ProbabilityWeight"] for r in rows) or 1; pw = hits = 0.0
    for r in rows:
        ops = compile_skill(SD.get(r["SkillDetailId"]), elem)
        p = sum(o["power"] * o["hits"] for o in ops if o["op"] == "dmg"); h = sum(o["hits"] for o in ops if o["op"] == "dmg") or 1
        pw += p * r["ProbabilityWeight"] / tot; hits += h * r["ProbabilityWeight"] / tot
    return (pw or 1.0), (hits or 1.0)


def merge_mods(mods):
    """Ability-text damage modifiers (deckbuilder/data/ability_mods.json) summed:
    low/high-HP and chain (pursuit) bonuses, full-HP bonus, self agility %."""
    m = dict(low_static=[], low_dyn=0.0, high_static=[], high_dyn=0.0, pursuit=[], full_hp=0.0, agi_pct=0.0)
    for x in mods:
        if not x:
            continue
        for k in ("low_static", "high_static", "pursuit"):
            m[k] += [tuple(v) for v in x.get(k, [])]
        for k in ("low_dyn", "high_dyn", "full_hp", "agi_pct"):
            m[k] += x.get(k, 0.0)
    return m


def gear_abilities(actor):
    """(ability id, level) of the gear beyond the costume and main weapon, as the client collects them
    (power.Actor, CollectAbilityStatus): both sub weapons' abilities, the active memoir set bonus, the debris.
    Their stat parts are already in the stats; build_unit adds their battle behaviour."""
    out = [(x.ability_id, x.level) for w in (actor.sub1, actor.sub2) if w for x in w["abilities"] if not x.locked]
    out += [(x.ability_id, x.level) for x in actor.series_bonus if not x.locked]
    if actor.thought:
        out.append((actor.thought.ability_id, actor.thought.level))
    return out


def build_unit(cid, elem, stats, main_weapon_id=None, companion_id=None, cs_level=15, extra_abilities=()):
    """A unit: the costume's character skill and passives, its main weapon's
    skills and abilities, its companion's skill, the sub weapons', memoir set's
    and debris' abilities (extra_abilities), and its real stats."""
    c = COSTUME[cid]
    g = sorted(CASG[c["CostumeActiveSkillGroupId"]], key=lambda x: x["CostumeLimitBreakCountLowerLimit"])[-1]
    csd = skill_detail_at(g["CostumeActiveSkillId"], cs_level)
    abil = ability_list(cid)
    pops, team, mods = passive_ops(abil, elem)
    wskills = []
    if main_weapon_id and main_weapon_id in WEAPON:
        w = WEAPON[main_weapon_id]
        for s in sorted(WSG.get(w["WeaponSkillGroupId"], []), key=lambda x: x["SlotNumber"]):
            d = skill_detail_at(s["SkillId"], 15)
            if d: wskills.append(dict(name=skill_name(d), cd=d["SkillCooltimeValue"] or 600, ops=compile_skill(d, elem), hits=d["SkillHitCount"], combo=d["IsComboCalculationTarget"]))
        wab = [(a["AbilityId"], max_ability_level(a["AbilityId"])) for a in WAG.get(w["WeaponAbilityGroupId"], [])]
        o2, t2, m2 = passive_ops(wab, elem); pops += o2; team += t2; mods = merge_mods([mods, m2])
    if extra_abilities:
        o3, t3, m3 = passive_ops(list(extra_abilities), elem); pops += o3; team += t3; mods = merge_mods([mods, m3])
    comp = None
    if companion_id and companion_id in COMP:
        d = skill_detail_at(COMP[companion_id]["SkillId"], 15)
        if d: comp = dict(cd=d["SkillCooltimeValue"] or 1110, ops=compile_skill(d, elem), atk=float(stats.get("comp_atk") or 800))
    na_pow, na_hits = default_attack(cid, elem)
    name = "%s %s" % ((N_COSTUME.get(cid) or {}).get("character_name", ""), nm(N_COSTUME, cid)) if N_COSTUME else "costume %d" % cid
    return with_stats(dict(cid=cid, name=name.strip() or "costume %d" % cid, elem=elem,
                cs=dict(name=skill_name(csd), gauge=csd["SkillCooltimeValue"] or 1000, timed=csd["SkillCooltimeBehaviourGroupId"] == 1,
                        ops=compile_skill(csd, elem), hits=csd["SkillHitCount"], combo=csd["IsComboCalculationTarget"]),
                # team stat passives (ability statuses) are already in stats: power
                # counts every status of the deck, party-wide ones included
                wskills=wskills, comp=comp, passives=pops, team=collections.Counter(), mods=mods, na=(na_pow, na_hits)), stats)


def with_stats(t, stats):
    """The unit template t with its stat fields from stats (power.character_stats): the part of a fighter that
    teammates' party-wide statuses change (deckbuilder.fighters)."""
    t = dict(t, hp=float(stats["hp"]), atk=float(stats["atk"]), df=float(stats["df"]),
             agi=float(stats["agi"]) * (1 + t["mods"]["agi_pct"]), crit=stats["crit"] / 1000, critdmg=stats["critdmg"] / 1000)
    if t.get("comp") is not None:
        t["comp"] = dict(t["comp"], atk=float(stats.get("comp_atk") or 800))
    return t


SLOTS = ("L", "M", "R")


def units_for(deck, tables):
    """(slot, unit template or None) for the deck's left, middle and right characters."""
    from deckbuilder import power
    _, actors, _ = power.actors_for(deck, tables)
    out = []
    for slot, a in zip(SLOTS, actors):
        if a is None or a.empty:
            out.append((slot, None))
            continue
        cid = a.costume["id"]
        elem = ELEMN.get(a.main["attr"]) if a.main else None
        elem = elem or tables.costume_element(cid) or "dark"
        stats = power.character_stats(a, tables)
        out.append((slot, build_unit(cid, elem, stats, a.main["id"] if a.main else None,
                                     a.companion["id"] if a.companion else None, cs_level=(a.costume["active_skill"][1] if a.costume.get("active_skill") else 15),
                                     extra_abilities=gear_abilities(a))))
    return out
