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
from typing import NamedTuple

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from web import config
import android_patcher as patcher
import android_runtime as runtime
from archive.schedule import ART_TITLES

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))
import bunker_text  # noqa: E402
from bunker_text import t, t_count  # noqa: E402
bunker_text.install(templates)  # Bunker's own text, in the chosen language

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
SPEEDS = ("1", "2", "3.5", "7")  # weeks a week (patcher.html names them)

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


def peek_state():
    """The calendar's saved state as it is, without read_state's upkeep
    (moving and rebuilding files): for pages that only show the clock."""
    state = runtime.read_json(state_path())
    return state if isinstance(state, dict) and state.get("loopStart") else None


def read_state():
    state = runtime.read_json(state_path())
    if not (isinstance(state, dict) and state.get("loopStart")):
        return None
    move_next(state)
    if state.get("dataVersion") != DATA_VERSION:
        activate_loop(state)
        state["dataVersion"] = DATA_VERSION
        write_state(state)
    refresh_view(state)
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


def shown_clock(state, real=None):
    """The time the game sees: real time with the calendar off, else the
    calendar's, moved back to the original service by "Show original dates"."""
    real = now_ms() if real is None else real
    if not state:
        return real
    game = game_now(state, real)
    return original(state, game) if state.get("originalDates") else game


def client_days_file():
    """Beside the save: the launcher clears the game's day markers before the
    game next starts (GameProcessProvider, LunarLauncher.m)."""
    return config.GAME_DB_PATH.parent / "client-days.reset"


def clock_moved(before, after):
    """The game keeps day markers (the last day it showed the login bonus,
    Mama's News, the roulette's FREE badge...) and counts only a later day as a
    new one. When its clock goes back they would hide those until the old day
    came round again, so they are cleared."""
    if after < before:
        mark_client_days_reset()


def mark_client_days_reset():
    """Clears the game's day markers before it next starts."""
    client_days_file().write_text("")


# --- Game data ---------------------------------------------------------------

# Runs the final game data lost: a rerun overwrote the original dates, or a
# finished event was parked in 2030 to 2099 (scripts/calendar_history.py).
HISTORY = Path(__file__).with_name("calendar_history.json")
# An event chapter's later runs are copies of its row with these ids, so each
# run opens in its own weeks: chapter + n * COPY_STEP for the nth later run.
COPY_STEP = 10_000_000
# Abyss Towers (EventQuestType 10) reran 2021-2023 before they stayed for good
# (notice 1037): each run is its own copy, with the floors it had then
# (tower_floors.json, from the weekly game data: 20, then 30, 40 and 50).
TOWER_TYPE = 10
TOWER_FLOORS = Path(__file__).with_name("tower_floors.json")


def history():
    try:
        return json.loads(HISTORY.read_text())["tables"]
    except FileNotFoundError:
        return {}


# Home banners whose run is not restored: their summon is not listed then
# (Bunker leaves out summon 9000085; summon 159 is a parked rerun), so the
# banner would open the Summons screen on another summon.
UNRESTORED_BANNERS = {274, 365}


def history_spec(table, spec):
    """A table's recorded runs to restore (calendar_history.json)."""
    if table != "m_mom_banner":
        return spec
    return dict(spec, rows={k: v for k, v in spec["rows"].items() if int(k) not in UNRESTORED_BANNERS})


def runs(final, lost, keep_runs=False):
    """The (start, end) ranges a row opens in a loop. One that ends up open for
    good opens from its first run, unless keep_runs (an Abyss Tower, which
    reran before it stayed); otherwise every run it had, in order."""
    start, end = final
    if keep_runs and lost:
        return [tuple(run) for run in lost]
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


# Tables whose rows replay every run as copies, and the id columns a copy moves
# by n * COPY_STEP: event chapters, and the Anecdotes (web panel missions: the
# mission and its target sheet; the sheet's story pages stay shared).
COPIED = {
    "m_event_quest_chapter": (0,),
    "m_webview_mission": (0, 3),
    "m_webview_panel_mission": (0,),
}


# The game's Library (Card Stories) and the Missions screen list the web
# missions of type 1, one row each; the live game had one row per Anecdote,
# its dates changed for each run. An Anecdote with several runs lists its runs
# as type 2 and gets one type-1 row for the lists at LIBRARY_SLOT * COPY_STEP,
# from its first run's start to its last run's end, with a sheet of its own
# (the game finds a mission's pages by its id) holding the first run's pages.
LIBRARY_SLOT = 99
MISSION_LISTED, MISSION_RUN = 1, 2


def library_missions(blob):
    """m_webview_mission with each Anecdote listed once (LIBRARY_SLOT)."""
    import msgpack
    rows = list(_rows(blob))
    runs = {}
    for _, cells in rows:
        runs.setdefault(msgpack.unpackb(cells[0]) % COPY_STEP, []).append(cells)
    out = []
    for header, cells in rows:
        cells = list(cells)
        if len(runs[msgpack.unpackb(cells[0]) % COPY_STEP]) > 1:
            cells[2] = msgpack.packb(MISSION_RUN)
        out.append(header + b"".join(cells))
    for base, group in sorted(runs.items()):
        if len(group) < 2:
            continue
        first = min(group, key=lambda c: msgpack.unpackb(c[0]))
        date = lambda c: b"\xd3" + struct.pack(">q", c)  # whole int64 cells, which the loop's date shift moves
        listed = msgpack.packb(base + LIBRARY_SLOT * COPY_STEP)
        cells = [listed, first[1], msgpack.packb(MISSION_LISTED), listed,
                 date(min(msgpack.unpackb(c[4]) for c in group)), date(max(msgpack.unpackb(c[5]) for c in group))]
        out.append(bytes([0x90 | len(cells)]) + b"".join(cells))
    return _table(out)


def library_sheets(blob):
    """m_webview_panel_mission with the sheet of each library_missions row: the
    first run's pages, dated across all the runs."""
    import msgpack
    rows = list(_rows(blob))
    runs = {}
    for _, cells in rows:
        runs.setdefault(msgpack.unpackb(cells[0]) % COPY_STEP, {}).setdefault(msgpack.unpackb(cells[0]), []).append(cells)
    out = [header + b"".join(cells) for header, cells in rows]
    date = lambda c: b"\xd3" + struct.pack(">q", c)
    for base, sheets in sorted(runs.items()):
        if len(sheets) < 2:
            continue
        every = [c for pages in sheets.values() for c in pages]
        start, end = min(msgpack.unpackb(c[3]) for c in every), max(msgpack.unpackb(c[4]) for c in every)
        for page in sorted(sheets[min(sheets)], key=lambda c: msgpack.unpackb(c[1])):
            cells = [msgpack.packb(base + LIBRARY_SLOT * COPY_STEP), page[1], page[2], date(start), date(end)]
            out.append(bytes([0x90 | len(cells)]) + b"".join(cells))
    return _table(out)


