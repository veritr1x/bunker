"""Offline Android host for the vendored Lunar Base UI and master-data patcher.

Desktop process execution is replaced by the same grant engine linked into JNI.
Paths are supplied by our private Android service, never inferred from the host.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib
import io
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

_server = None
_thread = None
_base_url = ""
_token = ""
_native = None
_data_root = None
_asset_root = None
_report = lambda message: None


def cli(module, arguments):
    """Call a bundled CLI in-process. Requests are serialized by our middleware."""
    old = sys.argv
    output = io.StringIO()
    try:
        sys.argv = [module.__name__, *map(str, arguments)]
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                module.main()
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise RuntimeError(output.getvalue()[-2000:] or str(exc)) from exc
    finally:
        sys.argv = old
    return output.getvalue()


def read_json(path, default=None):
    """A JSON file's value, or default when it is missing or damaged."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path, value, **options):
    """Writes through a temporary file, so a crash never leaves a half-written file."""
    path = Path(path)
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(value, **options))
    os.replace(pending, path)


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configure(data_root, asset_root, tools_root, native, reporter=None):
    global _native, _data_root, _asset_root, _report
    _native = native
    _data_root, _asset_root = str(data_root), str(asset_root)
    _report = reporter or (lambda message: None)
    os.environ["LUNAR_TEAR_DIR"] = str(asset_root)
    from web import config
    config.GAME_DB_PATH = Path(data_root) / "game.db"
    config.DATA_DIR = Path(tools_root)
    config.BACKUP_DIR = config.DATA_DIR / "backups"
    config.MASTERDATA_DIR = config.DATA_DIR / "masterdata"
    config.NAMES_DIR = config.DATA_DIR / "names"
    config.ASSETS_DIR = Path(asset_root) / "assets"
    config.RELEASE_DIR = config.ASSETS_DIR / "release"
    config.REVISIONS_DIR = config.ASSETS_DIR / "revisions"
    config.OTHER_LUNAR_TEAR_DIRS = []
    config.SHIM_LUNAR_TEAR_REF = "Bundled Android server (63df7d7)"
    config.find_master_data_bin = lambda: config.RELEASE_DIR / "20240404193219.bin.e"
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(config.ROOT / "tools"))
    adapt_services()
    return config


