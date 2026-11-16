#!/usr/bin/env python3
"""Checks the Original calendar's event runs in its game data: every earlier run
of a rerun event plays its own copies of the quests it had (android_calendar
run_quest_copies), each with its scenes and their battle rows, unlocked by the
run's own copies, listing the drops the run had; every medal they drop is a
currency of the run's exchange or the event's own medal, and every currency of
the exchange is dropped; the last run plays the original quests.

  check_run_quests.py --master 20240404193219.bin.e   (the original game data;
                                                        the calendar's is built from it)

Exits 1 and lists the problems when any check fails.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))


TABLES = ("m_event_quest_chapter", "m_event_quest_sequence_group", "m_event_quest_sequence", "m_quest", "m_quest_scene",
          "m_quest_pickup_reward_group", "m_battle_drop_reward", "m_quest_release_condition_list", "m_quest_release_condition_group",
          "m_quest_release_condition_quest_clear", "m_event_quest_link", "m_shop", "m_shop_item_cell_group", "m_shop_item_cell",
          "m_shop_item", "m_consumable_item")


def check(rows, runs, cal):
    """Problems found (strings) and a summary, from the calendar's tables (rows by name) and event_run_data()."""
    problems, summary = [], collections.Counter()
    by = lambda name, key: {r[key]: r for r in rows[name]}
    def grouped(name, key):
        out = collections.defaultdict(list)
        for r in rows[name]:
            out[r[key]].append(r)
        return out
    chapters = by("m_event_quest_chapter", "EventQuestChapterId")
    quests = by("m_quest", "QuestId")
    groups, sequences = grouped("m_event_quest_sequence_group", "EventQuestSequenceGroupId"), grouped("m_event_quest_sequence", "EventQuestSequenceId")
    scenes = grouped("m_quest_scene", "QuestId")
    scene_rows = {name: collections.Counter(r["QuestSceneId"] for r in rows[name]) for name in cal.COPY_SCENE_TABLES if name in rows}
    pickups, drops = grouped("m_quest_pickup_reward_group", "QuestPickupRewardGroupId"), by("m_battle_drop_reward", "BattleDropRewardId")
    lists, cgroups = grouped("m_quest_release_condition_list", "QuestReleaseConditionListId"), grouped("m_quest_release_condition_group", "QuestReleaseConditionGroupId")
    clears = by("m_quest_release_condition_quest_clear", "QuestReleaseConditionId")
    links = by("m_event_quest_link", "EventQuestLinkId")
    shops = by("m_shop", "ShopId")
    cells, items = grouped("m_shop_item_cell_group", "ShopItemCellGroupId"), grouped("m_shop_item_cell", "ShopItemCellId")
    shop_items = by("m_shop_item", "ShopItemId")

    def chapter_quests(chapter):
        return [q["QuestId"] for g in groups[chapter["EventQuestSequenceGroupId"]] for q in sequences[g["EventQuestSequenceId"]]]

    def shop_currencies(shop_id):
        shop = shops.get(shop_id)
        if not shop:
            return set()
        return {shop_items[i]["PriceId"] for c in cells[shop["ShopItemCellGroupId"]] for i in (x["ShopItemId"] for x in items[c["ShopItemCellId"]])
                if i in shop_items and shop_items[i]["PriceType"] == 1}

    for base, recorded in sorted(runs.items(), key=lambda kv: int(kv[0])):
        for n, run in enumerate(recorded):
            chapter_id = int(base) + n * cal.COPY_STEP
            chapter = chapters.get(chapter_id)
            if chapter is None:
                problems.append(f"chapter {chapter_id}: missing")
                continue
            played = chapter_quests(chapter)
            if run is None:
                if any(q >= cal.RUN_IDS * cal.COPY_STEP for q in played):
                    problems.append(f"chapter {chapter_id} (last run): plays copies")
                summary["last runs"] += 1
                continue
            step = (cal.RUN_IDS + n) * cal.COPY_STEP
            summary["earlier runs"] += 1
            want = {q + step for q in run["quests"]} if run["quests"] else None
            if not played or any(q - q % cal.COPY_STEP != step for q in played):
                problems.append(f"chapter {chapter_id}: plays {sorted(played)[:3]}…, not its run's copies (+{step})")
            if want is not None and set(played) != want:
                problems.append(f"chapter {chapter_id}: {len(played)} quests, the run had {len(want)}")
            link = links.get(chapter["EventQuestLinkId"], {})
            medal, shop = link.get("PossessionId"), link.get("DestinationDomainId")
            currencies = shop_currencies(shop)
            dropped = set()
            for copy in played:
                original = copy % cal.COPY_STEP
                summary["quest copies"] += 1
                if copy not in quests:
                    problems.append(f"quest {copy}: no m_quest row")
                    continue
                own, theirs = scenes[copy], scenes[original]
                if len(own) != len(theirs) or {s["QuestSceneId"] - step for s in own} != {s["QuestSceneId"] for s in theirs}:
                    problems.append(f"quest {copy}: scenes {[s['QuestSceneId'] for s in own]} do not copy {[s['QuestSceneId'] for s in theirs]}")
                for name, counts in scene_rows.items():
                    for s in theirs:
                        if counts[s["QuestSceneId"] + step] != counts[s["QuestSceneId"]]:
                            problems.append(f"quest {copy}: {name} has {counts[s['QuestSceneId'] + step]} rows for scene "
                                            f"{s['QuestSceneId'] + step}, the original {counts[s['QuestSceneId']]}")
                summary["scene copies"] += len(own)
                shown = [(drops[p["BattleDropRewardId"]]["PossessionType"], drops[p["BattleDropRewardId"]]["PossessionId"], drops[p["BattleDropRewardId"]]["Count"])
                         for p in sorted(pickups[quests[copy]["QuestPickupRewardGroupId"]], key=lambda p: p["SortOrder"])]
                recorded_drops = [tuple(d) for d in (run.get("drops") or {}).get(str(original), [])]
                if recorded_drops and shown != recorded_drops:
                    problems.append(f"quest {copy}: shows drops {shown}, the run had {recorded_drops}")
                for kind, item, _ in shown:
                    if kind == 6 and _is_medal(rows, item):
                        dropped.add(item)
                        # The event's own medal (its page shows it) or a currency of its exchange. 502's and 514's
                        # earlier runs showed one medal and took another, both dropped: so the game data had it.
                        if item not in currencies and item != medal:
                            problems.append(f"quest {copy}: drops medal {item}, neither the event's ({medal}) nor taken by exchange {shop} ({sorted(currencies)})")
                listed = quests[copy]["QuestReleaseConditionListId"]
                for row in lists.get(listed, []):
                    for cond in cgroups[row["QuestReleaseConditionGroupId"]]:
                        if cond["QuestReleaseConditionType"] != cal.CLEAR_QUEST:
                            continue
                        target = clears.get(cond["QuestReleaseConditionId"], {}).get("QuestId")
                        if target is None:
                            problems.append(f"quest {copy}: unlock condition {cond['QuestReleaseConditionId']} names no quest")
                        elif target - target % cal.COPY_STEP != step and target + step in quests:
                            problems.append(f"quest {copy}: unlocks with quest {target}, not this run's copy {target + step}")
                        else:
                            summary["unlocks pointing at the run's copies"] += 1
                if listed and quests[original]["QuestReleaseConditionListId"] == 0:
                    problems.append(f"quest {copy}: has unlock conditions its original lacks")
            unspendable = currencies - dropped
            if unspendable:
                problems.append(f"chapter {chapter_id}: its exchange {shop} takes {sorted(unspendable)}, which none of its quests drop")
            summary["exchanges whose currencies the run's quests drop"] += 1
    return problems, summary


def _is_medal(rows, item):
    """An event medal: a consumable whose name says so (m_consumable_item, asset category 110)."""
    for r in rows["m_consumable_item"]:
        if r["ConsumableItemId"] == item:
            return r["AssetCategoryId"] == 110
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--master", type=Path, required=True, help="The original 20240404193219.bin.e")
    args = parser.parse_args()
    import android_calendar as cal
    from tools import dump_masterdata
    schemas = dump_masterdata.load_schemas()
    with tempfile.TemporaryDirectory() as temp:
        built = Path(temp) / "calendar.bin.e"
        cal.build_master(args.master, built, 0)
        toc, blob = cal.read_master(built)
    names = TABLES + cal.COPY_SCENE_TABLES
    rows = {n: cal.table_rows(toc, blob, {}, schemas, n) for n in names if n in toc}
    problems, summary = check(rows, cal.event_run_data(), cal)
    print(json.dumps(dict(summary), indent=1))
    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