def merge_overlaps(lost):
    """Runs with overlapping windows as one, the first's (a run the history
    recorded twice: Anecdote: Tower's April 2022 run, 6 hours apart)."""
    out = []
    for run in sorted(lost):
        if out and run[0] < out[-1][-1]:
            continue
        out.append(run)
    return out


def restore_runs(blob, spec, copies=None, table_name="m_event_quest_chapter"):
    """Gives the rows calendar_history.json lists their runs. With copies (a
    dict), a row's later runs become copies of it (COPIED), recorded as
    copies[id] = [copy ids]; otherwise a row keeps its first run."""
    import msgpack
    keys, (start_col, end_col), lost = spec["key"], spec["dates"], spec["rows"]
    moved = COPIED.get(table_name, (0,))
    out = []
    for header, cells in _rows(blob):
        known = lost.get("|".join(str(msgpack.unpackb(cells[i])) for i in keys)) if max(start_col, end_col) < len(cells) else None
        if known is None:
            out.append(header + b"".join(cells))
            continue
        tower = copies is not None and table_name == "m_event_quest_chapter" and len(cells) > 1 and msgpack.unpackb(cells[1]) == TOWER_TYPE
        if table_name != "m_event_quest_chapter":
            known = merge_overlaps(known)
        ranges = runs((msgpack.unpackb(cells[start_col]), msgpack.unpackb(cells[end_col])), known, keep_runs=tower)
        for n, (start, end) in enumerate(ranges if copies is not None else ranges[:1]):
            row = list(cells)
            # Whole int64 cells, which the loop's date shift moves (shift_table).
            row[start_col], row[end_col] = b"\xd3" + struct.pack(">q", start), b"\xd3" + struct.pack(">q", end)
            if n:
                for col in moved:
                    row[col] = msgpack.packb(msgpack.unpackb(cells[col]) + n * COPY_STEP)
                first = msgpack.unpackb(cells[0])
                copies.setdefault(first, []).append(first + n * COPY_STEP)
            out.append(header + b"".join(row))
    return _table(out)


def tower_floors(chapters, groups, sequences, group_col, floors):
    """Gives each tower run the floors it had: a run with fewer than all of them
    gets a sequence of its first floors (sequence and group id: the tower's +
    floors * COPY_STEP). floors: tower -> floor count per run, the base row's
    run first. Returns the chapter, sequence group and sequence tables."""
    import msgpack
    first_seq = {}
    for _, c in _rows(groups):
        first_seq.setdefault(msgpack.unpackb(c[0]), msgpack.unpackb(c[2]))
    quests = {}
    for _, c in _rows(sequences):
        quests.setdefault(msgpack.unpackb(c[0]), []).append((msgpack.unpackb(c[1]), c))
    chapter_rows, new_groups, new_sequences, made = [], [], [], set()
    for header, cells in _rows(chapters):
        chapter = msgpack.unpackb(cells[0])
        counts = floors.get(str(chapter % COPY_STEP))
        n = chapter // COPY_STEP
        group = msgpack.unpackb(cells[group_col])
        seq = first_seq.get(group)
        if counts and n < len(counts) and seq in quests and counts[n] < len(quests[seq]):
            want = counts[n]
            new_group, new_seq = group + want * COPY_STEP, seq + want * COPY_STEP
            if new_group not in made:
                made.add(new_group)
                new_groups.append(bytes([0x93]) + msgpack.packb(new_group) + msgpack.packb(1) + msgpack.packb(new_seq))
                for order, qc in sorted(quests[seq], key=lambda q: q[0])[:want]:
                    new_sequences.append(bytes([0x90 | len(qc)]) + msgpack.packb(new_seq) + b"".join(qc[1:]))
            cells = list(cells)
            cells[group_col] = msgpack.packb(new_group)
        chapter_rows.append(header + b"".join(cells))
    keep = lambda blob: [h + b"".join(c) for h, c in _rows(blob)]
    return _table(chapter_rows), _table(keep(groups) + new_groups), _table(keep(sequences) + new_sequences)


# A rerun event's earlier runs as they were (scripts/event_runs.py): each its
# own exchange and medal (EventQuestLink), the medal its page shows and the
# quests it had. The final game data keeps the last run's only. The server
# pays each run's drops and quest bonuses from the same file.
EVENT_RUNS = Path(__file__).with_name("event_runs.json")
RUN_IDS = 100  # an earlier run's own link, sequence group and sequences: id + (RUN_IDS + n) * COPY_STEP


def event_run_data():
    try:
        return json.loads(EVENT_RUNS.read_text())["chapters"]
    except FileNotFoundError:
        return {}


def event_runs(chapters, links, groups, sequences, runs, cols):
    """Gives each chapter copy of a rerun event its run's link (a new row with
    that run's exchange and medal), shown medal and quests (a trimmed sequence
    group when the run had fewer). runs: base chapter -> per-run data, the
    last run None; cols: the chapter's link, display and group columns.
    Returns the chapter, link, sequence group and sequence tables."""
    import msgpack
    group_rows, seq_rows = {}, {}
    for _, c in _rows(groups):
        group_rows.setdefault(msgpack.unpackb(c[0]), []).append(c)
    for _, c in _rows(sequences):
        seq_rows.setdefault(msgpack.unpackb(c[0]), []).append(c)
    chapter_rows, new_links, new_groups, new_seqs, made = [], [], [], [], set()
    for header, cells in _rows(chapters):
        chapter = msgpack.unpackb(cells[0])
        n = chapter // COPY_STEP
        recorded = runs.get(str(chapter % COPY_STEP)) or []
        run = recorded[n] if n < len(recorded) else None
        if run:
            cells, step = list(cells), (RUN_IDS + n) * COPY_STEP
            link = run["link"] + step
            row = run["link_row"]
            new_links.append(bytes([0x95]) + b"".join(msgpack.packb(v) for v in (link, 3, row["shop"], row["possession_type"], row["possession_id"])))
            cells[cols["link"]] = msgpack.packb(link)
            cells[cols["display"]] = msgpack.packb(run["display"])
            group = msgpack.unpackb(cells[cols["group"]])
            had = set(run["quests"])
            every = {msgpack.unpackb(q[2]) for g in group_rows.get(group, []) for q in seq_rows.get(msgpack.unpackb(g[2]), [])}
            if had and had != every:
                if group + step not in made:
                    made.add(group + step)
                    for g in group_rows.get(group, []):
                        seq = msgpack.unpackb(g[2])
                        kept = [q for q in seq_rows.get(seq, []) if msgpack.unpackb(q[2]) in had]
                        if not kept:
                            continue
                        new_groups.append(bytes([0x90 | len(g)]) + msgpack.packb(group + step) + g[1] + msgpack.packb(seq + step) + b"".join(g[3:]))
                        new_seqs.extend(bytes([0x90 | len(q)]) + msgpack.packb(seq + step) + b"".join(q[1:]) for q in kept)
                cells[cols["group"]] = msgpack.packb(group + step)
        chapter_rows.append(header + b"".join(cells))
    keep = lambda blob: [h + b"".join(c) for h, c in _rows(blob)]
    return _table(chapter_rows), _table(keep(links) + new_links), _table(keep(groups) + new_groups), _table(keep(sequences) + new_seqs)


