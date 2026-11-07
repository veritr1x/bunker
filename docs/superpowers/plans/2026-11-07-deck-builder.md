# Deck Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Pod Programs page, Deck Builder, that:
- generates ranked Arena decks from criteria, showing the game's exact Force;
- explains each pick;
- writes a chosen deck to the slots the player selects;
- feeds the 5,000 Arena computer players (Part 2).

**Architecture:**
- **`deckbuilder` package.** A pure-Python package in the Android Python tree.
  - It holds four parts: the exact Force port, a fully-raised loadout model,
    the status-aware Arena simulator, and the generator.
  - It reads master data JSON and the save. It has no `web` import, so it
    tests without `prepare`.
- **The page.** `android_deckbuilder.py` is a FastAPI router like
  `android_gift.py` and renders `deck_builder.html`.
- **Writes** go through two new Lunar Base actions (`deck_write`,
  `arena_matching`), added by an overlay Go file plus a patch, the way Gift
  does it.
- **Part 2** exports a deck table that the Go Arena ladder reads.

**Tech Stack:**
- Python 3 (Chaquopy on Android), FastAPI and Jinja, unittest;
- Go (Lunar Tear server overlays);
- sqlite (Lunar Tear save schema).

**Spec:** `docs/superpowers/specs/2026-11-07-deck-builder-design.md`. Read it
first; section numbers below (§) refer to it.

## Global Constraints

- **Game version:** NieR Re[in]carnation 3.7.1 master data. Read it from
  `config.MASTERDATA_DIR/EntityM<Name>Table.json` on device, and from fixture
  JSON in tests.
- **Arena element coefficients:** ×1.2 advantage, ×0.8 disadvantage; light ↔
  dark is ×1.2 both ways.
- **Element ids:** main weapon AttributeType 1 dark, 2 fire, 3 light, 5 water,
  6 wind.
- **Deck types:** `model.DeckType`, where 2 is PvP (Arena) and 1 is Quest.
- **Force:** must equal the client's `CalculatorPower` exactly. No "≈" is
  shown once Task 1 passes.
- **Fully raised** (§5):
  - max level, limit breaks and rebirth (costume level 100);
  - all skills at max;
  - awakening maxed;
  - best karma at top values;
  - character board and rank bonus complete;
  - weapons at final evolution (EX weapons in IV form), max level, limit
    breaks, skills and abilities;
  - companion at max level;
  - memoirs at +15.
- **Memoirs, theoretical best:** original game rules.
  - Mains may be agility (kind 1), crit damage (3) or crit rate (4), as well as
    ATK, DEF and HP.
  - Up to 4 subs, duplicates allowed, at level-12 step values.
  - Master data numerical functions win over wiki numbers.
- **Never change** deck slots the player didn't select, or owned weapons,
  memoirs, companions or debris. Owned costumes and characters change only
  when ticked.
- **Snapshot:** one Save Data snapshot is taken before every write, via
  `backup_service.create_backup(reason="deck builder")`.
- **Ranking:** pure simulated win rate. A non-expert lineup above expert ones
  carries a "data pick" reason naming the expert deck it beats and by how much.
- **Mockups:** `deck-builder-v5.html` (cards and phones A–D) and
  `deck-builder-v4.html` (desktop controls, detail and write). Both are local
  and never published.
- **Shipped research data:** costume ids and weights only, with a credit in
  `THIRD-PARTY-NOTICES.md`. No tier-list text, pages or video.
- **Edits are refused while the game server runs**, by the existing
  `mobile.Edit` rule. Don't bypass it.

## Review Focus

- **A deck slot that holds a costume the player no longer owns, or a stale
  power value.** The page must show the computed Force and never crash.
  - Test: `test_page_stale_or_missing_piece` in Task 11.
- **Inventory full or a piece that can't be granted.** The write must be
  refused whole, with the reason, and leave no partial write.
  - Test: `TestDeckWriteRollsBackOnGrantFailure` in Task 10.
- **Two selected slots needing the same owned unique item.** Add a copy where
  duplicates are allowed; otherwise refuse before writing and name the item.
  - Test: `TestDeckWriteSharedItem` in Task 10.
- **Filters that match zero decks.** Show "No decks match" with the filter to
  relax. No endless spinner.
  - Test: `test_generate_no_match` in Task 8.
- **Active master data changed by a mod or patch** (a costume removed). The
  generator must skip ids missing from master data rather than crash. The
  expert file must tolerate unknown ids.
  - Test: `test_experts_unknown_ids_skipped` in Task 6.

---

## File Structure

All new Python lives under `android/app/src/main/python/`. Tests live in
`android/tools/` (the existing convention) and run with
`python3 android/tools/test_<name>.py`.

