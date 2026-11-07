"""Master-data helpers for the Arena simulation (ported from the research
prototype's nr.py). Tables come from the Tables object deckbuilder.sim.use()
binds before this module is (re)loaded; module-level indexes are built then."""
import collections, json, os

from deckbuilder.sim import _bound

def T(name):
    return _bound().T(name)

def idx(name, key):
    return _bound().idx(name, key)

def grp(name, key):
    return _bound().grp(name, key)

ELEM = {1: "dark", 2: "fire", 3: "light", 5: "water", 6: "wind"}
STAT = {1: "agi", 2: "atk", 3: "critdmg", 4: "critrate", 5: "eva", 6: "hp", 7: "def"}

# ---------- numerical functions ----------
NF = idx("NumericalFunction", "NumericalFunctionId")
NFP = collections.defaultdict(dict)
for r in T("NumericalFunctionParameterGroup"):
    NFP[r["NumericalFunctionParameterGroupId"]][r["ParameterIndex"]] = r["ParameterValue"]

def nf(fid, x):
    f = NF.get(fid)
    if not f: return 0
    p = NFP[f["NumericalFunctionParameterGroupId"]]
    t = f["NumericalFunctionType"]
    if t == 1:   # linear: a*x + b
        return p.get(0, 0) * x + p.get(1, 0)
    if t == 4 or t == 7:   # LinearPermil / PartsMainOption (lunar-tear numericalfunc.go): p0*x/1000 + p1
        return p.get(0, 0) * x / 1000 + p.get(1, 0)
    if t == 6:   # PolynomialThirdPermil: (p0 x^3 + p1 x^2 + p2 x)/1000 + p3  (p3 is NOT divided, per lunar-tear)
        return (p.get(0, 0) * x**3 + p.get(1, 0) * x**2 + p.get(2, 0) * x) / 1000 + p.get(3, 0)
    raise ValueError(t)

# ---------- skills ----------
SKILL = idx("Skill", "SkillId")
SLG = grp("SkillLevelGroup", "SkillLevelGroupId")
SD = idx("SkillDetail", "SkillDetailId")
SBG = grp("SkillBehaviourGroup", "SkillBehaviourGroupId")
SB = idx("SkillBehaviour", "SkillBehaviourId")
def A(name): return idx("SkillBehaviourAction" + name, "SkillBehaviourActionId")
ACT = {n: A(n) for n in ["Attack","AttackCombo","AttackIgnoreVitality","AttackVitality","AttackMainWeaponAttribute","AttackClampHp","AttackFixedDamage","HpRatioDamage","Abnormal","Buff","Recovery","AttributeDamageCorrection","DamageCorrectionHpRatio","AdvanceActiveSkillCooltime","AdvanceActiveSkillCooltimeImmediate","DefaultSkillLottery","ShortenActiveSkillCooltime","RemoveBuff","DamageMultiply","RemoveAbnormal","RecoveryPointCorrection","ExtendBuffCooltime"]}
BTYPE = {2:"Attack",17:"AttackCombo",21:"AttackIgnoreVitality",25:"AttackVitality",27:"AttackMainWeaponAttribute",28:"AttackClampHp",24:"AttackFixedDamage",26:"HpRatioDamage",1:"Abnormal",3:"Buff",6:"Recovery",8:"AttributeDamageCorrection",11:"DamageCorrectionHpRatio",12:"AdvanceActiveSkillCooltime",13:"AdvanceActiveSkillCooltimeImmediate",15:"DefaultSkillLottery",18:"ShortenActiveSkillCooltime",19:"RemoveBuff",20:"DamageMultiply",22:"RemoveAbnormal",30:"RecoveryPointCorrection",31:"ExtendBuffCooltime"}
BUFF = idx("SkillBuff", "SkillBuffId")
ABN = idx("SkillAbnormal", "SkillAbnormalId")
ACTMETH = idx("SkillBehaviourActivationMethod", "SkillBehaviourActivationMethodId")
DMD_ALWAYS = idx("SkillDamageMultiplyDetailAlways", "SkillDamageMultiplyDetailId")
DMD_CRIT = idx("SkillDamageMultiplyDetailCritical", "SkillDamageMultiplyDetailId")
DMD_BUFF = idx("SkillDamageMultiplyDetailBuffAttached", "SkillDamageMultiplyDetailId")
DMD_ABN = idx("SkillDamageMultiplyDetailAbnormalAttached", "SkillDamageMultiplyDetailId")
ABN_NAME = {1:"DoT(1 hit)",2:"accuracy down",3:"regen",6:"action lock (stun-like)",7:"poison-like DoT",
            10:"dmg up",16:"dmg up",17:"dmg up (count)",18:"dmg up",19:"dmg up (timed)",
            11:"elem dmg up",12:"elem dmg up",13:"elem dmg up",14:"elem dmg up",15:"elem dmg up",
            24:"hate/evasion",30:"elem resist down",31:"elem resist down",32:"elem resist down",33:"elem resist down",34:"elem resist down",
            43:"abnormal/buff seal",44:"hit-effect",45:"hate"}

