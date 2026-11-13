#!/usr/bin/env python3
"""The Original calendar's restored runs (android_calendar.py, calendar_history.json)
on small made-up tables. Needs the Android Python requirements (fastapi, msgpack)."""
from pathlib import Path
import json, struct, sys, unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))
import msgpack  # noqa: E402
import android_calendar as cal  # noqa: E402

DAY = 24 * 60 * 60 * 1000
T0 = 1627437600000  # global launch


def row(*cells):
    """A row as the game data stores it: dates as whole int64 cells."""
    parts = [b"\xd3" + struct.pack(">q", c) if isinstance(c, Date) else msgpack.packb(c) for c in cells]
    return bytes([0x90 | len(parts)]) + b"".join(parts)


class Date(int):
    pass


def table(*rows):
    return bytes([0x90 | len(rows)]) + b"".join(rows)


def cells(blob):
    return [[msgpack.unpackb(c) for c in values] for _, values in cal._rows(blob)]


class RestoredRuns(unittest.TestCase):
    def test_a_finished_run_comes_back_as_the_first(self):
        self.assertEqual(cal.runs((T0 + 900 * DAY, T0 + 910 * DAY), [[T0, T0 + 40 * DAY], [T0 + 900 * DAY, T0 + 910 * DAY]]),
                         [(T0, T0 + 40 * DAY), (T0 + 900 * DAY, T0 + 910 * DAY)])

    def test_content_open_for_good_opens_from_its_first_run(self):
        never = cal.NEVER
        self.assertEqual(cal.runs((T0 + 200 * DAY, never), [[T0 + 90 * DAY, T0 + 110 * DAY], [T0 + 200 * DAY, never]]),
                         [(T0 + 90 * DAY, never)])

    def test_a_row_without_history_keeps_its_dates(self):
        self.assertEqual(cal.runs((T0, T0 + DAY), []), [(T0, T0 + DAY)])

    def test_a_chapter_gets_a_copy_for_each_later_run(self):
        spec = {"key": [0], "dates": [1, 2], "rows": {"510": [[T0, T0 + 40 * DAY], [T0 + 600 * DAY, T0 + 620 * DAY]]}}
        copies = {}
        blob = cal.restore_runs(table(row(510, Date(T0 + 600 * DAY), Date(T0 + 620 * DAY), 7), row(511, Date(T0), Date(T0 + DAY), 8)), spec, copies)
        self.assertEqual(cells(blob), [[510, T0, T0 + 40 * DAY, 7], [510 + cal.COPY_STEP, T0 + 600 * DAY, T0 + 620 * DAY, 7], [511, T0, T0 + DAY, 8]])
        self.assertEqual(copies, {510: [510 + cal.COPY_STEP]})
        # Dates stay whole int64 cells, which the loop's shift moves.
        self.assertEqual(cal.shift_table(bytearray(blob), {1, 2}, 7 * DAY), 6)

    def test_other_tables_take_the_first_run_only(self):
        spec = {"key": [0], "dates": [1, 2], "rows": {"38": [[T0 + 35 * DAY, T0 + 45 * DAY], [T0 + 98 * DAY, T0 + 108 * DAY]]}}
        blob = cal.restore_runs(table(row(38, Date(T0 + 98 * DAY), Date(T0 + 108 * DAY))), spec)
        self.assertEqual(cells(blob), [[38, T0 + 35 * DAY, T0 + 45 * DAY]])

    def test_rows_keyed_by_a_copied_chapter_are_copied(self):
        blob = cal.copy_chapter_rows(table(row(302, 1009), row(303, 1010)), {302: [302 + cal.COPY_STEP]})
        self.assertEqual(cells(blob), [[302, 1009], [302 + cal.COPY_STEP, 1009], [303, 1010]])

    def test_history_names_only_start_and_end_columns(self):
        for name, spec in json.loads(cal.HISTORY.read_text())["tables"].items():
            self.assertEqual(len(spec["dates"]), 2, name)
            self.assertTrue(spec["rows"], name)


