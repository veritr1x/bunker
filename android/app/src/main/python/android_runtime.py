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
import logging
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import sys
import threading
import time

from bunker_text import t

log = logging.getLogger("bunker.tools")
_server = None
_thread = None
_base_url = ""
_token = ""
_native = None
# The game's texture decoder (bundle, target PNG, longest side) -> "" or an error,
# set by each platform's start: banner art for the Schedule page's timeline.
TEXTURE = None
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
    service_control.unavailable_reason = lambda: t("pods.runtime.cannot_stop_server")
    service_control.is_active = lambda: False
    # Restore is offered while the game runs: restoring is a change the game
    # guard asks to close the game for (install_game_guard), not a reason to
    # disable the button because the game's server is listening.
    backup_service.detect_lunar_tear_running = lambda: ""
    # The desktop tool uses second-resolution filenames, which collide on a
    # fast sequence of edits. Retain every snapshot with microsecond precision.
    # Bunker's own reasons (REASONS): switching players is backed up like any
    # other edit; the server takes a snapshot before a new Bunker version first
    # opens the save (backup_<time>_update.db: it keeps the newest three itself,
    # the ordinary retention leaves them alone); Pod Programs › Gift, Deck
    # Builder and Story Jump back the save up before each change
    # (android_gift.send, android_deckbuilder.write, android_story.jump).
    for reason in REASONS:
        if reason not in backup_service.VALID_REASONS:
            backup_service.VALID_REASONS = (*backup_service.VALID_REASONS, reason)
    # Each backup's reason, in the chosen language as the page is drawn (BackupInfo.reason_display).
    backup_service.reason_label = reason_label
    def prune(n):
        ordinary = [b for b in backup_service.list_backups() if b.reason != "update"]
        for b in ordinary[n:]:
            try:
                b.path.unlink()
            except OSError:
                pass
        return max(0, len(ordinary) - n)
    backup_service.prune_to_last_n = prune
    def backup(reason="manual"):
        if reason not in backup_service.VALID_REASONS:
            raise ValueError(t("pods.runtime.bad_backup_reason"))
        from web import config
        from datetime import datetime
        if not config.GAME_DB_PATH.is_file():
            raise FileNotFoundError(t("pods.runtime.no_save"))
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
                    raise ValueError(t("pods.runtime.backup_damaged"))
                if source.execute("SELECT count(*) FROM sqlite_master WHERE name='users'").fetchone()[0] != 1:
                    raise ValueError(t("pods.runtime.not_a_backup"))
                # A SQLite backup includes WAL content and produces a standalone file.
                stage.unlink(missing_ok=True)
                with contextlib.closing(sqlite3.connect(stage)) as output:
                    source.backup(output)
            if target.exists():
                with contextlib.closing(sqlite3.connect(target)) as current:
                    busy, _, _ = current.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                    if busy:
                        raise ValueError(t("pods.runtime.save_in_use"))
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
            raise FileNotFoundError(t("pods.runtime.snapshot_not_found"))
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
            return backup_service.RestoreResult(source=info, steps=(t("pods.runtime.previous_save_backed_up"),), server_restarted=False)
        finally:
            selected.unlink(missing_ok=True)
    backup_service.restore_backup = restore
    for name, error in (("grant", "GrantError"), ("costume", "CostumeError"), ("weapon", "WeaponError"), ("upgrade", "UpgradeError"), ("memoir", "MemoirError")):
        module = importlib.import_module("web.services." + name + "_service")
        exception = getattr(module, error)
        def invoke(payload, *, timeout=300, exception=exception):
            result = json.loads(_native(_data_root, _asset_root, json.dumps(payload)))
            if not result.get("ok"):
                raise exception(result.get("error", t("pods.runtime.edit_failed")))
            return result
        module._ensure_shim_available = lambda: None
        module._invoke_shim = invoke


# Backup reasons as players read them (BackupInfo.reason_display): lunar-base's and Bunker's.
REASONS = {"manual": "pods.backup.reason.manual", "auto": "pods.backup.reason.auto", "item-editor": "pods.backup.reason.item_editor",
           "costume-editor": "pods.backup.reason.costume_editor", "weapon-editor": "pods.backup.reason.weapon_editor",
           "upgrade-manager": "pods.backup.reason.upgrade_manager", "memoir-editor": "pods.backup.reason.memoir_editor",
           "pre-restore": "pods.backup.reason.pre_restore", "player-switch": "pods.backup.reason.player_switch",
           "update": "pods.backup.reason.update", "gift": "pods.backup.reason.gift", "deck builder": "pods.backup.reason.deck_builder",
           "story jump": "pods.backup.reason.story_jump"}