def skill_detail_at(skill_id, level):
    rows = SLG.get(SKILL[skill_id]["SkillLevelGroupId"], []) if skill_id in SKILL else []
    best = None
    for r in rows:
        if r["LevelLowerLimit"] <= level and (best is None or r["LevelLowerLimit"] > best["LevelLowerLimit"]):
            best = r
    return SD.get(best["SkillDetailId"]) if best else None

def max_skill_level(skill_id):
    rows = SLG.get(SKILL[skill_id]["SkillLevelGroupId"], []) if skill_id in SKILL else []
    return max((r["LevelLowerLimit"] for r in rows), default=0)

def describe_detail(d):
    """Flatten a skill detail into features. Powers are the raw SkillPower (percent of ATK per hit, as the game shows it)."""
    f = collections.Counter(); notes = []
    if not d: return f, notes
    f["cooltime"] = d["SkillCooltimeValue"]; f["hits"] = d["SkillHitCount"]
    for g in SBG.get(d["SkillBehaviourGroupId"], []):
        b = SB.get(g["SkillBehaviourId"])
        if not b: continue
        bt = BTYPE.get(b["SkillBehaviourType"], str(b["SkillBehaviourType"]))
        aid = b["SkillBehaviourActionId"]; a = ACT.get(bt, {}).get(aid, {})
        nh = max(1, g["SkillHitEndIndex"] - g["SkillHitStartIndex"] + 1)
        cond = ACTMETH.get(b["SkillBehaviourActivationMethodId"], {}).get("ActivationMethodType", 1)
        prob = b["HitRatioPermil"] / 1000
        tgt = g["TargetSelectorIndex"]
        if bt.startswith("Attack") or bt == "HpRatioDamage":
            p = a.get("SkillPower", 0)
            if bt == "AttackCombo": p = 0; notes.append("combo-scaled attack")
            f["power"] += p * nh * prob; f["attack_behaviours"] += 1
            if bt == "AttackIgnoreVitality": f["pierce_power"] += p * nh
            if bt == "AttackMainWeaponAttribute": f["power_elem_bonus"] += p * nh * (a.get("MagnificationRate", 1000) / 1000 - 1)
            if bt == "HpRatioDamage": notes.append("HP-ratio damage")
        elif bt == "Buff":
            s = BUFF.get(a.get("SkillBuffId"))
            if s:
                k = ("buff_" if s["BuffType"] == 1 else "debuff_") + s["BuffKey"]
                f[k] += s["Power"] * prob; f[k + "_frames"] = max(f[k + "_frames"], s["CooltimeFrameCount"])
        elif bt == "Abnormal":
            ab = ABN.get(a.get("SkillBehaviourAbnormalId"))
            if ab:
                f["abn_%d" % ab["SkillAbnormalTypeId"]] += prob
        elif bt == "Recovery":
            f["heal_hp_permil"] += a.get("HpRatioRecoveryPointPermil", 0) * prob; f["heal_power"] += a.get("SkillPower", 0) * prob
        elif bt in ("AdvanceActiveSkillCooltime", "AdvanceActiveSkillCooltimeImmediate"):
            f["cd_advance"] += a.get("AdvanceValue", 0) * prob
        elif bt == "ShortenActiveSkillCooltime":
            f["cd_shorten_permil"] += a.get("ShortenValuePermil", 0) * prob
        elif bt == "DamageMultiply":
            dm = a.get("SkillDamageMultiplyDetailId")
            v = (DMD_ALWAYS.get(dm) or DMD_CRIT.get(dm) or DMD_BUFF.get(dm) or {}).get("DamageMultiplyCoefficientValuePermil")
            if v: f["dmg_mult_permil"] += (v - 1000) * prob
            else: f["dmg_mult_conditional"] += 1
        elif bt == "AttributeDamageCorrection":
            f["attr_dmg_corr_permil"] += (a.get("CorrectionValuePermil", 1000) - 1000) * prob
        elif bt == "RemoveBuff": f["dispel"] += 1
        elif bt == "RemoveAbnormal": f["cleanse"] += 1
        elif bt == "DamageCorrectionHpRatio": f["hp_ratio_dmg_corr"] += 1
        elif bt == "DefaultSkillLottery": f["normal_attack_upgrade"] += 1
        else: f["other_" + bt] += 1
        if cond != 1: f["conditional_behaviours"] += 1
    return f, notes

