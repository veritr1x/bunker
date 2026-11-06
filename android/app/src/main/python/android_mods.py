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

from web import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))

COMFORT_MOD = "https://github.com/NavHobbyDev/lunar-tear-comfort-mod"
MAX_MULTIPLIER = 10

# (group, [(key, kind, title, what it does)]). kind is "bool", "multiplier"
# (×1–×10) or "hard" (Hard enemies). Keys match internal/mods.Settings.
GROUPS = [
    ("Quests", [
        ("staminaFree", "bool", "Free stamina", "Quests and skips cost no stamina."),
        ("unlimitedDailyPlays", "bool", "Unlimited daily plays", "Quests with a daily clear limit can be played as often as you like."),
        ("freeSkips", "bool", "Free skips", "Skipping a quest uses no skip tickets."),
        ("rewardMultiplier", "multiplier", "Reward multiplier", "Multiplies a quest's drops, gold and gems. Dark Memory quests, memoirs, costumes and weapons stay as they are."),
        ("expMultiplier", "multiplier", "EXP multiplier", "Multiplies the EXP a quest gives you, your characters and their costumes."),
    ]),
    ("Items & shops", [
        ("staminaItemsToGold", "bool", "Stamina items become gold", "Stamina recovery items you receive arrive as gold instead. Items you already hold stay."),
        ("ticketsToGems", "bool", "Premium tickets become gems", "Premium summon tickets you receive arrive as free gems instead. Tickets you already hold stay."),
        ("shopUnlimited", "bool", "Unlimited shop stock", "Shop items that restock daily, weekly or monthly never run out. Items with a lifetime limit keep it."),
        ("lostItemGems", "bool", "Lost Items give gems", "Picking up a Lost Item gives a random amount of free gems."),
    ]),
    ("Summons", [
        ("noDuplicateFourStar", "bool", "No duplicate ★4", "A ★4 costume or weapon you already own is swapped for one you don't from the same summon, until you own them all."),
        ("pityRewards", "bool", "Medals become gems", "Every 100 summon medals become 1,000 paid gems and 100 Mama Points, sent to the gift box."),
    ]),
    ("World", [
        ("storyFriends", "bool", "Friends from the story", "2B, 9S, Fio, Lars and others join your friends, cheer you every day and fight with their own costumes in the Arena."),
    ]),
    ("Challenges", [
        ("hardEnemies", "hard", "Hard enemies", "Every enemy's HP, attack and defense, in quests and events. Subjugation bosses stay as they are."),
        ("weaknessOnly", "bool", "Weakness only", "Hits that aren't super-effective do half damage. Rewards ×2."),
        ("slowSkills", "bool", "Slow skills", "Your skills take 50% longer to come back. Rewards ×2."),
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
PRESETS = {
    "original": ("Original", "Every mod off: the game as it was.", {}),
    "comfort": ("Comfort", "The Comfort Mod's set: its eight mods on, rewards ×10.",
                {**{key: True for key in COMFORT_KEYS}, "rewardMultiplier": MAX_MULTIPLIER}),
    "everything": ("Everything", "Every mod on, rewards and EXP ×10. Challenges stay off.",
                   {key: (MAX_MULTIPLIER if KIND[key] == "multiplier" else True)
                    for group, mods in GROUPS if group != "Challenges" for key, *_ in mods}),
}


def comfort_on(settings):
    """Whether a Quests, Items & shops or Summons mod is on (as mods.Settings.Comfort)."""
    world = {key for group, mods in GROUPS if group in ("World", "Challenges") for key, *_ in mods}
    return any(settings[k] > 1 if KIND[k] == "multiplier" else bool(settings[k]) for k in KEYS if k not in world)


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
        raise ValueError("Unknown mod")
    for key, title in (("rewardMultiplier", "reward"), ("expMultiplier", "EXP")):
        m = settings.get(key, 1)
        if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= MAX_MULTIPLIER:
            raise ValueError(f"The {title} multiplier must be 1–{MAX_MULTIPLIER}")
    h = settings.get("hardEnemies", 1)
    if isinstance(h, bool) or h not in (1, *HARD_ENEMIES):
        raise ValueError("Hard enemies must be 1.5, 2, 3 or 5")


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
    settings = read_settings()
    return templates.TemplateResponse(request, "mods.html", {"active": "mods", "settings": settings, "groups": GROUPS,
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
    after = read_settings()
    if all(before[k] == after[k] for k in CHALLENGE_KEYS):
        return False
    live = runtime.game_live()
    if live:
        error = runtime.pause_game()
        if error:
            write_settings(before)
            raise RuntimeError(error)
    try:
        challenges.reapply()
    finally:
        if live:
            runtime.resume_game(True)
    return True


def saved_message(title, reapplied):
    import android_runtime as runtime
    if reapplied:
        return f"{title} Challenges are in the game data. " + runtime.next_step()
    return f"{title} The mods are in use from the game's next action, with no restart."


@router.post("/mods")
async def save(request: Request):
    form = await request.form()
    try:
        reapplied = save_settings({k: form_value(k, form.get(k)) for k in KEYS})
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=saved_message("Saved.", reapplied))


@router.post("/mods/preset")
async def preset(request: Request):
    name = (await request.form()).get("name")
    if name not in PRESETS:
        return redirect(error="Unknown preset")
    title, _, values = PRESETS[name]
    try:
        reapplied = save_settings(values)
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=saved_message(f"{title} preset saved.", reapplied))


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