class AbyssTowers(unittest.TestCase):
    """A tower reruns on its own schedule, each run with the floors it had
    (notices 666, 716, 885; permanent from 22 March 2023, notice 1037)."""

    def test_a_tower_keeps_every_run_though_it_ends_open(self):
        lost = [[T0, T0 + 10 * DAY], [T0 + 100 * DAY, T0 + 110 * DAY], [T0 + 600 * DAY, cal.NEVER]]
        self.assertEqual(cal.runs((T0 + 600 * DAY, cal.NEVER), lost, keep_runs=True), [tuple(r) for r in lost])

    def test_a_tower_chapter_gets_a_copy_for_each_run(self):
        spec = {"key": [0], "dates": [2, 3], "rows": {"701": [[T0, T0 + 10 * DAY], [T0 + 600 * DAY, cal.NEVER]]}}
        copies = {}
        blob = cal.restore_runs(table(row(701, cal.TOWER_TYPE, Date(T0 + 600 * DAY), Date(cal.NEVER), 230001),
                                      row(510, 1, Date(T0 + 600 * DAY), Date(cal.NEVER), 200011)), spec, copies)
        self.assertEqual(cells(blob)[:2], [[701, cal.TOWER_TYPE, T0, T0 + 10 * DAY, 230001],
                                           [701 + cal.COPY_STEP, cal.TOWER_TYPE, T0 + 600 * DAY, cal.NEVER, 230001]])
        self.assertEqual(copies, {701: [701 + cal.COPY_STEP]})

    def test_each_run_shows_only_its_floors(self):
        chapters = table(row(701, cal.TOWER_TYPE, 0, 0, 230001), row(701 + cal.COPY_STEP, cal.TOWER_TYPE, 0, 0, 230001))
        groups = table(row(230001, 1, 230001))
        sequences = cal._table([row(230001, n, 230000 + n) for n in range(1, 31)])  # more rows than table() can head
        out = cal.tower_floors(chapters, groups, sequences, group_col=4, floors={"701": [20, 30]})
        ch, gr, sq = (cells(b) for b in out)
        first = 230001 + 20 * cal.COPY_STEP  # a sequence of the first 20 floors
        self.assertEqual([c[4] for c in ch], [first, 230001])  # the first run 20 floors, the second all 30
        self.assertIn([first, 1, first], gr)
        self.assertEqual(sorted(q[2] for q in sq if q[0] == first), [230000 + n for n in range(1, 21)])
        self.assertEqual(len([q for q in sq if q[0] == 230001]), 30)


class EventRuns(unittest.TestCase):
    """A rerun event replays each run with its own exchange, shown medal and
    quests (event_runs.json): chapter 510's first run had exchange 6008 and
    medal 25 and two of the three quests the last run has."""
    COLS = {"link": 5, "display": 6, "group": 7}

    def build(self, runs):
        # EventQuestChapterId, Type, SortOrder, Name, Banner, LinkId, DisplayItemGroupId, SequenceGroupId
        chapters = table(row(510, 1, 0, 0, 0, 84, 200061, 200011), row(510 + cal.COPY_STEP, 1, 0, 0, 0, 84, 200061, 200011),
                         row(510 + 2 * cal.COPY_STEP, 1, 0, 0, 0, 84, 200061, 200011), row(600, 1, 0, 0, 0, 90, 1, 2))
        links = table(row(84, 3, 6064, 6, 149))
        groups = table(row(200011, 1, 200028), row(200011, 2, 200509))
        sequences = table(row(200028, 1, 1), row(200028, 2, 2), row(200509, 1, 3))
        return [cells(b) for b in cal.event_runs(chapters, links, groups, sequences, runs, self.COLS)]

    RUN0 = {"link": 17, "display": 200011, "quests": [1, 2], "link_row": {"shop": 6008, "possession_type": 6, "possession_id": 25}}
    RUN1 = {"link": 36, "display": 200024, "quests": [1, 2, 3], "link_row": {"shop": 6020, "possession_type": 6, "possession_id": 46}}

    def test_each_run_links_its_own_exchange(self):
        ch, ln, _, _ = self.build({"510": [self.RUN0, self.RUN1, None]})
        first, second = 17 + 100 * cal.COPY_STEP, 36 + 101 * cal.COPY_STEP
        self.assertEqual([(c[0], c[5], c[6]) for c in ch], [(510, first, 200011), (510 + cal.COPY_STEP, second, 200024),
                                                             (510 + 2 * cal.COPY_STEP, 84, 200061), (600, 90, 1)])
        self.assertIn([first, 3, 6008, 6, 25], ln)
        self.assertIn([second, 3, 6020, 6, 46], ln)
        self.assertIn([84, 3, 6064, 6, 149], ln)  # the last run's own row stays

    def test_a_run_shows_only_the_quests_it_had(self):
        ch, _, gr, sq = self.build({"510": [self.RUN0, self.RUN1, None]})
        trimmed = 200011 + 100 * cal.COPY_STEP
        self.assertEqual(ch[0][7], trimmed)
        self.assertEqual(ch[1][7], 200011)  # the second run had every quest
        self.assertEqual(sorted(g for g in gr if g[0] == trimmed), [[trimmed, 1, 200028 + 100 * cal.COPY_STEP]])  # no quest left in 200509
        self.assertEqual(sorted(q[2] for q in sq if q[0] == 200028 + 100 * cal.COPY_STEP), [1, 2])
        self.assertEqual(len(sq), 5)  # the originals kept

    def test_a_run_gives_its_own_medals(self):
        run0 = dict(self.RUN0, drops={"1": [[6, 25, 9], [5, 100002, 4]], "2": []})
        given = cal.run_items([510, 510 + cal.COPY_STEP, 510 + 2 * cal.COPY_STEP, 600], {"510": [run0, None, None]})
        self.assertEqual(given, {510: {25}})  # the medal it drops then; other copies keep what the game data gives

    def test_a_calendar_in_use_is_rebuilt(self):
        """Calendars built before each run had its own exchange are rebuilt on update."""
        self.assertGreaterEqual(cal.DATA_VERSION, 4)
        self.assertGreaterEqual(int(cal.VIEW_VERSION), 5)

    def test_without_run_data_nothing_changes(self):
        ch, ln, gr, sq = self.build({})
        self.assertEqual([c[5] for c in ch], [84, 84, 84, 90])
        self.assertEqual((len(ln), len(gr), len(sq)), (1, 2, 3))