def run_items(chapters, runs):
    """The consumable items each earlier run's chapter copy drops (its run's
    drops, not the final game data's), by chapter id."""
    out = {}
    for chapter in chapters:
        recorded = runs.get(str(chapter % COPY_STEP)) or []
        n = chapter // COPY_STEP
        run = recorded[n] if n < len(recorded) else None
        if run:
            out[chapter] = {d[1] for drops in run.get("drops", {}).values() for d in drops if d[0] == CONSUMABLE_ITEM}
    return out


def apply_event_runs(toc, blob, changed, schemas):
    """Gives each restored run of a rerun event its own exchange, medal and quests (event_runs)."""
    from patcher import patch_masterdata as pm
    runs = event_run_data()
    names = ("m_event_quest_chapter", "m_event_quest_link", "m_event_quest_sequence_group", "m_event_quest_sequence")
    if not runs or not all(n in toc for n in names):
        return
    index = {name: i for i, _, name in schemas["m_event_quest_chapter"][1]}
    cols = {"link": index["EventQuestLinkId"], "display": index["EventQuestDisplayItemGroupId"], "group": index["EventQuestSequenceGroupId"]}
    tables = {}
    for n in names:
        pm.apply_to_table(toc, blob, changed, n, lambda b, n=n: tables.__setitem__(n, bytes(b)) or 0)
    built = event_runs(*(tables[n] for n in names), runs=runs, cols=cols)
    for n, new in zip(names, built):
        pm.apply_to_table(toc, blob, changed, n, lambda b, new=new: new)


def copy_chapter_rows(blob, copies):
    """Adds a row for each chapter copy to a table keyed by event chapter (first column)."""
    import msgpack
    out = []
    for header, cells in _rows(blob):
        out.append(header + b"".join(cells))
        for copy in copies.get(msgpack.unpackb(cells[0]), []) if cells else []:
            out.append(header + msgpack.packb(copy) + b"".join(cells[1:]))
    return _table(out)


def keep_key_order(blob):
    """The rows in their first column's order, ties as they were. The game finds rows by binary search
    (MasterMemory), so a table must stay in key order; copies written beside the rows they copy break it, and the
    game then misses rows that are there (CalculatorQuest.TryGetEventQuestType: every auto-repeat stopped)."""
    import msgpack
    rows = list(_rows(blob))
    rows.sort(key=lambda r: msgpack.unpackb(r[1][0]) if r[1] else 0)
    return _table([header + b"".join(cells) for header, cells in rows])


def sort_like_origin(toc, blob, changed, schemas):
    """Each changed table whose rows the original data keeps in first-column order, back in that order."""
    from patcher import patch_masterdata as pm
    for table in list(changed):
        if table not in schemas or not schemas[table][1]:
            continue
        ids = [r[0] for r in _read(toc, blob, {}, schemas, table, schemas[table][1][0][2])]
        if all(a <= b for a, b in zip(ids, ids[1:])):
            pm.apply_to_table(toc, blob, changed, table, keep_key_order)


def restore_history(toc, blob, changed, schemas):
    """Puts the runs the final game data lost back, before the loop's shift."""
    from patcher import patch_masterdata as pm
    copies, other = {}, {}
    for table, spec in history().items():
        spec = history_spec(table, spec)
        kept = copies if table == "m_event_quest_chapter" else other if table in COPIED else None
        pm.apply_to_table(toc, blob, changed, table, lambda b, s=spec, t=table, k=kept: restore_runs(b, s, k, table_name=t))
    if copies:
        for table, (_, columns) in schemas.items():
            if table != "m_event_quest_chapter" and table in toc and any(index == 0 and name == "EventQuestChapterId" for index, _, name in columns):
                pm.apply_to_table(toc, blob, changed, table, lambda b: copy_chapter_rows(b, copies))
    if "m_webview_mission" in toc:
        pm.apply_to_table(toc, blob, changed, "m_webview_mission", library_missions)
        pm.apply_to_table(toc, blob, changed, "m_webview_panel_mission", library_sheets)
    apply_tower_floors(toc, blob, changed, schemas)
    return copies


def apply_tower_floors(toc, blob, changed, schemas):
    """Gives each Abyss Tower run its own floors (tower_floors)."""
    from patcher import patch_masterdata as pm
    try:
        floors = json.loads(TOWER_FLOORS.read_text())["floors"]
    except FileNotFoundError:
        return
    names = ("m_event_quest_chapter", "m_event_quest_sequence_group", "m_event_quest_sequence")
    if not all(n in toc for n in names):
        return
    group_col = next(i for i, _, name in schemas["m_event_quest_chapter"][1] if name == "EventQuestSequenceGroupId")
    tables = {}
    for n in names:
        pm.apply_to_table(toc, blob, changed, n, lambda b, n=n: tables.__setitem__(n, bytes(b)) or 0)
    built = tower_floors(*(tables[n] for n in names), group_col=group_col, floors=floors)
    for n, new in zip(names, built):
        pm.apply_to_table(toc, blob, changed, n, lambda b, new=new: new)

# An event's medal exchange and the items it gives. The final game data keeps
# each event's last run only: its exchange (EventQuestLink) and the medals and
# tickets its quests drop date from that run. A chapter whose other runs the
# calendar restores opened without the exchange to spend its medals in
# (chapter 510 from 2021, its shop 6064 from 2023), and with medals and tickets
# not yet or no longer valid (chapter 300's tickets in 2023, its run in 2022).
# The exchange and every item the chapter gives open when it first does and
# stay until its last run ends.
LINK_SHOP = 3            # EventQuestLink.DestinationDomainType: a shop
CONSUMABLE_ITEM = 6      # PossessionType


def exchange_dates(chapters, links, shops, cell_groups, cell_terms, items, item_terms, given):
    """New (start, end) dates for the exchanges, their offers' terms and the
    terms of the items the chapters give, by table and id; only rows that change.

    chapters: (chapter, link, start, end); links: link -> (destination type,
    destination id, possession type, possession id); shops: shop -> (cell group,
    start, end); cell_groups: (cell group, cell term); cell_terms, item_terms:
    term -> (start, end); items: consumable item -> its term; given: chapter ->
    the consumable items its quests give."""
    wanted, medals = {}, {}

    def widen(found, key, start, end):
        first, last = found.get(key, (start, end))
        found[key] = (min(first, start), max(last, end))

    for chapter, link, start, end in chapters:
        if not EARLIEST <= start < FOREVER:
            continue
        kind, shop, possession, item = links.get(link, (0, 0, 0, 0))
        for each in set(given.get(chapter, ())) | ({item} if possession == CONSUMABLE_ITEM else set()):
            if each in items:
                widen(medals, items[each], start, end)
        if kind == LINK_SHOP and shop in shops:
            widen(wanted, shop, start, end)
    shop_dates = {}
    for shop, (first, last) in wanted.items():
        _, start, end = shops[shop]
        dates = (min(start, first), max(end, last))
        if dates != (start, end):
            shop_dates[shop] = dates
    # An offer's term opens with the exchange when no other shop uses it.
    users = {}
    group_shop = {group: shop for shop, (group, _, _) in shops.items()}
    for group, term in cell_groups:
        if term:
            users.setdefault(term, set()).add(group_shop.get(group))
    term_dates = {}
    for term, owners in users.items():
        if term in cell_terms and owners <= set(shop_dates):
            start, end = cell_terms[term]
            first = min(shop_dates[shop][0] for shop in owners)
            if first < start:
                term_dates[term] = (first, end)
    medal_dates = {}
    for term, (first, last) in medals.items():
        if term in item_terms:
            start, end = item_terms[term]
            if first < start or last > end:
                medal_dates[term] = (min(start, first), max(end, last))
    return {"m_shop": shop_dates, "m_shop_item_cell_term": term_dates, "m_consumable_item_term": medal_dates}


