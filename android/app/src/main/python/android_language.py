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

from bunker_language import MAX_PACK_BYTES, SHIPPED_DIR, Languages, PackError, for_config
from web import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))
SHIPPED = SHIPPED_DIR
UNSUPPORTED = "Language packs need the global game files: these have no English text."


def languages() -> Languages:
    return for_config(config, SHIPPED)


def supported() -> bool:
    """The game files have English text (the global client; the Japanese one has none)."""
    revision = config.REVISIONS_DIR / "0"
    return any((revision / tree / "assetbundle" / "text" / "en").is_dir() for tree in ("", "android", "ios"))


def count(n: int, word: str) -> str:
    """"1 text", "2 texts"."""
    return f"{n:,} {word}" + ("" if n == 1 else "s")


WAITING = "Saved. It applies the next time Lunar Tear starts."


def describes(status: dict, current: str, packs) -> bool:
    """Whether the server's status (from its last start) is about the current choice, or about one made before it."""
    state = status.get("state")
    if current == "en":
        return state == "off"
    if current == "other" or (state == "failed" and not status.get("language")):
        return True  # nothing to compare: a pack the page does not list, or one the server could not read
    if state == "off":
        return False  # a pack was chosen since the server last started
    pack = next((p for p in packs if f"{p.source}:{p.language}" == current), None)
    return pack is not None and status.get("language") == pack.language and (status.get("version") or "") == (pack.version or "")


def status_line(status: dict, current: str = "", packs=()) -> str:
    if not describes(status, current, packs):
        return WAITING
    name = status.get("name") or status.get("language")
    state = status.get("state")
    if state == "building":
        return f"Building {name}…"
    if state == "ready":
        kept = len(status.get("skipped") or [])
        line = f"Ready: {name}, {count(status.get('bundles', 0), 'text file')} translated"
        return line + (f", {kept:,} kept in English." if kept else ".")
    if state == "failed" and not name:
        return f"The chosen pack could not be read: {status.get('error', 'unknown error')}."
    if state == "failed":
        return f"{name} could not be applied: {status.get('error', 'unknown error')}."
    return ""


@router.get("/language")
def view(request: Request, message: str = "", error: str = ""):
    langs = languages()
    langs.refresh()  # a revised shipped pack, if launchers did not already bring it in
    packs = langs.packs()  # read once: a full pack is tens of MB
    status = langs.status()
    current = langs.active(packs)
    return templates.TemplateResponse(request, "language.html", {
        "active": "language", "packs": packs, "current": current, "status": status,
        "status_line": status_line(status, current, packs),
        "status_state": status.get("state") if describes(status, current, packs) else "waiting", "supported": supported(), "count": count,
        "message": message, "error": error})


def unchanged(response):
    """The game's language did not change: the game plays on (android_runtime.changed_game)."""
    response.headers["X-Bunker-Unchanged"] = "1"
    return response


@router.post("/language")
def choose(choice: str = Form("")):
    if not choice:
        return unchanged(redirect(error="Choose a language first."))
    if choice != "en" and not supported():  # English stays possible, to clear a pack left from other game files
        return redirect(error=UNSUPPORTED)
    langs = languages()
    if choice == langs.active():
        return unchanged(redirect(message="That language is already in use."))
    try:
        langs.choose(choice)
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
    return redirect(message=f"Loaded {info.name} ({count(info.texts, 'text')}). Choose it below to use it.")


@router.post("/language/remove")
def remove(language: str = Form(...)):
    langs = languages()
    in_use = langs.active() == f"loaded:{language}"
    try:
        langs.remove(language)
    except PackError as exc:
        return redirect(error=str(exc))
    if in_use:
        import android_runtime
        return redirect(message=f"Removed the {language} pack; back to English. {android_runtime.next_step()}")
    return unchanged(redirect(message=f"Removed the {language} pack."))


def redirect(**kwargs):
    return RedirectResponse("/language?" + urlencode(kwargs), status_code=303)
