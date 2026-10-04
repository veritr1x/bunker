"""Choose which player the game signs in as on this device.

The game signs in with an ID it created on this device, and Lunar Tear plays
the player that holds that ID. Using another player swaps the two players'
IDs, so the one that was in use is kept, not lost.
"""
from __future__ import annotations

import contextlib
import secrets
import sqlite3
from urllib.parse import urlencode

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from web import config

router = APIRouter()
REASON = "player-switch"


def _device_id(db):
    """This device's ID: the one behind the newest sign-in, or None before the first."""
    row = db.execute("SELECT uuid FROM sessions ORDER BY rowid DESC LIMIT 1").fetchone()
    return row[0] if row else None


def device_player():
    """The user_id the game signs in as on this device, or None."""
    if not config.GAME_DB_PATH.is_file():
        return None
    try:
        with contextlib.closing(sqlite3.connect(f"file:{config.GAME_DB_PATH}?mode=ro", uri=True)) as db:
            device = _device_id(db)
            row = device and db.execute("SELECT user_id FROM users WHERE uuid = ?", (device,)).fetchone()
            return row[0] if row else None
    except sqlite3.Error:
        return None


def use_player(user_id: int, path=None, backup=None) -> bool:
    """Makes the game sign in as user_id on this device. False if it already does."""
    path = path or config.GAME_DB_PATH
    with contextlib.closing(sqlite3.connect(path)) as db:
        device = _device_id(db)
        if device is None:
            raise ValueError("Deploy and sign in to the game once on this device first.")
        row = db.execute("SELECT uuid FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError(f"Player {user_id} not found.")
        chosen = row[0]
        if chosen == device:
            return False
        current = db.execute("SELECT user_id FROM users WHERE uuid = ?", (device,)).fetchone()
    if backup:
        backup(REASON)
    with contextlib.closing(sqlite3.connect(path)) as db:
        with db:  # one transaction
            # IDs are unique, so the swap goes through a spare one.
            spare = "switch-" + secrets.token_hex(8)
            if current:
                db.execute("UPDATE users SET uuid = ? WHERE user_id = ?", (spare, current[0]))
            db.execute("UPDATE users SET uuid = ? WHERE user_id = ?", (device, user_id))
            if current:
                db.execute("UPDATE users SET uuid = ? WHERE user_id = ?", (chosen, current[0]))
            # Sign-ins follow their IDs, so the game's next request is already the chosen player.
            db.execute("UPDATE sessions SET user_id = ? WHERE uuid = ?", (user_id, device))
            if current:
                db.execute("UPDATE sessions SET user_id = ? WHERE uuid = ?", (current[0], chosen))
    return True


def new_player(path=None, backup=None) -> int | None:
    """Frees this device's ID so the game starts a new player on its next sign-in.

    The player that had the ID keeps everything under a spare ID, so it can be
    chosen again with Use this player. Returns that player's user_id.
    """
    path = path or config.GAME_DB_PATH
    with contextlib.closing(sqlite3.connect(path)) as db:
        device = _device_id(db)
        if device is None:
            raise ValueError("Deploy and sign in to the game once on this device first.")
        row = db.execute("SELECT user_id FROM users WHERE uuid = ?", (device,)).fetchone()
    if row is None:
        return None  # Already free: the next sign-in starts a new player.
    if backup:
        backup(REASON)
    with contextlib.closing(sqlite3.connect(path)) as db:
        with db:
            # The sign-in records stay: they are how Pod Programs knows this device's ID.
            db.execute("UPDATE users SET uuid = ? WHERE user_id = ?", ("spare-" + secrets.token_hex(8), row[0]))
    return row[0]


def _back(user_id, **kwargs):
    return RedirectResponse(f"/users/{user_id}?" + urlencode(kwargs), status_code=303)


@router.post("/users/{user_id}/use")
def use(user_id: int):
    from web.services import backup_service
    try:
        blocker = backup_service.detect_lunar_tear_running()
        if blocker:
            raise ValueError("Stop Lunar Tear before changing the player.")
        changed = use_player(user_id, backup=backup_service.create_backup)
    except Exception as exc:
        return _back(user_id, error=str(exc))
    if not changed:
        return _back(user_id, message="The game already plays as this player.")
    return _back(user_id, message="The game will play as this player. Close Pod Programs and tap Deploy.")


@router.post("/users/new")
def new():
    from web.services import backup_service
    try:
        if backup_service.detect_lunar_tear_running():
            raise ValueError("Stop Lunar Tear before starting a new player.")
        kept = new_player(backup=backup_service.create_backup)
    except Exception as exc:
        return RedirectResponse("/users?" + urlencode({"error": str(exc)}), status_code=303)
    message = "The game will start a new player. Close Pod Programs and tap Deploy."
    if kept:
        message += f" Player {kept} is kept; choose it here to go back."
    return RedirectResponse("/users?" + urlencode({"message": message}), status_code=303)


def install(app):
    """Adds the route, and lets the player pages ask which player is in use."""
    import importlib
    app.include_router(router)
    for name in ("users",):
        importlib.import_module("web.routes." + name).templates.env.globals["device_player"] = device_player