| File | Responsibility |
|---|---|
| `deckbuilder/__init__.py` | Package marker; `__all__` of public entry points |
| `deckbuilder/tables.py` | `Tables`: master data access by table name, the names map, element/costume/weapon lookups, the EX and playable flags |
| `deckbuilder/power.py` | Exact Force port (from scratchpad `power/power.py`) |
| `deckbuilder/raise_.py` | Fully raised stats and memoir rolls (theoretical best) |
| `deckbuilder/model.py` | `Piece`, `CharacterLoadout`, `Deck`, `Inventory`; reading decks and inventory from a save |
| `deckbuilder/sim/rules.py` | Order, combo and damage rules, coefficients, `PARAMS` (from `data-meta/sim_rules.py` and the `sim.py` params) |
| `deckbuilder/sim/status.py` | Status library: Compromised, Dauntless, Defiance, Provoke, Indomitable, Crush, revive, cleanse |
| `deckbuilder/sim/battle.py` | `simulate(attacker: Deck, defender: Deck, seed: int, auto: bool) -> Outcome`; `win_rate(...)` |
| `deckbuilder/experts.py` + `deckbuilder/data/experts.json` | Expert lineups, roles and weights; the meta pool; the video decks as id lists |
| `deckbuilder/equip.py` | Data-picked weapons, memoirs, companion, debris and karma for a lineup, with override reasons |
| `deckbuilder/generate.py` | Criteria, enumeration, ranking, variant folding, paging |
| `deckbuilder/explain.py` | Strategy labels, plan text, per-piece reasons, the banned-claims check |
| `android_deckbuilder.py` | FastAPI router: page, results JSON, detail, matching list, write |
| `overlays/python/web/templates/deck_builder.html` | Page (desktop and phone), from mockups v4/v5 |
| `overlays/python/web/templates/base.html` | Add the nav entry |
| `overlays/server/internal/lunarbase/bunker_deckbuilder.go` (+ `_test.go`) | `deck_write`, `arena_matching` |
| `patches/lunar-base-zz-deckbuilder.patch` | Add the two cases and the `Deck` request field to `lunarbase/main.go` |
| `android/tools/fixtures/deckbuilder/` | Trimmed master tables plus deck-input fixtures extracted from saves (game ids and levels only) |
| `scripts/build_deckbuilder_fixtures.py` | Rebuilds the fixtures from a master dump and saves |
| `docs/superpowers/specs/mockups/` | Copies of v4, v5 and `automata.css` |

---

## Part 1 — Deck Builder

### Task 0: Fixtures and mockups in the repo

**Files:**
- Create: `scripts/build_deckbuilder_fixtures.py`
- Create: `android/tools/fixtures/deckbuilder/master/*.json`
- Create: `android/tools/fixtures/deckbuilder/decks/*.json`
- Create: `android/tools/fixtures/deckbuilder/turn_order.csv`
- Create: `docs/superpowers/specs/mockups/{deck-builder-v4.html,deck-builder-v5.html,automata.css}`

**Interfaces:**
- Produces: `build_deckbuilder_fixtures.py --master <md dir> --save <game.db>... --out android/tools/fixtures/deckbuilder`.
  - It writes master tables trimmed to the rows needed by the fixture decks
    and the test lineups.
  - It writes one `decks/<name>.json` per sampled deck:
    `{"stored_deck": int, "stored_characters": [int,int,int], "inputs": {...}}`,
    where `inputs` is what `model.Deck.from_inputs` takes (Task 3).
  - It strips everything that isn't a game id, level or count. No user names
    and no uuids beyond deck-local ones.

- [ ] **Step 1:** Write the script. Sources:
  - master dump: `scratchpad/md/`;
  - saves:
    - `bunker-work/ipad-arena-check/game.db` (23445);
    - the save holding deck 215842 and the 193843/191007/166783 Big Hunt
      decks, as listed in `scratchpad/power/check.txt`;
    - the new-player save (1590).
  - turn order: copy `scratchpad/videos/turn_order.csv`.
  - video decks: write `decks/video_<id>.json` from each
    `scratchpad/videos/<id>/deck.json`, adding `"video_win_seconds"` where the
    video shows the fight's end.
- [ ] **Step 2:** Run it and check that each `decks/*.json` has nonzero
  `stored_deck`.
- [ ] **Step 3:** Copy the mockups from
  `scratchpad/mockups/.superpowers/brainstorm/50469-1794023185/content/`.
- [ ] **Step 4: Commit**
  `git add scripts/build_deckbuilder_fixtures.py android/tools/fixtures/deckbuilder docs/superpowers/specs/mockups && git commit -m "Deck Builder: fixtures and mockups"`

### Task 1: Tables and the exact Force port

**Files:**
- Create: `deckbuilder/__init__.py`, `deckbuilder/tables.py`, `deckbuilder/power.py`
- Test: `android/tools/test_deckbuilder_power.py`

**Interfaces:**
- Produces: `Tables(master_dir: Path, names_dir: Path | None = None)` with:
  - `.table(name: str) -> list[dict]`
  - `.by_id(name: str, key: str) -> dict[int, dict]`
  - `.name(kind: str, id: int) -> str`
  - `.costume_element(costume_id) -> str`
  - `.is_playable(costume_id) -> bool`
  - `.is_ex(costume_id) -> bool`: Reborn 41000–45003 and Frozen-Heart
    51001–55003.