def reason_label(reason):
    """A backup's reason in the chosen language; an unknown one as its file names it."""
    return t(REASONS[reason]) if reason in REASONS else reason


def prepare_data():
    from web import config
    import tools
    from tools import dump_masterdata, extract_names
    master = config.find_master_data_bin()
    if not master.is_file():
        raise FileNotFoundError(t("pods.runtime.import_master_first"))
    marker = config.DATA_DIR / "catalog-version.json"
    revision = config.REVISIONS_DIR / "0" / "android" / "list.bin"
    if not revision.exists():
        revision = config.REVISIONS_DIR / "0" / "list.bin"
    signature = {"master": fingerprint(master), "catalog": fingerprint(revision) if revision.exists() else None, "format": 3}
    if read_json(marker) == signature:
        return
    _report(t("pods.runtime.reading_data"))
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
    _report(t("pods.runtime.preparing_names"))
    config.NAMES_DIR.mkdir(exist_ok=True)
    text_root = extract_names.resolve_text_root(config.REVISIONS_DIR, "0")
    kinds = ("consumables", "materials", "important_items", "costumes", "characters", "weapons", "companions", "thoughts", "parts", "parts_groups", "event_quests", "main_quests", "gacha_banners", "shops")
    for kind in kinds:
        if kind in extract_names.KIND_CONFIG:
            extract_names.extract_kind(kind, config.MASTERDATA_DIR, text_root, config.NAMES_DIR)
    for name in ("names", "costume", "weapon", "karma", "upgrade", "memoir"):
        importlib.reload(importlib.import_module("web.services." + name + "_service"))
    adapt_services()
    write_json(marker, signature)


# Pod Programs opens while the game keeps running. These changes are read by
# the server or the game later (summon rates and roulette before each draw,
# mods as each is used,
# display at the next launch, the timeline's filter, a backup copied with
# SQLite's online backup), so they need nothing closed.
LIVE_SAFE = frozenset(("/gacha", "/gacha/roulette", "/gacha/preset", "/mods", "/mods/preset", "/display", "/patcher/calendar/timeline", "/backups/create",
                       "/language/load"))  # a loaded pack is only kept; choosing it is the change
# These change what the game reads only as it launches: they move its clock
# back (the calendar turned off, "Show original dates"), and the game keeps
# day markers in memory that only a fresh start clears (client-days.reset,
# GameProcessProvider, LunarLauncher.m). The game is closed first, without
# asking (ServerService.closeGameForTools, or the iOS launcher).
CLOSES = frozenset(("/patcher/calendar/view", "/patcher/calendar/off", "/patcher/new-day"))
# Any other change edits the save, the master data or the calendar, which the
# server reads as it starts and the game as it signs in: the server stops for
# the change and starts again after it (pause_game, resume_game), and the game
# goes back to its title screen to sign in again (interceptor.ReturnToTitle).
# The game keeps running throughout.

# Set as Pod Programs starts: whether the game and its server are running, a
# call that stops them, and the two around a change beside the game (each
# returns "" or an error). Without them, nothing runs.
game_live = lambda: False
close_game = lambda: ""
pause_game = lambda: ""
resume_game = lambda title=True: ""


def changed_game(response):
    """Whether a change's response may have changed what the game loads.
    A refusal (4xx or 5xx), a redirect back with an error, or a handler's
    X-Bunker-Unchanged leaves the save as it was: the server starts again,
    but the game is not sent back to its title screen."""
    if response.headers.get("x-bunker-unchanged"):
        return False
    # A change the game picks up from the server on its next call (a gift
    # in its Gift Box): Lunar Tear restarts around it, the game plays on.
    if response.headers.get("x-bunker-keep-playing"):
        return False
    if response.status_code >= 400:
        return False
    if 300 <= response.status_code < 400 and "error=" in response.headers.get("location", ""):
        return False
    return True


def next_step():
    """How a change reaches the game, for the message after it."""
    if game_live():
        return t("pods.runtime.title_screen")
    return t("pods.runtime.deploy")


