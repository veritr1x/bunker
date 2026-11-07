# Deck power ("Force") in NieR Re[in]carnation 3.7.1, as the client computes it

Source: `libil2cpp.so` of the 3.7.1 client, read through the IL2CPP dump (`dump.cs`) and
disassembly. Every RVA below is a method or jump table in that binary. The Python port is
`power.py` in this folder. `check.txt` holds the results against every save.

Notation:

- `permil(a, p)` is `(int)((long)a * p / 1000)`, truncated toward zero. The binary does it as
  `smull` + `smulh` by `0x20C49BA5E353F7CF` + shift 7 + sign fix. All the Serval helpers use it:
  `PermilServal.multiplyPermil` 0x292201C, `PowerServal.calcStatusPower` 0x29227EC,
  `calcWeaponStatusPower` 0x29227C4 and `calcStatusReferenceValue` 0x2922998.
- Every value is `int` (32-bit). Each product is truncated on its own, and the sums come after.
  No floating point is involved anywhere.
- Stat kinds: 1 agility, 2 attack, 3 crit damage, 4 crit rate, 5 evasion, 6 HP, 7 vitality.
  Calculation types: 1 ADD, 2 MULTIPLY (permil).

## 1. Top level

`CalculatorDeck.UpdatePower` 0x28817B8 runs these steps in order:

1. For each deck actor, `MemorySeriesBonus = CalculatorMemory.CreateMemorySeriesBonusDataAbility(memories)` 0x29A3780 (see section 6).
2. `CalculatorStatusOutgame.ApplyDeckAbilityStatusList` 0x2A1039C (section 4).
3. `CalculatorPower.CalculateDeckActorPower` 0x2A1049C for each actor, then `CalculateDeckPower` 0x2A102EC.

`CalculateDeckPower` = the int sum of `CalculateDeckActorPower` over the 3 actors. An empty slot gives 0.

`CalculateDeckActorPower(actor)` 0x2A1049C:

- It sets this actor's `HpPower`, `AttackPower`, `VitalityPower` and `Power` to 0.
- For every actor in the deck whose `HpPower < 1 || AttackPower < 1 || VitalityPower <= 0`, it runs
  `CalculateDeckActorBasePower` 0x2A110B0 to fill those three. The others keep their cached values.
  All three must be known before any skill power is computed, because skills can read other actors' powers.
- `Power = HpPower + AttackPower + VitalityPower + CalculateSkillPower(actor)` 0x2A11308.

## 2. Base power (`CalculateDeckActorBasePower` 0x2A110B0)

The HP, attack and vitality powers are each the sum over the actor's equipment:

| part | call | stat source | coefficients (constant type) |
|---|---|---|---|
| costume | `CalculateDeckCostumeStatusPower` 0x2A1192C → `CalculateCostumeStatusPower` 0x2A1074C | `GetDeckActorCostumeStatus` 0x2A11F08 | HP 74 (2), ATK 956 (1), VIT 956 (3) |
| main weapon | `CalculateDeckWeaponStatusPower(isMainWeapon=true)` 0x2A11980 → `CalculateWeaponStatusPower` 0x2A10BBC | `GetDeckActorWeaponStatus` 0x2A120AC | HP 57 (5), ATK 781 (4), VIT 781 (6) |
| sub weapon 1, 2 | same, `isMainWeapon=false` | same | same |
| companion | `CalculateDeckCompanionStatusPower` 0x2A11A20 → `CalculateCompanionStatusPower` 0x2A10D2C | `GetDeckActorCompanionStatus` 0x2A1218C | HP 31 (8), ATK 416 (7), VIT 416 (9) |
| memoirs | `CalculateDeckPartsStatusPower` 0x2A11A74 | memoir main and sub stats (not costume stats) | section 7 |

Each part's power is `permil(HP, cHP)`, `permil(ATK, cATK)` and `permil(VIT, cVIT)`, each computed on its own.
`CalculateWeaponStatusPower` takes `isSkillful` and `isMainWeapon` and ignores both. The weapon rules act
earlier, on the stats (section 3.2).

The constants come from `DeckPowerCalculationConstantValues.Setup` 0x27F7F2C. It reads `m_power_calculation_constant_value`
and uses jump table 0x5A23228, which maps types 1–23 to fields 0x10–0x68 one to one. Types 24 and up
(`CHARACTER_BOARD_ADD_POWER_*` etc.) have no case in that jump table. Their fields don't exist, so nothing reads them.
A type missing from the table leaves its field at 0. Values in 3.7.1 master data:

