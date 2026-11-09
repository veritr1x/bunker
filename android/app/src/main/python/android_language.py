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
import bunker_text  # noqa: E402
from bunker_text import number, t, t_count  # noqa: E402
bunker_text.install(templates)  # Bunker's own text, in the chosen language
SHIPPED = SHIPPED_DIR


def languages() -> Languages:
    return for_config(config, SHIPPED)


def supported() -> bool:
    """The game files have English text (the global client; the Japanese one has none)."""
    revision = config.REVISIONS_DIR / "0"
    return any((revision / tree / "assetbundle" / "text" / "en").is_dir() for tree in ("", "android", "ios"))


def texts(n: int) -> str:
    """"1 text", "2,345 texts", in the chosen language."""
    return t_count("pods.language.texts", n, count=number(n))


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
        return t("pods.language.waiting")
    name = status.get("name") or status.get("language")
    state = status.get("state")
    if state == "building":
        return t("pods.language.building", name=name)
    if state == "ready":
        kept = len(status.get("skipped") or [])
        bundles = status.get("bundles", 0)
        files = t_count("pods.language.text_files", bundles, count=number(bundles))
        if kept:
            return t("pods.language.ready_kept", name=name, files=files, kept=number(kept))
        return t("pods.language.ready", name=name, files=files)
    error = status["error"] if "error" in status else t("pods.language.unknown_error")
    if state == "failed" and not name:
        return t("pods.language.unreadable", error=error)
    if state == "failed":
        return t("pods.language.not_applied", name=name, error=error)
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
        "status_state": status.get("state") if describes(status, current, packs) else "waiting", "supported": supported(), "texts": texts,
        "message": message, "error": error})


def unchanged(response):
    """The game's language did not change: the game plays on (android_runtime.changed_game)."""
    response.headers["X-Bunker-Unchanged"] = "1"
    return response


@router.post("/language")
def choose(choice: str = Form("")):
    if not choice:
        return unchanged(redirect(error=t("pods.language.choose_first")))
    if choice != "en" and not supported():  # English stays possible, to clear a pack left from other game files
        return redirect(error=t("pods.language.unsupported"))
    langs = languages()
    if choice == langs.active():
        return unchanged(redirect(message=t("pods.language.in_use")))
    try:
        langs.choose(choice)
    except PackError as exc:
        return redirect(error=str(exc))
    bunker_text.reload()  # Bunker's own pages follow the choice at once
    import android_challenges as challenges
    challenges.reapply_texts()  # the game data's texts (shop lines, gift texts…) follow it too
    import android_runtime
    if choice == "en":
        return redirect(message=t("pods.language.chose_english", next=android_runtime.next_step()))
    return redirect(message=t("pods.language.pack_set", next=android_runtime.next_step()))


@router.post("/language/load")
def load(pack: UploadFile = File(...)):
    data = pack.file.read(MAX_PACK_BYTES + 1)
    try:
        info = languages().load(data)
    except PackError as exc:
        return redirect(error=str(exc))
    return redirect(message=t("pods.language.loaded", name=info.name, texts=texts(info.texts)))


@router.post("/language/remove")
def remove(language: str = Form(...)):
    langs = languages()
    in_use = langs.active() == f"loaded:{language}"
    try:
        langs.remove(language)
    except PackError as exc:
        return redirect(error=str(exc))
    if in_use:
        bunker_text.reload()
        import android_challenges as challenges
        challenges.reapply_texts()  # back to the game data's own English
        import android_runtime
        return redirect(message=t("pods.language.removed_in_use", language=language, next=android_runtime.next_step()))
    return unchanged(redirect(message=t("pods.language.removed", language=language)))


def redirect(**kwargs):
    return RedirectResponse("/language?" + urlencode(kwargs), status_code=303)
