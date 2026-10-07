"""Summon rates, used by the next draw.

Writes gacha_rates.json in the save folder, which the server reads before each
premium draw (internal/gacha/rates.go). The game's "Rates" page shows the same
values. Deleting the file, or Reset, brings back Lunar Tear's rates.
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from web import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))
DEFAULTS = {"fourStarPercent": 5.0, "threeStarPercent": 15.0, "fourStarCostumeShare": 40.0,
            "threeStarCostumeShare": round(100 / 3, 4), "featuredPercent": 35.0, "stepUpBoost": True, "multiMinRarity": 3}
PRESETS = [
    ("default", "Default (5% ★4, 15% ★3)", {}),
    ("generous", "Generous (15% ★4, 30% ★3)", {"fourStarPercent": 15.0, "threeStarPercent": 30.0}),
    ("featured", "Featured first (10% ★4, always featured, ★4 in every 10-draw)",
     {"fourStarPercent": 10.0, "featuredPercent": 100.0, "multiMinRarity": 4}),
]


def rates_path():
    return config.GAME_DB_PATH.parent / "gacha_rates.json"


def validate(s):
    if not 0.1 <= s["fourStarPercent"] <= 100:
        raise ValueError("★4 rate must be between 0.1% and 100%")
    if s["threeStarPercent"] < 0 or s["fourStarPercent"] + s["threeStarPercent"] > 100:
        raise ValueError("★4 and ★3 together must be at most 100%")
    for key in ("fourStarCostumeShare", "threeStarCostumeShare", "featuredPercent"):
        if not 0 <= s[key] <= 100:
            raise ValueError("Shares must be between 0% and 100%")
    if s["multiMinRarity"] not in (3, 4):
        raise ValueError("The 10-draw guarantee must be ★3 or ★4")


def read_settings(path=None):
    """The saved rates; a missing or invalid file means the defaults."""
    settings = dict(DEFAULTS)
    try:
        saved = json.loads((path or rates_path()).read_text())
        merged = {**settings, **{k: saved[k] for k in DEFAULTS if k in saved}}
        merged["multiMinRarity"] = int(merged["multiMinRarity"])
        merged["stepUpBoost"] = bool(merged["stepUpBoost"])
        for k in ("fourStarPercent", "threeStarPercent", "fourStarCostumeShare", "threeStarCostumeShare", "featuredPercent"):
            merged[k] = float(merged[k])
        validate(merged)
        return merged
    except (OSError, ValueError, TypeError, KeyError):
        return settings


def write_settings(settings, path=None):
    validate(settings)
    path = path or rates_path()
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(settings, indent=2) + "\n")
    os.replace(pending, path)


def reset(path=None):
    (path or rates_path()).unlink(missing_ok=True)


@router.get("/gacha")
def view(request: Request, message: str = "", error: str = ""):
    s = read_settings()
    return templates.TemplateResponse(request, "gacha.html", {"active": "gacha", "settings": s, "presets": PRESETS,
        "two_star": round(100 - s["fourStarPercent"] - s["threeStarPercent"], 3), "message": message, "error": error})


@router.post("/gacha")
def save(four: float = Form(...), three: float = Form(...), four_costume: float = Form(...), three_costume: float = Form(...),
         featured: float = Form(...), guarantee: int = Form(...), stepup: str = Form("")):
    try:
        write_settings({"fourStarPercent": four, "threeStarPercent": three, "fourStarCostumeShare": four_costume,
                        "threeStarCostumeShare": three_costume, "featuredPercent": featured, "stepUpBoost": stepup == "on",
                        "multiMinRarity": guarantee})
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message="Saved. The next summon uses these rates.")


@router.post("/gacha/preset")
def preset(name: str = Form(...)):
    for key, _, values in PRESETS:
        if key == name:
            if not values:
                reset()
                return redirect(message="Back to the default rates.")
            write_settings({**DEFAULTS, **values})
            return redirect(message="Saved. The next summon uses these rates.")
    return redirect(error="Unknown preset")


def redirect(**kwargs):
    return RedirectResponse("/gacha?" + urlencode(kwargs), status_code=303)
