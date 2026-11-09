"""Tools on iOS: the Android tools runtime, inside the game process.

LunarTear.framework starts Python only when Tools opens and calls start() and
stop() here. Saves are edited by the Go server's LunarEdit, which is already
loaded in this process.
"""
from __future__ import annotations

import contextlib
import ctypes
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import sys
import threading
import time
from urllib.parse import unquote, urlparse



def _fix_pycryptodome():
    # iOS keeps each compiled library in Frameworks/ and leaves a .fwork file
    # naming it. pycryptodome loads its libraries by path, so follow that link.
    from Crypto.Util import _raw_api
    original = _raw_api.load_pycryptodome_raw_lib
    packages = Path(_raw_api.__file__).parents[2]
    def load(name, cdecl):
        parts = name.split(".")
        link = packages.joinpath(*parts[:-1], parts[-1] + ".abi3.fwork")
        if link.is_file():
            return _raw_api.load_lib(str(Path(sys.executable).parent / link.read_text().strip()), cdecl)
        return original(name, cdecl)
    _raw_api.load_pycryptodome_raw_lib = load


_fix_pycryptodome()

import android_runtime  # noqa: E402  (needs the fix above first)

_process = ctypes.CDLL(None)
_process.LunarEdit.argtypes = [ctypes.c_char_p] * 3
_process.LunarEdit.restype = ctypes.c_void_p
_process.LunarToolsReport.argtypes = [ctypes.c_char_p]
_process.free.argtypes = [ctypes.c_void_p]
# The Archive's converters, in the same Go library (server/cmd/android-bridge).
for _name, _count in (("LunarTexture", 2), ("LunarAudio", 2), ("LunarModel", 2), ("LunarMotion", 3), ("LunarScenario", 2)):
    getattr(_process, _name).argtypes = [ctypes.c_char_p] * _count
    getattr(_process, _name).restype = ctypes.c_void_p
_process.LunarTexture.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]

# Go and Python each include their own SQLite. Never let both use a save at once.
_save_lock = threading.Lock()
_connect = sqlite3.connect
_server = _thread = None
_state = {}


def _report(message):
    _process.LunarToolsReport(str(message).encode())


def _edit(data_root, asset_root, request):
    with _save_lock:
        pointer = _process.LunarEdit(str(data_root).encode(), str(asset_root).encode(), request.encode())
    # Go returns a C string that the caller frees.
    try:
        return ctypes.string_at(pointer).decode()
    finally:
        _process.free(pointer)


def _ensure_readable(path):
    """Let a read-only connection open a WAL database that has no -wal file.

    Go's SQLite deletes game.db-wal and -shm when it closes the save, and
    backups keep the WAL flag without those files. Apple's SQLite cannot open
    such a database read-only, but it keeps both files after a read-write
    connection closes, so one brief read-write open restores them.
    """
    if not os.path.isfile(path) or os.path.exists(path + "-wal"):
        return
    with open(path, "rb") as handle:
        if handle.read(20)[18:20] != b"\x02\x02":  # file format versions 2 mean WAL
            return
    # SQLite opens the file lazily; a query makes it create the files.
    with contextlib.closing(_connect(path)) as connection:
        connection.execute("PRAGMA schema_version").fetchone()


def _connect_readable(database, *args, **kwargs):
    if kwargs.get("uri") and str(database).startswith("file:"):
        parsed = urlparse(str(database))
        if "mode=ro" in parsed.query.split("&"):
            with _save_lock:
                _ensure_readable(unquote(parsed.path))
    return _connect(database, *args, **kwargs)


def _adapt_patcher():
    import android_calendar
    import android_display
    import android_mods
    import android_patcher
    from bunker_text import t
    for module in (android_patcher, android_display, android_calendar, android_mods):
        redirect = module.redirect
        def ios_redirect(redirect=redirect, **kwargs):
            # In the language shown now (Bunker's catalogue): there is no Deploy on iPhone and iPad.
            if "message" in kwargs:
                kwargs["message"] = kwargs["message"].replace(t("pods.runtime.deploy"), t("pods.runtime.restart_ios"))
            return redirect(**kwargs)
        module.redirect = ios_redirect
    # Texture size goes to Unity on the game's command line, which only Android's launcher sets.
    android_display.TEXTURES = android_display.TEXTURES[:1]
    # Upscaling: MetalFX on iPhone and iPad (LunarUpscale.m) in place of Android's FSR 1 and SGSR.
    android_display.UPSCALE = android_display.UPSCALE[:1] + android_display.UPSCALE_IOS


def _prepare(data_root, asset_root, tools_root, original_master):
    sqlite3.connect = _connect_readable
    patcher = Path(tools_root) / "patcher"
    patcher.mkdir(parents=True, exist_ok=True)
    origin = patcher / "origin.bin.e"
    if not origin.exists() and Path(original_master).is_file():
        pending = patcher / "origin.pending"
        shutil.copyfile(original_master, pending)
        os.replace(pending, origin)
    config = android_runtime.configure(data_root, asset_root, tools_root, _edit, _report)
    config.SHIM_LUNAR_TEAR_REF = "Bundled iOS server (63df7d7)"
    android_runtime.TEXTURE = lambda bundle, target, size: _go(_process.LunarTexture, bundle, target, int(size))
    android_runtime.prepare_data()