- Produces: `power.deck_power(deck: Deck, tables: Tables) -> PowerResult`.
  - `PowerResult` has `total: int`, `characters: list[CharacterPower]`.
  - `CharacterPower` has `total`, `hp`, `atk`, `vit`, `skill` and
    `parts: dict[str, tuple[int,int,int]]`.
- Produces: `power.deck_power_from_save(db_path, user_id, deck_type, deck_number, tables) -> PowerResult`.

- [ ] **Step 1: Write the failing tests**

```python
class PowerTest(unittest.TestCase):
    def test_matches_stored_power_exactly(self):
        for f in sorted((FIX / "decks").glob("*.json")):
            d = json.loads(f.read_text())
            r = power.deck_power(model.Deck.from_inputs(d["inputs"]), TABLES)
            self.assertEqual(r.total, d["stored_deck"], f.name)
            self.assertEqual([c.total for c in r.characters], d["stored_characters"], f.name)

    def test_permil_truncates_toward_zero(self):
        self.assertEqual(power.permil(436, 81), 35)
        self.assertEqual(power.permil(-436, 81), -35)

    def test_only_constants_1_to_23_are_read(self):
        self.assertEqual(sorted(power.constants(TABLES)), list(range(1, 24)))
```

- [ ] **Step 2:** Run `python3 android/tools/test_deckbuilder_power.py`.
  Expect FAIL with `ModuleNotFoundError: deckbuilder`.
- [ ] **Step 3: Port `scratchpad/power/power.py` into `deckbuilder/power.py`.**
  - Split save reading into `model.py` (Task 3 grows it; create the minimal
    `Deck.from_inputs` now).
  - Keep `formula.md`'s RVA comments on each step.
  - Keep the costume level bonus and karma projection that mirrors
    `zz_bunker_costume.go`.
  - Copy `formula.md` to `deckbuilder/POWER.md`.
- [ ] **Step 4:** Run the tests. Expect PASS on every fixture.
- [ ] **Step 5:** Add a test per unverified path (stained glass, HP-down
  abilities, VitalityPower references, attribute conditions 3/4/7, the minimum
  clamps). Each asserts the value the code path computes for a hand-built
  input, with a comment `# from code only (RVA …), no save sample`.
- [ ] **Step 6: Commit** `"Deck Builder: exact Force port"`

### Task 2: Fully raised stats and theoretical-best memoirs

**Files:**
- Create: `deckbuilder/raise_.py`
- Test: `android/tools/test_deckbuilder_raise.py`

**Interfaces:**
- Consumes: `Tables`.
- Produces:
  - `raised_costume(costume_id, tables) -> CostumeState`
  - `raised_weapon(weapon_id, tables) -> WeaponState`, which evolves to the
    final form via the evolution tables
  - `raised_companion(companion_id, tables) -> CompanionState`
  - `memoir(parts_id, main_kind: int, subs: list[int], tables) -> MemoirState`
  - `MAIN_KINDS = {1: "agility", 2: "attack", 3: "crit_damage", 4: "crit_rate", 6: "hp", 7: "defense"}`
  - The `*State` types are the dataclasses in `model.py` that `power` and
    `sim` consume. Define them here if Task 3 isn't done yet, and move them
    there.

- [ ] **Step 1: Write failing tests**
  - `test_raised_costume_is_level_100_max_awakening_full_board`: for costume
    35036, assert level 100, awakening at the master max, every board panel
    released, rank bonus at max.
  - `test_raised_weapon_ex_is_iv_form`: Glimmering Stephanos ends at the IV
    form id, and Blade of Parting IV has its agility +20% ability.
  - `test_memoir_main_values_at_15`:
    - flat ATK 610, flat DEF 610, ATK%/DEF%/HP% 195‰, flat HP 6600;
    - crit rate, crit damage and agility equal the numerical-function value at
      +15. Assert against the function, and assert it equals 20% / 25% / 120.
      If master data differs, master data wins; change the expected number and
      say why in a comment.
  - `test_memoir_subs_level12_step`:
    - % subs 75‰;
    - crit damage 140‰;
    - agility 75;
    - duplicates allowed;
    - a 5th sub raises `ValueError`.
  - `test_raised_deck_power_is_exact_shape`: a theoretical-best deck
    (35036 / 33029 / 34048) gets a deterministic Force from `power.deck_power`.
    Snapshot the number in the test.
- [ ] **Step 2:** Run and see it fail.
- [ ] **Step 3:** Implement. Source rules: §5 and `scratchpad/data-meta/nr.py`.
  Use the master numerical functions, never hard-coded curves.
- [ ] **Step 4:** Run and see it pass.
- [ ] **Step 5: Commit** `"Deck Builder: fully raised pieces and memoirs"`

### Task 3: Loadout model and reading the save

**Files:**
- Modify: `deckbuilder/model.py`
- Test: `android/tools/test_deckbuilder_model.py`

