"""Host for the Archive: its own private loopback server, separate from Pod Programs.

Android calls start() through Chaquopy; iOS calls it from ios_runtime with its
own converters.

The Archive only reads the imported game files and master data, so it runs
beside Lunar Tear and the game; nothing is stopped and the save is never opened.
"""
from __future__ import annotations

import gc
import json
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

_server = None
_thread = None
_base_url = ""
_token = ""


def revision_root(asset_root: Path) -> Path:
    """Revision 0 of the imported files; some dumps keep it under an android/ or ios/ folder."""
    revision = asset_root / "assets" / "revisions" / "0"
    for platform in ("android", "ios"):
        if (revision / platform / "assetbundle").is_dir():
            return revision / platform
    return revision


def packaged(name: str) -> Path:
    """A bundled package's folder. Chaquopy unpacks templates and styles on first import, so import first."""
    import importlib
    return Path(importlib.import_module(name).__file__).resolve().parent


def android_converters():
    """Textures, sounds, models and story scenes convert in the Go library, reached through Java."""
    from java import jclass
    native = jclass("org.veritr1x.bunker.NativeBridge")
    return dict(decode=lambda bundle, target, size: native.texture(bundle, target, size),
                sound=lambda bundle, target: native.audio(bundle, target),
                model=lambda actor, target: native.model(actor, target),
                motion=lambda clip, actor, target: native.motion(clip, actor, target),
                scenario=lambda folder, target: native.scenario(folder, target))


def original_master(asset_root: Path, archive_root: Path) -> tuple[Path, bool]:
    """The game's own master data, which Pod Programs keeps beside the Archive's folder (files/tools on
    Android, LunarTools on iOS) once it has started; else the master data in use, which a patch may change."""
    for tools in ("tools", "LunarTools"):
        origin = archive_root.parent / tools / "patcher" / "origin.bin.e"
        if origin.is_file():
            return origin, True
    return asset_root / "assets" / "release" / "20240404193219.bin.e", False


def _tools_on_path():
    """Lunar Base's extract_names and dump_masterdata, which the Archive's index imports."""
    tools = str(packaged("tools"))
    if tools not in sys.path:
        sys.path.insert(0, tools)


def _builder(asset_root: str, archive_root: str, scenario=None):
    """The Archive's index builder for these game files, or None when they have no English text to index."""
    _tools_on_path()
    from archive import app as archive_app
    master, _ = original_master(Path(asset_root), Path(archive_root))
    revision = revision_root(Path(asset_root))
    if not (revision / "assetbundle" / "text" / "en").is_dir() or not master.is_file():
        return None
    return archive_app.shared_builder(revision, master, Path(archive_root) / "archive.db", scenario)


def index_status(asset_root: str, archive_root: str) -> str:
    """JSON: possible (there are game files to index), ready (the index is current), running, done, total, step, error."""
    builder = _builder(asset_root, archive_root)
    if builder is None:
        return json.dumps({"possible": False, "ready": False, "running": False, "done": 0, "total": 0, "step": "", "error": ""})
    return json.dumps({"possible": True, **builder.status()})


_ANDROID = object()


def build_index(asset_root: str, archive_root: str, scenario=_ANDROID) -> str:
    """The launcher, before it starts the game: builds the index when it is missing or out of date. Returns index_status."""
    if scenario is _ANDROID:
        scenario = None
        if _builder(asset_root, archive_root) is not None:
            scenario = android_converters()["scenario"]
    builder = _builder(asset_root, archive_root, scenario)
    if builder is not None and not builder.ready():
        builder.start()
    return index_status(asset_root, archive_root)


def create_app(asset_root: Path, archive_root: Path, token: str, origin: str, converters=None):
    from fastapi.responses import JSONResponse
    from archive.app import create_app as archive_app
    master, original = original_master(asset_root, archive_root)
    app = archive_app(revision_root(asset_root), master, archive_root, packaged("web") / "static",
                      original=original, language=asset_root.parent / "translation" / "active.json",
                      **(converters or android_converters()))

    @app.middleware("http")
    async def private_session(request, call_next):
        # Same rule as Pod Programs: only the launcher's WebView holds this cookie.
        if request.headers.get("host") != origin.removeprefix("http://") or not secrets.compare_digest(request.cookies.get("lunar_archive", ""), token):
            return JSONResponse({"ok": False, "error": "Private launcher session required"}, status_code=403)
        if request.method not in ("GET", "HEAD") and request.headers.get("origin") not in (None, origin):
            return JSONResponse({"ok": False, "error": "Invalid origin"}, status_code=403)
        response = await call_next(request)
        if not request.url.path.startswith("/media/"):
            response.headers["Cache-Control"] = "no-store"
        return response
    return app


def start(asset_root: str, archive_root: str, converters=None) -> str:
    global _server, _thread, _base_url, _token
    if _thread and _thread.is_alive():
        return json.dumps({"url": _base_url, "token": _token})
    _tools_on_path()
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    _base_url = "http://127.0.0.1:" + str(sock.getsockname()[1])
    _token = secrets.token_urlsafe(32)
    app = create_app(Path(asset_root), Path(archive_root), _token, _base_url, converters)
    _server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False, loop="asyncio", http="h11", lifespan="off"))
    _thread = threading.Thread(target=lambda: _server.run(sockets=[sock]), name="lunar-archive", daemon=True)
    _thread.start()
    for _ in range(500):
        if _server.started:
            return json.dumps({"url": _base_url, "token": _token})
        if not _thread.is_alive():
            break
        time.sleep(.02)
    sock.close()
    raise RuntimeError("The Archive could not start")


def stop():
    global _server, _thread
    if _server:
        _server.should_exit = True
    if _thread:
        _thread.join(30)
    _server = _thread = None
    gc.collect()  # free the app's tables now, reference cycles included
