"""Android host for the Archive: its own private loopback server, separate from Pod Programs.

The Archive only reads the imported game files and master data, so it runs
beside Lunar Tear and the game; nothing is stopped and the save is never opened.
"""
from __future__ import annotations

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
    """Revision 0 of the imported files; some dumps keep it under an android/ folder."""
    revision = asset_root / "assets" / "revisions" / "0"
    nested = revision / "android"
    return nested if (nested / "assetbundle").is_dir() else revision


def packaged(name: str) -> Path:
    """A bundled package's folder. Chaquopy unpacks templates and styles on first import, so import first."""
    import importlib
    return Path(importlib.import_module(name).__file__).resolve().parent


def create_app(asset_root: Path, archive_root: Path, token: str, origin: str):
    from fastapi.responses import JSONResponse
    from java import jclass
    from archive.app import create_app as archive_app
    native = jclass("org.veritr1x.bunker.NativeBridge")  # textures and sounds convert in the Go library
    app = archive_app(revision_root(asset_root), asset_root / "assets" / "release" / "20240404193219.bin.e",
                      archive_root, packaged("web") / "static",
                      decode=lambda bundle, target, size: native.texture(bundle, target, size),
                      sound=lambda bundle, target: native.audio(bundle, target))

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
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                                                      "img-src 'self' data:; media-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        return response
    return app


def start(asset_root: str, archive_root: str) -> str:
    global _server, _thread, _base_url, _token
    if _thread and _thread.is_alive():
        return json.dumps({"url": _base_url, "token": _token})
    tools = str(packaged("tools"))  # Lunar Base's extract_names and dump_masterdata
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    _base_url = "http://127.0.0.1:" + str(sock.getsockname()[1])
    _token = secrets.token_urlsafe(32)
    app = create_app(Path(asset_root), Path(archive_root), _token, _base_url)
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
