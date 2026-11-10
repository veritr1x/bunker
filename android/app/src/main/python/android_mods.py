"""Mods: gameplay changes the player turns on, for the whole device.

Writes mods.json in the save folder, which the server reads again whenever it
changes (internal/mods), so a mod takes effect on the next call that uses it.
Every mod is off without the file: Bunker plays like the original game.
"Original" removes the file; "Comfort" turns on the Comfort Mod's set and
"Everything" every mod but the challenges.

Most mods come from the Lunar Tear Comfort Mod by NavHobbyDev (MIT):
https://github.com/NavHobbyDev/lunar-tear-comfort-mod
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from web import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))
import bunker_text  # noqa: E402
bunker_text.install(templates)  # Bunker's own text, in the chosen language

COMFORT_MOD = "https://github.com/NavHobbyDev/lunar-tear-comfort-mod"
MAX_MULTIPLIER = 10

# (group, [(key, kind, title, what it does)]). kind is "bool", "multiplier"
# (×1–×10) or "hard" (Hard enemies). Keys match internal/mods.Settings. A group's
# title is the catalogue's "pods.mods.group.<group>"; titles and what each mod
# does are catalogue keys, translated when the page shows them.
GROUPS = [
    ("quests", [
        ("staminaFree", "bool", "pods.mods.mod.stamina_free", "pods.mods.mod.stamina_free_info"),
        ("unlimitedDailyPlays", "bool", "pods.mods.mod.unlimited_daily_plays", "pods.mods.mod.unlimited_daily_plays_info"),
        ("freeSkips", "bool", "pods.mods.mod.free_skips", "pods.mods.mod.free_skips_info"),
        ("rewardMultiplier", "multiplier", "pods.mods.mod.reward_multiplier", "pods.mods.mod.reward_multiplier_info"),
        ("expMultiplier", "multiplier", "pods.mods.mod.exp_multiplier", "pods.mods.mod.exp_multiplier_info"),
    ]),
    ("items", [
        ("staminaItemsToGold", "bool", "pods.mods.mod.stamina_items_to_gold", "pods.mods.mod.stamina_items_to_gold_info"),
        ("ticketsToGems", "bool", "pods.mods.mod.tickets_to_gems", "pods.mods.mod.tickets_to_gems_info"),
        ("shopUnlimited", "bool", "pods.mods.mod.shop_unlimited", "pods.mods.mod.shop_unlimited_info"),
        ("lostItemGems", "bool", "pods.mods.mod.lost_item_gems", "pods.mods.mod.lost_item_gems_info"),
    ]),
    ("summons", [
        ("noDuplicateFourStar", "bool", "pods.mods.mod.no_duplicate_four_star", "pods.mods.mod.no_duplicate_four_star_info"),
        ("pityRewards", "bool", "pods.mods.mod.pity_rewards", "pods.mods.mod.pity_rewards_info"),
    ]),
    ("world", [
        ("storyFriends", "bool", "pods.mods.mod.story_friends", "pods.mods.mod.story_friends_info"),
    ]),
    ("challenges", [
        ("hardEnemies", "hard", "pods.mods.mod.hard_enemies", "pods.mods.mod.hard_enemies_info"),
        ("weaknessOnly", "bool", "pods.mods.mod.weakness_only", "pods.mods.mod.weakness_only_info"),
        ("slowSkills", "bool", "pods.mods.mod.slow_skills", "pods.mods.mod.slow_skills_info"),
    ]),
]
KEYS = [key for _, mods in GROUPS for key, *_ in mods]
KIND = {key: kind for _, mods in GROUPS for key, kind, *_ in mods}
CHALLENGE_KEYS = ("hardEnemies", "weaknessOnly", "slowSkills")
# Hard enemies: the enemies' strength and the reward bonus it pays.
HARD_ENEMIES = {1.5: 2, 2: 3, 3: 4, 5: 6}
OFF = {key: (1 if KIND[key] in ("multiplier", "hard") else False) for key in KEYS}
COMFORT_KEYS = ("staminaFree", "staminaItemsToGold", "ticketsToGems", "shopUnlimited", "lostItemGems",
                "noDuplicateFourStar", "pityRewards")
# (title, what it does, values); title and what are catalogue keys.
PRESETS = {
    "original": ("pods.mods.preset.original", "pods.mods.preset.original_info", {}),
    "comfort": ("pods.mods.preset.comfort", "pods.mods.preset.comfort_info",
                {**{key: True for key in COMFORT_KEYS}, "rewardMultiplier": MAX_MULTIPLIER}),
    "everything": ("pods.mods.preset.everything", "pods.mods.preset.everything_info",
                   {key: (MAX_MULTIPLIER if KIND[key] == "multiplier" else True)
                    for group, mods in GROUPS if group != "challenges" for key, *_ in mods}),
}


def comfort_on(settings):
    """Whether a Quests, Items & shops or Summons mod is on (as mods.Settings.Comfort)."""
    world = {key for group, mods in GROUPS if group in ("world", "challenges") for key, *_ in mods}
    return any(settings[k] > 1 if KIND[k] == "multiplier" else bool(settings[k]) for k in KEYS if k not in world)


def bonus_view(settings, paused=False):
    """The Challenges panel's bonus line: the bonus, and why it is what it is."""
    on = HARD_ENEMIES.get(settings.get("hardEnemies"), 1) > 1 or settings.get("weaknessOnly") or settings.get("slowSkills")
    full = challenge_bonus(settings) if not comfort_on(settings) else challenge_bonus({**OFF, **{k: settings[k] for k in CHALLENGE_KEYS}})
    if not on:
        reason = bunker_text.t("pods.mods.bonus_off")
    elif comfort_on(settings):
        reason = bunker_text.t("pods.mods.bonus_paused_comfort")
    elif paused:
        reason = bunker_text.t("pods.mods.bonus_paused_new_day")
    else:
        reason = bunker_text.t("pods.mods.bonus_earned")
    return {"bonus": full, "bonus_reason": reason, "bonus_paused": bool(on) and challenge_bonus(settings, paused) == 1,
            "new_day": bool(paused)}  # the page's live line, whatever the reason shown now


