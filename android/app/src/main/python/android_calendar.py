"""Original calendar: replays the live service from global launch, week for week.

The game data is built once per loop with every rotating date moved forward by
the whole weeks between launch and the loop's start. The server's clock then
runs ahead of real time by jumpMillis (plus whole weeks for faster speeds), so
the game moves through the loop while the data stays the same. The server
reads calendar.json next to the save, and swaps in the next loop's game data
when a loop ends.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import struct

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from web import config
import android_patcher as patcher
import android_runtime as runtime
from archive.schedule import ART_TITLES

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))

DAY = 24 * 60 * 60 * 1000
WEEK = 7 * DAY
# Global launch week: Wednesday 28 July 2021, 02:00 UTC, the hour updates went live.
LAUNCH = int(datetime(2021, 7, 28, 2, tzinfo=timezone.utc).timestamp() * 1000)
LOOP_WEEKS = 144
# The first summons opened 20 hours into the launch week (28 July 2021, 22:00
# UTC). The game hangs on a summon page with none open, so a loop opens then
# (server: gametime.FirstSummons).
FIRST_SUMMONS = 20 * 60 * 60 * 1000
# Dates after the service closed (30 April 2024) mean "never ends" or "never starts".
FOREVER = int(datetime(2024, 6, 1, tzinfo=timezone.utc).timestamp() * 1000)
EARLIEST = int(datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
NEVER = int(datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)
# The game day starts at 00:00 GMT-8 (08:00 UTC).
DAY_START = 8 * 60 * 60 * 1000
# Kept in step with server/internal/masterdata/gacha.go and gacha_special.go.
SHARED_MEDAL = {46, 151} | {401, 501, 535, 541, 542, 543, 549, 550, 555, 556, 582, 583, 585, 510001, 513001, 515001, 536001, 537001, 9000035}
SPECIAL_SUMMONS = {43, 49, 52, 60, 64, 66, 70, 85, 153, 160, 199, 410, 416, 428, 430, 433, 449, 452, 453, 468, 472, 493, 501, 503, 510, 514, 515, 524, 545, 547, 581, 584, 593, 597, 9000007}
PARKED_RERUNS = {159: 3110399000, 414: 1123199000}
BANNERLESS_SKIPPED = {617, 10016, 10107, 10108, 9000040}
SPEEDS = {"1": "Real time", "2": "2×", "3.5": "3.5×", "7": "7×"}

# Rotating content: these tables move with the calendar.
ROTATING = (
    "m_beginner_campaign", "m_big_hunt_schedule", "m_big_hunt_score_reward_group_schedule",
    "m_big_hunt_weekly_attribute_score_reward_group_schedule", "m_cage_ornament", "m_comeback_campaign",
    "m_consumable_item_term", "m_costume_collection_bonus", "m_dokan", "m_enhance_campaign",
    "m_event_quest_chapter", "m_event_quest_daily_group", "m_event_quest_guerrilla_free_open",
    "m_event_quest_labyrinth_season", "m_event_quest_limit_content", "m_event_quest_limit_content_deck_restriction",
    "m_explore", "m_gacha_medal", "m_gimmick_sequence", "m_gimmick_sequence_schedule", "m_important_item_effect",
    "m_login_bonus", "m_mission_pass", "m_mission_term", "m_mom_banner", "m_mom_point_banner",
    "m_omikuji", "m_portal_cage_access_point_function_group_schedule", "m_premium_item", "m_pvp_season",
    "m_quest_bonus_term_group", "m_quest_campaign", "m_quest_schedule", "m_shop", "m_shop_item_cell_term",
    "m_tip", "m_title_flow_movie", "m_webview_mission", "m_webview_panel_mission",
)
# The main story, character and memoir lists, collections and the character
# viewer keep their original dates, so they count as already released.
# m_maintenance and the advert tables are handled as in the everything-open
# patch, which leaves the fortune draws (m_omikuji) closed.


def state_path():
    return config.GAME_DB_PATH.parent / "calendar.json"


def read_state():
    state = runtime.read_json(state_path())
    if not (isinstance(state, dict) and state.get("loopStart")):
        return None
    move_next(state)
    return state


def write_state(state):
    runtime.write_json(state_path(), state, indent=2)


def start_of_day(ms):
    return (ms - DAY_START) // DAY * DAY + DAY_START


def auto_weeks(state, real):
    """Whole weeks a faster speed has added since it was chosen, one step per daily reset."""
    twice = round(float(state.get("speed", 1)) * 2)
    since = state.get("speedSince") or real
    days = max(0, (start_of_day(real) - since) // DAY)
    return days * (twice - 2) // 14


def game_now(state, real=None):
    real = now_ms() if real is None else real
    return real + state.get("jumpMillis", 0) + auto_weeks(state, real) * WEEK


def now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def loop_end(state):
    return state["loopStart"] + LOOP_WEEKS * WEEK


def week_of(state, game):
    return (game - state["loopStart"]) // WEEK + 1


def original(state, game):
    """The same moment in the original service."""
    return game - (state["loopStart"] - LAUNCH)


# --- Game data ---------------------------------------------------------------

# Runs the final game data lost: a rerun overwrote the original dates, or a
# finished event was parked in 2030 to 2099 (scripts/calendar_history.py).
HISTORY = Path(__file__).with_name("calendar_history.json")
# An event chapter's later runs are copies of its row with these ids, so each
# run opens in its own weeks: chapter + n * COPY_STEP for the nth later run.
COPY_STEP = 10_000_000


def history():
    try:
        return json.loads(HISTORY.read_text())["tables"]
    except FileNotFoundError:
        return {}


def runs(final, lost):
    """The (start, end) ranges a row opens in a loop. One that ends up open for
    good opens from its first run; otherwise every run it had, in order."""
    start, end = final
    if EARLIEST <= start < FOREVER <= end:
        return [(min([start] + [run[0] for run in lost]), end)]
    return [tuple(run) for run in lost] or [final]


def _rows(blob):
    """The rows of a table blob as (array header, [cell bytes])."""
    from patcher.patch_masterdata import read_array_len, skip_msgpack_value
    count, pos = read_array_len(blob, 0)
    for _ in range(count):
        cells, p = read_array_len(blob, pos)
        header, values = bytes(blob[pos:p]), []
        for _ in range(cells):
            q = skip_msgpack_value(blob, p)
            values.append(bytes(blob[p:q]))
            p = q
        yield header, values
        pos = p


def _table(rows):
    total = len(rows)
    header = bytes([0x90 | total]) if total <= 0x0f else b"\xdc" + struct.pack(">H", total) if total <= 0xffff else b"\xdd" + struct.pack(">I", total)
    return header + b"".join(rows)


def restore_runs(blob, spec, copies=None):
    """Gives the rows calendar_history.json lists their runs. With copies (a
    dict), an event chapter's later runs become copies of its row, recorded as
    copies[chapter] = [copy ids]; otherwise a row keeps its first run."""
    import msgpack
    keys, (start_col, end_col), lost = spec["key"], spec["dates"], spec["rows"]
    out = []
    for header, cells in _rows(blob):
        known = lost.get("|".join(str(msgpack.unpackb(cells[i])) for i in keys)) if max(start_col, end_col) < len(cells) else None
        if known is None:
            out.append(header + b"".join(cells))
            continue
        ranges = runs((msgpack.unpackb(cells[start_col]), msgpack.unpackb(cells[end_col])), known)
        for n, (start, end) in enumerate(ranges if copies is not None else ranges[:1]):
            row = list(cells)
            # Whole int64 cells, which the loop's date shift moves (shift_table).
            row[start_col], row[end_col] = b"\xd3" + struct.pack(">q", start), b"\xd3" + struct.pack(">q", end)
            if n:
                chapter = msgpack.unpackb(cells[0])
                row[0] = msgpack.packb(chapter + n * COPY_STEP)
                copies.setdefault(chapter, []).append(chapter + n * COPY_STEP)
            out.append(header + b"".join(row))
    return _table(out)


def copy_chapter_rows(blob, copies):
    """Adds a row for each chapter copy to a table keyed by event chapter (first column)."""
    import msgpack
    out = []
    for header, cells in _rows(blob):
        out.append(header + b"".join(cells))
        for copy in copies.get(msgpack.unpackb(cells[0]), []) if cells else []:
            out.append(header + msgpack.packb(copy) + b"".join(cells[1:]))
    return _table(out)


def restore_history(toc, blob, changed, schemas):
    """Puts the runs the final game data lost back, before the loop's shift."""
    from patcher import patch_masterdata as pm
    copies = {}
    for table, spec in history().items():
        pm.apply_to_table(toc, blob, changed, table, lambda b, s=spec, t=table: restore_runs(b, s, copies if t == "m_event_quest_chapter" else None))
    if copies:
        for table, (_, columns) in schemas.items():
            if table != "m_event_quest_chapter" and table in toc and any(index == 0 and name == "EventQuestChapterId" for index, _, name in columns):
                pm.apply_to_table(toc, blob, changed, table, lambda b: copy_chapter_rows(b, copies))
    return copies

