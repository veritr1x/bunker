"""Pod Programs › Story Jump: brings a save forward to the start of a main-story
chapter, or a quest in one, as if everything before it had been played.

The page reads where the save is from the save itself (read-only); the jump
is the editing shim's "story_jump" (bunker_story.go), which clears each quest
before the target the way the server clears a quest the story moves past.
A preview is the same action with dry_run. Every jump is backed up first, and
on the Original calendar's first loop the game data is rebuilt so the chapter
jumped to is open (android_calendar.reopen_reached_chapters).
"""
from __future__ import annotations

import contextlib
import json
import sqlite3

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import android_calendar as cal
from web import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))

SEASON2 = 2
KINDS = {1: "Character", 7: "Character", 2: "Weapon", 8: "Weapon", 3: "Companion", 9: "Companion",
         4: "Part", 10: "Part", 13: "Key item", 5: "Material", 6: "Item", 14: "Debris"}


class StoryError(Exception):
    """A jump refused: the shim's reason, for the player."""


def _shim(payload):
    from web.services import grant_service
    try:
        return grant_service._invoke_shim(payload)
    except grant_service.GrantError as exc:
        raise StoryError(str(exc)) from exc


def _backup():
    from web.services import backup_service
    return backup_service.create_backup(reason="story jump").filename


def _name(possession_type, possession_id):
    import android_gift
    if possession_type == 13:
        from web.services import names_service
        return names_service.get_names("important_items").get(possession_id, f"#{possession_id}")
    base = {7: 1, 8: 2, 9: 3, 10: 4}.get(possession_type, possession_type)
    return android_gift._name(base, possession_id)


# --- The story's shape (master data) ------------------------------------------

def _story():
    """Seasons → routes → chapters → quests (difficulty 1), in play order."""
    routes = sorted(cal.table("MainQuestRoute"), key=lambda r: r["SortOrder"])
    season_of = {r["MainQuestRouteId"]: r["MainQuestSeasonId"] for r in routes}
    seasons: dict[int, list[int]] = {}
    for r in routes:
        seasons.setdefault(r["MainQuestSeasonId"], []).append(r["MainQuestRouteId"])
    main = {g["MainQuestSequenceGroupId"]: g["MainQuestSequenceId"] for g in cal.table("MainQuestSequenceGroup") if g["DifficultyType"] == 1}
    seqs: dict[int, list[dict]] = {}
    for s in cal.table("MainQuestSequence"):
        seqs.setdefault(s["MainQuestSequenceId"], []).append(s)
    chapters: dict[int, list[dict]] = {}
    for c in sorted(cal.table("MainQuestChapter"), key=lambda c: c["SortOrder"]):
        if c["MainQuestSequenceGroupId"] not in main:
            continue
        quests = [s["QuestId"] for s in sorted(seqs.get(main[c["MainQuestSequenceGroupId"]], []), key=lambda s: s["SortOrder"])]
        chapters.setdefault(c["MainQuestRouteId"], []).append({"id": c["MainQuestChapterId"], "route": c["MainQuestRouteId"], "quests": quests})
    return seasons, season_of, chapters