def challenge_bonus(settings, paused=False):
    """The reward bonus the challenges pay, as mods.Settings.ChallengeBonus."""
    if paused or comfort_on(settings):
        return 1
    bonus = HARD_ENEMIES.get(settings.get("hardEnemies"), 1)
    bonus *= 2 if settings.get("weaknessOnly") else 1
    bonus *= 2 if settings.get("slowSkills") else 1
    return min(bonus, MAX_MULTIPLIER)


def mods_path():
    return config.GAME_DB_PATH.parent / "mods.json"


def validate(settings):
    if set(settings) - set(KEYS):
        raise ValueError(bunker_text.t("pods.mods.error_unknown_mod"))
    for key in ("rewardMultiplier", "expMultiplier"):
        m = settings.get(key, 1)
        if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= MAX_MULTIPLIER:
            raise ValueError(bunker_text.t("pods.mods.error_reward_multiplier", max=MAX_MULTIPLIER)
                             if key == "rewardMultiplier" else
                             bunker_text.t("pods.mods.error_exp_multiplier", max=MAX_MULTIPLIER))
    h = settings.get("hardEnemies", 1)
    if isinstance(h, bool) or h not in (1, *HARD_ENEMIES):
        raise ValueError(bunker_text.t("pods.mods.error_hard_enemies"))


def read_settings(path=None):
    """The mods in use; a missing or invalid file means none."""
    try:
        saved = json.loads((path or mods_path()).read_text())
        settings = {**OFF, **{k: saved[k] for k in KEYS if k in saved}}
        for k in KEYS:
            if KIND[k] == "multiplier":
                settings[k] = int(settings[k] or 1)
            elif KIND[k] == "hard":
                h = float(settings[k] or 1)
                settings[k] = int(h) if h.is_integer() else h
            else:
                settings[k] = bool(settings[k])
        validate(settings)
        return settings
    except (OSError, ValueError, TypeError, KeyError):
        return dict(OFF)