def adapt_services():
    from web.services import backup_service, service_control
    service_control.available = lambda: False
    service_control.unavailable_reason = lambda: "The game is stopped while Tools is open."
    service_control.is_active = lambda: False
    # The desktop tool uses second-resolution filenames, which collide on a
    # fast sequence of edits. Retain every snapshot with microsecond precision.
    # Switching players is backed up like any other edit.
    if "player-switch" not in backup_service.VALID_REASONS:
        backup_service.VALID_REASONS = (*backup_service.VALID_REASONS, "player-switch")
        backup_service.REASON_LABELS["player-switch"] = "Player Switch"
    def backup(reason="manual"):
        if reason not in backup_service.VALID_REASONS:
            raise ValueError("Invalid backup reason")
        from web import config
        from datetime import datetime
        if not config.GAME_DB_PATH.is_file():
            raise FileNotFoundError("Play the game once to create a save.")
        backup_service.ensure_dirs()
        dest = config.BACKUP_DIR / ("backup_" + datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f") + "_" + reason + ".db")
        with contextlib.closing(sqlite3.connect(f"file:{config.GAME_DB_PATH}?mode=ro", uri=True)) as source:
            with contextlib.closing(sqlite3.connect(dest)) as target:
                source.backup(target)
        backup_service.prune_to_last_n(config.BACKUP_RETENTION)
        return backup_service._info_from_path(dest)
    backup_service.create_backup = backup

    def swap(path):
        from web import config
        target = config.GAME_DB_PATH
        stage = target.with_suffix(".restore-tmp")
        try:
            with contextlib.closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as source:
                if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup failed its integrity check")
                if source.execute("SELECT count(*) FROM sqlite_master WHERE name='users'").fetchone()[0] != 1:
                    raise ValueError("This is not a game backup")
                # A SQLite backup includes WAL content and produces a standalone file.
                stage.unlink(missing_ok=True)
                with contextlib.closing(sqlite3.connect(stage)) as output:
                    source.backup(output)
            if target.exists():
                with contextlib.closing(sqlite3.connect(target)) as current:
                    busy, _, _ = current.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                    if busy:
                        raise ValueError("Save is still in use")
            for suffix in ("-wal", "-shm"):
                Path(str(target) + suffix).unlink(missing_ok=True)
            with stage.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(stage, target)
        finally:
            stage.unlink(missing_ok=True)
    backup_service._swap_database = swap
    def restore(filename, *, manage_server=False):
        from web import config
        source = (config.BACKUP_DIR / filename).resolve()
        if source.parent != config.BACKUP_DIR.resolve() or not source.is_file():
            raise FileNotFoundError("Snapshot not found")
        blocker = backup_service.detect_lunar_tear_running()
        if blocker:
            raise backup_service.RestoreBlocked(blocker)
        info = backup_service._info_from_path(source)
        # Protect the selected oldest snapshot from retention pruning when the
        # pre-restore snapshot is created.
        selected = config.DATA_DIR / "restore-selected.db"
        try:
            shutil.copyfile(source, selected)
            if config.GAME_DB_PATH.exists():
                backup("pre-restore")
            swap(selected)
            return backup_service.RestoreResult(source=info, steps=("Previous save backed up",), server_restarted=False)
        finally:
            selected.unlink(missing_ok=True)
    backup_service.restore_backup = restore
    for name, error in (("grant", "GrantError"), ("costume", "CostumeError"), ("weapon", "WeaponError"), ("upgrade", "UpgradeError"), ("memoir", "MemoirError")):
        module = importlib.import_module("web.services." + name + "_service")
        exception = getattr(module, error)
        def invoke(payload, *, timeout=300, exception=exception):
            result = json.loads(_native(_data_root, _asset_root, json.dumps(payload)))
            if not result.get("ok"):
                raise exception(result.get("error", "Save edit failed"))
            return result
        module._ensure_shim_available = lambda: None
        module._invoke_shim = invoke


def prepare_data():
    from web import config
    import tools
    from tools import dump_masterdata, extract_names
    master = config.find_master_data_bin()
    if not master.is_file():
        raise FileNotFoundError("Import master data first")
    marker = config.DATA_DIR / "catalog-version.json"
    revision = config.REVISIONS_DIR / "0" / "android" / "list.bin"
    if not revision.exists():
        revision = config.REVISIONS_DIR / "0" / "list.bin"
    signature = {"master": fingerprint(master), "catalog": fingerprint(revision) if revision.exists() else None, "format": 1}
    if read_json(marker) == signature:
        return
    _report("Reading game data…")
    # Decode every table and fail if any table is malformed; the desktop CLI
    # otherwise prints errors and exits successfully with an incomplete catalog.
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    import msgpack
    decoded = unpad(AES.new(bytes.fromhex(dump_masterdata.DEFAULT_KEY), AES.MODE_CBC, bytes.fromhex(dump_masterdata.DEFAULT_IV)).decrypt(master.read_bytes()), AES.block_size)
    try:
        toc = msgpack.unpackb(decoded, raw=False, strict_map_key=False)
        blob = b""
    except msgpack.ExtraData as exc:
        toc, blob = exc.unpacked, exc.extra
    schemas = dump_masterdata.load_schemas()
    stage = config.DATA_DIR / "masterdata.pending"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir()
    for table, (offset, length) in toc.items():
        rows = dump_masterdata.decompress_table(blob, offset, length)
        if table in schemas:
            name, columns = schemas[table]
            rows = dump_masterdata.rows_to_dicts(rows, columns)
            name += "Table"
        else:
            name = table
        (stage / (name + ".json")).write_text(json.dumps(rows, ensure_ascii=False))
    shutil.rmtree(config.MASTERDATA_DIR, ignore_errors=True)
    stage.rename(config.MASTERDATA_DIR)
    _report("Preparing item names…")
    config.NAMES_DIR.mkdir(exist_ok=True)
    text_root = extract_names.resolve_text_root(config.REVISIONS_DIR, "0")
    kinds = ("consumables", "materials", "important_items", "costumes", "characters", "weapons", "companions", "thoughts", "parts", "parts_groups")
    for kind in kinds:
        if kind in extract_names.KIND_CONFIG:
            extract_names.extract_kind(kind, config.MASTERDATA_DIR, text_root, config.NAMES_DIR)
    for name in ("names", "costume", "weapon", "karma", "upgrade", "memoir"):
        importlib.reload(importlib.import_module("web.services." + name + "_service"))
    adapt_services()
    write_json(marker, signature)


def create_app(token, origin):
    from fastapi.responses import JSONResponse
    from web.app import create_app as base_app
    from android_patcher import router
    import android_players
    app = base_app()
    app.include_router(router)
    android_players.install(app)
    serial = asyncio.Lock()
    @app.middleware("http")
    async def private_session(request, call_next):
        # The non-exported Android activity receives this random cookie over
        # private IPC. Loopback binding alone does not authenticate other apps.
        if request.headers.get("host") != origin.removeprefix("http://") or not secrets.compare_digest(request.cookies.get("lunar_tools", ""), token):
            return JSONResponse({"ok": False, "error": "Private launcher session required"}, status_code=403)
        if request.method not in ("GET", "HEAD") and request.headers.get("origin") not in (None, origin):
            return JSONResponse({"ok": False, "error": "Invalid origin"}, status_code=403)
        async with serial:
            try:
                response = await call_next(request)
            except Exception as exc:
                return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        return response
    return app


def start(data_root, asset_root, tools_root, reporter):
    global _server, _thread, _base_url, _token
    if _thread and _thread.is_alive():
        return json.dumps({"url": _base_url, "token": _token})
    from java import jclass
    native = jclass("org.veritr1x.bunker.NativeBridge")
    configure(data_root, asset_root, tools_root, native.edit, reporter.report)
    prepare_data()
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    _base_url = "http://127.0.0.1:" + str(sock.getsockname()[1])
    _token = secrets.token_urlsafe(32)
    app = create_app(_token, _base_url)
    _server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False, loop="asyncio", http="h11", lifespan="off"))
    _thread = threading.Thread(target=lambda: _server.run(sockets=[sock]), name="lunar-tools", daemon=True)
    _thread.start()
    for _ in range(500):
        if _server.started:
            return json.dumps({"url": _base_url, "token": _token})
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