def set_dates(blob, columns, dates):
    """Gives the rows keyed by their first cell the (start, end) in dates."""
    import msgpack
    out = []
    for header, cells in _rows(blob):
        new = dates.get(msgpack.unpackb(cells[0])) if cells else None
        if new is not None:
            cells = list(cells)
            for column, value in zip(columns, new):
                cells[column] = b"\xd3" + struct.pack(">q", value)
        out.append(header + b"".join(cells))
    return _table(out)


def chapter_items(read):
    """The consumable items each event chapter's quests give: first-clear
    rewards and drops."""
    def grouped(rows):
        out = {}
        for key, value in rows:
            out.setdefault(key, []).append(value)
        return out

    sequences = grouped(read("m_event_quest_sequence_group", "EventQuestSequenceGroupId", "EventQuestSequenceId"))
    quests = grouped(read("m_event_quest_sequence", "EventQuestSequenceId", "QuestId"))
    rewards = {r[0]: r[1:] for r in read("m_quest", "QuestId", "QuestFirstClearRewardGroupId", "QuestPickupRewardGroupId")}
    first_clear = grouped([(g, item) for g, kind, item in read("m_quest_first_clear_reward_group", "QuestFirstClearRewardGroupId", "PossessionType", "PossessionId") if kind == CONSUMABLE_ITEM])
    drops = {d: item for d, kind, item in read("m_battle_drop_reward", "BattleDropRewardId", "PossessionType", "PossessionId") if kind == CONSUMABLE_ITEM}
    pickup = grouped([(g, drops[d]) for g, d in read("m_quest_pickup_reward_group", "QuestPickupRewardGroupId", "BattleDropRewardId") if d in drops])
    out = {}
    for chapter, group in read("m_event_quest_chapter", "EventQuestChapterId", "EventQuestSequenceGroupId"):
        items = set()
        for quest in (q for sequence in sequences.get(group, []) for q in quests.get(sequence, [])):
            first, pick = rewards.get(quest, (0, 0))
            items.update(first_clear.get(first, []), pickup.get(pick, []))
        out[chapter] = items
    return out


def open_exchanges(toc, blob, changed, schemas):
    """Opens each event's medal exchange and items with its chapter (exchange_dates)."""
    from patcher import patch_masterdata as pm
    read = lambda table, *names: _read(toc, blob, changed, schemas, table, *names) if table in toc else []
    rows = lambda table, *names: {r[0]: r[1:] for r in read(table, *names)}
    found = exchange_dates(
        read("m_event_quest_chapter", "EventQuestChapterId", "EventQuestLinkId", "StartDatetime", "EndDatetime"),
        rows("m_event_quest_link", "EventQuestLinkId", "DestinationDomainType", "DestinationDomainId", "PossessionType", "PossessionId"),
        rows("m_shop", "ShopId", "ShopItemCellGroupId", "StartDatetime", "EndDatetime"),
        read("m_shop_item_cell_group", "ShopItemCellGroupId", "ShopItemCellTermId"),
        rows("m_shop_item_cell_term", "ShopItemCellTermId", "StartDatetime", "EndDatetime"),
        dict(read("m_consumable_item", "ConsumableItemId", "ConsumableItemTermId")),
        rows("m_consumable_item_term", "ConsumableItemTermId", "StartDatetime", "EndDatetime"),
        {**chapter_items(read), **run_items([c for c, *_ in read("m_event_quest_chapter", "EventQuestChapterId")], event_run_data())})
    for table, dates in found.items():
        if dates:
            index = {name: i for i, _, name in schemas[table][1]}
            columns = (index["StartDatetime"], index["EndDatetime"])
            pm.apply_to_table(toc, blob, changed, table, lambda b, c=columns, d=dates: set_dates(b, c, d))
    return found


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


def cap_table(blob, columns, latest):
    """Moves every dated int64 cell in columns later than latest back to latest."""
    from patcher.patch_masterdata import read_array_len, skip_msgpack_value
    count, pos = read_array_len(blob, 0)
    for _ in range(count):
        cells, p = read_array_len(blob, pos)
        for index in range(cells):
            if index in columns and blob[p] == 0xd3 and struct.unpack(">q", blob[p + 1:p + 9])[0] > latest:
                struct.pack_into(">q", blob, p + 1, latest)
            p = skip_msgpack_value(blob, p)
        pos = p
    return 0


# Tables the calendar doesn't move are all in the past in a loop's dates (2026
# on): every character listed, every filter complete. The copy for "Show
# original dates" (2021 on, view=True) caps their start dates at launch so
# the game behaves the same: the final game data lists 33 characters (the
# starting cast among them) only from 2022, and Enhance > Characters was
# empty. Story chapters (m_main_quest_chapter) keep their dates and open as
# the calendar reaches them, as in the live game. m_catalog_term keeps its
# dates too: the server compares it in the live service's dates (summon notices).
VIEW_FROM_LAUNCH = {
    "m_character": ("ListSettingDisplayStartDatetime",),
    "m_list_setting_ability_group": ("ListSettingDisplayStartDatetime",),
    "m_parts_series": ("ListSettingDisplayStartDatetime",),
    "m_character_viewer_field": ("PublishDatetime",),
    "m_costume_lottery_effect_release_schedule": ("ReleaseDatetime",),
    "m_possession_acquisition_route": ("StartDatetime",),
    "m_navi_cut_in": ("StartDatetime",),
    "m_appeal_dialog": ("StartDatetime",),
    "m_stained_glass": ("EmptyDisplayStartDatetime", "LockDisplayStartDatetime"),
}


def gate_chapters(blob, id_index, column, offset, open_ids):
    """Story chapters released after launch open on their dates moved by
    offset; those in open_ids open at the loop's start instead."""
    from patcher.patch_masterdata import read_array_len, skip_msgpack_value
    import msgpack
    count, pos = read_array_len(blob, 0)
    for _ in range(count):
        cells, p = read_array_len(blob, pos)
        chapter, at = None, None
        for index in range(cells):
            if index == id_index:
                end = skip_msgpack_value(blob, p)
                chapter = msgpack.unpackb(bytes(blob[p:end]))
            if index == column and blob[p] == 0xd3:
                at = p
            p = skip_msgpack_value(blob, p)
        if at is not None:
            value = struct.unpack(">q", blob[at + 1:at + 9])[0]
            if LAUNCH <= value < FOREVER:  # earlier: open from the start
                struct.pack_into(">q", blob, at + 1, (LAUNCH if chapter in open_ids else value) + offset)
        pos = p
    return 0