**Interfaces:**
- Produces:
  - `Piece(kind: Literal["costume","weapon","companion","memoir","debris"], id: int, owned_uuid: str | None, state: object, new: bool)`
  - `CharacterLoadout(costume, main_weapon, subs: tuple[Piece,Piece], companion, memoirs: tuple[Piece,Piece,Piece], debris, karma: list[int])`
  - `Deck(characters: tuple[CharacterLoadout,CharacterLoadout,CharacterLoadout])`, where the slot order is left, middle, right
  - `Deck.from_inputs(dict)`
  - `Deck.from_save(db_path, user_id, deck_type, deck_number, tables)`
  - `Deck.key() -> tuple`: the lineup plus gear ids, used for folding
  - `Inventory.from_save(db_path, user_id, tables)`, which has
    `.owned(kind, id) -> list[Piece]` and `.costume_state(costume_id)`
  - `missing_pieces(deck, inventory) -> list[Piece]`
  - `raises_needed(deck, inventory) -> list[RaiseItem]`, where
    `RaiseItem(costume_id, field, current, target, used_in: list[str])`
  - `slots(db_path, user_id, tables) -> list[Slot]`, where
    `Slot(deck_type, number, label, summary: str | None)`
- Saves are opened read-only (`file:...?mode=ro`, falling back to
  `immutable=1` as power.py does).

- [ ] **Step 1: Write failing tests**
  - `test_from_save_roundtrip`: for each fixture, `Deck.from_inputs`
    reproduces the fixture's ids.
  - `test_missing_and_raises`: a theoretical deck against a fixture inventory
    lists the right missing pieces. An owned costume below max appears in
    `raises_needed` with `used_in` naming the other slots that use it.
  - `test_slots_labels`: Arena attack and defense slots are labelled, with a
    summary of the existing lineup or `None` when empty.
- [ ] **Steps 2–4:** fail, implement, pass.
- [ ] **Step 5: Commit** `"Deck Builder: loadout model"`

### Task 4: The Arena simulator

**Files:**
- Create: `deckbuilder/sim/__init__.py`, `rules.py`, `status.py`, `battle.py`
- Test: `android/tools/test_deckbuilder_sim.py`