def install_game_guard(app, live, close, pause=lambda: pause_game(), resume=lambda title=True: resume_game(title)):
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool

    @app.get("/bunker/state")
    def state():
        return {"live": bool(live()), "safe": sorted(LIVE_SAFE)}

    @app.middleware("http")
    async def needs_closed_game(request, call_next):
        path = request.url.path
        if request.method in ("GET", "HEAD") or path in LIVE_SAFE or not live():
            return await call_next(request)
        if path in CLOSES:
            error = await run_in_threadpool(close)
            if error:
                return JSONResponse({"ok": False, "error": error}, status_code=500)
            return await call_next(request)
        error = await run_in_threadpool(pause)
        if error:
            return JSONResponse({"ok": False, "error": error}, status_code=500)
        title = True  # a handler that fails part-way: the game loads the save again
        try:
            response = await call_next(request)
            title = changed_game(response)
            return response
        finally:
            error = await run_in_threadpool(resume, title)
            if error:
                log.warning("The server did not start again beside the game: %s", error)


def create_app(token, origin):
    from fastapi.responses import JSONResponse
    # Before any page module makes its templates: they all get t() (Bunker's own text, bunker_text.py).
    import bunker_text
    bunker_text.install_everywhere()
    from web.app import create_app as base_app
    from android_patcher import router
    import android_display
    import android_gacha
    import android_deckbuilder
    import android_gift
    import android_language
    import android_mods
    import android_story
    import android_players
    app = base_app()
    app.include_router(router)
    import android_calendar
    app.include_router(android_calendar.router)
    app.include_router(android_display.router)
    app.include_router(android_gacha.router)
    app.include_router(android_gift.router)
    app.include_router(android_language.router)
    app.include_router(android_deckbuilder.router)
    app.include_router(android_mods.router)
    app.include_router(android_story.router)
    android_players.install(app)
    # Inside the session check below: middleware added later runs first.
    install_game_guard(app, lambda: game_live(), lambda: close_game())

    @app.middleware("http")
    async def language(request, call_next):
        # The pack the server applies may have changed (Pod Programs › Language, an update): cheap when not.
        try:
            bunker_text.reload()
        except Exception as exc:  # never a reason not to show a page: English it is
            log.warning("Bunker's text stays as it was: %s", exc)
        return await call_next(request)
    serial = asyncio.Lock()
    @app.middleware("http")
    async def private_session(request, call_next):
        # The non-exported Android activity receives this random cookie over
        # private IPC. Loopback binding alone does not authenticate other apps.
        if request.headers.get("host") != origin.removeprefix("http://") or not secrets.compare_digest(request.cookies.get("lunar_tools", ""), token):
            return JSONResponse({"ok": False, "error": t("common.private_session_required")}, status_code=403)
        if request.method not in ("GET", "HEAD") and request.headers.get("origin") not in (None, origin):
            return JSONResponse({"ok": False, "error": t("common.invalid_origin")}, status_code=403)
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
    global _server, _thread, _base_url, _token, TEXTURE
    if _thread and _thread.is_alive():
        return json.dumps({"url": _base_url, "token": _token})
    global game_live, close_game, pause_game, resume_game
    from java import jclass
    native = jclass("org.veritr1x.bunker.NativeBridge")
    service = jclass("org.veritr1x.bunker.ServerService")
    game_live = lambda: bool(service.gameLive())
    close_game = lambda: str(service.closeGameForTools())
    pause_game = lambda: str(service.pauseForTools())
    # only logged: in English (Java's references put in words)
    resume_game = lambda title=True: str(service.inEnglish(service.resumeForTools(bool(title))))
    TEXTURE = lambda bundle, target, size: native.texture(bundle, target, size)
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
    raise RuntimeError(t("pods.runtime.could_not_start"))


def update_data(data_root, asset_root, tools_root, version):
    """Before the server starts after an update (ServerService): the game data
    for this build, the calendar's or a preset's (android_patcher.update_for)."""
    from java import jclass
    configure(data_root, asset_root, tools_root, jclass("org.veritr1x.bunker.NativeBridge").edit)
    prepare_data()
    refresh_language()
    import android_patcher
    updated = android_patcher.update_for(version)  # a preset or calendar rebuild brings the texts too
    try:
        import android_challenges
        android_challenges.reapply_texts()  # a revised shipped pack's game data texts
    except Exception:  # noqa: BLE001 — the update stands; Pod Programs › Language can try again
        log.exception("Game data texts not updated")
    return updated


def refresh_language():
    """A chosen shipped language pack this build revised replaces the active copy (Pod Programs › Language),
    before the server starts and applies it."""
    import bunker_language
    from web import config
    try:
        if bunker_language.for_config(config).refresh():
            log.info("Language pack updated for this build")
    except OSError as exc:
        log.warning("Language pack not updated: %s", exc)


def stop():
    global _server, _thread
    if _server:
        _server.should_exit = True
    if _thread:
        _thread.join(120)
        if _thread.is_alive():
            raise RuntimeError(t("pods.runtime.editor_finishing"))
    _server = _thread = None
