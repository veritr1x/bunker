"""Status-effect decoding (ported from the research prototype's status_lib.py): abnormal details, lifetimes, activation conditions, owners."""
import collections, json, re
from deckbuilder.sim.data import *

# ---------- enums decoded from data + text (see glossary notes) ----------
# AbnormalBehaviourActionType -> which parameter table holds the action (verified by id coverage)
ABN_ACTION = {1: "Damage(DoT)", 2: "TurnRestriction", 3: "AttributeDamageCorrection", 4: "Recovery(regen)",
              5: "HitRatioDown", 7: "DamageMultiply", 8: "AbnormalResistance", 9: "BuffResistance",
              10: "OverrideHitEffect", 11: "ModifyHateValue", 12: "(no table: survive at 1 HP)",
              13: "OverrideEvasionValue"}
# ActivationMethodType (behaviours) — inferred from the texts they carry
ACT_METHOD = {1: "on skill use", 3: "always (passive)", 5: "on trigger (HP threshold / when acting)",
              6: "at battle/wave start", 7: "inside the skill's damage (conditional multiplier)"}
COND_TYPE = {1: "none", 2: "wave number", 5: "when acting", 6: "HP ratio", 7: "activation upper count",
             8: "in skill flow", 10: "main-weapon element", 11: "proficient main weapon", 12: "passive check"}
# activation method ids N*1000+1 (not in the method table) = "when own affinity is X";
# N follows the in-game element order fire, water, wind, light, dark (verified on 31032/33029/32035/35036 texts)
AFFINITY_METHOD = {1001: "fire", 2001: "water", 3001: "wind", 4001: "light", 5001: "dark"}
HPTH = {r["SkillBehaviourActivationConditionId"]: r for r in T("SkillBehaviourActivationConditionHpRatio")}
CG = grp("SkillBehaviourActivationConditionGroup", "SkillBehaviourActivationConditionGroupId")
ATTRC = {r["SkillBehaviourActivationConditionId"]: r["SkillBehaviourActivationConditionAttributeType"] for r in T("SkillBehaviourActivationConditionAttribute")}
ABN_RES = idx("SkillAbnormalBehaviourActionAbnormalResistance", "SkillAbnormalBehaviourActionId")
ABN_HITDOWN = idx("SkillAbnormalBehaviourActionHitRatioDown", "SkillAbnormalBehaviourActionId")
ABN_EVA = idx("SkillAbnormalBehaviourActionOverrideEvasionValue", "SkillAbnormalBehaviourActionId")
ABN_HATE = idx("SkillAbnormalBehaviourActionModifyHateValue", "SkillAbnormalBehaviourActionId")
REMOVE_ABN = idx("SkillBehaviourActionRemoveAbnormal", "SkillBehaviourActionId")
REMOVE_BUFF = idx("SkillBehaviourActionRemoveBuff", "SkillBehaviourActionId")
ADV = ACT["AdvanceActiveSkillCooltime"]; ADVI = ACT["AdvanceActiveSkillCooltimeImmediate"]
SHORT = ACT["ShortenActiveSkillCooltime"]
CLAMP = idx("SkillBehaviourActionAttackClampHp", "SkillBehaviourActionId")

# Names of abnormal types, from the words that co-occur with each type in the skill/ability texts
ABN_TYPE_NAME = {
    1: "Poison", 2: "Blind", 3: "Regen (continually recover HP)", 6: "Stun", 7: "Burn",
    10: "Invulnerable (damage x0 for N hits)", 11: "Element damage up (fire)", 12: "Element damage up (water)",
    13: "Element damage up (wind)", 14: "Element damage up (light)", 15: "Element damage up (dark)",
    16: "Chain damage up (timed)", 17: "Chain damage up (4+ chains, passive)", 18: "Indomitable (damage taken reduced for N hits)",
    19: "Chain damage up (timed, self)", 20: "Status immunity (all ailments)", 21: "Status immunity (single ailment)",
    22: "Status immunity (single ailment)", 23: "Element damage correction (boss)", 24: "Provoke",
    30: "Fire damage taken up (Crush)", 31: "Water damage taken up (Crush)", 32: "Wind damage taken up (Crush)",
    33: "Light damage taken up (Crush)", 34: "Dark damage taken up (Crush)", 40: "Special (boss/hit effect)",
    41: "Status immunity (single ailment)", 42: "Status immunity (single ailment)", 43: "Compromised",
    44: "Dauntless (HP cannot fall below 1)", 45: "Defiance (evade normal attacks)", 62: "Special", 63: "Special"}


