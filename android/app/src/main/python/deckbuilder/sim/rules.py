"""Rules of the Arena simulation: every tunable (PARAMS), elements, and the
swappable parts (chosen by name in PARAMS):
- ORDER: who acts next  -> battle.Battle.run_queue implements "queue", "turn" and "hybrid" (P["ACTION_MODEL"]); opening order in opening_order()
- COMBO: team combo counter and its damage coefficient (EntityMComboCalculationSetting)       -> Combo
- DAMAGE: damage formula                                                                         -> DAMAGE_FORMULAS
"""
import math
from deckbuilder.sim.data import T


# ---------------- order ----------------
def opening_order(units, attacker_manual, slot_order, interleave=False):
    """Start-of-battle skills (ready at t=0) resolve immediately, before any turn: the attacker's first when played by hand
    (calibrated on Fo5jCU4TIxc 2:31-2:34), else the defender's first (Auto; expert notes). Inside a side: slot order (R -> L -> M)."""
    side_rank = {"A": 0, "D": 1} if attacker_manual else {"D": 0, "A": 1}
    so = {s: i for i, s in enumerate(slot_order)}
    if not interleave:
        return sorted(units, key=lambda u: (side_rank[u.side], so[u.slot]))
    # alternate sides: first side's 1st, other side's 1st, first side's 2nd, ... (videos: ohOXve1qM9c 74.5-75.5 s, n3zcqj-457E F2)
    by = {s: sorted([u for u in units if u.side == s], key=lambda u: so[u.slot]) for s in ("A", "D")}
    order = sorted(("A", "D"), key=lambda s: side_rank[s]); out = []
    for i in range(3):
        for s in order:
            if i < len(by[s]): out.append(by[s][i])
    return out


# ---------------- combo ----------------

_COMBO = None


def _combo_table():
    """(rows sorted by lower limit, coefficient for every count up to the last lower limit): read once per master
    data (sim.use reloads this module). The coefficient for count n is the last row whose lower limit is <= n; past
    the last lower limit it stays the last row's."""
    global _COMBO
    if _COMBO is None:
        table = sorted((r["ComboCountLowerLimit"], r["DamageCoefficientPermil"] / 1000) for r in T("ComboCalculationSetting"))
        by_count = []
        for n in range((table[-1][0] + 1) if table else 0):
            c = 1.0
            for lo, v in table:
                if n >= lo: c = v
            by_count.append(c)
        _COMBO = (table, by_count)
    return _COMBO


class Combo:
    """Team combo counter. Coefficient table from EntityMComboCalculationSetting (master data): lower limit -> damage permil.
    The on-screen COMBO n uses the row with lower limit n-1 (checked on Fo5jCU4TIxc: COMBO 5 = 125%, COMBO 9 = 137%, COMBO 14 = 162%).
    Counting rule (not in data; parameters): every damaging action of a side adds 1 (normal attacks too if count_na);
    the counter resets when the other side acts (reset='other_side_acts') or never within the fight (reset='never')."""
    def __init__(self, enabled=True, count_na=True, reset="other_side_acts"):
        self.enabled = enabled; self.count_na = count_na; self.reset = reset
        self.table, self.by_count = _combo_table()
        self.count = {"A": 0, "D": 0}

    def coef(self, side):
        if not self.enabled: return 1.0
        n = max(0, self.count[side] - 1)
        by = self.by_count
        if not by: return 1.0
        return by[n] if n < len(by) else by[-1]


    def on_action(self, side, damaging, normal=False):
        if not self.enabled: return
        other = "D" if side == "A" else "A"
        if self.reset == "other_side_acts": self.count[other] = 0
        if damaging and (self.count_na or not normal): self.count[side] += 1


# ---------------- damage ----------------
def dmg_def_k(atk, power, mult, dfv, P, pierce=False):
    """ATK x power x multipliers x DEF_K/(DEF_K+DEF). The DEF term is a guess (not in data)."""
    return atk * power * mult * (1 if pierce else P["DEF_K"] / (P["DEF_K"] + max(dfv, 0)))


def dmg_subtract(atk, power, mult, dfv, P, pierce=False):
    """Alternative: (ATK - DEF/2) x power x multipliers, floored at 10% of ATK x power."""
    base = atk if pierce else max(atk - dfv / 2, atk * 0.1)
    return base * power * mult