```
1 COSTUME_ATTACK 956     2 COSTUME_HP 74      3 COSTUME_VITALITY 956
4 WEAPON_ATTACK 781      5 WEAPON_HP 57       6 WEAPON_VITALITY 781
7 COMPANION_ATTACK 416   8 COMPANION_HP 31    9 COMPANION_VITALITY 416
10..16 PARTS_ADD  agi 2000, atk 1083, critAtk 677, critRatio 609, eva 2000, hp 81, vit 1083
17..23 PARTS_MUL  agi 73152, atk 2031, critAtk 73152, critRatio 73152, eva 73152, hp 2592, vit 2031
```

## 3. Stats that feed the power

### 3.1 Costume (`GetDeckActorCostumeStatus` 0x2A11F08 → `CalculatorStatus.GetCostumeStatus` 0x2A142A4)

The parts lists are passed as `null`, so memoir stats are not part of the costume status for power.

1. **Base** `GetCostumeBaseStatus` 0x2A1518C → `CalcCostumeStatus` 0x2A16AF0 → `CostumeServal.calcStatusValue` 0x2921EB8:
   - `raw(L) = calcParameter(f, [L]) + baseValue`. `baseValue` comes from `m_costume_base_status`, the function `f`
     from `m_costume_status_calculation`, one per stat (`CreateCostumeStatusCalculationSetting` 0x276EC60). `L` is the costume level.
   - Above the growth threshold (`L > T`): `raw(T) + permil(raw(L) - raw(T), C)`. `T` is
     `COSTUME_STATUS_FUNCTION_THRESHOLD_LEVEL` (90) and `C` is `..._OVER_COEFFICIENT` (850), both from `m_config`.
     The keys are set in `Config.cctor` 0x2E1ED80.
2. Diffs, each computed **from the base values only, never chained**. They are summed afterwards:
   - ability statuses: `GetAbilityStatusDiff(base, attributeType = 0, orgCondition = COSTUME)` 0x2A152C4 (section 4)
   - character board: `GetCharacterBoardStatusDiff` 0x2A15CC4. Input `IUserCharacterBoardStatusUp` (`CreateCharacterBoardStatusList` 0x2A0E368)
   - costume level bonus: `GetCostumeLevelBonusStatusDiff` 0x2A15FF8. Input `IUserCharacterCostumeLevelBonus`, which is per character (0x2A0EAC8)
   - costume awakening: `GetCostumeAwakenStatusDiff` 0x2A1632C. Input `IUserCostumeAwakenStatusUp` (0x2A0E7A4)
   - stained glass: `GetStainedGlassStatusDiff` 0x2A16660. Only ADD rows count (section 3.4)
   - karma: `GetCostumeLotteryEffectStatusDiff` 0x2A167BC. Input `IUserCostumeLotteryEffectStatusUp` (0x2A0ED40)

   Every list diff has the same shape. ADD rows are summed. MULTIPLY permils are summed per stat, and the diff is
   `ADDsum + multiplyPermil(base, MULsum)` (`GetStatusDiff` 0x2A17300). So each source's percentages add together
   and are truncated once per source.
3. `HP += properAttributeHp`. `GetCostumeProperAttributeHpAdditionalValue` 0x2A0F064 gives
   `MainWeaponHpAdditionalValue` when the main weapon's attribute equals `CostumeProperAttributeType`,
   plus `SubWeaponHpAdditionalValue` for each sub weapon with that attribute.
4. `stat = max(stat, kMin)`. From `CalculatorStatus.cctor` 0x2A17A10: agi 0, atk 1, critAtk 1000, critRatio 0, eva 0, hp 1, vit 1.

### 3.2 Weapons (`GetDeckActorWeaponStatus` 0x2A120AC → `CalculatorStatus.GetWeaponStatus(ws, list, isSkillful, isMainWeapon)` 0x2A14C58)

- `isSkillful` = `weapon.WeaponType == costume.SkillfulWeaponType`. The test is at 0x2A119C0 in `CalculateDeckWeaponStatusPower`.
- Base: `GetWeaponBaseStatus` 0x2A16BF4 → `CalcWeaponStatus` 0x2A171FC → `WeaponServal.calcStatusValue` 0x29230D8.
  This is the same growth rule as costumes, with `WEAPON_STATUS_FUNCTION_THRESHOLD_LEVEL` 90 and
  `..._OVER_COEFFICIENT` 290. Only ATK, HP and VIT exist.
