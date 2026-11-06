"""Mods: gameplay changes the player turns on, for the whole device.

Writes mods.json in the save folder, which the server reads again whenever it
changes (internal/mods), so a mod takes effect on the next call that uses it.
Every mod is off without the file: Bunker plays like the original game.
"Original" removes the file; "Comfort" turns on the Comfort Mod's set.

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

# (group, [(key, title, what it does)]). Booleans unless the
# key is rewardMultiplier. Keys match internal/mods.Settings.
GROUPS = [
    ("Economy", [
        ("staminaFree", "Free stamina", "Quests and skips cost no stamina."),
        ("staminaItemsToGold", "Stamina items become gold", "Stamina recovery items you receive arrive as gold instead. Items you already hold stay."),
        ("ticketsToGems", "Premium tickets become gems", "Premium summon tickets you receive arrive as free gems instead. Tickets you already hold stay."),
        ("shopUnlimited", "Unlimited shop stock", "Shop items that restock daily, weekly or monthly never run out. Items with a lifetime limit keep it."),
        ("lostItemGems", "Lost Items give gems", "Picking up a Lost Item gives a random amount of free gems."),
    ]),
    ("Quests", [
        ("rewardMultiplier", "Reward multiplier", "Multiplies a quest's drops, gold and gems. Dark Memory quests, memoirs, costumes and weapons stay as they are."),
    ]),
    ("Summons", [
        ("noDuplicateFourStar", "No duplicate ★4", "A ★4 costume or weapon you already own is swapped for one you don't from the same summon, until you own them all."),
        ("pityRewards", "Medals become gems", "Every 100 summon medals become 1,000 paid gems and 100 Mama Points, sent to the gift box."),
    ]),
]
KEYS = [key for _, mods in GROUPS for key, *_ in mods]
OFF = {key: (1 if key == "rewardMultiplier" else False) for key in KEYS}
PRESETS = {
    "original": ("Original", "Every mod off: the game as it was.", {}),
    "comfort": ("Comfort", "The Comfort Mod's set: every mod on, rewards ×10.",
                {**{key: True for key in KEYS}, "rewardMultiplier": MAX_MULTIPLIER}),
}


def mods_path():
    return config.GAME_DB_PATH.parent / "mods.json"


def validate(settings):
    if set(settings) - set(KEYS):
        raise ValueError("Unknown mod")
    m = settings.get("rewardMultiplier", 1)
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= MAX_MULTIPLIER:
        raise ValueError(f"The reward multiplier must be 1–{MAX_MULTIPLIER}")


def read_settings(path=None):
    """The mods in use; a missing or invalid file means none."""
    try:
        saved = json.loads((path or mods_path()).read_text())
        settings = {**OFF, **{k: saved[k] for k in KEYS if k in saved}}
        settings["rewardMultiplier"] = int(settings["rewardMultiplier"] or 1)
        for k in KEYS:
            if k != "rewardMultiplier":
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
        "presets": PRESETS, "current": preset_of(settings), "max_multiplier": MAX_MULTIPLIER, "source": COMFORT_MOD,
        "message": message, "error": error})


@router.post("/mods")
async def save(request: Request):
    form = await request.form()
    try:
        m = int(form.get("rewardMultiplier") or 1)
        write_settings({**{k: form.get(k) == "on" for k in KEYS if k != "rewardMultiplier"}, "rewardMultiplier": m})
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message="Saved. The mods are in use from the game's next action, with no restart.")


@router.post("/mods/preset")
async def preset(request: Request):
    name = (await request.form()).get("name")
    if name not in PRESETS:
        return redirect(error="Unknown preset")
    title, _, values = PRESETS[name]
    write_settings(values)
    return redirect(message=f"{title} preset saved.")


def redirect(**kwargs):
    return RedirectResponse("/mods?" + urlencode(kwargs), status_code=303)