# With the Original calendar story chapters open on their release dates, in
# the first loop only: from the second the player has been through the story.
# Chapters the player has reached (a quest cleared in them) stay open.
def all_chapters():
    return {r["MainQuestChapterId"] for r in table("MainQuestChapter")}


def reached_chapters():
    """Chapters with a quest any player of this save has cleared, and the
    chapter each player's story is at (Pod Programs › Story Jump puts a player
    at the start of a chapter with nothing in it cleared yet)."""
    import sqlite3
    try:
        db = sqlite3.connect(f"file:{config.GAME_DB_PATH}?mode=ro", uri=True)
        try:
            cleared = {q for (q,) in db.execute("select distinct quest_id from user_quests where clear_count > 0")}
            try:
                heads = {s for (s,) in db.execute("select distinct head_quest_scene_id from user_main_quest")}
            except sqlite3.Error:  # a save without the table: cleared quests only
                heads = set()
        finally:
            db.close()
    except sqlite3.Error:
        return set()
    scene_quest = {r["QuestSceneId"]: r["QuestId"] for r in table("QuestScene")}
    cleared |= {scene_quest[s] for s in heads if s in scene_quest}
    sequence = {r["QuestId"]: r["MainQuestSequenceId"] for r in table("MainQuestSequence")}
    group = {r["MainQuestSequenceId"]: r["MainQuestSequenceGroupId"] for r in table("MainQuestSequenceGroup")}
    chapter = {r["MainQuestSequenceGroupId"]: r["MainQuestChapterId"] for r in table("MainQuestChapter")}
    return {chapter[group[sequence[q]]] for q in cleared if q in sequence and sequence[q] in group and group[sequence[q]] in chapter}


def open_chapters(state):
    return reached_chapters() if state.get("loop", 1) <= 1 else all_chapters()


def reopen_reached_chapters():
    """Builds the game data again so the chapters reached open now (Story Jump):
    only the Original calendar's first loop locks chapters by date. Returns
    whether it rebuilt."""
    state = read_state()
    if state is None or state.get("loop", 1) > 1:
        return False
    activate_loop(state)
    if state.get("originalDates"):
        build_view(state)
    return True


def read_master(path):
    """A master data file's table of contents and table blob."""
    import msgpack
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    from patcher import patch_masterdata as pm
    key, iv = bytes.fromhex(pm.DEFAULT_KEY), bytes.fromhex(pm.DEFAULT_IV)
    decoded = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(Path(path).read_bytes()), AES.block_size)
    try:
        msgpack.unpackb(decoded, raw=False, strict_map_key=False)
        raise ValueError(t("pods.patcher.no_tables"))
    except msgpack.ExtraData as exc:
        return exc.unpacked, exc.extra


def _read(toc, blob, changed, schemas, table, *names):
    """A table's rows as tuples of the named columns."""
    import msgpack
    from patcher import patch_masterdata as pm
    index = {name: i for i, _, name in schemas[table][1]}
    columns, out = [index[name] for name in names], []

    def collect(b):
        for _, cells in _rows(b):
            if max(columns) < len(cells):
                out.append(tuple(msgpack.unpackb(cells[i]) for i in columns))
        return 0
    pm.apply_to_table(toc, blob, changed, table, collect)
    return out


def build_master(origin, output, offset, view=False, open_chapters=None):
    """Writes origin's game data with rotating content moved forward by offset;
    view: the copy for "Show original dates" (VIEW_FROM_LAUNCH); open_chapters:
    story chapters open on their dates (moved by offset) except these (None: all open)."""
    import msgpack
    from patcher import patch_masterdata as pm
    from tools import dump_masterdata
    if offset % WEEK:
        raise ValueError(t("pods.calendar.whole_weeks"))
    toc, blob = read_master(origin)
    schemas = dump_masterdata.load_schemas()
    changed = {}
    restore_history(toc, blob, changed, schemas)
    apply_event_runs(toc, blob, changed, schemas)
    open_exchanges(toc, blob, changed, schemas)
    moved = 0
    for table in ROTATING:
        if table not in toc or table not in schemas:
            continue
        columns = {index for index, kind, name in schemas[table][1] if kind == "long" and "Datetime" in name}
        moved += pm.apply_to_table(toc, blob, changed, table, lambda b: shift_table(b, columns, offset)) or 0
    if open_chapters is not None and "m_main_quest_chapter" in toc:
        names = [name for _, _, name in schemas["m_main_quest_chapter"][1]]
        pm.apply_to_table(toc, blob, changed, "m_main_quest_chapter", lambda b: gate_chapters(
            b, names.index("MainQuestChapterId"), names.index("StartDatetime"), offset, set(open_chapters)))
    for table, names in (VIEW_FROM_LAUNCH if view else {}).items():
        if table in toc and table in schemas:
            columns = {index for index, kind, name in schemas[table][1] if name in names}
            pm.apply_to_table(toc, blob, changed, table, lambda b, c=columns: cap_table(b, c, LAUNCH))
    for table, column in pm.EXPIRED_AD_TABLES.items():
        pm.apply_to_table(toc, blob, changed, table, lambda b, c=column: pm.expire_table_end(b, c))
    for table in pm.EMPTY_TABLES:
        if table in toc:
            changed[table] = msgpack.packb([], use_bin_type=True)
    for table, rows in pm.TABLE_ROW_ADDITIONS.items():
        pm.apply_to_table(toc, blob, changed, table, lambda b, r=rows: pm.add_table_rows(b, r))
    pm.apply_to_table(toc, blob, changed, "m_battle_group", pm.patch_wolf_chapter_battle_point)
    sort_like_origin(toc, blob, changed, schemas)
    write_master(toc, blob, changed, output)
    return moved


def write_master(toc, blob, changed, output):
    """Writes a master data file from read_master's tables, with the changed ones replaced."""
    import msgpack
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    from patcher import patch_masterdata as pm
    parts, layout, offset_in_blob = [], {}, 0
    for table, (start, length) in sorted(toc.items(), key=lambda item: item[1][0]):
        part = changed.get(table, blob[start:start + length])
        layout[table] = (offset_in_blob, len(part))
        parts.append(part)
        offset_in_blob += len(part)
    plain = msgpack.packb(layout, use_bin_type=True) + b"".join(parts)
    Path(output).write_bytes(AES.new(bytes.fromhex(pm.DEFAULT_KEY), AES.MODE_CBC, bytes.fromhex(pm.DEFAULT_IV)).encrypt(pad(plain, AES.block_size)))


def origin_file():
    origin = patcher.folder() / "origin.bin.e"
    if not origin.exists():
        raise ValueError(t("pods.patcher.load_original"))
    return origin