def shift_table(blob, columns, offset):
    """Move every dated int64 cell in columns by offset; far-future dates become NEVER."""
    from patcher.patch_masterdata import read_array_len, skip_msgpack_value
    count, pos = read_array_len(blob, 0)
    moved = 0
    for _ in range(count):
        cells, p = read_array_len(blob, pos)
        for index in range(cells):
            if index in columns and blob[p] == 0xd3:
                value = struct.unpack(">q", blob[p + 1:p + 9])[0]
                if EARLIEST <= value < FOREVER:
                    struct.pack_into(">q", blob, p + 1, value + offset)
                    moved += 1
                elif FOREVER <= value < NEVER:
                    struct.pack_into(">q", blob, p + 1, NEVER)
            p = skip_msgpack_value(blob, p)
        pos = p
    return moved


def build_master(origin, output, offset):
    """Writes origin's game data with rotating content moved forward by offset."""
    import msgpack
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    from patcher import patch_masterdata as pm
    from tools import dump_masterdata
    if offset % WEEK:
        raise ValueError("The calendar moves in whole weeks")
    key, iv = bytes.fromhex(pm.DEFAULT_KEY), bytes.fromhex(pm.DEFAULT_IV)
    decoded = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(Path(origin).read_bytes()), AES.block_size)
    try:
        msgpack.unpackb(decoded, raw=False, strict_map_key=False)
        raise ValueError("Master data has no tables")
    except msgpack.ExtraData as exc:
        toc, blob = exc.unpacked, exc.extra
    schemas = dump_masterdata.load_schemas()
    changed = {}
    restore_history(toc, blob, changed, schemas)
    moved = 0
    for table in ROTATING:
        if table not in toc or table not in schemas:
            continue
        columns = {index for index, kind, name in schemas[table][1] if kind == "long" and "Datetime" in name}
        moved += pm.apply_to_table(toc, blob, changed, table, lambda b: shift_table(b, columns, offset)) or 0
    for table, column in pm.EXPIRED_AD_TABLES.items():
        pm.apply_to_table(toc, blob, changed, table, lambda b, c=column: pm.expire_table_end(b, c))
    for table in pm.EMPTY_TABLES:
        if table in toc:
            changed[table] = msgpack.packb([], use_bin_type=True)
    for table, rows in pm.TABLE_ROW_ADDITIONS.items():
        pm.apply_to_table(toc, blob, changed, table, lambda b, r=rows: pm.add_table_rows(b, r))
    pm.apply_to_table(toc, blob, changed, "m_battle_group", pm.patch_wolf_chapter_battle_point)
    parts, layout, offset_in_blob = [], {}, 0
    for table, (start, length) in sorted(toc.items(), key=lambda item: item[1][0]):
        part = changed.get(table, blob[start:start + length])
        layout[table] = (offset_in_blob, len(part))
        parts.append(part)
        offset_in_blob += len(part)
    plain = msgpack.packb(layout, use_bin_type=True) + b"".join(parts)
    Path(output).write_bytes(AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plain, AES.block_size)))
    return moved