def _titles():
    """Chapter titles, season titles and route characters from the game's text (names/main_quests.json)."""
    try:
        data = json.loads((config.NAMES_DIR / "main_quests.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        return {}
    records = data.get("records", []) if isinstance(data, dict) else data
    return {r["id"]: r for r in records if isinstance(r, dict) and isinstance(r.get("id"), int)}


def _position(user_id):
    """The quest the save's story is at (0 if none) and the quests it has cleared."""
    try:
        with contextlib.closing(sqlite3.connect(f"file:{config.GAME_DB_PATH}?mode=ro", uri=True)) as db:
            cleared = {q for (q,) in db.execute("select quest_id from user_quests where user_id = ? and clear_count > 0", (user_id,))}
            row = db.execute("select head_quest_scene_id from user_main_quest where user_id = ?", (user_id,)).fetchone()
    except sqlite3.Error:
        return 0, set()
    scene_quest = {r["QuestSceneId"]: r["QuestId"] for r in cal.table("QuestScene")}
    return scene_quest.get(row[0] if row else 0, 0), cleared


def _taken_route(seasons, chapters, route_of, head, cleared):
    """The season-2 route the save has taken, or 0."""
    if route_of.get(head) in seasons.get(SEASON2, []):
        return route_of[head]
    for r in seasons.get(SEASON2, []):
        if any(q in cleared for c in chapters.get(r, []) for q in c["quests"]):
            return r
    return 0


def chapters(user_id: int, season2_route: int | None = None) -> dict:
    """The page's list: each season's chapters on the chosen season-2 route,
    each chapter and quest "cleared", "here", "ahead" (can be jumped to),
    "passed" (behind the save, not cleared) or "other" (the save took the other route)."""
    seasons, season_of, chapter_rows = _story()
    route_of = {q: c["route"] for cs in chapter_rows.values() for c in cs for q in c["quests"]}
    head, cleared = _position(user_id)
    taken = _taken_route(seasons, chapter_rows, route_of, head, cleared)
    route = season2_route if season2_route in seasons.get(SEASON2, []) else (taken or (seasons.get(SEASON2) or [0])[0])
    path = [q for s in sorted(seasons) for r in seasons[s] if len(seasons[s]) == 1 or r == route
            for c in chapter_rows.get(r, []) for q in c["quests"]]
    at = path.index(head) if head in path else -1
    other = bool(taken) and taken != route
    titles = _titles()

    def state(q):
        if q in cleared:
            return "cleared"
        if other and season_of[route_of[q]] >= SEASON2:
            return "other"
        if q == head:
            return "here"
        return "ahead" if path.index(q) > at else "passed"

    out = []
    for s in sorted(seasons):
        rows = []
        for r in seasons[s]:
            if len(seasons[s]) > 1 and r != route:
                continue
            for c in chapter_rows.get(r, []):
                t = titles.get(c["id"], {})
                quests = [{"id": q, "name": f"Quest {i}", "state": state(q)} for i, q in enumerate(c["quests"], 1)]
                states = {q["state"] for q in quests}
                cstate = ("cleared" if states == {"cleared"} else "other" if "other" in states else
                          "here" if "here" in states else quests[0]["state"] if quests else "passed")
                rows.append({"id": c["id"], "title": t.get("name") or f"Chapter {c['id']}", "state": cstate, "quests": quests,
                             "start": quests[0]["id"] if quests and quests[0]["state"] == "ahead" else 0})
        first = next((titles[c["id"]] for c in chapter_rows.get(seasons[s][0], []) if c["id"] in titles), {})
        out.append({"season": s, "title": first.get("season_title") or f"Season {s}", "chapters": rows,
                    "routes": [{"id": r, "first": chapter_rows[r][0]["id"], "last": chapter_rows[r][-1]["id"],
                                "character": next((titles[c["id"]].get("character_name") for c in chapter_rows[r] if c["id"] in titles), "")}
                               for r in seasons[s] if len(seasons[s]) > 1 and chapter_rows.get(r)]})
    return {"route": route, "taken": taken, "head": head, "seasons": out}


# --- Preview and jump -------------------------------------------------------------

def _request(user_id, quest_id, season2_route, dry_run):
    return {"action": "story_jump", "db_path": str(config.GAME_DB_PATH), "master_data_path": str(config.find_master_data_bin()),
            "user_id": int(user_id), "story": {"quest_id": int(quest_id), "season2_route": int(season2_route), "dry_run": bool(dry_run)}}


def _summary(data):
    _, _, chapter_rows = _story()
    chapter_of = {q: c["id"] for cs in chapter_rows.values() for c in cs for q in c["quests"]}
    seen = []
    for q in data.get("cleared", []):
        c = chapter_of.get(q)
        if c is not None and c not in seen:
            seen.append(c)
    span = "" if not seen else str(seen[0]) if len(seen) == 1 else f"{seen[0]}–{seen[-1]}"
    grants = [{"kind": KINDS.get(g["possession_type"], "Item"), "name": _name(g["possession_type"], g["possession_id"]), "count": g["count"]}
              for g in data.get("grants", [])]
    return {"cleared_count": len(data.get("cleared", [])), "chapters": span, "grants": grants, "gems": data.get("gems", 0)}


def preview(user_id: int, quest_id: int, season2_route: int) -> dict:
    """What a jump would clear and give, without writing."""
    result = _shim(_request(user_id, quest_id, season2_route, True)) or {}
    return dict({"ok": True}, **_summary(result.get("data") or {}))


def jump(user_id: int, quest_id: int, season2_route: int) -> dict:
    """Backs the save up, jumps, then opens the chapter under the Original calendar.
    A trial run comes first, so a refused jump leaves no backup behind."""
    _shim(_request(user_id, quest_id, season2_route, True))
    backup = _backup()
    result = _shim(_request(user_id, quest_id, season2_route, False)) or {}
    try:
        calendar = "rebuilt" if cal.reopen_reached_chapters() else "not needed"
    except Exception as exc:  # the jump stands; the next calendar rebuild opens the chapter
        calendar = f"failed: {exc}"
    out = dict({"ok": True, "backup": backup, "calendar": calendar}, **_summary(result.get("data") or {}))
    out["message"] = f"Cleared {out['cleared_count']} quests. Backup: {backup}."
    return out


# --- Routes -----------------------------------------------------------------------

def _body(payload):
    return int(payload.get("quest_id") or 0), int(payload.get("season2_route") or 0)


@router.get("/story")
def open_player_in_use():
    """Programs › Story Jump: the player the game plays as."""
    import android_players
    return RedirectResponse(f"/users/{android_players.device_player() or 1}/story", status_code=303)


@router.get("/users/{user_id}/story")
def page(request: Request, user_id: int, route: int = 0):
    view = chapters(user_id, route or None)
    return templates.TemplateResponse(request, "story_jump.html", {"active": "story", "user_id": user_id, "view": view})


@router.post("/users/{user_id}/story/preview")
def preview_route(user_id: int, payload: dict = Body(...)):
    try:
        out = JSONResponse(preview(user_id, *_body(payload)))
    except StoryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    out.headers["X-Bunker-Unchanged"] = "1"  # a preview writes nothing: the game keeps playing
    return out


@router.post("/users/{user_id}/story/jump")
def jump_route(user_id: int, payload: dict = Body(...)):
    try:
        return jump(user_id, *_body(payload))
    except StoryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