# Lifetime behaviour ids overlap between the four tables; AbnormalLifetimeMethodType picks the table
# (1 frames, 2 turns, 4 activations, 5 hits received). Verified on texts: stun lifetime 5 -> "1 turn",
# blind lifetime 8 -> "3 turns", Compromised lifetime 4 -> "60 seconds", damage-cut lifetime 6 -> "3 times".
LT_TAB = {1: {r["SkillAbnormalLifetimeBehaviourId"]: r["FrameCount"] for r in T("SkillAbnormalLifetimeBehaviourFrameCount")},
          2: {r["SkillAbnormalLifetimeBehaviourId"]: r["TurnCount"] for r in T("SkillAbnormalLifetimeBehaviourTurnCount")},
          4: {r["SkillAbnormalLifetimeBehaviourId"]: r["ActivateCount"] for r in T("SkillAbnormalLifetimeBehaviourActivateCount")},
          5: {r["SkillAbnormalLifetimeBehaviourId"]: r["ReceiveDamageCount"] for r in T("SkillAbnormalLifetimeBehaviourReceiveDamageCount")}}


def life_desc(abn):
    lt = ABN_LT.get(abn["SkillAbnormalLifetimeId"])
    if not lt: return "?"
    out = []
    for g in ABN_LTG.get(lt["SkillAbnormalLifetimeBehaviourGroupId"], []):
        m, lid = g["AbnormalLifetimeMethodType"], g["SkillAbnormalLifetimeBehaviourId"]
        v = LT_TAB.get(m, {}).get(lid)
        if v is None: out.append("method %d id %d" % (m, lid)); continue
        if m == 1: out.append("%gs" % (v / 30) if v < 54000 else "whole battle")
        elif m == 2: out.append("%d turn(s)" % v if v < 999 else "whole battle")
        elif m == 4: out.append("%d activation(s)" % v)
        elif m == 5: out.append("%d hit(s) received" % v)
    return " or ".join(out) or "?"


