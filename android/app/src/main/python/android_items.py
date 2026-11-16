"""Pod Programs › Item Editor › Set: makes an item's count the amount given.

Grant adds to what the player holds; Set writes the count itself, up or down
(0 empties it). The edit is the editing shim's "set_possession_batch"
(bunker_set_items.go). The save is backed up before each change, as a grant's
is; amounts out of range are refused before that.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

import bunker_text
from web import config

router = APIRouter()

STACKABLE = frozenset({5, 6, 11, 12, 13})  # material, consumable, paid gem, free gem, important item
MAX_COUNT = 2_147_483_647  # the game's 32-bit counts


class SetError(Exception):
    """An amount refused: the reason, for the player."""


def _shim(payload):
    from web.services import grant_service
    try:
        return grant_service._invoke_shim(payload)
    except grant_service.GrantError as exc:
        raise SetError(str(exc)) from exc


def _number(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def set_counts(user_id: int, items: list[dict]) -> list[dict]:
    """Backs the save up, then makes each {possession_type, possession_id, count} the count held."""
    for item in items:
        kind, pid, count = item.get("possession_type"), item.get("possession_id"), item.get("count")
        if not (_number(kind) and kind in STACKABLE and _number(pid) and _number(count) and 0 <= count <= MAX_COUNT):
            raise SetError(bunker_text.t("pods.items.set_range"))
    from web.services import backup_service, grant_service
    backup_service.create_backup(reason=grant_service.BACKUP_REASON)
    grants = [{"possession_type": i["possession_type"], "possession_id": i["possession_id"], "count": i["count"]} for i in items]
    _shim({"action": "set_possession_batch", "db_path": str(config.GAME_DB_PATH), "user_id": int(user_id), "grants": grants})
    return [{"possession_type": g["possession_type"], "possession_id": g["possession_id"], "amount": g["count"]} for g in grants]


@router.post("/users/{user_id}/edit/items/set")
def set_endpoint(user_id: int, payload: dict[str, Any] = Body(...)) -> JSONResponse:
    try:
        results = set_counts(user_id, [payload])
    except SetError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "results": results})
