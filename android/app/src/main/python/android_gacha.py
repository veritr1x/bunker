"""Summon rates, used by the next draw.

Writes gacha_rates.json in the save folder, which the server reads before each
premium draw (internal/gacha/rates.go). The game's "Rates" page shows the same
values. Deleting the file, or Reset, brings back Lunar Tear's rates.

The Special Gift Roulette's chances go to roulette_rates.json beside it, read
by the server on the next spin (internal/gacha/roulette.go).
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
import bunker_text  # noqa: E402
bunker_text.install(templates)  # Bunker's own text, in the chosen language
DEFAULTS = {"fourStarPercent": 5.0, "threeStarPercent": 15.0, "fourStarCostumeShare": 40.0,
            "threeStarCostumeShare": round(100 / 3, 4), "featuredPercent": 35.0, "stepUpBoost": True, "multiMinRarity": 3}
# (name, title, values); the title is a catalogue key, translated on the page.
PRESETS = [
    ("default", "pods.gacha.preset.default", {}),
    ("generous", "pods.gacha.preset.generous", {"fourStarPercent": 15.0, "threeStarPercent": 30.0}),
    ("featured", "pods.gacha.preset.featured",
     {"fourStarPercent": 10.0, "featuredPercent": 100.0, "multiMinRarity": 4}),
]


# The wheel's amounts and their default chances (server: RouletteGems, DefaultRouletteRates).
ROULETTE_GEMS = (10, 30, 50, 100, 3000)
ROULETTE_DEFAULTS = [60.0, 25.0, 10.0, 4.7, 0.3]


def roulette_path():
    return config.GAME_DB_PATH.parent / "roulette_rates.json"


def validate_roulette(percents):
    if len(percents) != len(ROULETTE_GEMS) or any(not 0 <= p <= 100 for p in percents):
        raise ValueError(bunker_text.t("pods.gacha.error_roulette_range"))
    if abs(sum(percents) - 100) > 0.001:
        total = round(sum(percents), 3)
        raise ValueError(bunker_text.t("pods.gacha.error_roulette_total", total=total))


def read_roulette(path=None):
    """The saved roulette chances; a missing or invalid file means the defaults."""
    try:
        percents = [float(p) for p in json.loads((path or roulette_path()).read_text())["percents"]]
        validate_roulette(percents)
        return percents
    except (OSError, ValueError, TypeError, KeyError):
        return list(ROULETTE_DEFAULTS)


def write_roulette(percents, path=None):
    validate_roulette(percents)
    path = path or roulette_path()
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps({"percents": percents}, indent=2) + "\n")
    os.replace(pending, path)


def rates_path():
    return config.GAME_DB_PATH.parent / "gacha_rates.json"


def validate(s):
    if not 0.1 <= s["fourStarPercent"] <= 100:
        raise ValueError(bunker_text.t("pods.gacha.error_four_rate"))
    if s["threeStarPercent"] < 0 or s["fourStarPercent"] + s["threeStarPercent"] > 100:
        raise ValueError(bunker_text.t("pods.gacha.error_four_three"))
    for key in ("fourStarCostumeShare", "threeStarCostumeShare", "featuredPercent"):
        if not 0 <= s[key] <= 100:
            raise ValueError(bunker_text.t("pods.gacha.error_shares"))
    if s["multiMinRarity"] not in (3, 4):
        raise ValueError(bunker_text.t("pods.gacha.error_guarantee"))


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
        "two_star": round(100 - s["fourStarPercent"] - s["threeStarPercent"], 3), "message": message, "error": error,
        "roulette": list(zip(ROULETTE_GEMS, read_roulette()))})


@router.post("/gacha/roulette")
def save_roulette(g10: float = Form(...), g30: float = Form(...), g50: float = Form(...), g100: float = Form(...),
                  g3000: float = Form(...), action: str = Form("save")):
    if action == "reset":
        roulette_path().unlink(missing_ok=True)
        return redirect(message=bunker_text.t("pods.gacha.roulette_reset"))
    try:
        write_roulette([g10, g30, g50, g100, g3000])
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=bunker_text.t("pods.gacha.roulette_saved"))


@router.post("/gacha")
def save(four: float = Form(...), three: float = Form(...), four_costume: float = Form(...), three_costume: float = Form(...),
         featured: float = Form(...), guarantee: int = Form(...), stepup: str = Form("")):
    try:
        write_settings({"fourStarPercent": four, "threeStarPercent": three, "fourStarCostumeShare": four_costume,
                        "threeStarCostumeShare": three_costume, "featuredPercent": featured, "stepUpBoost": stepup == "on",
                        "multiMinRarity": guarantee})
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=bunker_text.t("pods.gacha.saved"))


@router.post("/gacha/preset")
def preset(name: str = Form(...)):
    for key, _, values in PRESETS:
        if key == name:
            if not values:
                reset()
                return redirect(message=bunker_text.t("pods.gacha.back_to_default"))
            write_settings({**DEFAULTS, **values})
            return redirect(message=bunker_text.t("pods.gacha.saved"))
    return redirect(error=bunker_text.t("common.unknown_preset"))


def redirect(**kwargs):
    return RedirectResponse("/gacha?" + urlencode(kwargs), status_code=303)