# ---------- scopes ----------
SCOPE = {}
for r in T("AssetCalculator"):
    p = r["AssetPath"]
    if "target_selector_" in p: SCOPE[r["AssetCalculatorId"]] = p.split("target_selector_")[-1]
def scope_n(sid):
    """How many units a behaviour reaches in a 3v3 Arena (party scopes count 3, 'without self' 2)."""
    s = SCOPE.get(sid, "")
    if "without_self" in s: return 2
    if "all" in s: return 3
    return 1
def scope_side(sid):
    s = SCOPE.get(sid, "")
    if "enemy" in s: return "enemy"
    if s.startswith("dead"): return "revive"
    if s == "self_01": return "self"
    return "ally"
def scope_match_attr(sid):
    return SCOPE.get(sid, "").endswith("match_attribute")

# ---------- abilities ----------
ALG = grp("AbilityLevelGroup", "AbilityLevelGroupId")
AD = idx("AbilityDetail", "AbilityDetailId")
ABG = grp("AbilityBehaviourGroup", "AbilityBehaviourGroupId")
ABH = idx("AbilityBehaviour", "AbilityBehaviourId")
AB_STATUS = idx("AbilityBehaviourActionStatus", "AbilityBehaviourActionId")
AB_STATUSDOWN = idx("AbilityBehaviourActionStatusDown", "AbilityBehaviourActionId")
AB_PASSIVE = idx("AbilityBehaviourActionPassiveSkill", "AbilityBehaviourActionId")
AB_BLESS = idx("AbilityBehaviourActionBless", "AbilityBehaviourActionId")
ASTAT = idx("AbilityStatus", "AbilityStatusId")

def ability_detail(aid, level):
    rows = ALG.get(aid, [])
    best = None
    # LevelLowerLimit 0 is level 1, then 2,3,... are levels 2,3,...
    for r in rows:
        if r["LevelLowerLimit"] <= max(level, 0) and (best is None or r["LevelLowerLimit"] > best["LevelLowerLimit"]):
            best = r
    return AD.get(best["AbilityDetailId"]) if best else None

def max_ability_level(aid):
    return max((r["LevelLowerLimit"] for r in ALG.get(aid, [])), default=0) or 1