class DailyMissions(unittest.TestCase):
    """Daily missions 21-26 (term 1002) were the daily set from launch to 24
    November 2021; the weekly masters only kept the run from 24 September."""

    def test_the_first_daily_set_opens_at_launch_and_closes_for_the_next(self):
        spec = cal.history()["m_mission_term"]
        # The final game data's dates: 24 September 2021 to "2011-11-24".
        blob = cal.restore_runs(table(row(1002, Date(1632470400000), Date(1322121599000))), spec, table_name="m_mission_term")
        self.assertEqual(cells(blob), [[1002, T0, 1637740799000]])

    def test_a_loop_has_a_daily_set_from_its_first_week(self):
        blob = cal.restore_runs(table(row(1002, Date(1632470400000), Date(1322121599000))), cal.history()["m_mission_term"],
                                table_name="m_mission_term")
        moved = bytearray(blob)
        loop_start = T0 + 1000 * DAY
        cal.shift_table(moved, {1, 2}, loop_start - T0)
        (_, start, end), = cells(bytes(moved))
        self.assertLessEqual(start, loop_start)
        self.assertEqual(end, 1637740799000 + loop_start - T0)  # closed when 31-36 open, not left open for good

    def test_a_calendar_in_use_gets_the_daily_missions(self):
        self.assertGreaterEqual(cal.DATA_VERSION, 5)
        self.assertGreaterEqual(int(cal.VIEW_VERSION), 6)


