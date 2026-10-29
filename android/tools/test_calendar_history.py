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
        checked = rewards = 0
        for chapter, link, start, end in read("m_event_quest_chapter", "EventQuestChapterId", "EventQuestLinkId", "StartDatetime", "EndDatetime"):
            if not cal.EARLIEST <= start < cal.FOREVER:
                continue
            for quest in (q for sequence in sequences.get(group_of[chapter], []) for q in quests_of.get(sequence, [])):
                first, pick = quest_rewards.get(quest, (0, 0))
                for given in first_clear.get(first, set()) | pickup.get(pick, set()):
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


if __name__ == "__main__":
    unittest.main()