def describe_ability(aid, level=None):
    """Features of one ability. stat_<kind>_<calc>_<scope> = summed value. Passive skills are flattened with prefix p_."""
    if level is None: level = max_ability_level(aid)
    d = ability_detail(aid, level); f = collections.Counter(); tags = []
    if not d: return f, tags
    for g in ABG.get(d["AbilityBehaviourGroupId"], []):
        b = ABH.get(g["AbilityBehaviourId"])
        if not b: continue
        t = b["AbilityBehaviourType"]; a = b["AbilityBehaviourActionId"]
        if t == 3 or t == 5:
            st = (AB_STATUS if t == 3 else AB_STATUSDOWN).get(a)
            if not st: continue
            s = ASTAT.get(st["AbilityStatusId"], {})
            calc = "pct" if st["AbilityBehaviourStatusChangeType"] == 2 else "flat"
            scope = "team" if st["ApplyScopeType"] == 2 else "self"
            cond = "" if st["AttributeConditionType"] == 8 else "_if%s" % ELEM.get(st["AttributeConditionType"], st["AttributeConditionType"])
            sign = -1 if t == 5 else 1
            for k, nm in [("Attack","atk"),("Vitality","def"),("Hp","hp"),("Agility","agi"),("CriticalRatioPermil","critrate"),("CriticalAttackRatioPermil","critdmg"),("EvasionRatioPermil","eva")]:
                if s.get(k): f[f"stat_{nm}_{calc}_{scope}{cond}"] += sign * s[k]
        elif t == 1:
            p = AB_PASSIVE.get(a)
            if p:
                pf, notes = describe_detail(SD.get(p["SkillDetailId"]))
                for k, v in pf.items():
                    if k in ("cooltime", "hits"): continue
                    f["p_" + k] += v
                tags.append("passive:%d" % p["SkillDetailId"])
        elif t == 4:
            f["bless"] += 1
    return f, tags

# ---------- structured effects (used by score.py) ----------
ABN_BG = grp("SkillAbnormalBehaviourGroup", "SkillAbnormalBehaviourGroupId")
ABN_B = idx("SkillAbnormalBehaviour", "SkillAbnormalBehaviourId")
ABN_DMG = idx("SkillAbnormalBehaviourActionDamage", "SkillAbnormalBehaviourActionId")
ABN_REC = idx("SkillAbnormalBehaviourActionRecovery", "SkillAbnormalBehaviourActionId")
ABN_ADC = idx("SkillAbnormalBehaviourActionAttributeDamageCorrection", "SkillAbnormalBehaviourActionId")
ABN_DM = idx("SkillAbnormalBehaviourActionDamageMultiply", "SkillAbnormalBehaviourActionId")
ABN_DM_ALW = idx("SkillAbnormalBehaviourActionDamageMultiplyDetailAlways", "DamageMultiplyAbnormalDetailId")
ABN_DM_HIT = idx("SkillAbnormalDamageMultiplyDetailHitIndex", "DamageMultiplyAbnormalDetailId")
HITVAL = grp("SkillDamageMultiplyHitIndexValueGroup", "SkillDamageMultiplyHitIndexValueGroupId")
ABN_LT = idx("SkillAbnormalLifetime", "SkillAbnormalLifetimeId")
ABN_LTG = grp("SkillAbnormalLifetimeBehaviourGroup", "SkillAbnormalLifetimeBehaviourGroupId")
LT_FRAMES = {r["SkillAbnormalLifetimeBehaviourId"]: r["FrameCount"] for r in T("SkillAbnormalLifetimeBehaviourFrameCount")}
LT_COUNT = {}
for _t in ["TurnCount", "ActivateCount", "ReceiveDamageCount"]:
    for r in T("SkillAbnormalLifetimeBehaviour%sTable" % _t if False else "SkillAbnormalLifetimeBehaviour" + _t):
        LT_COUNT[r["SkillAbnormalLifetimeBehaviourId"]] = (_t, [v for k, v in r.items() if k != "SkillAbnormalLifetimeBehaviourId"][0])