class Anecdotes(unittest.TestCase):
    """An Anecdote (web panel mission) replays every run as a copy: the mission
    and its sheet get the run's ids, the story pages stay shared."""

    def test_a_mission_and_its_sheet_get_a_copy_per_run(self):
        mission = {"key": [0], "dates": [4, 5], "rows": {"8": [[T0, T0 + 9 * DAY], [T0 + 200 * DAY, T0 + 230 * DAY]]}}
        sheet = {"key": [0, 1], "dates": [3, 4], "rows": {"8|1": [[T0, T0 + 9 * DAY], [T0 + 200 * DAY, T0 + 230 * DAY]]}}
        copies = {}
        m = cal.restore_runs(table(row(8, 8, 1, 8, Date(T0 + 200 * DAY), Date(T0 + 230 * DAY))), mission, copies, table_name="m_webview_mission")
        s = cal.restore_runs(table(row(8, 1, 15, Date(T0 + 200 * DAY), Date(T0 + 230 * DAY))), sheet, copies, table_name="m_webview_panel_mission")
        step = cal.COPY_STEP
        self.assertEqual(cells(m), [[8, 8, 1, 8, T0, T0 + 9 * DAY], [8 + step, 8, 1, 8 + step, T0 + 200 * DAY, T0 + 230 * DAY]])
        self.assertEqual(cells(s), [[8, 1, 15, T0, T0 + 9 * DAY], [8 + step, 1, 15, T0 + 200 * DAY, T0 + 230 * DAY]])

    def test_the_library_lists_an_anecdote_once(self):
        # The game's Library and Missions list the missions of type 1: the
        # runs become type 2 and one type-1 row stands for the Anecdote, from
        # its first run's start to its last run's end, with its own sheet
        # (the game finds a mission's pages by its id): the first run's pages.
        step = cal.COPY_STEP
        runs = table(row(8, 8, 1, 8, Date(T0), Date(T0 + 9 * DAY)),
                     row(8 + step, 8, 1, 8 + step, Date(T0 + 200 * DAY), Date(T0 + 230 * DAY)),
                     row(3, 3, 1, 3, Date(T0 + 50 * DAY), Date(T0 + 60 * DAY)))
        out = cal.library_missions(runs)
        self.assertEqual(sorted(cells(out)), sorted([
            [8, 8, 2, 8, T0, T0 + 9 * DAY],
            [8 + step, 8, 2, 8 + step, T0 + 200 * DAY, T0 + 230 * DAY],
            [8 + cal.LIBRARY_SLOT * step, 8, 1, 8 + cal.LIBRARY_SLOT * step, T0, T0 + 230 * DAY],
            [3, 3, 1, 3, T0 + 50 * DAY, T0 + 60 * DAY],  # one run: as it was
        ]))
        # Dates stay whole int64 cells, which the loop's date shift moves.
        library = [c for _, c in cal._rows(out) if msgpack.unpackb(c[0]) == 8 + cal.LIBRARY_SLOT * step][0]
        self.assertTrue(library[4].startswith(b"\xd3") and library[5].startswith(b"\xd3"))

    def test_the_library_row_has_the_first_runs_pages(self):
        step = cal.COPY_STEP
        sheets = table(row(8, 1, 15, Date(T0), Date(T0 + 9 * DAY)), row(8, 2, 16, Date(T0), Date(T0 + 9 * DAY)),
                       row(8 + step, 1, 15, Date(T0 + 200 * DAY), Date(T0 + 230 * DAY)),
                       row(8 + step, 2, 16, Date(T0 + 200 * DAY), Date(T0 + 230 * DAY)),
                       row(3, 1, 5, Date(T0 + 50 * DAY), Date(T0 + 60 * DAY)))
        lib = 8 + cal.LIBRARY_SLOT * step
        added = [c for c in cells(cal.library_sheets(sheets)) if c[0] == lib]
        self.assertEqual(added, [[lib, 1, 15, T0, T0 + 230 * DAY], [lib, 2, 16, T0, T0 + 230 * DAY]])
        self.assertFalse([c for c in cells(cal.library_sheets(sheets)) if c[0] == 3 + cal.LIBRARY_SLOT * step])

    def test_a_run_recorded_twice_plays_once(self):
        # Anecdote: Tower's April 2022 run is in the history twice, 6 hours apart.
        self.assertEqual(cal.merge_overlaps([[0, 10 * DAY], [DAY // 4, 10 * DAY + DAY // 4], [100 * DAY, 110 * DAY]]),
                         [[0, 10 * DAY], [100 * DAY, 110 * DAY]])


class Exchanges(unittest.TestCase):
    """An event's medal exchange and the items it gives open with the event (GitHub issue #5)."""
    SHOP, LINK, MEDAL = 3, 6, 6  # link to a shop; the medal is a consumable item

    def dates(self, chapters, shops, cell_groups=(), cell_terms=None, item_terms=None, given=None):
        links = {84: (self.SHOP, 6064, self.MEDAL, 149), 90: (1, 7, self.MEDAL, 150)}
        items = {149: 149, 150: 150, 6006: 6006}
        return cal.exchange_dates(chapters, links, shops, cell_groups, cell_terms or {}, items, item_terms or {}, given or {})

    def test_the_exchange_opens_when_its_chapter_first_does(self):
        # Chapter 510 opens from its 2021 run; its exchange only from 2023.
        out = self.dates([(510, 84, T0, cal.NEVER)], {6064: (600064, T0 + 600 * DAY, cal.NEVER)})
        self.assertEqual(out["m_shop"], {6064: (T0, cal.NEVER)})

    def test_an_exchange_already_open_stays_as_it_is(self):
        out = self.dates([(510, 84, T0 + 10 * DAY, cal.NEVER)], {6064: (600064, T0, cal.NEVER)})
        self.assertEqual(out["m_shop"], {})

    def test_the_exchange_stays_open_through_the_last_run(self):
        out = self.dates([(510, 84, T0, T0 + 40 * DAY), (510 + cal.COPY_STEP, 84, T0 + 600 * DAY, T0 + 620 * DAY)],
                         {6064: (600064, T0 + 600 * DAY, T0 + 610 * DAY)})
        self.assertEqual(out["m_shop"], {6064: (T0, T0 + 620 * DAY)})

    def test_the_medal_is_valid_when_its_chapter_opens(self):
        out = self.dates([(510, 84, T0, cal.NEVER)], {6064: (600064, T0, cal.NEVER)}, item_terms={149: (T0 + 600 * DAY, cal.NEVER)})
        self.assertEqual(out["m_consumable_item_term"], {149: (T0, cal.NEVER)})

    def test_a_medal_its_quests_drop_is_valid_while_its_chapter_is_open(self):
        # Chapter 510's silver medal: dropped by its quests, dated to the 2023 run.
        out = self.dates([(510, 84, T0, cal.NEVER)], {6064: (600064, T0, cal.NEVER)}, item_terms={150: (T0 + 600 * DAY, T0 + 640 * DAY)}, given={510: [150]})
        self.assertEqual(out["m_consumable_item_term"], {150: (T0, cal.NEVER)})

    def test_an_item_dated_to_another_run_covers_this_one(self):
        # Chapter 306's tickets: valid in October, the event runs in December.
        out = self.dates([(306, 90, T0 + 140 * DAY, T0 + 154 * DAY)], {}, item_terms={6006: (T0 + 75 * DAY, T0 + 91 * DAY)}, given={306: [6006]})
        self.assertEqual(out["m_consumable_item_term"], {6006: (T0 + 75 * DAY, T0 + 154 * DAY)})

    def test_an_item_parked_for_good_opens_with_its_chapter(self):
        out = self.dates([(508, 90, T0 + 36 * DAY, T0 + 51 * DAY)], {}, item_terms={6006: (cal.NEVER, cal.NEVER)}, given={508: [6006]})
        self.assertEqual(out["m_consumable_item_term"], {6006: (T0 + 36 * DAY, cal.NEVER)})

    def test_an_offer_added_later_opens_with_the_exchange(self):
        out = self.dates([(510, 84, T0, cal.NEVER)], {6064: (600064, T0 + 600 * DAY, cal.NEVER)},
                         cell_groups=[(600064, 22)], cell_terms={22: (T0 + 620 * DAY, cal.NEVER)})
        self.assertEqual(out["m_shop_item_cell_term"], {22: (T0, cal.NEVER)})

    def test_an_offer_term_another_shop_shares_is_left(self):
        out = self.dates([(510, 84, T0, cal.NEVER)], {6064: (600064, T0 + 600 * DAY, cal.NEVER), 7000: (700000, T0 + 600 * DAY, cal.NEVER)},
                         cell_groups=[(600064, 22), (700000, 22)], cell_terms={22: (T0 + 620 * DAY, cal.NEVER)})
        self.assertEqual(out["m_shop_item_cell_term"], {})

    def test_links_to_other_screens_are_ignored(self):
        out = self.dates([(511, 90, T0, cal.NEVER)], {7: (700000, T0 + 600 * DAY, cal.NEVER)})
        self.assertEqual(out, {"m_shop": {}, "m_shop_item_cell_term": {}, "m_consumable_item_term": {}})


ORIGINAL = Path(__file__).resolve().parents[2] / "inputs/20240404193219.bin.e"


@unittest.skipUnless(ORIGINAL.exists(), "needs inputs/20240404193219.bin.e")
class TowersInTheGameData(unittest.TestCase):
    def test_every_tower_run_opens_with_its_floors(self):
        import tempfile
        from tools import dump_masterdata
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "loop.bin.e"
            cal.build_master(ORIGINAL, out, 0)
            toc, blob = cal.read_master(out)
        changed, schemas = {}, dump_masterdata.load_schemas()
        read = lambda table, *names: cal._read(toc, blob, changed, schemas, table, *names)
        floors = json.loads(cal.TOWER_FLOORS.read_text())["floors"]
        runs = json.loads(cal.HISTORY.read_text())["tables"]["m_event_quest_chapter"]["rows"]
        chapters = {c: (g, s, e) for c, t, g, s, e in read("m_event_quest_chapter", "EventQuestChapterId", "EventQuestType", "EventQuestSequenceGroupId", "StartDatetime", "EndDatetime") if t == cal.TOWER_TYPE}
        seq_of = dict(read("m_event_quest_sequence_group", "EventQuestSequenceGroupId", "EventQuestSequenceId"))
        count = {}
        for seq, _ in read("m_event_quest_sequence", "EventQuestSequenceId", "QuestId"):
            count[seq] = count.get(seq, 0) + 1
        for tower, counts in floors.items():
            for n, (want, (start, end)) in enumerate(zip(counts, runs[tower])):
                group, s, e = chapters[int(tower) + n * cal.COPY_STEP]
                end = cal.NEVER if end >= cal.FOREVER else end  # the build writes "never" as 2099-12-31
                self.assertEqual((s, e), (start, end), f"tower {tower} run {n}")
                self.assertEqual(count[seq_of[group]], want, f"tower {tower} run {n} floors")


@unittest.skipUnless(ORIGINAL.exists(), "needs inputs/20240404193219.bin.e")
class AnecdotesInTheGameData(unittest.TestCase):
    def test_every_anecdote_run_opens_with_its_sheet(self):
        import tempfile
        from tools import dump_masterdata
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "loop.bin.e"
            cal.build_master(ORIGINAL, out, 0)
            toc, blob = cal.read_master(out)
        changed, schemas = {}, dump_masterdata.load_schemas()
        read = lambda table, *names: cal._read(toc, blob, changed, schemas, table, *names)
        missions = read("m_webview_mission", "WebviewMissionId", "WebviewMissionTargetId", "StartDatetime")
        sheets = {}
        for sheet, start in read("m_webview_panel_mission", "WebviewPanelMissionId", "StartDatetime"):
            sheets.setdefault(sheet, []).append(start)
        types = dict(read("m_webview_mission", "WebviewMissionId", "WebviewMissionType"))
        self.assertEqual(sum(1 for t in types.values() if t == 1), 8)  # the Library lists each Anecdote once
        listed = [m for m in missions if m[0] // cal.COPY_STEP == cal.LIBRARY_SLOT]
        for mission, target, _ in listed:
            self.assertEqual((target, len(sheets.get(target, []))), (mission, 2), f"library row {mission}")
        missions = [m for m in missions if m[0] // cal.COPY_STEP != cal.LIBRARY_SLOT]
        self.assertEqual(len(missions), 15)  # 8 Anecdotes, 7 reruns (Stars and Doll twice)
        for mission, target, start in missions:
            self.assertEqual(len(sheets.get(target, [])), 2, f"mission {mission}")
            self.assertTrue(all(abs(s - start) <= 6 * 3600_000 for s in sheets[target]), f"mission {mission}")


@unittest.skipUnless(ORIGINAL.exists(), "needs inputs/20240404193219.bin.e")
class ExchangesInTheGameData(unittest.TestCase):
    def test_every_event_exchange_opens_with_its_chapter(self):
        import tempfile
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "loop.bin.e"
            cal.build_master(ORIGINAL, out, 0)
            toc, blob = cal.read_master(out)
        from tools import dump_masterdata
        changed, schemas = {}, dump_masterdata.load_schemas()
        read = lambda table, *names: cal._read(toc, blob, changed, schemas, table, *names)
        links = {r[0]: r[1:] for r in read("m_event_quest_link", "EventQuestLinkId", "DestinationDomainType", "DestinationDomainId", "PossessionType", "PossessionId")}
        shops = {r[0]: r[1:] for r in read("m_shop", "ShopId", "StartDatetime", "EndDatetime")}
        item_term = dict(read("m_consumable_item", "ConsumableItemId", "ConsumableItemTermId"))
        item_terms = {r[0]: r[1:] for r in read("m_consumable_item_term", "ConsumableItemTermId", "StartDatetime", "EndDatetime")}
        sequences, quests_of = {}, {}
        for group, sequence in read("m_event_quest_sequence_group", "EventQuestSequenceGroupId", "EventQuestSequenceId"):
            sequences.setdefault(group, []).append(sequence)
        for sequence, quest in read("m_event_quest_sequence", "EventQuestSequenceId", "QuestId"):
            quests_of.setdefault(sequence, []).append(quest)
        quest_rewards = {r[0]: r[1:] for r in read("m_quest", "QuestId", "QuestFirstClearRewardGroupId", "QuestPickupRewardGroupId")}
        first_clear, pickup = {}, {}
        for group, kind, item in read("m_quest_first_clear_reward_group", "QuestFirstClearRewardGroupId", "PossessionType", "PossessionId"):
            if kind == 6:
                first_clear.setdefault(group, set()).add(item)
        drops = {r[0]: r[1:] for r in read("m_battle_drop_reward", "BattleDropRewardId", "PossessionType", "PossessionId")}
        for group, drop in read("m_quest_pickup_reward_group", "QuestPickupRewardGroupId", "BattleDropRewardId"):
            kind, item = drops.get(drop, (0, 0))
            if kind == 6:
                pickup.setdefault(group, set()).add(item)
        group_of = {r[0]: r[1] for r in read("m_event_quest_chapter", "EventQuestChapterId", "EventQuestSequenceGroupId")}
        # An earlier run of a rerun event drops its own medals (event_runs.json; the server pays them).
        run_given = cal.run_items(list(group_of), cal.event_run_data())
        checked = rewards = 0
        for chapter, link, start, end in read("m_event_quest_chapter", "EventQuestChapterId", "EventQuestLinkId", "StartDatetime", "EndDatetime"):
            if not cal.EARLIEST <= start < cal.FOREVER:
                continue
            for quest in (q for sequence in sequences.get(group_of[chapter], []) for q in quests_of.get(sequence, [])):
                first, pick = quest_rewards.get(quest, (0, 0))
                for given in first_clear.get(first, set()) | (run_given[chapter] if chapter in run_given else pickup.get(pick, set())):
                    if item_term.get(given) in item_terms:
                        rewards += 1
                        term_start, term_end = item_terms[item_term[given]]
                        self.assertTrue(term_start <= start and term_end >= end, f"chapter {chapter}: item {given} not valid while it is open")
            kind, shop, possession, item = links.get(link, (0, 0, 0, 0))
            if kind != 3 or shop not in shops:
                continue
            checked += 1
            self.assertLessEqual(shops[shop][0], start, f"chapter {chapter}: exchange {shop} opens after the chapter")
            self.assertGreaterEqual(shops[shop][1], end, f"chapter {chapter}: exchange {shop} closes before the chapter")
            if possession == 6 and item_term.get(item) in item_terms:
                self.assertLessEqual(item_terms[item_term[item]][0], start, f"chapter {chapter}: medal {item} not valid yet")
        self.assertGreater(checked, 20)
        self.assertGreater(rewards, 1000)



class BannerRuns(unittest.TestCase):
    def test_banners_of_summons_bunker_does_not_list_stay_parked(self):
        # Banner 274 opens summon 9000085, which Bunker leaves out; banner 365
        # opens summon 159, a parked rerun. Their restored runs would open the
        # Summons screen on another summon.
        spec = {"key": [0], "dates": [6, 7], "rows": {"274": [[1, 2]], "365": [[3, 4]], "22": [[5, 6]]}}
        self.assertEqual(sorted(cal.history_spec("m_mom_banner", spec)["rows"]), ["22"])
        self.assertIs(cal.history_spec("m_tip", spec), spec)


class EventBanners(unittest.TestCase):
    """Each run shows the banner it had (event_banners.json): Sunset Port's
    first run banner 509, not its rerun's 535."""

    def chapters(self):
        # EventQuestChapterId, Type, SortOrder, Name, BannerAssetId
        return table(row(509, 1, 0, 509, 535), row(509 + cal.COPY_STEP, 1, 0, 509, 535),
                     row(509 + 2 * cal.COPY_STEP, 1, 0, 509, 535), row(600, 1, 0, 600, 600))

    def test_each_run_shows_its_own_banner(self):
        out = cells(cal.event_banners(self.chapters(), {"509": [509, 520, None]}, banner_col=4))
        self.assertEqual([(c[0], c[4]) for c in out], [(509, 509), (509 + cal.COPY_STEP, 520), (509 + 2 * cal.COPY_STEP, 535), (600, 600)])

    def test_a_run_past_the_recorded_ones_keeps_the_final_banner(self):
        out = cells(cal.event_banners(self.chapters(), {"509": [509]}, banner_col=4))
        self.assertEqual([c[4] for c in out], [509, 535, 535, 600])

    def test_without_banner_data_nothing_changes(self):
        self.assertEqual(cal.event_banners(self.chapters(), {}, banner_col=4), self.chapters())

    def test_a_home_banner_shows_its_first_runs_image(self):
        # MomBannerId, SortOrderDesc, DestinationDomainType, DestinationDomainId, BannerAssetName
        home = table(row(107, 1, 23, 269, "event_mom_banner_512"), row(22, 1, 23, 289, "event_mom_banner_512"))
        out = cells(cal.home_banners(home, {"107": "event_mom_banner_520"}, name_col=4))
        self.assertEqual([(c[0], c[3], c[4]) for c in out], [(107, 269, "event_mom_banner_520"), (22, 289, "event_mom_banner_512")])

    def test_a_calendar_in_use_is_rebuilt(self):
        """Calendars built before each run had its own banner are rebuilt on update."""
        self.assertGreaterEqual(cal.DATA_VERSION, 6)
        self.assertGreaterEqual(int(cal.VIEW_VERSION), 7)


@unittest.skipUnless(ORIGINAL.exists(), "needs inputs/20240404193219.bin.e")
class EventBannersInTheGameData(unittest.TestCase):
    def test_every_run_shows_its_recorded_banner(self):
        import tempfile
        from tools import dump_masterdata
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "loop.bin.e"
            cal.build_master(ORIGINAL, out, 0)
            toc, blob = cal.read_master(out)
        schemas = dump_masterdata.load_schemas()
        shown = dict(cal._read(toc, blob, {}, schemas, "m_event_quest_chapter", "EventQuestChapterId", "BannerAssetId"))
        recorded = json.loads(cal.EVENT_BANNERS.read_text())["chapters"]
        self.assertEqual((shown[509], shown[510], shown[510 + 2 * cal.COPY_STEP]), (509, 510, 559))  # Sunset Port, Cage: first runs, Cage's last
        for chapter, banners in recorded.items():
            for n, banner in enumerate(banners):
                if banner is not None and int(chapter) + n * cal.COPY_STEP in shown:
                    self.assertEqual(shown[int(chapter) + n * cal.COPY_STEP], banner, f"chapter {chapter} run {n}")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(ORIGINAL.exists(), "needs inputs/20240404193219.bin.e")
class ViewFromLaunch(unittest.TestCase):
    """Tables the calendar doesn't move are all in the past in the loop's dates
    (2026 on): characters listed, filters complete. The copy for Show original
    dates (2021) caps those start dates at launch so the game behaves the same;
    before, Enhance > Characters was empty (m_character 2022). Story chapters
    keep their dates and open as the calendar reaches them."""
    @classmethod
    def setUpClass(cls):
        import tempfile
        from tools import dump_masterdata
        cls.schemas = dump_masterdata.load_schemas()
        with tempfile.TemporaryDirectory() as work:
            view, loop = Path(work) / "view.bin.e", Path(work) / "loop.bin.e"
            cal.build_master(ORIGINAL, view, 0, view=True)
            cal.build_master(ORIGINAL, loop, 100 * cal.WEEK)
            cls.view, cls.loop = cal.read_master(view), cal.read_master(loop)
        cls.original = cal.read_master(ORIGINAL)

    def rows(self, master, table, *names):
        toc, blob = master
        return cal._read(toc, blob, {}, self.schemas, table, *names)

    def test_start_dates_are_capped_at_launch(self):
        self.assertIn("m_character", cal.VIEW_FROM_LAUNCH)
        for table, columns in cal.VIEW_FROM_LAUNCH.items():
            for column in columns:
                built = [r[0] for r in self.rows(self.view, table, column)]
                original = [r[0] for r in self.rows(self.original, table, column)]
                self.assertEqual(built, [min(v, cal.LAUNCH) for v in original], f"{table}.{column}")
                self.assertTrue(any(v > cal.LAUNCH for v in original), f"{table}.{column} has nothing to cap")

    def test_story_chapters_open_on_their_dates(self):
        # As in the live game: a chapter opens when the calendar reaches its date.
        self.assertEqual(self.rows(self.view, "m_main_quest_chapter", "StartDatetime"),
                         self.rows(self.original, "m_main_quest_chapter", "StartDatetime"))

    def test_catalog_terms_keep_their_dates(self):
        # The server compares them in the live service's dates (summon notices).
        self.assertEqual(self.rows(self.view, "m_catalog_term", "StartDatetime"), self.rows(self.original, "m_catalog_term", "StartDatetime"))

    def test_loop_data_is_not_capped(self):
        self.assertEqual(self.rows(self.loop, "m_main_quest_chapter", "StartDatetime"), self.rows(self.original, "m_main_quest_chapter", "StartDatetime"))


@unittest.skipUnless(ORIGINAL.exists(), "needs inputs/20240404193219.bin.e")
class StoryChaptersInTheGameData(unittest.TestCase):
    """With the Original calendar, story chapters open on their release dates
    (moved into the loop), except chapters the player already reached."""
    @classmethod
    def setUpClass(cls):
        from tools import dump_masterdata
        cls.schemas = dump_masterdata.load_schemas()
        cls.original = dict(cls.rows(cal.read_master(ORIGINAL)))
        cls.dated = sorted(c for c, v in cls.original.items() if cal.LAUNCH < v < cal.FOREVER)

    @classmethod
    def rows(cls, master):
        toc, blob = master
        return cal._read(toc, blob, {}, cls.schemas, "m_main_quest_chapter", "MainQuestChapterId", "StartDatetime")

    def build(self, offset, chapters, view=False):
        import tempfile
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "out.bin.e"
            cal.build_master(ORIGINAL, out, offset, view=view, open_chapters=chapters)
            return dict(self.rows(cal.read_master(out)))

    def test_loop_moves_chapters_and_opens_reached_ones(self):
        offset, reached = 100 * cal.WEEK, self.dated[0]
        built = self.build(offset, {reached})
        self.assertEqual(built[reached], min(self.original[reached], cal.LAUNCH) + offset)
        for chapter in self.dated[1:]:
            self.assertEqual(built[chapter], self.original[chapter] + offset, chapter)

    def test_chapters_open_from_the_start_stay_as_they_are(self):
        built = self.build(100 * cal.WEEK, set())
        early = [c for c, v in self.original.items() if v < cal.LAUNCH]
        self.assertTrue(early)
        self.assertEqual([built[c] for c in early], [self.original[c] for c in early])

    def test_view_keeps_dates_and_opens_reached_ones(self):
        reached = self.dated[0]
        built = self.build(0, {reached}, view=True)
        self.assertEqual(built[reached], min(self.original[reached], cal.LAUNCH))
        self.assertEqual([built[c] for c in self.dated[1:]], [self.original[c] for c in self.dated[1:]])

    def test_every_chapter_open_when_all_are_reached(self):
        built = self.build(100 * cal.WEEK, set(self.original))
        self.assertTrue(all(v <= cal.LAUNCH + 100 * cal.WEEK for v in built.values()))