def abn_detail(abn_id):
    """Plain description of one abnormal instance (type name, polarity, parameters, lifetime)."""
    a = ABN.get(abn_id)
    if not a: return None
    parts = []
    for g in ABN_BG.get(a["SkillAbnormalBehaviourGroupId"], []):
        b = ABN_B.get(g["SkillAbnormalBehaviourId"])
        if not b: continue
        t, aid = b["AbnormalBehaviourActionType"], b["SkillAbnormalBehaviourActionId"]
        if t == 1 and aid in ABN_DMG: parts.append("DoT power %d (type %d)" % (ABN_DMG[aid]["Power"], ABN_DMG[aid]["AbnormalBehaviourDamageType"]))
        elif t == 2: parts.append("cannot act (turn restriction)")
        elif t == 3 and aid in ABN_ADC:
            x = ABN_ADC[aid]; parts.append("%s dmg %s x%.2f" % (ELEM.get(x["AttributeType"], x["AttributeType"]), "dealt" if x["CorrectionTargetDamageType"] == 1 else "taken", x["CorrectionValuePermil"] / 1000))
        elif t == 4 and aid in ABN_REC: parts.append("regen %.1f%% HP/turn" % (ABN_REC[aid]["Value"] / 10))
        elif t == 5 and aid in ABN_HITDOWN: parts.append("hit rate x%.2f" % (ABN_HITDOWN[aid]["Value"] / 1000))
        elif t == 7 and aid in ABN_DM:
            dm = ABN_DM[aid]; did = dm["DamageMultiplyAbnormalDetailId"]
            if did in ABN_DM_ALW:
                v = ABN_DM_ALW[did]["DamageMultiplyCoefficientValuePermil"]
                parts.append(("damage taken x%.2f" if dm["DamageMultiplyTargetType"] == 1 else "damage dealt +%.0f%%") % ((v / 1000) if dm["DamageMultiplyTargetType"] == 1 else v / 10))
            elif did in ABN_DM_HIT:
                vals = [r["DamageMultiplyCoefficientValuePermil"] for r in HITVAL.get(ABN_DM_HIT[did]["SkillDamageMultiplyHitIndexValueGroupId"], [])]
                rows = HITVAL.get(ABN_DM_HIT[did]["SkillDamageMultiplyHitIndexValueGroupId"], [])
                lo = min((r["TotalHitCountConditionLower"] for r in rows), default=0)
                parts.append("chain dmg x%.2f on %d+ chains" % (max(vals) / 1000 if vals else 0, lo))
            else: parts.append("damage multiplier (detail %d)" % did)
        elif t == 8 and aid in ABN_RES:
            r = ABN_RES[aid]
            if r["AbnormalResistancePolarityType"] == 1: parts.append("blocks every new BENEFICIAL status (%.0f%%)" % (r["BlockProbabilityPermil"] / 10))
            elif r["AbnormalResistanceSkillAbnormalTypeId"] == 0: parts.append("blocks every new status ailment (%.0f%%)" % (r["BlockProbabilityPermil"] / 10))
            else: parts.append("blocks %s (%.0f%%)" % (ABN_TYPE_NAME.get(r["AbnormalResistanceSkillAbnormalTypeId"], r["AbnormalResistanceSkillAbnormalTypeId"]), r["BlockProbabilityPermil"] / 10))
        elif t == 9: parts.append("blocks stat buffs/debuffs")
        elif t == 10: parts.append("override hit effect")
        elif t == 11 and aid in ABN_HATE: parts.append("hate +%d (draws attacks)" % ABN_HATE[aid]["ModifyValue"])
        elif t == 12: parts.append("HP cannot fall below 1")
        elif t == 13 and aid in ABN_EVA: parts.append("evasion overridden to %.0f%%" % (ABN_EVA[aid]["CorrectionValuePermil"] / 10))
        else: parts.append("action %d" % t)
    return dict(abnormal_id=abn_id, type=a["SkillAbnormalTypeId"], name=ABN_TYPE_NAME.get(a["SkillAbnormalTypeId"], "type %d" % a["SkillAbnormalTypeId"]),
                polarity="beneficial" if a["AbnormalPolarityType"] == 1 else "ailment", effect="; ".join(parts), duration=life_desc(a))


def when_desc(b):
    mid = b["SkillBehaviourActivationMethodId"]
    if mid in AFFINITY_METHOD: return "if own affinity is " + AFFINITY_METHOD[mid]
    am = ACTMETH.get(mid)
    if not am: return "method %d" % mid
    s = ACT_METHOD.get(am["ActivationMethodType"], "method type %d" % am["ActivationMethodType"])
    cs = []
    for c in sorted(CG.get(am["SkillBehaviourActivationConditionGroupId"], []), key=lambda c: c["ConditionCheckOrder"]):
        ct, cid = c["SkillBehaviourActivationConditionType"], c["SkillBehaviourActivationConditionId"]
        if ct == 1 or ct == 12: continue
        if ct == 6 and cid in HPTH:
            h = HPTH[cid]; cs.append("HP %s %d%%" % ({1: ">", 2: ">=", 3: "<", 4: "<"}.get(h["SkillBehaviourActivationConditionHpRatioThresholdType"], "?"), h["ThresholdRatioPermil"] / 10))
        elif ct == 7: cs.append("once")
        elif ct == 10: cs.append("main weapon %s" % ELEM.get(ATTRC.get(cid), cid))
        elif ct == 11: cs.append("proficient weapon")
        else: cs.append(COND_TYPE.get(ct, "cond %d" % ct))
    return s + (" [" + ", ".join(cs) + "]" if cs else "")