**Interfaces:**
- Consumes: `Deck`, `Tables`, and the stats used by `power` (reuse its
  final-stat computation; don't recompute).
- Produces:
  - `simulate(attacker: Deck, defender: Deck, tables, seed: int = 0, auto_defender: bool = True) -> Outcome`,
    where `Outcome(win: bool, seconds: float, log: list[Event])`
  - `win_rate(attacker, defender, tables, runs: int = PARAMS["runs"]) -> float`
  - `PARAMS: dict`, holding every tunable, including `OPEN_DELAY = 3.0`,
    `OPEN_INTERLEAVE`, `OPEN_ANIM`, the combo table use and `damage_scale`

- [ ] **Step 1: Write failing tests (the mechanics in §6)**
  - `test_element_coefficients`: fire→wind 1.2, wind→fire 0.8, light→dark
    1.2, dark→light 1.2.
  - `test_compromise_does_not_remove_active_dauntless`: Compromised applied
    after Dauntless leaves Dauntless active, and blocks a new Dauntless.
  - `test_crush_is_cleansable`.
  - `test_opening_order_right_left_middle`: three usable-from-start units fire
    R, L, M after 3.0 s. On auto the defender goes first.
  - `test_combo_multiplier`: COMBO 19+ gives ×2.00, and on-screen n uses row
    n−1. Only flagged skills get it.
  - `test_cooldown_fps`: a weapon skill recovers at 60/s; buffs tick at 30/s.
  - `test_opening_matches_video`: replays `fixtures/turn_order.csv`. The
    attacker's first skill is right in ≥ 19 of 21, and the mean timing error
    is ≤ 1.2 s.
- [ ] **Step 2:** Run and see it fail.
- [ ] **Step 3:** Port from `scratchpad/data-meta/sim.py`, `sim_rules.py`,
  `status_lib.py` and `params.json`.
  - Rewrite as the modules above.
  - Keep the hybrid opening model and the calibrated numbers.
  - Use `random.Random(seed)` for determinism.
- [ ] **Step 4:** Run and see it pass.
- [ ] **Step 5: Commit** `"Deck Builder: Arena simulator"`

### Task 5: Damage calibration (§9)

**Files:**
- Modify: `deckbuilder/sim/rules.py` (`PARAMS["damage_scale"]` and related)
- Test: `android/tools/test_deckbuilder_sim.py`

- [ ] **Step 1: Write failing test**
  `test_video_win_times_in_range`. For the video decks in
  `fixtures/decks/video_*.json` (Task 0 extracts them from
  `scratchpad/videos/*/deck.json`), the simulated median win time is within
  0.5×–2× the video time. Griff / New Year's Boor Yudil / Akeha won in 13 s on
  video and takes 49 s now.
- [ ] **Step 2:** Run and see it fail.
- [ ] **Step 3:** Find the cause before tuning.
  - Compare per-hit damage in one traced fight (the
    `scratchpad/data-meta/sim_trace.py` approach) with the video's hit
    numbers.
  - Fix the formula if a term is missing. Change `damage_scale` only for
    what's left, and record the reason in a comment.
- [ ] **Step 4:** Run the whole sim test file and see it pass.
  `test_opening_matches_video` must still pass.
- [ ] **Step 5: Commit** `"Deck Builder: damage calibrated to video"`

### Task 6: Expert data

**Files:**
- Create: `deckbuilder/data/experts.json`, `deckbuilder/experts.py`
- Modify: `THIRD-PARTY-NOTICES.md` (credit the community tier lists and loadouts)
- Test: `android/tools/test_deckbuilder_experts.py`

**Interfaces:**
- Produces:
  - `Experts.load(tables) -> Experts`, with:
    - `.weight(costume_id) -> float` (0 when not an expert pick)
    - `.roles(costume_id) -> set[str]`
    - `.lineups() -> list[ExpertLineup]`, where
      `ExpertLineup(name, costumes: tuple[int,int,int], loadout: dict | None, source: str)`
    - `.meta_pool() -> list[Deck]`: weighted, for General best
- Schema of `experts.json`:

```json
{"version": 1,
 "costumes": {"35036": {"weight": 1.0, "roles": ["turret"], "tier": "X"}},
 "lineups": [{"name": "Top defense", "costumes": [31032, 35036, 33029],
              "loadout": {"31032": {"memoir_set": 17}}, "source": "video:OV5NyFAmDRc"}]}
```

- [ ] **Step 1: Write failing tests**
  - `test_experts_load`
  - `test_experts_unknown_ids_skipped`: an id missing from fixture master
    data is ignored with a logged warning.
  - `test_meta_pool_includes_top_defense`
- [ ] **Step 2:** Run and see it fail.
- [ ] **Step 3:** Write the reduction.
  - Sources:
    - `scratchpad/web-meta/nierrein-pvp-tierlists.md`
    - `scratchpad/web-meta/nierrein-arena-loadouts.md`
    - `scratchpad/videos/arena_decks.txt` and `videos/*/deck.json`
  - Put the reduction in `scripts/build_deckbuilder_experts.py`, so it can be
    re-run. Its output is ids and weights only.
- [ ] **Step 4:** Run and see it pass.
- [ ] **Step 5: Commit** `"Deck Builder: expert lineups (ids and weights)"`

### Task 7: Equipping a lineup

**Files:**
- Create: `deckbuilder/equip.py`
- Test: `android/tools/test_deckbuilder_equip.py`

**Interfaces:**
- Consumes: `Tables`, `Experts`, `Inventory`, `raise_`, `sim.win_rate`.
- Produces:
  - `equip(lineup: tuple[int,int,int], mode: Mode, inventory: Inventory | None, target: Deck | None, tables, experts) -> Equipped`
  - `Mode(kind: Literal["owned","best"], allow_missing: int)`
  - `Equipped(deck: Deck, reasons: dict[str, str], overrides: list[Override], to_add: list[Piece])`
  - `Override(costume_id, slot: str, expert_choice, data_choice, reason: str, evidence: dict)`

- [ ] **Step 1: Write failing tests**
  - `test_set7_overridden_by_set17_with_reason`. Phantasmal Boor Yudil's
    expert loadout gives memoir set 7. The data picks set 17, and the reason
    mentions the wearer's DEF −30%.
  - `test_owned_mode_respects_allow_missing`: with `allow_missing=2`, at most
    2 pieces are added and the rest are owned.
  - `test_best_mode_memoir_mains_by_role`: attackers get crit rate, crit
    damage and ATK% mains; the result has ≥ 50% crit rate.
  - `test_main_weapon_sets_element`: the main weapon's element equals the
    lineup's element choice for that slot.
- [ ] **Step 2:** Run and see it fail.
- [ ] **Step 3:** Implement.
  - Candidates per slot come from the rankings in
    `scratchpad/data-meta/*_ranked.csv`, rebuilt from master data.
  - Choose by `win_rate` against `target`, or the meta pool, and use a greedy
    per-slot search with one improvement pass. That's my call; any better
    search that passes the tests is fine.
- [ ] **Step 4:** Run and see it pass.
- [ ] **Step 5: Commit** `"Deck Builder: equipping"`

### Task 8: The generator

**Files:**
- Create: `deckbuilder/generate.py`
- Test: `android/tools/test_deckbuilder_generate.py`

**Interfaces:**
- Consumes: `equip`, `Experts`, `sim.win_rate`, `power.deck_power`.
- Produces:
  - `Criteria(deck_for: Literal["attack","defense"], mode: Mode, against: Deck | None, strategy: str = "any", elements: tuple[str|None,str|None,str|None] = (None,None,None), must_have: frozenset[str] = frozenset(), include: frozenset[int] = frozenset(), exclude: frozenset[int] = frozenset(), exclude_elements: frozenset[str] = frozenset(), min_stats: dict[str,int] = {}, sort: Literal["match","force","fewest"] = "match")`
  - `Generator(tables, experts, inventory).page(criteria, offset: int, limit: int) -> Page`
  - `Page(total: int, items: list[Result], exhausted: bool, relax: str | None)`.
    `relax` names the filter that removes the most lineups; it is set only
    when `total == 0`.
  - `Result(rank, deck: Deck, strategy: str, win_rate: float, force: int, to_add: int, tags: list[str], why: str, variants: list[Deck], data_pick: DataPick | None, equipped: Equipped)`
  - `DataPick(beats: str, by: float)`
  - `must_have` values: `compromise`, `cleanse`, `revive`, `provoke`,
    `dauntless`, `indomitable`, `from_start`.
  - Strategies: `any`, `stall`, `burst`, `dauntless`, `compromise_counter`,
    `tank`, `mono`.

- [ ] **Step 1: Write failing tests**
  - `test_generate_ranks_by_win_rate`: page items are non-increasing in
    `win_rate`.
  - `test_data_pick_reason`: a non-expert lineup ranked above an expert one
    has `data_pick.beats` set to that expert lineup's name and `by > 0`.
  - `test_filters`: elements by slot, `must_have={"compromise"}`, exclude
    Sarafa and min agility all hold for every item.
  - `test_variants_fold`: the same three costumes with different gear or slot
    order appear once, with variants listed.
  - `test_paging_stable`: page(0,6) followed by page(6,6) equals page(0,12).
    Results are deterministic for a given seed.
  - `test_generate_no_match`: impossible criteria give `total == 0`,
    `exhausted`, and `relax` naming the most restrictive filter.
- [ ] **Step 2:** Run and see it fail.
- [ ] **Step 3:** Implement.
  - Enumerate lineups lazily:
    - expert lineups first;
    - then pairs of costumes by expert weight × static score;
    - then the rest.
  - Prune by criteria before equipping.
  - Simulate only what a page needs, plus a lookahead of one page. Cache by
    `Deck.key()` in memory.
  - `total` is the count of lineups that pass the criteria, before
    simulation.
- [ ] **Step 4:** Run and see it pass. Time `page(0,6)` on the fixture and
  print it. It should be under 5 s on a laptop.
- [ ] **Step 5: Commit** `"Deck Builder: generator"`

### Task 9: Explanations

**Files:**
- Create: `deckbuilder/explain.py`
- Test: `android/tools/test_deckbuilder_explain.py`

**Interfaces:**
- Produces:
  - `explain(result: Result, against: Deck | None, tables) -> Explanation`
  - `Explanation(title: str, why_short: str, why_long: str, per_character: list[str], per_piece: dict[tuple[int,str], str], overrides: list[str])`
  - `BANNED_CLAIMS: list[re.Pattern]`

- [ ] **Step 1: Write failing tests**
  - `test_no_banned_claims`: across 50 generated results against the top
    defense, no text matches the banned patterns. These include "Compromise
    (removes|cancels|ends) .*Dauntless" and "blocks (her|the) first
    Dauntless".
  - `test_short_reason_fits`: `why_short` is ≤ 110 characters (two lines on
    a card).
  - `test_override_text_has_evidence`: each override string contains the
    numeric evidence, for example "DEF −30%".
- [ ] **Steps 2–4:** fail, implement from the sim's event log (statuses,
  timing, element roles), pass.