def _takeoff(x):
    return 2 * (1 - 1 / (2 - math.exp(-x)))


def base_damage(atk, dfv):
    """The client's base damage, CalculatorMath.GetBaseDamage (0x324A8D0; constants read from the binary): ATK
    against DEF scales a hit by 0.5x to 2x, and the result eases toward 300,000 (Takeoff, FloorToInt)."""
    m = max(atk, dfv)
    r = (atk + m) / (dfv + m)
    s = 200 * atk * _takeoff(r / 400)
    return math.floor(300000 * _takeoff(s / 600000))


HIT_CAP = 1_500_000      # CalculateAttackSkillExec clamps a hit (0x34F6248)


def dmg_game(atk, power, mult, dfv, P, pierce=False):
    """The client's damage: base damage x skill power x the multipliers, at most HIT_CAP. Pierce ignores DEF."""
    return min(HIT_CAP, base_damage(atk, 1 if pierce else max(dfv, 1)) * power * mult)


DAMAGE_FORMULAS = {"def_k": dmg_def_k, "subtract": dmg_subtract, "game": dmg_game}


# ---------------- parameters (calibrated; see the notes beside each) ----------------
PARAMS = dict(
    FPS=30, STEP=6, DURATION_S=60,
    TIE_ORDER="defender_first",       # or "attacker_first"
    SLOT_ORDER=("R", "L", "M"),       # fire order inside a side
    AGI_RULE="interval",              # normal-attack interval = NA_BASE_FRAMES * 1000 / agility
    NA_BASE_FRAMES=90,                # 3 s between normal attacks at agility 1000
    FIRST_NA_FRAC=0.5,                # first normal attack after half an interval
    LOCK_CS=45, LOCK_WS=30, LOCK_NA=20,  # frames a unit is busy after an action (animation, not in data)
    # statuses measured in turns (stun, provoke, blind) count down at their holder's turns (Battle.count_turn)
    TICK_FRAMES=90,                   # regen/poison tick
    DEF_K=200000,                     # mitigation = DEF_K / (DEF_K + DEF)  (formula not in data). Calibrated on DFMQmpJxA-A 10:52.75:
                                      # NY Sarafa's Void Boon crit at 1% HP on a stall unit, 306,573 on screen; the model gives 305,866
                                      # (the research's 20,000 cut DEF-heavy targets ~3x too much: the "damage 3x too slow" gap)
    BLIGHTED=0.30, HASTE_MULT=0.70,   # Blighted Flowers 3-piece and 30% haste karma on every unit
    GAUGE_WS=250, GAUGE_COMP=400, GAUGE_NA={1: 50, 2: 100, 3: 150, 4: 175, 5: 200}, GAUGE_HIT_TAKEN=30,
    TARGET_RULE="smart",              # single-target pick when nobody provokes: smart (lowest HP share among enemies without Dauntless) | lowest_hp | slot | highest_atk
    CHAIN_WEIGHT=0.5,                 # chain-damage statuses apply at this expectation
    WEAPON_SHARE=0.5,                 # "stats of equipped X weapons" party passives: share of ATK/HP that is weapon
    COMP_TARGET="reliance",           # single-target Compromise goes to the enemy whose character skill grants the most beneficial statuses
                                      # (self Dauntless + HP cost first, as the expert notes do); "default" = same rule as other single-target skills
    TIMEOUT_RULE="hp_ratio",          # at time-out the side with more remaining HP share wins (ties: defender)
    TIMEOUT_MARGIN=0.01,              # ... by more than this share of HP; closer is a tie (two units at Dauntless' 1 HP)
    SEED=7,
    BOARD_ELEM_DMG=0.09,              # character board ability at max level (all characters)
    AGI_BUILD=0,                      # extra flat agility for agility-built units (memoir/karma/weapon agility; experts quote 2000-3000 total) - 0 = base agility only
    AGI_BUILD_FOR="fleetfoot",        # which units get AGI_BUILD: fleetfoot = costumes with a self agility passive (Fleetfoot etc.)
    # ---- sequential engine (default): one action on stage at a time, as the expert notes describe ("resolve on every animation/turn end") ----
    ENGINE="queue",                   # "queue" (sequential) or "parallel" (every unit acts on its own clock)
    ANIM_CS=36, ANIM_WS=30, ANIM_NA=20, ANIM_COMP=20,  # calibrated on Fo5jCU4TIxc 2:31-2:44: CS -> next CS ~1 s, two weapon skills in ~3 s, 13 s fight
    ATTACKER_FIRST_AT_START=True,     # calibrated on Fo5jCU4TIxc: the (manual) attacker's start-of-battle skills went first (R Akeha then M Yudil);
                                      # the experts' "defense first" applies to skills left on Auto after that
    START_WINDOW=15,                  # frames counted as "battle start" for ATTACKER_FIRST_AT_START
    HOLD_VS_DAUNTLESS=False,          # Lisy's rule test: a unit holds damaging skills while every enemy is under Dauntless (fires as it blinks out)
    HOLD_MARGIN=60,
    FOCUS_CID=0,                      # Lisy's rule test: attackers' single-target picks prefer this costume (0 = off)                   # frames before Dauntless ends at which held skills are released  # frames an action holds the stage (animation lengths: NOT in data, calibrate on videos)
    AGI_RULE_QUEUE="turn_order",      # normal attacks come in turns; inside a turn units act by agility (ties: defender first, then slot order)
    AGI_DOUBLE_RATIO=2.0,             # a unit with >= this x the slowest unit's agility gets a second normal attack per turn
    SKILLS_FIRST=True,                # ready skills resolve before the next normal attack
    READY_GRANULE=15,
    ACTION_MODEL="hybrid",            # "hybrid" (default): start-of-battle skills resolve at once (sim_rules.opening_order), then units act on
                                      #   their agility-ordered turns (skill if ready, else normal attack); "queue" and "turn" kept for comparison
    ATTACKER_MANUAL=True,             # hybrid: the attacker taps start skills by hand -> attacker first (Fo5jCU4TIxc); False = Auto -> defender first
    COMBO="table", COMBO_COUNT_NA=True, COMBO_RESET="other_side_acts",   # sim_rules.Combo (table from EntityMComboCalculationSetting); COMBO="off" disables
    DAMAGE="game",                    # the client's formula (dmg_game); "def_k" was the calibrated guess before it
    OPEN_DELAY=3.0,                   # calibrated (opening_check.py, 21 video openings): seconds of wave intro before the first start-of-battle skill (videos: ~2.5-3.5 s after the WAVE banner)
    OPEN_INTERLEAVE=False,            # opening: alternate attacker/defender start skills instead of one side's batch first
    OPEN_ANIM=1.2,                    # seconds per start-of-battle skill in the opening
    CD_RATE=2.0,                      # cooldown units per frame. Data: +1 per frame; at the game's 60 fps logic vs the 30 fps used for buff
                                      # durations that is 2 per 30-fps frame. Calibrated: Fo5jCU4TIxc Yudil fires both weapon skills within ~3 s.                   # sim_rules.DAMAGE_FORMULAS key             # "queue": ready skills interrupt after every action (FIFO, ties: defender first, R->L->M), normal attacks in agility turns
                                      # "turn":  every unit acts only on its own turn (agility order); on its turn: character skill if ready, else a ready weapon skill, else normal attack
    OPENING_NA=0,
    INTERLEAVE=True,                  # queue model: skills ready at a normal-attack boundary resolve as a batch, then the next normal attack (stops skills starving normal attacks)                     # queue model: number of normal attacks (agility order) that happen before any skill can resolve at battle start                 # skills that became ready within the same 0.5 s count as simultaneous (tie order applies)
)
P = PARAMS
PARAMS.setdefault("runs", 8)       # seeds per win-rate estimate

ADV = {("dark", "light"): 1.2, ("light", "dark"): 1.2, ("fire", "wind"): 1.2, ("wind", "water"): 1.2, ("water", "fire"): 1.2,
       ("fire", "water"): 0.8, ("water", "wind"): 0.8, ("wind", "fire"): 0.8}

ELEMN = ELEM_BY_ID = {1: "dark", 2: "fire", 3: "light", 5: "water", 6: "wind"}
ABN_SHORT = {43: "Compromised", 44: "Dauntless", 45: "Defiance", 18: "Indomitable", 24: "Provoke", 3: "Regen", 6: "Stun"}
