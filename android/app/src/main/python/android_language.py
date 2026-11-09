"""Pod Programs › Language: play in a language the game never had.

The choice is a copy of the chosen pack at <assetRoot>/translation/active.json, which the server
applies as it starts (overlays/server/internal/translation). Choosing goes through Pod Programs'
game guard like any change: the server stops, the pack is set, the server starts again with it and
the game goes back to its title screen.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from bunker_language import MAX_PACK_BYTES, Languages, PackError
from web import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))
SHIPPED = Path(__file__).resolve().parent / "shipped_languages"
UNSUPPORTED = "Translation needs the global (English) game files: these have no English text."


def languages() -> Languages:
    return Languages(config.ASSETS_DIR.parent / "translation", SHIPPED)


def supported() -> bool:
    """The game files have English text (the global client; the Japanese one has none)."""
    revision = config.REVISIONS_DIR / "0"
    return any((revision / tree / "assetbundle" / "text" / "en").is_dir() for tree in ("", "android", "ios"))


def status_line(status: dict) -> str:
    name = status.get("name") or status.get("language") or "the pack"
    state = status.get("state")
    if state == "building":
        return f"Building {name}… The game gets it the next time it loads its file list."
    if state == "ready":
        kept = len(status.get("skipped") or [])
        line = f"Ready: {name}, {status.get('bundles', 0):,} text files translated"
        return line + (f", {kept:,} kept in English." if kept else ".")
    if state == "failed":
        return f"{name} could not be applied: {status.get('error', 'unknown error')}. It is tried again the next time the server starts."
    return ""


@router.get("/language")
def view(request: Request, message: str = "", error: str = ""):
    langs = languages()
    status = langs.status()
    return templates.TemplateResponse(request, "language.html", {
        "active": "language", "packs": langs.packs(), "current": langs.active(), "status": status,
        "status_line": status_line(status), "status_state": status.get("state"), "supported": supported(),
        "message": message, "error": error})


@router.post("/language")
def choose(choice: str = Form(...)):
    if not supported():
        return redirect(error=UNSUPPORTED)
    try:
        languages().choose(choice)
    except PackError as exc:
        return redirect(error=str(exc))
    import android_runtime
    what = "English" if choice == "en" else "The pack is set"
    return redirect(message=f"{what}. {android_runtime.next_step()}")


@router.post("/language/load")
def load(pack: UploadFile = File(...)):
    data = pack.file.read(MAX_PACK_BYTES + 1)
    try:
        info = languages().load(data)
    except PackError as exc:
        return redirect(error=str(exc))
    return redirect(message=f"Loaded {info.name} ({info.texts:,} texts). Choose it below to use it.")


@router.post("/language/remove")
def remove(language: str = Form(...)):
    try:
        languages().remove(language)
    except PackError as exc:
        return redirect(error=str(exc))
    return redirect(message=f"Removed the {language} pack.")


def redirect(**kwargs):
    return RedirectResponse("/language?" + urlencode(kwargs), status_code=303)