def origin_file():
    origin = patcher.folder() / "origin.bin.e"
    if not origin.exists():
        raise ValueError("Choose original master data under Advanced")
    return origin


# The next loop's game data sits beside the master data, where the server
# looks for it (gametime.NextName): a full path in calendar.json goes stale
# when iOS moves the app's folder on an update. Not .bin.e, which the tools
# would take for the master data.
NEXT_NAME = "calendar-next.bin"


def next_file():
    return config.RELEASE_DIR / NEXT_NAME


def old_next_file():
    return patcher.folder() / "calendar-next.bin.e"


def move_next(state):
    """Moves a calendar started before 1.1.3 to the next loop's new place."""
    if not state.get("next") or state["next"] == NEXT_NAME:
        return
    if old_next_file().exists():
        if next_file().exists():
            old_next_file().unlink()
        else:
            os.replace(old_next_file(), next_file())
    state["next"] = NEXT_NAME
    write_state(state)


def label(state):
    return f"Original calendar · loop {state['loop']}"


def activate_loop(state):
    candidate = patcher.folder() / "candidate.bin.e"
    try:
        build_master(origin_file(), candidate, state["loopStart"] - LAUNCH)
        patcher.activate(candidate, label(state))
    finally:
        candidate.unlink(missing_ok=True)


