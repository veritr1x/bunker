"""Frame rate, resolution, screen area and texture size for the game, applied the next time it opens.

Writes tools/display.conf, which the game's process reads before Unity starts
(DisplayPatch.java on Android). That process writes tools/display.status:
"ok", or "error=<reason>" when the game could not be changed.
"""
from __future__ import annotations

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
# Each choice: its value in display.conf, and its words' key in Bunker's catalogue (bunker_text: translated as the page is drawn).
FPS = [("30", "pods.display.option.fps_30"), ("60", "pods.display.option.fps_60"), ("90", "pods.display.option.fps_90"),
       ("120", "pods.display.option.fps_120"), ("max", "pods.display.option.fps_max")]
RESOLUTIONS = [("540", "pods.display.option.res_540"), ("640", "pods.display.option.res_640"), ("default", "pods.display.option.res_default"),
               ("1080", "pods.display.option.res_1080"), ("1440", "pods.display.option.res_1440"), ("native", "pods.display.option.res_native")]
SCREENS = [("full", "pods.display.option.screen_full"), ("safe", "pods.display.option.screen_safe")]
# Unity's texture-mipmap-skip-level, on the game's command line (DisplayPatch.unityArguments): each
# step halves the width and height of every texture with mipmaps; menus have none.
TEXTURES = [("full", "pods.display.option.textures_full"), ("half", "pods.display.option.textures_half"), ("quarter", "pods.display.option.textures_quarter")]
# Above 30 fps (render_pace.c): draw 30 a second after 2 s without a touch outside battles,
# and slow down when the device reports it is hot.
IDLE = [("on", "pods.display.option.idle_on"), ("off", "pods.display.option.keep_rate")]
HEAT = [("on", "pods.display.option.heat_on"), ("off", "pods.display.option.keep_rate")]
# The game's effects (render_effects.c): each costs GPU time every frame, more at high resolutions.
EFFECT = [("on", "pods.display.option.effect_on"), ("off", "pods.display.option.effect_off")]
EFFECTS = ("shadows", "reflections", "bloom")
# Below the screen's own resolution the picture is stretched to the screen. Android can use FSR 1 or
# SGSR instead (render_scale.c); iPhone and iPad MetalFX (LunarUpscale.m), which ios_runtime puts in their place.
UPSCALE = [("off", "pods.display.option.upscale_off"), ("fsr", "pods.display.option.upscale_fsr"), ("sgsr", "pods.display.option.upscale_sgsr")]
UPSCALE_IOS = [("metalfx", "pods.display.option.upscale_metalfx")]
# In a window of another shape (an iPad's Stage Manager window, an external display such as a TV)
# the picture is stretched to it; iPhone and iPad can keep its shape with black bars instead
# (LunarWindow.m, LunarUpscale.m), which ios_runtime offers.
WINDOW = [("stretch", "pods.display.option.window_stretch")]
WINDOW_IOS = [("fit", "pods.display.option.window_fit")]
DEFAULTS = {"fps": "30", "resolution": "default", "screen": "full", "textures": "full", "idle": "on", "heat": "on",
            "shadows": "on", "reflections": "on", "bloom": "on", "upscale": "off", "window": "stretch"}


def conf_path():
    return config.DATA_DIR / "display.conf"


def read_settings(path=None):
    """The saved choices; unknown or missing values fall back to the game's own."""
    settings = dict(DEFAULTS)
    try:
        lines = (path or conf_path()).read_text().splitlines()
    except OSError:
        return settings
    allowed = {"fps": dict(FPS), "resolution": dict(RESOLUTIONS), "screen": dict(SCREENS), "textures": dict(TEXTURES), "idle": dict(IDLE), "heat": dict(HEAT),
               **{name: dict(EFFECT) for name in EFFECTS}, "upscale": dict(UPSCALE), "window": dict(WINDOW)}
    for line in lines:
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key in allowed and value in allowed[key]:
            settings[key] = value
    return settings


def write_settings(fps, resolution, screen, path=None, textures="full", idle="on", heat="on", shadows="on", reflections="on", bloom="on",
                   upscale="off", window="stretch"):
    if (fps not in dict(FPS) or resolution not in dict(RESOLUTIONS) or screen not in dict(SCREENS) or textures not in dict(TEXTURES)
            or idle not in dict(IDLE) or heat not in dict(HEAT) or any(v not in dict(EFFECT) for v in (shadows, reflections, bloom)) or upscale not in dict(UPSCALE) or window not in dict(WINDOW)):
        raise ValueError(bunker_text.t("pods.display.unknown_setting"))
    path = path or conf_path()
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(f"fps={fps}\nresolution={resolution}\nscreen={screen}\ntextures={textures}\nidle={idle}\nheat={heat}\n"
                       f"shadows={shadows}\nreflections={reflections}\nbloom={bloom}\nupscale={upscale}\nwindow={window}\n")
    os.replace(pending, path)


def last_result():
    """What happened the last time the game opened with these choices, or None."""
    try:
        text = (config.DATA_DIR / "display.status").read_text().strip()
    except OSError:
        return None
    if text == "ok":
        return {"ok": True}
    error = text.removeprefix("error=")
    # What the iOS launcher knows is written as a code, shown in the page's language; anything else as it is.
    return {"ok": False, "error": KNOWN_FAILURES[error]() if error in KNOWN_FAILURES else error}


KNOWN_FAILURES = {"il2cpp-missing": lambda: bunker_text.t("pods.display.il2cpp_missing")}


@router.get("/display")
def view(request: Request, message: str = "", error: str = ""):
    # The options' words are catalogue keys: display.html translates them (t(title)).
    return templates.TemplateResponse(request, "display.html", {"active": "display", "settings": read_settings(), "fps_options": FPS,
        "resolution_options": RESOLUTIONS, "screen_options": SCREENS, "texture_options": TEXTURES, "idle_options": IDLE, "heat_options": HEAT, "effect_options": EFFECT, "upscale_options": UPSCALE, "window_options": WINDOW, "result": last_result(), "message": message, "error": error})


@router.post("/display")
def save(fps: str = Form(...), resolution: str = Form(...), screen: str = Form("full"), textures: str = Form("full"), idle: str = Form("on"),
         heat: str = Form("on"), shadows: str = Form("on"), reflections: str = Form("on"), bloom: str = Form("on"),
         upscale: str = Form("off"), window: str = Form("stretch")):
    try:
        write_settings(fps, resolution, screen, textures=textures, idle=idle, heat=heat, shadows=shadows, reflections=reflections, bloom=bloom, upscale=upscale, window=window)
        # The status describes the previous choices until the game opens again.
        (config.DATA_DIR / "display.status").unlink(missing_ok=True)
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=bunker_text.t("pods.runtime.saved", next=bunker_text.t("pods.runtime.deploy")))


def redirect(**kwargs):
    return RedirectResponse("/display?" + urlencode(kwargs), status_code=303)