def abnormal_info(abn_id):
    """kind, magnitude (permil or power), lifetime description."""
    a = ABN.get(abn_id)
    if not a: return None
    info = {"type": a["SkillAbnormalTypeId"], "neg": a["AbnormalPolarityType"] == 2, "dot": 0, "regen": 0,
            "dmg_mult": 0, "dmg_taken_cut": 0, "attr_corr": 0, "stun": 0, "hitdown": 0, "other": 0, "life": None}
    for g in ABN_BG.get(a["SkillAbnormalBehaviourGroupId"], []):
        b = ABN_B.get(g["SkillAbnormalBehaviourId"])
        if not b: continue
        t, aid = b["AbnormalBehaviourActionType"], b["SkillAbnormalBehaviourActionId"]
        if t == 1 and aid in ABN_DMG: info["dot"] += ABN_DMG[aid]["Power"]
        elif t == 2: info["stun"] = 1
        elif t == 3 and aid in ABN_ADC: info["attr_corr"] += ABN_ADC[aid]["CorrectionValuePermil"] - 1000
        elif t == 4 and aid in ABN_REC: info["regen"] += ABN_REC[aid]["Value"]
        elif t == 5: info["hitdown"] = 1
        elif t == 7 and aid in ABN_DM:
            dm = ABN_DM[aid]; did = dm["DamageMultiplyAbnormalDetailId"]
            if did in ABN_DM_ALW:
                v = ABN_DM_ALW[did]["DamageMultiplyCoefficientValuePermil"]
                if dm["DamageMultiplyTargetType"] == 1:   # damage TAKEN multiplier (text: "damage taken reduced 15%" = 850)
                    info["dmg_taken_cut"] += 1000 - v
                else:
                    info["dmg_mult"] += v - 1000 if v > 1000 else v
            elif did in ABN_DM_HIT:
                vals = [r["DamageMultiplyCoefficientValuePermil"] for r in HITVAL.get(ABN_DM_HIT[did]["SkillDamageMultiplyHitIndexValueGroupId"], [])]
                if vals: info["dmg_mult"] += (sum(vals) / len(vals)) - (1000 if sum(vals) / len(vals) > 1000 else 0)
        else: info["other"] += 1
    lt = ABN_LT.get(a["SkillAbnormalLifetimeId"])
    if lt:
        for g in ABN_LTG.get(lt["SkillAbnormalLifetimeBehaviourGroupId"], []):
            lid = g["SkillAbnormalLifetimeBehaviourId"]
            if lid in LT_FRAMES: info["life"] = ("frames", LT_FRAMES[lid])
            elif lid in LT_COUNT: info["life"] = LT_COUNT[lid]
    return info

