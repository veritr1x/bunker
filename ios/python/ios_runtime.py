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
    import android_display
    import android_patcher
    for module in (android_patcher, android_display):
        redirect = module.redirect
        def ios_redirect(redirect=redirect, **kwargs):
            if "message" in kwargs:
                kwargs["message"] = kwargs["message"].replace("Close Pod Programs and tap Deploy.", "Close Pod Programs, then restart the game.")
            return redirect(**kwargs)
        module.redirect = ios_redirect


def start(data_root, asset_root, tools_root, original_master):
    """Prepare the editors and serve them on loopback. Returns url and token as JSON."""
    global _server, _thread
    if _thread and _thread.is_alive():
        return json.dumps(_state)
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
    android_runtime.prepare_data()
    _adapt_patcher()
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
    raise RuntimeError("Tools could not start")


def stop():
    global _server, _thread
    if _server:
        _server.should_exit = True
    if _thread:
        _thread.join(120)
        if _thread.is_alive():
            raise RuntimeError("An editor is still finishing. Try closing Tools again.")
    _server = _thread = None
    _state.clear()