def update_data(data_root, asset_root, tools_root, original_master, version):
    """Before the server starts after an update (LunarLauncher.m): the game data
    for this build, the calendar's or a preset's (android_patcher.update_for)."""
    _prepare(data_root, asset_root, tools_root, original_master)
    android_runtime.refresh_language()
    import android_patcher
    updated = android_patcher.update_for(version)  # a preset or calendar rebuild brings the texts too
    try:
        import android_challenges
        android_challenges.reapply_texts()  # a revised shipped pack's game data texts
    except Exception:  # noqa: BLE001 — the update stands; Pod Programs › Language can try again
        android_runtime.log.exception("Game data texts not updated")
    return updated


def start(data_root, asset_root, tools_root, original_master):
    """Prepare the editors and serve them on loopback. Returns url and token as JSON."""
    global _server, _thread
    if _thread and _thread.is_alive():
        return json.dumps(_state)
    _prepare(data_root, asset_root, tools_root, original_master)
    _adapt_patcher()
    _process.LunarToolsGameLive.restype = ctypes.c_int
    _process.LunarToolsCloseGame.restype = ctypes.c_void_p
    _process.LunarToolsPauseGame.restype = ctypes.c_void_p
    _process.LunarToolsResumeGame.restype = ctypes.c_void_p
    _process.LunarToolsResumeGame.argtypes = [ctypes.c_int]
    android_runtime.game_live = lambda: bool(_process.LunarToolsGameLive())
    android_runtime.close_game = _close_game
    android_runtime.pause_game = lambda: _launcher(_process.LunarToolsPauseGame)
    android_runtime.resume_game = lambda title=True: _launcher(_process.LunarToolsResumeGame, 1 if title else 0)
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    url = "http://127.0.0.1:" + str(sock.getsockname()[1])
    token = secrets.token_urlsafe(32)
    app = android_runtime.create_app(token, url)
    _server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False, loop="asyncio", http="h11", lifespan="off"))
    _thread = threading.Thread(target=lambda: _server.run(sockets=[sock]), name="lunar-tools", daemon=True)
    _thread.start()
    for _ in range(500):
        if _server.started:
            _state.update(url=url, token=token)
            return json.dumps(_state)
        if not _thread.is_alive():
            break
        time.sleep(.02)
    sock.close()
    raise RuntimeError("It didn't start. Try again.")


def _close_game():
    """Before a change the game reads only as it launches: the launcher stops the game's server. "" or an error."""
    return _launcher(_process.LunarToolsCloseGame)


def _launcher(function, *arguments):
    """Calls a launcher export that returns "" or an error as a C string the caller frees."""
    pointer = function(*arguments)
    try:
        return ctypes.string_at(pointer).decode()
    finally:
        _process.free(pointer)


def _go(function, *arguments):
    """Calls a Go export that returns "" or an error as a C string the caller frees."""
    pointer = function(*(a if isinstance(a, int) else str(a).encode() for a in arguments))
    try:
        return ctypes.string_at(pointer).decode()
    finally:
        _process.free(pointer)


def _archive_converters():
    """Textures, sounds, models and story scenes convert in the Go library, in this process."""
    return dict(
        decode=lambda bundle, target, size: _go(_process.LunarTexture, bundle, target, int(size)),
        sound=lambda bundle, target: _go(_process.LunarAudio, bundle, target),
        model=lambda actor, target: _go(_process.LunarModel, actor, target),
        motion=lambda clip, actor, target: _go(_process.LunarMotion, clip, actor, target),
        scenario=lambda folder, target: _go(_process.LunarScenario, folder, target))


def archive_start(asset_root, archive_root):
    """The Archive: read only, so it runs beside Lunar Tear and the game. Returns url and token as JSON."""
    import android_archive
    return android_archive.start(asset_root, archive_root, _archive_converters())


def archive_build_index(asset_root, archive_root):
    """As the app starts: builds the Archive's index in the background when it is missing or out of
    date, beside the game. Returns its status as JSON (android_archive.index_status)."""
    import android_archive
    return android_archive.build_index(asset_root, archive_root, scenario=_archive_converters()["scenario"])


def archive_index_status(asset_root, archive_root):
    import android_archive
    return android_archive.index_status(asset_root, archive_root)


def archive_stop():
    """Stops the Archive's server when it closes: Python shares the game's process, and
    the Archive's tables would otherwise stay in its memory for the rest of the game."""
    import android_archive
    android_archive.stop()
    return ""


def stop():
    global _server, _thread
    if _server:
        _server.should_exit = True
    if _thread:
        _thread.join(120)
        if _thread.is_alive():
            raise RuntimeError("An editor is still saving. Close Pod Programs again.")
    _server = _thread = None
    _state.clear()


def build_ipa_update(app_dir, framework_zip, python_zip, sha_framework, sha_python, output_ipa, notices_zip="", sha_notices=""):
    """The launcher's update: the next Bunker IPA, for the player's sideloading tool (bunker_ios_update.py).
    notices_zip is "" when the app keeps its notices."""
    import bunker_ios_update
    return bunker_ios_update.build_ipa(app_dir, framework_zip, python_zip, sha_framework, sha_python, output_ipa, _report,
                                       notices_zip or None, sha_notices or None)