def skill_statuses(d, owner_kind):
    """Status-relevant effects of one skill detail: list of dicts."""
    out = []
    if not d: return out
    for g in SBG.get(d["SkillBehaviourGroupId"], []):
        b = SB.get(g["SkillBehaviourId"])
        if not b: continue
        bt = BTYPE.get(b["SkillBehaviourType"], str(b["SkillBehaviourType"]))
        aid = b["SkillBehaviourActionId"]
        tgt = SCOPE.get(b["SkillTargetScopeAssetCalculatorId"], str(b["SkillTargetScopeAssetCalculatorId"]))
        rec = dict(target=tgt, when=when_desc(b), chance="%.0f%%" % (b["HitRatioPermil"] / 10))
        if bt == "Abnormal":
            x = ACT["Abnormal"].get(aid); det = abn_detail(x["SkillBehaviourAbnormalId"]) if x else None
            if det: rec.update(kind="status", **det)
            else: continue
        elif bt == "Buff":
            s = BUFF.get(ACT["Buff"].get(aid, {}).get("SkillBuffId"))
            if not s: continue
            rec.update(kind="buff" if s["BuffType"] == 1 else "debuff", name="%s %s%d%%" % (s["BuffKey"], "+" if s["BuffType"] == 1 else "-", s["Power"] / 10), duration="%gs" % (s["CooltimeFrameCount"] / 30))
        elif bt == "RemoveAbnormal":
            r = REMOVE_ABN.get(aid, {})
            n = r.get("RemoveKindCountUpper", 0)
            rec.update(kind="cleanse" if r.get("TargetPolarityType") == 2 else "purge-status",
                       name="remove %s %s" % ("all" if n == 0 else n, "ailment kind(s)" if r.get("TargetPolarityType") == 2 else "beneficial status kind(s)"))
        elif bt == "RemoveBuff":
            r = REMOVE_BUFF.get(aid, {})
            rec.update(kind="purge-buff" if r.get("BuffType") == 1 else "cleanse-debuff", name="remove %d %s" % (r.get("RemoveCount", 0), "stat buff(s)" if r.get("BuffType") == 1 else "stat debuff(s)"))
        elif bt in ("AdvanceActiveSkillCooltime", "AdvanceActiveSkillCooltimeImmediate"):
            x = (ADV if bt == "AdvanceActiveSkillCooltime" else ADVI).get(aid, {})
            rec.update(kind="cooldown advance", name="%s skill cooldown -%d%%%s" % ({2: "weapon", 3: "costume"}.get(x.get("ActiveSkillType"), "?"), x.get("AdvanceValue", 0) / 10, " (immediate)" if bt.endswith("Immediate") else ""))
        elif bt == "ShortenActiveSkillCooltime":
            x = SHORT.get(aid, {}); v = x.get("ShortenValuePermil", 1000)
            rec.update(kind="cooldown multiplier", name="%s skill cooldown x%.2f" % ({2: "weapon", 3: "costume"}.get(x.get("ActiveSkillType"), "?"), v / 1000))
        elif bt == "Recovery" and tgt.startswith("dead"):
            x = ACT["Recovery"].get(aid, {}); rec.update(kind="revive", name="revive at %d%% HP" % (x.get("HpRatioRecoveryPointPermil", 0) / 10))
        elif bt == "14":
            continue  # pairs with the revive recovery (marks the dead-ally target)
        elif bt == "HpRatioDamage":
            rec.update(kind="self HP cost", name="lose HP (ratio)")
        elif bt == "AttackClampHp":
            x = CLAMP.get(aid, {}); rec.update(kind="damage (non-lethal)", name="damage cannot drop target below %d%% HP" % (x.get("ClampThresholdHpRatioPermil", 0) / 10))
        else:
            continue
        rec["source_kind"] = owner_kind
        out.append(rec)
    return out