- [ ] **Step 5: Commit** `"Deck Builder: explanations"`

### Task 10: Save writes in Lunar Base (Go)

**Files:**
- Create: `overlays/server/internal/lunarbase/bunker_deckbuilder.go`
- Create: `overlays/server/internal/lunarbase/bunker_deckbuilder_test.go`
- Create: `patches/lunar-base-zz-deckbuilder.patch`. It adds
  `case "deck_write": return runDeckWrite(&req)` and
  `case "arena_matching": return runArenaMatching(&req)` to `run()`, and a
  `Deck json.RawMessage \`json:"deck"\`` field to `request`.

**Interfaces:**
- Consumes: the existing grant helpers in `lunarbase` (costume, weapon,
  companion, thought and memoir batch grants; `runSetMemoirSubsBatch`;
  karma), and `pvp.Current()`.
- Produces the `deck_write` request:

```json
{"action":"deck_write","user_id":1,
 "deck":{"slots":[{"deck_type":2,"number":2}],
         "characters":[{"costume":{"id":32035,"uuid":null},
                        "main_weapon":{"id":...,"uuid":null},
                        "subs":[...],"companion":{...},
                        "memoirs":[{"id":...,"uuid":null,"main_status_id":...,"subs":[...]}],
                        "debris":{"id":...,"uuid":null},"karma":[...]}],
         "raise":[{"costume_id":31032}]}}
```

  - `uuid: null` means grant the piece fully raised.
  - A uuid means use that owned piece unchanged.
  - `raise` lists the only owned costumes that may be raised.
  - The reply is `{"ok":true,"added":[...],"raised":[...]}` or
    `{"ok":false,"error":"..."}`.