def effects(d):
    """List of effect dicts for one skill detail: kind, side (enemy/ally/self/revive), n targets, magnitude, duration."""
    out = []
    if not d: return out
    for g in SBG.get(d["SkillBehaviourGroupId"], []):
        b = SB.get(g["SkillBehaviourId"])
        if not b: continue
        bt = BTYPE.get(b["SkillBehaviourType"], str(b["SkillBehaviourType"]))
        a = ACT.get(bt, {}).get(b["SkillBehaviourActionId"], {})
        nh = max(1, g["SkillHitEndIndex"] - g["SkillHitStartIndex"] + 1)
        sid = b["SkillTargetScopeAssetCalculatorId"]
        side = scope_side(sid); n = scope_n(sid)
        cond = ACTMETH.get(b["SkillBehaviourActivationMethodId"], {}).get("ActivationMethodType", 1) != 1
        prob = b["HitRatioPermil"] / 1000
        e = {"bt": bt, "side": side, "n": n, "prob": prob, "cond": cond, "mono": scope_match_attr(sid)}
        if bt in ("Attack", "AttackIgnoreVitality", "AttackVitality", "AttackClampHp", "AttackMainWeaponAttribute"):
            p = a.get("SkillPower", 0) * nh
            if bt == "AttackMainWeaponAttribute": e["elem"] = a.get("AttributeType"); e["elem_mult"] = a.get("MagnificationRate", 1000) / 1000
            e.update(kind="damage", power=p, pierce=(bt == "AttackIgnoreVitality"))
        elif bt == "AttackCombo":
            e.update(kind="damage", power=0, combo=True)
        elif bt == "AttackFixedDamage":
            e.update(kind="fixed_damage", power=0)
        elif bt == "HpRatioDamage":
            e.update(kind="hp_ratio_damage", power=0)
        elif bt == "Buff":
            s = BUFF.get(a.get("SkillBuffId"))
            if not s: continue
            e.update(kind=("buff_" if s["BuffType"] == 1 else "debuff_") + s["BuffKey"], value=s["Power"], frames=s["CooltimeFrameCount"])
        elif bt == "Abnormal":
            info = abnormal_info(a.get("SkillBehaviourAbnormalId"))
            if not info: continue
            e.update(kind="abn", abn=info)
        elif bt == "Recovery":
            e.update(kind="heal", value=a.get("HpRatioRecoveryPointPermil", 0), power=a.get("SkillPower", 0))
            if side == "revive": e["kind"] = "revive"
        elif bt in ("AdvanceActiveSkillCooltime", "AdvanceActiveSkillCooltimeImmediate"):
            e.update(kind="cd_advance", value=a.get("AdvanceValue", 0), adv_type=a.get("SkillCooltimeAdvanceType"))
        elif bt == "ShortenActiveSkillCooltime":
            e.update(kind="cd_shorten", value=a.get("ShortenValuePermil", 0))
        elif bt == "DamageMultiply":
            dm = a.get("SkillDamageMultiplyDetailId")
            v = (DMD_ALWAYS.get(dm) or {}).get("DamageMultiplyCoefficientValuePermil")
            if v is None:
                v2 = (DMD_CRIT.get(dm) or DMD_BUFF.get(dm) or {}).get("DamageMultiplyCoefficientValuePermil")
                e.update(kind="dmg_mult_cond", value=(v2 - 1000) if v2 else 0)
            else:
                e.update(kind="dmg_mult", value=v - 1000)
        elif bt == "AttributeDamageCorrection":
            e.update(kind="attr_corr", value=a.get("CorrectionValuePermil", 1000) - 1000, elem=a.get("AttributeType"))
        elif bt == "RemoveBuff": e.update(kind="dispel")
        elif bt == "RemoveAbnormal": e.update(kind="cleanse")
        elif bt == "DamageCorrectionHpRatio": e.update(kind="hp_ratio_corr")
        elif bt == "DefaultSkillLottery": e.update(kind="normal_attack_up", value=a.get("ValuePermil", 1000) - 1000)
        else: e.update(kind="other")
        out.append(e)
    return out

# ---------- English names, and the numbers read from ability texts ----------
def _names(kind):
    return _bound()._names(kind)
N_COSTUME = _names("costumes"); N_WEAPON = _names("weapons"); N_COMPANION = _names("companions")
N_THOUGHT = _names("thoughts"); N_CHAR = _names("characters"); N_PARTS = _names("parts_group_notes")
N_SKILL = _names("skills"); N_ABILITY = _names("abilities")
def nm(table, i): return (table.get(i) or {}).get("name", "")
def char_name(cid): return nm(N_CHAR, cid)
def skill_name(d):
    return nm(N_SKILL, d["SkillDetailId"]) if d else ""
def ability_name(aid, level=None):
    if level is None: level = max_ability_level(aid)
    d = ability_detail(aid, level)
    return nm(N_ABILITY, d["AbilityDetailId"]) if d else ""
_MODS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ability_mods.json")
ABILITY_MODS = {}
if os.path.exists(_MODS_PATH):
    with open(_MODS_PATH) as _f:
        ABILITY_MODS = {int(k): v for k, v in json.load(_f).items()}
def ability_mods(aid, level=None):
    """Damage modifiers an ability's description states (low/high HP, chain), keyed by AbilityDetailId."""
    if level is None: level = max_ability_level(aid)
    d = ability_detail(aid, level)
    return ABILITY_MODS.get(d["AbilityDetailId"]) if d else None
def series_name(sid):
    gs = [g["PartsGroupId"] for g in T("PartsGroup") if g["PartsSeriesId"] == sid]
    names = sorted({nm(N_PARTS, g) for g in gs if nm(N_PARTS, g)})
    return " / ".join(names)