def write_settings(settings, path=None):
    """Saves the mods; with every mod off, removes the file (the original game)."""
    settings = {**OFF, **settings}
    validate(settings)
    path = path or mods_path()
    if settings == OFF:
        path.unlink(missing_ok=True)
        return
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(settings, indent=2) + "\n")
    os.replace(pending, path)


def preset_of(settings):
    """The preset these settings match, or None."""
    for key, (_, _, values) in PRESETS.items():
        if settings == {**OFF, **values}:
            return key
    return None


@router.get("/mods")
def view(request: Request, message: str = "", error: str = ""):
    import android_patcher
    settings = read_settings()
    return templates.TemplateResponse(request, "mods.html", {**bonus_view(settings, android_patcher.new_day_today()),
        "active": "mods", "settings": settings, "groups": GROUPS,
        "presets": PRESETS, "current": preset_of(settings), "max_multiplier": MAX_MULTIPLIER, "hard_enemies": HARD_ENEMIES, "source": COMFORT_MOD,
        "message": message, "error": error})


def save_settings(settings):
    """Saves the mods; when a challenge changed, the game data is built again
    with them (android_challenges.reapply) with the server stopped around it,
    and the game goes back to its title screen. Returns whether it did."""
    import android_challenges as challenges
    import android_runtime as runtime
    before = read_settings()
    write_settings(settings)
    # Against what the game data has, not the last mods.json: a save that
    # failed part-way is applied again rather than taken as done.
    want, applied = challenges.wanted(read_settings()), challenges.applied_challenges()
    if all(want[k] == applied[k] for k in challenges.CHALLENGES):  # the language's texts are Language's business
        return False
    live = runtime.game_live()
    if live:
        error = runtime.pause_game()
        if error:
            write_settings(before)
            raise RuntimeError(error)
    try:
        challenges.reapply()
    except Exception:
        write_settings(before)  # mods.json stays as the game data is
        raise
    finally:
        if live:
            error = runtime.resume_game(True)
            if error:
                runtime.log.warning("The server did not start again after the challenges changed: %s", error)
    return True


def saved_message(title, reapplied, settings):
    """title: what was saved ("Saved.", already translated), then what happens next."""
    import android_challenges as challenges
    import android_runtime as runtime
    if reapplied and challenges.active(settings):
        return bunker_text.t("pods.mods.saved_challenges_on", saved=title, next=runtime.next_step())
    if reapplied:
        return bunker_text.t("pods.mods.saved_challenges_off", saved=title, next=runtime.next_step())
    return bunker_text.t("pods.mods.saved_next_action", saved=title)


@router.post("/mods")
async def save(request: Request):
    form = await request.form()
    try:
        # Off the event loop: a challenge change rewrites the game data for seconds.
        reapplied = await run_in_threadpool(save_settings, {k: form_value(k, form.get(k)) for k in KEYS})
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=saved_message(bunker_text.t("pods.mods.saved"), reapplied, read_settings()))


@router.post("/mods/preset")
async def preset(request: Request):
    name = (await request.form()).get("name")
    if name not in PRESETS:
        return redirect(error=bunker_text.t("common.unknown_preset"))
    title, _, values = PRESETS[name]
    try:
        reapplied = await run_in_threadpool(save_settings, values)
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=saved_message(bunker_text.t("pods.mods.preset_saved", preset=bunker_text.t(title)), reapplied, read_settings()))


def form_value(key, raw):
    """A mod's value from the page's form."""
    if KIND[key] == "multiplier":
        return int(raw or 1)
    if KIND[key] == "hard":
        h = float(raw or 1)
        return int(h) if h.is_integer() else h
    return raw == "on"


def redirect(**kwargs):
    return RedirectResponse("/mods?" + urlencode(kwargs), status_code=303)