- Produces `arena_matching` → `{"ok":true,"opponents":[{"id":...,"name":...,"points":...,"costumes":[...],"weapons":[...]}]}`.
  It reads the current matching list via `pvp.Current().Sync` and the
  player's `PvpState`, and changes nothing.
- The whole write happens in one save transaction. Any failure rolls it all
  back.

- [ ] **Step 1: Write failing Go tests**
  - `TestDeckWriteOnlySelectedSlots`: every other `user_decks` and
    `user_deck_characters` row is byte-identical before and after.
  - `TestDeckWriteGrantsRaised`: a new costume is level 100 with max
    awakening and full board; a memoir carries `main_status_id` for crit rate
    (kind 4).
  - `TestDeckWriteRaisesOnlyTicked`: owned costume A in `raise` is maxed;
    owned costume B not in `raise` is unchanged.
  - `TestDeckWriteNeverTouchesOwnedWeapons`: an owned weapon used by uuid
    keeps its level.
  - `TestDeckWriteRollsBackOnGrantFailure`: with a full inventory, the reply
    is `ok:false`, the error names the reason, and the save is unchanged.
  - `TestDeckWriteSharedItem`: two slots need one owned debris. A copy is
    added where duplicates are allowed; otherwise the write is refused,
    naming the item.
  - `TestArenaMatchingReadsOnly`.
- [ ] **Step 2:** Run `python3 scripts/prepare.py`, then
  `cd server && go test ./internal/lunarbase/ -run 'DeckWrite|ArenaMatching'`.
  Expect FAIL.
- [ ] **Step 3:** Implement `runDeckWrite` and `runArenaMatching`. Write the
  patch with `git diff` from a prepared tree, as the existing
  `lunar-base-zz-gift.patch` does.
- [ ] **Step 4:** Run the tests and see them pass. Run the full
  `go test ./internal/lunarbase/ ./mobile/` and confirm nothing else breaks.
- [ ] **Step 5: Commit** `"Deck Builder: deck_write and arena_matching"`

### Task 11: The page

**Files:**
- Create: `android/app/src/main/python/android_deckbuilder.py`
- Create: `overlays/python/web/templates/deck_builder.html`
- Modify: `overlays/python/web/templates/base.html`: add
  `<a href="/decks" {% if active == "decks" %}class="active"{% endif %}>Deck Builder</a>`
  after Gift
- Modify: `android/app/src/main/python/android_runtime.py`: in `create_app`,
  add `import android_deckbuilder` and
  `app.include_router(android_deckbuilder.router)`
- Test: `android/tools/test_deckbuilder_page.py` (uses `web`, so run
  `scripts/prepare.py` first, like `test_gift.py`)

**Interfaces:**
- Consumes: everything above, and `grant_service._invoke_shim` for
  `deck_write` and `arena_matching`, the same way `android_gift._shim` does.
- Produces these routes:
  - `GET /decks?user=` renders the page.
  - `GET /decks/results?user=&offset=&limit=&<criteria>` returns
    `{"total","items":[card...],"exhausted","relax"}`. A card has
    `rank, title, win_pct, tiles:[{name,element,slot,new}], tags, why, force, to_add, variants`.
  - `GET /decks/detail?user=&key=` returns the full loadout, explanation,
    overrides and `raises` (owned items with current → max and `used_in`).
  - `GET /decks/opponents?user=` returns the matching list from
    `arena_matching`.
  - `POST /decks/write {user, key, slots:[...], raise:[costume_id...]}` takes
    a snapshot, calls `deck_write`, then returns `{ok, added, raised}` or an
    error.
  - `GET /decks/rescore?user=&key=&raise=` returns Force and win % with only
    the ticked raises, for the Write summary.

- [ ] **Step 1: Write failing tests**
  - `test_nav_has_deck_builder`
  - `test_results_json_shape`
  - `test_write_takes_snapshot_then_calls_shim`: mock `backup_service` and
    `_shim`, and assert the order and payload.
  - `test_write_refused_reason_shown`
  - `test_page_stale_or_missing_piece`: a save deck pointing at a missing
    costume uuid renders with computed Force and a notice.
  - `test_rescore_changes_with_raise`
- [ ] **Step 2:** Run and see it fail.
- [ ] **Step 3:** Implement the router and template.
  - Match mockup v5 for the cards and phones A–D, and v4 for the desktop
    controls, detail and write.
  - One template with CSS breakpoints: at ≤ 640px the phone layout applies,
    the Filters bottom sheet replaces the criteria panel, and the Write button
    sticks to the bottom.
  - Results load with `fetch` as the list scrolls.
  - The page follows the live-game banner rules already in `base.html`.
- [ ] **Step 4:** Run and see it pass. Then run the app (`run` skill or the
  emulator) and look at desktop width and 390px portrait against the
  mockups.
- [ ] **Step 5: Commit** `"Deck Builder: page"`

### Task 12: Acceptance (§11)

**Files:**
- Test: `android/tools/test_deckbuilder_acceptance.py`