# The next loop's game data sits beside the master data, where the server
# looks for it (gametime.NextName): a full path in calendar.json goes stale
# when iOS moves the app's folder on an update. Not .bin.e, which the tools
# would take for the master data.
NEXT_NAME = "calendar-next.bin"


def next_file():
    return config.RELEASE_DIR / NEXT_NAME


# "Show original dates": the game is sent its data with no date shift and its
# clock and times moved back by the loop's offset, so it shows 2021-2024
# (server: gametime.ViewOffset, service.ViewMasterName). The copy does not
# depend on the loop, so one serves every loop.
VIEW_NAME = "calendar-view.bin.e"


def view_file():
    return config.RELEASE_DIR / VIEW_NAME


# Bumped when the copy's build changes, so a copy built before is rebuilt
# (refresh_view): 2 caps start dates at launch (VIEW_FROM_LAUNCH) and opens
# story chapters on their dates; 5 replays each event run with its own exchange;
# 6 has daily missions from launch (daily set 21-26's first run).
VIEW_VERSION = "6"
# Bumped when a loop's game data changes, so the loop in use is rebuilt
# (read_state): 1 opens story chapters on their dates; 2 keeps every table in key order (auto-repeat);
# 4 replays each event run with its own exchange, medal and quests (event_runs.json);
# 5 has daily missions from launch (daily set 21-26's first run, calendar_history.json).
DATA_VERSION = 5


def view_version_file():
    return config.RELEASE_DIR / "calendar-view.version"


def view_version(state):
    """The copy's version: the build's, and first loop or later (story chapters)."""
    return f"{VIEW_VERSION}:{min(state.get('loop', 1), 2)}"


def build_view(state):
    pending = view_file().with_suffix(".tmp")
    build_master(origin_file(), pending, 0, view=True, open_chapters=open_chapters(state))
    import android_challenges as challenges
    challenges.finish(pending)  # Mods › Challenges, before the game can load it
    os.replace(pending, view_file())
    view_version_file().write_text(view_version(state))


def view_outdated(state):
    version = view_version_file()
    return not view_file().exists() or not version.exists() or version.read_text().strip() != view_version(state)


def refresh_view(state):
    """Rebuilds the game's copy for "Show original dates" when it is on and the copy is missing or older."""
    if state.get("originalDates") and view_outdated(state):
        build_view(state)


def set_original_dates(state, on):
    """Turns "Show original dates" on or off, building the game's copy when needed."""
    if on and view_outdated(state):
        build_view(state)
    before = shown_clock(state)
    state["originalDates"] = bool(on)
    clock_moved(before, shown_clock(state))


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
    """The content the patcher page names, in the chosen language."""
    return t("pods.patcher.label_calendar", loop=state["loop"])


def activate_loop(state):
    candidate = patcher.folder() / "candidate.bin.e"
    try:
        build_master(origin_file(), candidate, state["loopStart"] - LAUNCH, open_chapters=open_chapters(state))
        patcher.activate(candidate, patcher.calendar_id(state["loop"]))
    finally:
        candidate.unlink(missing_ok=True)


def prepare_next(state):
    """Builds the next loop's game data ahead, so the server can start it on its own."""
    pending = next_file().with_suffix(".tmp")
    build_master(origin_file(), pending, state["loopStart"] + LOOP_WEEKS * WEEK - LAUNCH)
    import android_challenges as challenges
    challenges.finish(pending)  # Mods › Challenges, before the server can load it by itself
    os.replace(pending, next_file())
    state["next"] = NEXT_NAME
    state["nextLoop"] = state["loop"] + 1


def roll_over(state, real=None):
    """Starts the next loop if this one has ended. Returns True when it did."""
    if game_now(state, real) < loop_end(state):
        return False
    before = shown_clock(state, real)
    while game_now(state, real) >= loop_end(state):
        state["loop"] += 1
        state["loopStart"] += LOOP_WEEKS * WEEK
    open_at_first_summons(state, real)
    activate_loop(state)
    state.pop("next", None)
    prepare_next(state)
    write_state(state)
    clock_moved(before, shown_clock(state, real))  # with original dates, back to launch
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
    state = {"version": 1, "loop": 1, "loopStart": start, "jumpMillis": 0, "speed": 1, "speedSince": start_of_day(real), "dataVersion": DATA_VERSION}
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
    before = shown_clock(read_state())
    state_path().unlink(missing_ok=True)
    next_file().unlink(missing_ok=True)
    view_file().unlink(missing_ok=True)
    view_version_file().unlink(missing_ok=True)
    old_next_file().unlink(missing_ok=True)
    clock_moved(before, now_ms())


def set_speed(state, speed, real=None):
    if speed not in SPEEDS:
        raise ValueError(t("pods.calendar.unknown_speed"))
    real = now_ms() if real is None else real
    # Keep the weeks the old speed has already added.
    state["jumpMillis"] = state.get("jumpMillis", 0) + auto_weeks(state, real) * WEEK
    state["speed"] = float(speed) if "." in speed else int(speed)
    state["speedSince"] = start_of_day(real)