- **Halving** (0x2A14D00–0x2A14D70): each base stat `x` becomes `x / 2` (C# int division) when the weapon is
  not of the costume's proficient type. It is then halved again, from that result, when the weapon is a sub weapon.
  So a non-proficient sub weapon gives `(x/2)/2`.
- Diffs are computed from the halved base:
  - `GetAbilityStatusDiff(base, attributeType = weapon attribute, orgCondition = WEAPON)`
  - `GetWeaponAwakenStatusDiff` 0x2A16CC8: `m_weapon_awaken_status_up_group` rows, present only when the weapon is awakened (`IUserWeaponAwaken` row)
- `stat = max(base + diffs, kMin)`.

### 3.3 Companion (`GetCompanionStatus` 0x2A14F7C)

- Base `CalcCompanionStatus` 0x2A17558 → `CompanionServal.calcStatusValue` 0x2921AD8 = `calcParameter(f, [level]) + base`.
  There is no growth threshold.
- Plus `GetAbilityStatusDiff(base, attributeType = companion attribute, orgCondition = COMPANION)`. Then clamp to kMin.

### 3.4 Status inputs and where they come from

- **Board**: rows of `IUserCharacterBoardStatusUp` for the costume's character.
- **Level bonus**: rows of `IUserCharacterCostumeLevelBonus` for the character. The bunker server projects this table
  (`overlays/server/internal/userdata/zz_bunker_costume.go`). For each owned costume id it takes the highest level,
  then each `m_costume_level_bonus` row of that costume with `Level <= level` adds its value.
  Types 1–10 map to (agi, atk, critAtk, critRatio, hp, vit) × (ADD, MUL). The sum covers every owned costume of the
  character, not only the equipped one. `power.py` repeats this projection.
- **Awakening**: rows of `IUserCostumeAwakenStatusUp` for the costume uuid.
- **Karma**: `IUserCostumeLotteryEffectStatusUp`, which the server also projects. Each drawn slot goes
  odds group → `m_costume_lottery_effect_target_status_up`, summed per calculation type.
- **Stained glass** `CreateStainedGlassStatusList` 0x2A0F218: for every `m_important_item` of type 5 the user owns,
  look up `StainedGlass(ExternalReferenceId)`. Its target group must contain (type 1, characterId) or
  (type 2, skillful weapon type) (`IsCharacterStatusUpTarget` 0x2A0F524). Then its status-up group rows with
  calculation type ADD are added (0x2A0F67C).

## 4. Ability statuses

Building one ability, `CalculatorAbility.CreateDataAbility` 0x2801368:

- detail = the `m_ability_level_group` row with the largest `LevelLowerLimit <= level`
  (`FindClosest…(selectLower)`, `GetEntityMAbilityDetail` 0x27F3598)
- **`IsLocked = (level == 0)`** (0x28014A0)
- its behaviours (`CreateDataAbilityBehaviours` 0x28015A4, jump table 0x5A23290):
  1 passive skill → added to `PassiveSkillList`; 3 status → a `DataAbilityStatus`; 4 bless → flag;
  5 status down → a `DataAbilityStatus` with every value negated (0x280243C); 2 → nothing.
- A `DataAbilityStatus` holds the change type (ADD/MUL), the attribute condition, the apply scope (1 actor, 2 party),
  the organization condition (1 costume, 2 weapon, 3 companion, 4 all) and a StatusValue.

An actor's own list comes from `CollectAbilityStatus` 0x2A19060. Abilities whose `IsLocked` is set are skipped:

- costume abilities and karma slot abilities (`CollectCostumeAbilityStatus` 0x2A1891C)
- character abilities (`CollectCharacterAbility` 0x2A19240):
  - **rank** abilities: `m_character_level_bonus_ability_group` rows of the character's group with
    `ActivationCharacterLevel <= rank`, where rank = `IUserCharacter.level` (`CalculatorCharacterRank` 0x2871D84 / 0x2871980)
  - **board** abilities from `IUserCharacterBoardAbility` (0x2A0B0F4)
- the companion ability. No lock check here.
- the abilities of the main weapon and both sub weapons (`CollectWeaponAbilityStatus` 0x2A18B5C). Bless abilities are not included.
- memoir set bonus abilities that are not locked
- the debris (thought) ability, no lock check

Party scope (`ApplyDeckAbilityStatusList` 0x2A1039C → `ApplyDeckOtherDeckActorAbility` 0x2A18F64): each actor also
receives every status with `ApplyScope == PARTY` from the other two actors' own lists. A party-scope status of the
actor's own also applies to itself, through its own list.

`GetAbilityStatusDiff(base, attr, org)` 0x2A152C4 selects statuses in two steps:

1. Organization check, inlined `AbilityOrganizationConditionTypeCheck` 0x2A1761C. A status whose
   `org == ALL(4)` passes for the costume. For weapons and companions it passes only when it is MULTIPLY,
   so ALL-scope flat ADD bonuses reach the costume only. Any other `org` must equal the caller's.
2. Attribute check, `AbilityAttributeConditionTypeCheck` 0x2A17648 (jump table 0x5A6D690). Condition ALL(8) always
   passes. Otherwise attribute 1→cond 1, 2→2, 3→3, 4(none)→7, 5→5, 6→6. The costume calls with attribute 0, so only
   ALL-condition statuses reach costume stats. Weapons use the weapon's attribute, companions the companion's attribute.

Then: `ADDsum + multiplyPermil(base, MULsum)` per stat, as in section 3.1.

## 5. Skill power (`CalculateSkillPower(userId, actor, deck)` 0x2A11308)

The skill power is the int sum of:

- the costume active skill (`CostumeActiveSkill`)
- every main-weapon skill. **Sub-weapon skills don't count.**
- the companion skill
- `CalculateAbilityPower` 0x2A124EC over:
  - the costume abilities, which include the awakening ability
  - karma slot abilities
  - the abilities of the main weapon and both sub weapons
  - the companion ability
  - the memoir set bonus abilities
  - the debris ability
  - character rank + board abilities. 0x2A11780 builds them through `CalculatorCharacterRank.CreateCharacterRankAbilityList`
    and `CalculatorCharacterBoard.CreateCharacterBoardAbilityList`. When `OutgameAbilityCache` is on, the same
    abilities come from its passive-skill cache instead.

`CalculateAbilityPower(ability)` is 0 if `IsLocked`. Otherwise it is the sum of `CalculateSkillPower` over its
`PassiveSkillList` (0x2A12558).

`CalculateSkillPower(actor, deck, skill)` 0x2A12410 = `calcSkillPower(base, Σ ref)` 0x29229C0, which is `base + Σ ref`. It has no lock check.
Its inputs come from `DataSkillPower`, built by `CalculatorSkill.CreateDataSkillPower` 0x2918C90 from the skill detail at
the skill's level (the closest lower `LevelLowerLimit`):

- `base = SkillPowerBaseValue`. It is 0 for every detail in 3.7.1.
- `refType = PowerCalculationReferenceStatusType` (1 SELF, 2 PARTY, 3 NONE)
- `refs` = the `m_power_reference_status_group` rows with id `PowerReferenceStatusGroupId`. Each row gives
  (`ReferenceStatusType` → a status kind, `AttributeConditionType`, `CoefficientValuePermil`).

Each ref goes through `CalculateStatusReferenceValue` 0x2A1267C:

- `refType` 0 or 3 → 0
- otherwise loop over the deck actors. SELF skips every actor whose uuid differs from the owner's.
- the actor's attribute is the **main weapon's** `AttributeType`, or 0 with no main weapon.
  The condition check is `IsMatchAttributeCondition` 0x2A11020 (jump table 0x5A6D620):
  - cond 1/2/3/5/6 match the same attribute
  - cond 7 (NOTHING) matches attribute 4
  - cond 4 never matches
  - cond 8 (ALL) always matches
- value: status kinds 1–5 → the actor's **AttackPower**, kind 6 → **HpPower**, kind 7 → **VitalityPower**.
  These are the base powers from section 2, not stats.
- `ref += permil(value, CoefficientValuePermil)`, truncated for each actor separately.

## 6. Where the abilities and skills come from

- **Costume** `CreateDataOutgameCostume` 0x287705C:
  - status `Level` = costume level.
  - active skill: the `m_costume_active_skill_group` row with the largest `CostumeLimitBreakCountLowerLimit <= LB`.
    Its level comes from `IUserCostumeActiveSkill`.
  - abilities `CreateCostumeDataAbilityList` 0x2878328: each `m_costume_ability_group` slot gets its level from
    `m_costume_ability_level_group` (closest lower LB). The awakening abilities follow
    (`CalculatorAwaken.CreateCostumeAwakenAbilities` 0x2C66CD8): effect type 2 rows with `AwakenStep <= awakenCount`
    → `m_costume_awaken_ability` (ability id, level).
- **Karma** slot ability: drawn odds row of type ABILITY → `m_costume_lottery_effect_target_ability` (ability id, level).
- **Weapon** `CreateUserDataWeapon` 0x27B7BA4:
  - each `m_weapon_skill_group` slot gets its level from `IUserWeaponSkill`; a missing row means level 0 (0x27BDC34).
  - each `m_weapon_ability_group` slot gets its level from `IUserWeaponAbility`; a missing row means level 0, so the ability is locked (0x27BDD3C).
  - when awakened, it adds the effect type 2 ability from `m_weapon_awaken_ability`, forced unlocked (0x27BD1FC),
    and the effect type 1 status rows from `m_weapon_awaken_status_up_group`.
- **Companion**: the skill level is the largest `m_companion_skill_level.SkillLevel` with `CompanionLevelLowerLimit <= level`.
  The ability level is found the same way from `m_companion_ability_level`.
- **Memoir set bonus** (0x29A3780): memoirs are grouped by series. A series needs at least `kMinBonusSetCount` (2) pieces.
  Each row of its `m_parts_series_bonus_ability_group` becomes an ability (id, level), **locked unless
  `SetCount == pieces`** (0x29A3C70). With 3 pieces only the 3-piece ability counts; the 2-piece one is locked.
- **Debris**: `m_thought` (AbilityId, AbilityLevel) of the equipped thought.

## 7. Memoir power (`CalculateDeckPartsStatusPower` 0x2A11A74)

For each memoir:

- **Main stat**: `value = PartsServal.calcStatusDiffByMainOption(level, initial, f)` 0x2922670, which is
  `calcParameter(f, [level]) + StatusChangeInitialValue` from `m_parts_status_main`.
  The function type is 7 (PARTS_MAIN_OPTION), section 8.
- **Sub stats**: the `IUserPartsStatusSub.StatusChangeValue` the server stores is used as is.
- Each (kind, calcType, value) goes through `CalculatePartsStatusPower` 0x2A1225C → `PowerServal.calcStatusPower` (14 args)
  0x2922814. The result is `permil(value, coef[kind])`, with the ADD coefficients (types 10–16) for ADD rows and the
  MUL base values (types 17–23) for MULTIPLY rows. It is 0 when the value or the coefficient is 0.
- Bucketing: kind 6 → HP power, kind 7 → vitality power, kinds 1–5 (agility, attack, crit, evasion) → **attack power**.

## 8. Numerical functions (`FunctionsServal.calcParameter` 0x29218BC, jump table 0x5A4EAFC)

| type | function | formula (32-bit wrap unless noted) |
|---|---|---|
| 1 LINEAR | 0x29221CC | `p0*x + p1` |
| 2 MONOMIAL | 0x2922128 | `p0 * (x-1)^p1` (power `p1`, or 1 when `p1 < 2`) |
| 3 DUPLEX_LINEAR | 0x2922248 | `p0*x + p1*y` |
| 4 LINEAR_PERMIL | 0x29222CC | `permil(p0, x) + p1` |
| 5 POLYNOMIAL_THIRD | 0x2922368 | `((p0*x + p1)*x + p2)*x + p3` |
| 6 POLYNOMIAL_THIRD_PERMIL | 0x292241C | `permil(p0, x³) + permil(p1, x²) + permil(p2, x) + p3`, with `x³` and `x²` in int32 |
| 7 PARTS_MAIN_OPTION | 0x2922518 | `(long)p0 * min(max(x-1,0),13) / 1000 + p1 * (x-14 < 2 ? max(x-14,0) : 1)` |

## 9. What the samples confirm

Every code path in sections 1–8 is reproduced in `power.py`. Paths that matched against stored client values
(check.txt, 9 distinct deck states, 23 distinct characters exact) are:

- costume levels above and below 90; weapon levels above 90; awakened weapons
- proficient and **non-proficient** main and sub weapons (the halving rule)
- companions; memoirs with ADD and MULTIPLY main and sub stats; 2- and 3-piece set bonuses
- debris; karma abilities and statuses; awakening statuses; level bonus
- one character board (statuses + abilities); rank abilities; proper-attribute HP
- party-scope abilities
- SELF and PARTY skill references with attribute conditions 1, 2, 5, 6 and 8, on attack and HP powers

Implemented from the code but not exercised by any sample:

- stained glass (no save owns one)
- status-down abilities. `m_ability_behaviour_action_status_down` has 10 rows, all of them HP down. None was equipped in a sample.
- skill references on vitality power or with conditions 3, 4 or 7
- the kMin clamps