- [ ] **Step 1: Write tests**
  - `test_top20_agrees_with_experts`: General best plus theoretical best;
    ≥ 19 of the top 20 costumes are expert or video picks.
  - `test_opening_check_holds`: re-asserts Task 4's 19/21 and 1.2 s.
  - `test_force_exact_on_all_fixtures`: re-runs Task 1 over every fixture.
- [ ] **Step 2:** Run all `android/tools/test_deckbuilder_*.py` and see them
  pass.
- [ ] **Step 3: Commit** `"Deck Builder: acceptance checks"`

---

## Part 2 — Arena computer players

### Task 13: Deck table export

**Files:**
- Create: `deckbuilder/ladder.py`
- Test: `android/tools/test_deckbuilder_ladder.py`

**Interfaces:**
- Produces:
  - `export_table(tables, experts, out: Path, size: int = 2000) -> None`
  - `score_player(db_path, user_id, tables) -> PlayerScore`, where
    `PlayerScore(attack: float, defense: float, power: int)`
  - `write_player_score(path: Path, user_id: int, score: PlayerScore)`

  The table is `bunker_arena_decks.json`:

```json
{"version":1,"master_sha256":"...",
 "decks":[{"quality":0.874,"power":412318,
           "characters":[{"costume":35036,"main_weapon":...,"subs":[..],"companion":..,
                          "parts":[{"id":..,"main":..,"subs":[..]}],"thought":..,
                          "karma":[..],"awaken":..,"board":true}, ...]}],
 "power_to_quality":[[100000,0.2],[300000,0.5],[420000,0.85]]}
```

  - `quality` is the deck's win rate against the meta pool, from 0 to 1.
  - The table covers gear levels from low to fully raised, so the lower
    ladder can field weaker decks.
- The file goes in `config.GAME_DB_PATH.parent`, next to `game.db` (my
  call). The Go side reads it from `dataRoot`, the same folder `mobile.Edit`
  uses. Pod
  Programs rewrites it whenever the active master data's sha256 changes, and
  rewrites player scores after a write and on page open.
- A default generated at build time ships in the APK assets via
  `scripts/build.py`.

- [ ] **Step 1: Write failing tests**
  - `test_export_sorted_by_quality`
  - `test_export_covers_low_to_max`
  - `test_score_player_matches_sim`
  - `test_master_change_triggers_rewrite`
- [ ] **Steps 2–4:** fail, implement, pass.
- [ ] **Step 5: Commit** `"Deck Builder: Arena deck table"`

### Task 14: The ladder uses the table (Go)

**Files:**
- Modify: `overlays/server/internal/pvp/ladder.go`: extend `CPU` with
  `Loadout *DeckLoadout`
- Modify: `overlays/server/internal/pvp/deck.go`: `Deck()` fills `Companion`,
  `SubWeapon`, `Parts`, `Thought`, `CharacterBoard*`, `Awaken*` and
  `CostumeLotteryEffect*` from the loadout
- Create: `overlays/server/internal/pvp/decktable.go` and `decktable_test.go`
- Modify: `overlays/server/internal/pvp/pvp_test.go`, `rotation_test.go` as
  needed

**Interfaces:**
- Produces:
  - `LoadDeckTable(path string) (*DeckTable, error)`
  - `(*DeckTable).Pick(rank, ladderSize int, playerQuality float64, r *rand.Rand) DeckLoadout`
  - `PlayerQuality(dataDir string, userId int64, power int32, t *DeckTable) float64`:
    reads the score Pod Programs wrote, otherwise falls back to the
    `power_to_quality` mapping.
- **Curve** (my call; tune in tests):
  - Rank 1 to 100 always pick from the top 2% of the table by quality.
  - Below that, the target quality is
    `q(rank) = playerQuality + (q_top − playerQuality) · (1 − rank/ladderSize)^γ`
    with γ = 2. Pick the nearest table entries, with jitter of ±0.03.
  - With no table file, behaviour is exactly as today.
- The existing `Strength` clamp (0.8–1.25) and the point system stay
  unchanged.

- [ ] **Step 1: Write failing tests**
  - `TestTop100AreMeta`
  - `TestQualityRisesWithRank`: mean quality per decile is non-decreasing
    toward rank 1.
  - `TestScalesToPlayer`: mid-ladder quality moves with `playerQuality`.
  - `TestNoTableUnchanged`: output matches the current `Deck()` exactly.
  - `TestDeckCarriesFullLoadout`: the proto has a companion, parts and a
    thought.
  - `TestMatchingStillWorks`: the existing `Match` and point tests pass.
- [ ] **Step 2:** Run `cd server && go test ./internal/pvp/` after
  `prepare`. Expect FAIL.
- [ ] **Step 3:** Implement. The season ladder stays seeded per season; only
  which loadout each CPU uses comes from `Pick`.
- [ ] **Step 4:** Run `go test ./internal/pvp/ ./mobile/` and see it pass.
- [ ] **Step 5: Commit** `"Arena: computer players use Deck Builder decks"`