def jump(state, target, real=None):
    """Moves the clock forward to target in whole days, so the daily reset stays at the same hour."""
    now = game_now(state, real)
    if target <= now:
        raise ValueError(t("pods.calendar.only_forward"))
    if target >= loop_end(state):
        raise ValueError(t("pods.calendar.week_in_loop"))
    state["jumpMillis"] = state.get("jumpMillis", 0) + -(-(target - now) // DAY) * DAY


# --- What is open ------------------------------------------------------------

def table(name):
    return runtime.read_json(config.MASTERDATA_DIR / f"EntityM{name}Table.json", []) or []


def names(kind):
    data = runtime.read_json(config.NAMES_DIR / f"{kind}.json", {}) or {}
    return {r["id"]: r["name"] for r in data.get("records", []) if isinstance(r, dict) and r.get("name_found") and isinstance(r.get("id"), int)}


class Entry(NamedTuple):
    """Dated content: its kind and name, when it is open, the Archive page it
    links to (or "") and its banner art's bundle path (or "")."""
    kind: str
    name: str | None
    start: int
    end: int
    ref: str = ""
    art: str = ""


def summon_art(asset):
    return f"ui/gacha/en/{asset}/mom_banner.assetbundle" if asset else ""


def entries():
    """Dated content the Schedule page lists (Entry)."""
    found = []
    event_names = names("event_quests")
    # The loop's game data already holds every run the history restored, each
    # as its own row with its dates moved into the loop (restore_history,
    # build_master); the history's original dates are not this loop's.
    for row in table("EventQuestChapter"):
        # A rerun's copy (chapter + n * COPY_STEP) is the same event in the Archive.
        banner = row.get("BannerAssetId", 0)
        found.append(Entry("event", event_names.get(row["EventQuestChapterId"]), row["StartDatetime"], row["EndDatetime"],
                           f"/schedule/event/{row['EventQuestChapterId'] % COPY_STEP}",
                           f"ui/quest/en/banner/event_banner_{banner:03d}.assetbundle" if banner else ""))
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
            found.append(Entry("summon", banner_names.get(row["MomBannerId"]) or ART_TITLES.get(row["BannerAssetName"]), convert - PARKED_RERUNS[gacha], convert - 2 * DAY,
                               f"/schedule/summon/{gacha}", summon_art(row["BannerAssetName"])))
    for row in table("MomBanner"):
        if row["DestinationDomainType"] == 1 and row["DestinationDomainId"] in offered and row["DestinationDomainId"] not in PARKED_RERUNS:
            # Some titles are only in the banner art (ART_TITLES).
            found.append(Entry("summon", banner_names.get(row["MomBannerId"]) or ART_TITLES.get(row["BannerAssetName"]), row["StartDatetime"], row["EndDatetime"],
                               f"/schedule/summon/{row['DestinationDomainId']}", summon_art(row["BannerAssetName"])))
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
            label = t("pods.calendar.shard_summons", name=label)
        found.append(Entry("summon", label or None, start, end, f"/schedule/summon/{gacha}"))
    shop_names = names("shops")
    for row in table("Shop"):
        if row["ShopGroupType"] == 4:
            found.append(Entry("shop", shop_names.get(row["ShopId"]), row["StartDatetime"], row["EndDatetime"]))
    for row in table("PvpSeason"):
        if not row.get("IsInvalid"):
            found.append(Entry("arena", t("pods.calendar.arena_season", n=f"{row['PvpSeasonId'] % 1000:03d}"), row["SeasonStartDatetime"], row["SeasonEndDatetime"]))
    for index, row in enumerate(sorted(table("MissionPass"), key=lambda r: r["StartDatetime"]), 1):
        found.append(Entry("pass", t("pods.calendar.mission_pass", n=index), row["StartDatetime"], row["EndDatetime"]))
    for row in table("BigHuntSchedule"):
        found.append(Entry("hunt", t("pods.calendar.subjugation", n=row["BigHuntScheduleId"]), row["ChallengeStartDatetime"], row["ChallengeEndDatetime"]))
    for row in table("EnhanceCampaign") + table("QuestCampaign"):
        found.append(Entry("campaign", "", row["StartDatetime"], row["EndDatetime"]))
    for row in table("ConsumableItemTerm"):
        found.append(Entry("expiry", "", row["StartDatetime"], row["EndDatetime"]))
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


# Day and month names: catalogue keys (common.weekday_short.*, common.month_short.*), translated as a page is drawn.
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def _date_parts(ms):
    """The day's weekday name, day, month name and year."""
    d = datetime.fromtimestamp(ms / 1000, timezone.utc)
    weekday, month = "common.weekday_short." + WEEKDAYS[d.weekday()], "common.month_short." + MONTHS[d.month - 1]
    return t(weekday), d.day, t(month), d.year


def day_label(ms):
    """"Wed 28 Jul 2021"."""
    weekday, day, month, year = _date_parts(ms)
    return t("pods.calendar.day_label", weekday=weekday, day=day, month=month, year=year)


def short_label(ms):
    """"Wed 28 Jul"."""
    weekday, day, month, _ = _date_parts(ms)
    return t("pods.calendar.day_label_short", weekday=weekday, day=day, month=month)


def open_at(items, at):
    return [e for e in items if e[2] <= at < e[3]]


def others(kind, n):
    """"3 other events": unnamed content of a kind."""
    if kind == "event":
        return t_count("pods.calendar.other_events", n)
    if kind == "summon":
        return t_count("pods.calendar.other_summons", n)
    return t_count("pods.calendar.other_shops", n)


def summary(items, at):
    """Open content by kind, soonest to close first; unnamed entries are counted in one line."""
    groups, unnamed = {}, {}
    for kind, name, start, end, *_ in sorted(open_at(items, at), key=lambda e: e[3]):
        if name or kind in ("campaign", "expiry"):
            groups.setdefault(kind, []).append({"name": name, "until": short_label(end - 1)})
        else:
            unnamed[kind] = unnamed.get(kind, 0) + 1
    for kind, count in unnamed.items():
        groups.setdefault(kind, []).append({"name": others(kind, count), "until": ""})
    return groups


# The Schedule page's timeline: from a week back to three months ahead (or
# the loop's end), and what ends within a week. Times are in the dates the
# game shows; the page draws them in the phone's local time.
TIMELINE_KINDS = ("summon", "event", "shop", "arena")


def kind_names():
    """Each timeline row's name, and the name of an entry of its kind with none of its own."""
    return {"summon": (t("pods.calendar.kind_summons"), t("pods.calendar.unnamed_summon")),
            "event": (t("pods.calendar.kind_events"), t("pods.calendar.unnamed_event")),
            "shop": (t("pods.calendar.kind_shops"), t("pods.calendar.unnamed_shop")),
            "arena": (t("pods.calendar.kind_arena"), t("pods.calendar.unnamed_arena"))}
TIMELINE_BEFORE, TIMELINE_AFTER, ENDING_SOON = 7 * DAY, 92 * DAY, 7 * DAY


def timeline(state, items, now):
    """Rows of the summons, events, shops and Arena seasons in the window, and those ending soon."""
    from urllib.parse import quote
    start, end = now - TIMELINE_BEFORE, min(now + TIMELINE_AFTER, loop_end(state))
    shift = state["loopStart"] - LAUNCH if state.get("originalDates") else 0
    labels = kind_names()

    def item(e):
        # Ends after the loop are the game data's placeholders for content that stays: no end.
        return {"kind": e.kind, "name": e.name or labels[e.kind][1], "start": e.start - shift,
                "end": e.end - shift if e.end <= loop_end(state) else None, "ref": e.ref,
                "art": "/patcher/calendar/art?path=" + quote(e.art, safe="/") if e.art else ""}
    shown = sorted((e for e in items if e.kind in labels and e.start < end and e.end > start), key=lambda e: (e.start, e.end))
    soon = sorted((e for e in shown if e.start <= now < e.end <= now + ENDING_SOON), key=lambda e: e.end)
    return {"now": now - shift, "from": start - shift, "to": end - shift, "soon": [item(e) for e in soon],
            "rows": [{"kind": kind, "label": labels[kind][0], "items": [item(e) for e in shown if e.kind == kind]} for kind in TIMELINE_KINDS]}


def timeline_file():
    return config.DATA_DIR / "timeline.json"


def timeline_hidden():
    """The timeline rows the player hid. Kept here, not in the page: iOS keeps no page storage between sessions."""
    data = runtime.read_json(timeline_file(), {})
    hidden = data.get("hidden", []) if isinstance(data, dict) else []
    return [k for k in hidden if k in TIMELINE_KINDS] if isinstance(hidden, list) else []


def set_timeline_hidden(kinds):
    runtime.write_json(timeline_file(), {"hidden": [k for k in kinds if k in TIMELINE_KINDS]})


def updates(state, items, after):
    """Days in the rest of the loop when new events or summons open, named by their first event."""
    days = {}
    for kind, name, start, end, *_ in sorted(items, key=lambda e: (e[2], e[0] != "event")):
        if kind in ("event", "summon") and after < start < loop_end(state):
            day = days.setdefault(start_of_day(start), {"at": start, "names": [], "count": 0})
            day["count"] += 1
            if name:
                day["names"].append(name)
    return [{"at": v["at"], "day": day_label(v["at"]), "week": week_of(state, v["at"]), "name": (v["names"] or [t("pods.calendar.new_content")])[0],
             "more": v["count"] - 1, "all": " ".join(v["names"])} for k, v in sorted(days.items())]


# What a jump skips, by kind, in the order the Jump to page lists them.
MISSED_KINDS = ("event", "summon", "shop", "arena", "pass")


def missed_text(missed):
    """preview's missed counts as text: "10 events, 1 Arena season"."""
    def words(kind, n):
        if kind == "event":
            return t_count("pods.calendar.missed_events", n)
        if kind == "summon":
            return t_count("pods.calendar.missed_summons", n)
        if kind == "shop":
            return t_count("pods.calendar.missed_shops", n)
        if kind == "arena":
            return t_count("pods.calendar.missed_arena", n)
        return t_count("pods.calendar.missed_passes", n)
    return t("pods.calendar.list_separator").join(words(kind, missed[kind]) for kind in MISSED_KINDS if missed.get(kind))


def preview(state, items, now, target):
    """What a jump from now to target opens, still pays out, and skips."""
    arrive = now + -(-(target - now) // DAY) * DAY
    paid, missed = [], {}
    for kind, name, start, end, *_ in items:
        if not now < end <= arrive:
            continue
        if start <= now and kind in ("arena", "pass"):
            paid.append(name)
        elif start > now and kind in ("event", "summon", "shop", "arena", "pass"):
            missed[kind] = missed.get(kind, 0) + 1
    return {"arrive": arrive, "day": day_label(arrive), "original": day_label(original(state, arrive)), "week": week_of(state, arrive),
            "days": (arrive - now) // DAY, "open": summary(items, arrive), "paid": paid, "missed": missed,
            "missedText": missed_text(missed)}


# --- Pages -------------------------------------------------------------------

def redirect(path="/patcher", **kwargs):
    from urllib.parse import urlencode
    return RedirectResponse(path + ("?" + urlencode(kwargs) if kwargs else ""), status_code=303)


def context(state):
    now = game_now(state)
    items = entries()
    shown = original(state, now) if state.get("originalDates") else now
    return {"state": state, "loop": state["loop"], "week": week_of(state, now), "weeks": LOOP_WEEKS,
            "progress": round(100 * (now - state["loopStart"]) / (LOOP_WEEKS * WEEK), 1),
            "today": day_label(shown), "originalDates": bool(state.get("originalDates")), "original": day_label(original(state, now)), "ends": day_label(loop_end(state)),
            "speed": str(state.get("speed", 1)), "speeds": SPEEDS, "now": now, "timeline": dict(timeline(state, items, now), hidden=timeline_hidden())}


@router.post("/patcher/calendar/on")
def calendar_on():
    try:
        turn_on()
        return redirect(message=t("pods.calendar.on", next=runtime.next_step()))
    except Exception as exc:
        return redirect(error=str(exc))


@router.post("/patcher/calendar/off")
def calendar_off():
    turn_off()
    return redirect(message=t("pods.calendar.off", next=runtime.next_step()))


@router.post("/patcher/calendar/speed")
def calendar_speed(speed: str = Form(...)):
    state = read_state()
    if not state:
        return redirect(error=t("pods.calendar.off_already"))
    try:
        set_speed(state, speed)
        write_state(state)
        return redirect(message=t("pods.calendar.speed_saved", next=runtime.next_step()))
    except Exception as exc:
        return redirect(error=str(exc))


# Banner art for the timeline, decoded from the game files with the same
# decoder the Archive uses, into Pod Programs' own folder: the Archive runs in
# another process and clears its older images.
_art = {}


def art_file(path):
    """The banner art PNG for a bundle path; FileNotFoundError when there is none."""
    from archive.media import Textures
    from android_archive import revision_root
    if not runtime.TEXTURE:
        raise FileNotFoundError(path)
    key = (str(config.ASSETS_DIR), str(config.DATA_DIR), runtime.TEXTURE)
    if key not in _art:
        _art.clear()
        _art[key] = Textures(revision_root(config.ASSETS_DIR.parent) / "assetbundle", config.DATA_DIR / "art", runtime.TEXTURE)
    try:
        return _art[key].png(path, "thumb")
    except ValueError as exc:
        raise FileNotFoundError(path) from exc


@router.get("/patcher/calendar/art")
def calendar_art(path: str):
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    try:
        return FileResponse(art_file(path), media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})
    except FileNotFoundError:
        raise HTTPException(404)


@router.post("/patcher/calendar/timeline")
def calendar_timeline(hidden: str = Form("")):
    from fastapi import Response
    set_timeline_hidden([k for k in hidden.split(",") if k])
    return Response(status_code=204)


@router.post("/patcher/calendar/view")
def calendar_view(on: str = Form("")):
    state = read_state()
    if not state:
        return redirect(error=t("pods.calendar.off_already"))
    try:
        set_original_dates(state, on == "1")
        write_state(state)
        return redirect(message=t("pods.runtime.saved", next=runtime.next_step()))
    except Exception as exc:
        return redirect(error=str(exc))


@router.post("/patcher/calendar/jump")
def calendar_jump(target: int = Form(...)):
    state = read_state()
    if not state:
        return redirect(error=t("pods.calendar.off_already"))
    try:
        jump(state, target)
        write_state(state)
        week = week_of(state, game_now(state))
        return redirect(message=t("pods.calendar.moved", week=week, next=runtime.next_step()))
    except Exception as exc:
        return redirect(error=str(exc))


@router.get("/patcher/calendar/next")
def calendar_next(request: Request, by: str = "update"):
    state = read_state()
    if not state:
        return redirect(error=t("pods.calendar.off_already"))
    now = game_now(state)
    items = entries()
    if by == "week":
        target = now + WEEK
        title = t("pods.calendar.next_week")
    else:
        upcoming = updates(state, items, now)
        if not upcoming:
            return redirect(error=t("pods.calendar.no_more_updates"))
        target, title = upcoming[0]["at"], t("pods.calendar.next_update")
    if target >= loop_end(state):
        return redirect(error=t("pods.calendar.past_loop_end"))
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
        return redirect(error=t("pods.calendar.off_already"))
    now = game_now(state)
    items = entries()
    upcoming = updates(state, items, now)
    week = week_of(state, now)
    target = at or (upcoming[0]["at"] if upcoming else 0)
    view = preview(state, items, now, target) if now < target < loop_end(state) else None
    return templates.TemplateResponse(request, "calendar_jump.html", {"active": "patcher", "now": now, "week": week,
        "today": day_label(now), "weeks": LOOP_WEEKS, "updates": upcoming, "target": target, "view": view,
        "loopStart": state["loopStart"], "weekMillis": WEEK})