def prepare_next(state):
    """Builds the next loop's game data ahead, so the server can start it on its own."""
    pending = next_file().with_suffix(".tmp")
    build_master(origin_file(), pending, state["loopStart"] + LOOP_WEEKS * WEEK - LAUNCH)
    os.replace(pending, next_file())
    state["next"] = NEXT_NAME
    state["nextLoop"] = state["loop"] + 1


def roll_over(state, real=None):
    """Starts the next loop if this one has ended. Returns True when it did."""
    if game_now(state, real) < loop_end(state):
        return False
    while game_now(state, real) >= loop_end(state):
        state["loop"] += 1
        state["loopStart"] += LOOP_WEEKS * WEEK
    open_at_first_summons(state, real)
    activate_loop(state)
    state.pop("next", None)
    prepare_next(state)
    write_state(state)
    return True


def open_at_first_summons(state, real=None):
    """Moves a clock before the loop's first summons on in whole days until they are open (server: OpenAtFirstSummons). Returns True when it did."""
    behind = state["loopStart"] + FIRST_SUMMONS - game_now(state, real)
    if behind <= 0:
        return False
    state["jumpMillis"] = state.get("jumpMillis", 0) + -(-behind // DAY) * DAY
    return True


def new_state(real):
    start = LAUNCH + (real - LAUNCH) // WEEK * WEEK
    state = {"version": 1, "loop": 1, "loopStart": start, "jumpMillis": 0, "speed": 1, "speedSince": start_of_day(real)}
    open_at_first_summons(state, real)
    return state


def start_preview(real=None):
    real = now_ms() if real is None else real
    state = new_state(real)
    now = game_now(state, real)
    return {"day": day_label(now), "original": day_label(original(state, now)), "ends": day_label(loop_end(state))}


def turn_on(real=None):
    real = now_ms() if real is None else real
    state = new_state(real)
    activate_loop(state)
    prepare_next(state)
    write_state(state)
    return state


def turn_off():
    state_path().unlink(missing_ok=True)
    next_file().unlink(missing_ok=True)
    old_next_file().unlink(missing_ok=True)


def set_speed(state, speed, real=None):
    if speed not in SPEEDS:
        raise ValueError("Unknown speed")
    real = now_ms() if real is None else real
    # Keep the weeks the old speed has already added.
    state["jumpMillis"] = state.get("jumpMillis", 0) + auto_weeks(state, real) * WEEK
    state["speed"] = float(speed) if "." in speed else int(speed)
    state["speedSince"] = start_of_day(real)


def jump(state, target, real=None):
    """Moves the clock forward to target in whole days, so the daily reset stays at the same hour."""
    now = game_now(state, real)
    if target <= now:
        raise ValueError("The calendar only moves forward")
    if target >= loop_end(state):
        raise ValueError("Choose a week in this loop")
    state["jumpMillis"] = state.get("jumpMillis", 0) + -(-(target - now) // DAY) * DAY


# --- What is open ------------------------------------------------------------

def table(name):
    return runtime.read_json(config.MASTERDATA_DIR / f"EntityM{name}Table.json", []) or []


def names(kind):
    data = runtime.read_json(config.NAMES_DIR / f"{kind}.json", {}) or {}
    return {r["id"]: r["name"] for r in data.get("records", []) if isinstance(r, dict) and r.get("name_found") and isinstance(r.get("id"), int)}


def entries():
    """Dated content the Schedule page lists: (kind, name, start, end)."""
    found = []
    event_names = names("event_quests")
    lost = history().get("m_event_quest_chapter", {}).get("rows", {})
    for row in table("EventQuestChapter"):
        final = (row["StartDatetime"], row["EndDatetime"])
        for start, end in runs(final, lost.get(str(row["EventQuestChapterId"]), [])):
            found.append(("event", event_names.get(row["EventQuestChapterId"]), start, end))
    banner_names = names("gacha_banners")
    # The summons the server offers (server/internal/masterdata/gacha.go):
    # those with a medal, summons sharing a known medal, and the special
    # free, paid-only and guaranteed summons.
    medals = {row["ShopTransitionGachaId"]: row for row in table("GachaMedal")}
    offered = set(medals) | SHARED_MEDAL | SPECIAL_SUMMONS
    parked = set()
    for row in table("MomBanner"):
        gacha = row["DestinationDomainId"]
        if row["DestinationDomainType"] == 1 and gacha in PARKED_RERUNS and gacha in medals and gacha not in parked:
            # Only placeholder rows: the dates come from the medal (see parkedReruns).
            parked.add(gacha)
            convert = medals[gacha]["AutoConvertDatetime"]
            found.append(("summon", banner_names.get(row["MomBannerId"]) or ART_TITLES.get(row["BannerAssetName"]), convert - PARKED_RERUNS[gacha], convert - 2 * DAY))
    for row in table("MomBanner"):
        if row["DestinationDomainType"] == 1 and row["DestinationDomainId"] in offered and row["DestinationDomainId"] not in PARKED_RERUNS:
            # Some titles are only in the banner art (ART_TITLES).
            found.append(("summon", banner_names.get(row["MomBannerId"]) or ART_TITLES.get(row["BannerAssetName"]), row["StartDatetime"], row["EndDatetime"]))
    # Summons with a medal but no banner row (server: bannerlessSummons).
    with_banner = {row["DestinationDomainId"] for row in table("MomBanner") if row["DestinationDomainType"] == 1}
    opens = shop_opens_by_price()
    item_names = names("consumables")
    for gacha, medal in medals.items():
        start = opens.get(medal["ConsumableItemId"])
        end = medal["AutoConvertDatetime"] - 2 * DAY
        if gacha in with_banner or gacha in BANNERLESS_SKIPPED or start is None or not 0 < start < end:
            continue
        shard = item_names.get(medal["ConsumableItemId"], "")
        label = shard[shard.find("(") + 1:shard.rfind(")")] if "(" in shard else ""
        if label and "summons" not in label.lower():
            label += " Summons"
        found.append(("summon", label or None, start, end))
    shop_names = names("shops")
    for row in table("Shop"):
        if row["ShopGroupType"] == 4:
            found.append(("shop", shop_names.get(row["ShopId"]), row["StartDatetime"], row["EndDatetime"]))
    for row in table("PvpSeason"):
        if not row.get("IsInvalid"):
            found.append(("arena", f"Arena Season {row['PvpSeasonId'] % 1000:03d}", row["SeasonStartDatetime"], row["SeasonEndDatetime"]))
    for index, row in enumerate(sorted(table("MissionPass"), key=lambda r: r["StartDatetime"]), 1):
        found.append(("pass", f"Mission pass, month {index}", row["StartDatetime"], row["EndDatetime"]))
    for row in table("BigHuntSchedule"):
        found.append(("hunt", f"Subjugation Battle {row['BigHuntScheduleId']}", row["ChallengeStartDatetime"], row["ChallengeEndDatetime"]))
    for row in table("EnhanceCampaign") + table("QuestCampaign"):
        found.append(("campaign", "", row["StartDatetime"], row["EndDatetime"]))
    for row in table("ConsumableItemTerm"):
        found.append(("expiry", "", row["StartDatetime"], row["EndDatetime"]))
    # Content that never ends after release is part of the game, not the calendar.
    return [e for e in found if e[2] < NEVER and e[3] < NEVER and e[2] < e[3]]


def shop_opens_by_price():
    """When the first shop selling for each item opens (server: shopOpensByPrice)."""
    price = {r["ShopItemId"]: r["PriceId"] for r in table("ShopItem")}
    cell = {r["ShopItemCellId"]: r["ShopItemId"] for r in table("ShopItemCell")}
    groups = {}
    for r in table("ShopItemCellGroup"):
        groups.setdefault(r["ShopItemCellGroupId"], set()).add(price.get(cell.get(r["ShopItemCellId"])))
    out = {}
    for shop in table("Shop"):
        for item in groups.get(shop["ShopItemCellGroupId"], ()):
            if item is not None and (item not in out or shop["StartDatetime"] < out[item]):
                out[item] = shop["StartDatetime"]
    return out


def day_label(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%a %-d %b %Y")


def short_label(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%a %-d %b")


def open_at(items, at):
    return [e for e in items if e[2] <= at < e[3]]


OTHER = {"event": "other event", "summon": "other summon", "shop": "other shop"}


def summary(items, at):
    """Open content by kind, soonest to close first; unnamed entries are counted in one line."""
    groups, unnamed = {}, {}
    for kind, name, start, end in sorted(open_at(items, at), key=lambda e: e[3]):
        if name or kind in ("campaign", "expiry"):
            groups.setdefault(kind, []).append({"name": name, "until": short_label(end - 1)})
        else:
            unnamed[kind] = unnamed.get(kind, 0) + 1
    for kind, count in unnamed.items():
        groups.setdefault(kind, []).append({"name": f"{count} {OTHER[kind]}{'s' if count != 1 else ''}", "until": ""})
    return groups


def updates(state, items, after):
    """Days in the rest of the loop when new events or summons open, named by their first event."""
    days = {}
    for kind, name, start, end in sorted(items, key=lambda e: (e[2], e[0] != "event")):
        if kind in ("event", "summon") and after < start < loop_end(state):
            day = days.setdefault(start_of_day(start), {"at": start, "names": [], "count": 0})
            day["count"] += 1
            if name:
                day["names"].append(name)
    return [{"at": v["at"], "day": day_label(v["at"]), "week": week_of(state, v["at"]), "name": (v["names"] or ["New summons and quests"])[0],
             "more": v["count"] - 1, "all": " ".join(v["names"])} for k, v in sorted(days.items())]


def preview(state, items, now, target):
    """What a jump from now to target opens, still pays out, and skips."""
    arrive = now + -(-(target - now) // DAY) * DAY
    paid, missed = [], {}
    for kind, name, start, end in items:
        if not now < end <= arrive:
            continue
        if start <= now and kind in ("arena", "pass"):
            paid.append(name)
        elif start > now and kind in ("event", "summon", "shop", "arena", "pass"):
            missed[kind] = missed.get(kind, 0) + 1
    return {"arrive": arrive, "day": day_label(arrive), "original": day_label(original(state, arrive)), "week": week_of(state, arrive),
            "days": (arrive - now) // DAY, "open": summary(items, arrive), "paid": paid, "missed": missed}


# --- Pages -------------------------------------------------------------------

def redirect(path="/patcher", **kwargs):
    from urllib.parse import urlencode
    return RedirectResponse(path + ("?" + urlencode(kwargs) if kwargs else ""), status_code=303)


def context(state):
    now = game_now(state)
    items = entries()
    return {"state": state, "loop": state["loop"], "week": week_of(state, now), "weeks": LOOP_WEEKS,
            "progress": round(100 * (now - state["loopStart"]) / (LOOP_WEEKS * WEEK), 1),
            "today": day_label(now), "original": day_label(original(state, now)), "ends": day_label(loop_end(state)),
            "speed": str(state.get("speed", 1)), "speeds": SPEEDS, "open": summary(items, now), "now": now}


@router.post("/patcher/calendar/on")
def calendar_on():
    try:
        turn_on()
        return redirect(message="Calendar on. Close Pod Programs and tap Deploy.")
    except Exception as exc:
        return redirect(error=str(exc))


@router.post("/patcher/calendar/off")
def calendar_off():
    turn_off()
    return redirect(message="Calendar off. Choose content and tap Apply.")


@router.post("/patcher/calendar/speed")
def calendar_speed(speed: str = Form(...)):
    state = read_state()
    if not state:
        return redirect(error="The calendar is off")
    try:
        set_speed(state, speed)
        write_state(state)
        return redirect(message="Speed saved. Close Pod Programs and tap Deploy.")
    except Exception as exc:
        return redirect(error=str(exc))


@router.post("/patcher/calendar/jump")
def calendar_jump(target: int = Form(...)):
    state = read_state()
    if not state:
        return redirect(error="The calendar is off")
    try:
        jump(state, target)
        write_state(state)
        return redirect(message=f"Moved to week {week_of(state, game_now(state))}. Close Pod Programs and tap Deploy.")
    except Exception as exc:
        return redirect(error=str(exc))


@router.get("/patcher/calendar/next")
def calendar_next(request: Request, by: str = "update"):
    state = read_state()
    if not state:
        return redirect(error="The calendar is off")
    now = game_now(state)
    items = entries()
    if by == "week":
        target = now + WEEK
        title = "Next week"
    else:
        upcoming = updates(state, items, now)
        if not upcoming:
            return redirect(error="No more updates in this loop")
        target, title = upcoming[0]["at"], "Next update"
    if target >= loop_end(state):
        return redirect(error="That is past the end of this loop")
    view = preview(state, items, now, target)
    def listed(moments):
        found = [e for e, at in moments if e[0] in ("event", "summon", "shop") and now < at <= view["arrive"]]
        return {"names": [e[1] for e in found if e[1]], "more": sum(1 for e in found if not e[1])}
    opens = listed((e, e[2]) for e in items)
    closes = listed((e, e[3]) for e in items)
    return templates.TemplateResponse(request, "calendar_next.html", {"active": "patcher", "title": title, "target": target,
        "view": view, "opens": opens, "closes": closes})


@router.get("/patcher/calendar/jump")
def calendar_jump_view(request: Request, at: int = 0):
    state = read_state()
    if not state:
        return redirect(error="The calendar is off")
    now = game_now(state)
    items = entries()
    upcoming = updates(state, items, now)
    week = week_of(state, now)
    target = at or (upcoming[0]["at"] if upcoming else 0)
    view = preview(state, items, now, target) if now < target < loop_end(state) else None
    return templates.TemplateResponse(request, "calendar_jump.html", {"active": "patcher", "now": now, "week": week,
        "today": day_label(now), "weeks": LOOP_WEEKS, "updates": upcoming, "target": target, "view": view,
        "loopStart": state["loopStart"], "weekMillis": WEEK})
