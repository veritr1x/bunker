"""Pod Programs › Players › Arena points: sets a player's Arena points.

The edit is the editing shim's "set_arena_points" (bunker_arena_points.go),
which runs the server's own Arena sync first, so a save that has never been
in the current season enters it and the points survive the next Arena visit.
Points earn the week's and season's rewards like any others. The save is
backed up before each change; points out of range are refused before that.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
from urllib.parse import quote_plus

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

import bunker_text
from web import config

router = APIRouter()

# pvp.MaxPlayerPoint. 52,000 (the top computer player's) is rank 1; players pass it in normal play.
MAX_POINTS = 999999


class ArenaError(Exception):
    """Points refused: the reason, for the player."""


def _shim(payload):
    from web.services import grant_service
    try:
        return grant_service._invoke_shim(payload)
    except grant_service.GrantError as exc:
        raise ArenaError(str(exc)) from exc


def current_points(user_id: int, db_path=None) -> int:
    """The Arena points the save holds for the player; 0 when it has none."""
    path = db_path or config.GAME_DB_PATH
    try:
        with contextlib.closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
            row = db.execute("select data from user_bunker_ext where user_id = ?", (int(user_id),)).fetchone()
    except sqlite3.Error:
        return 0
    try:
        return int(json.loads(row[0]).get("pvp", {}).get("point", 0)) if row else 0
    except (ValueError, TypeError, AttributeError):
        return 0


def set_points(user_id: int, point: int) -> dict:
    """Backs the save up, then gives the player point Arena points."""
    if isinstance(point, bool) or not isinstance(point, int) or not 0 <= point <= MAX_POINTS:
        raise ArenaError(bunker_text.t("pods.player.arena_points_range"))
    from web.services import backup_service
    backup = backup_service.create_backup(reason="arena points").filename
    result = _shim({"action": "set_arena_points", "db_path": str(config.GAME_DB_PATH),
                    "master_data_path": str(config.find_master_data_bin()), "user_id": int(user_id),
                    "arena_points": point}) or {}
    data = result.get("data") or {}
    return {"ok": True, "point": data.get("point", point), "rank": data.get("rank", 0), "backup": backup}


@router.post("/users/{user_id}/arena-points")
def save(user_id: int, points: str = Form("")):
    try:
        value = int(points.strip())
    except ValueError:
        value = -1
    try:
        out = set_points(user_id, value)
    except ArenaError as exc:
        return RedirectResponse(f"/users/{user_id}?error={quote_plus(str(exc))}", status_code=303)
    message = bunker_text.t("pods.player.arena_points_saved", points=bunker_text.number(out["point"]),
                            rank=bunker_text.number(out["rank"]), backup=out["backup"])
    return RedirectResponse(f"/users/{user_id}?message={quote_plus(message)}", status_code=303)
