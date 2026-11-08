#!/usr/bin/env python3
"""Writes what each earlier run of a rerun event had (event_runs.json).

An event that reran kept its quests, but each run had its own medal: a new
exchange (the chapter's EventQuestLink), the medal its page shows (its
display item group), the medals its quests drop (their pickup reward groups,
rewritten for each rerun, and in one event reused with other contents later)
and the medals its quest bonuses pay (bonus effects were reused with other
meanings). Later runs also added quests. The final game data keeps the last
run only, so the Original calendar replayed every run with the last run's
medals while the earlier runs' exchanges opened too, taking medals nothing
drops.

For each event chapter in calendar_history.json with more than one run and a
medal exchange, this reads the master published during each earlier run and
records, by run in order (the calendar's chapter copies: chapter + n *
COPY_STEP), its link, display item group, quests, each quest's drops and its
quest bonuses' medal payouts, all as they were then. The last run is null:
the final game data is that run. android_calendar.py gives each chapter copy
its run's link, display and quests; the server pays its drops and bonuses.

  event_runs.py --masters DIR

Needs pycryptodome, msgpack and lz4.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import calendar_history as ch

OUT = ch.PYTHON / "event_runs.json"
SERVER_OUT = ch.ROOT / "overlays/server/internal/masterdata/event_runs.json"
LINK_SHOP = 3
TABLES = ("m_event_quest_chapter", "m_event_quest_link", "m_event_quest_sequence_group", "m_event_quest_sequence",
          "m_quest", "m_quest_pickup_reward_group", "m_battle_drop_reward", "m_quest_bonus",
          "m_quest_bonus_character_group", "m_quest_bonus_costume_group", "m_quest_bonus_costume_setting_group",
          "m_quest_bonus_weapon_group", "m_quest_bonus_effect_group", "m_quest_bonus_drop_reward")


def pick(times, run):
    """The newest master published during the run, else the newest before it."""
    start, end = run
    during = [t for t in times if start <= t <= end]
    if during:
        return max(during)
    before = [t for t in times if t <= start]
    return max(before) if before else min(times)


def read(toc, blob, schemas, names=TABLES):
    """Tables as lists of dicts by column name (a column missing from an older master is left out)."""
    out = {}
    for name in names:
        if name not in toc or name not in schemas:
            out[name] = []
            continue
        cols = [(i, col) for i, _, col in schemas[name][1]]
        out[name] = [{col: row[i] for i, col in cols if i < len(row)} for row in ch.dm.decompress_table(blob, *toc[name])]
    return out


def _by(rows, key):
    out = {}
    for r in rows:
        out.setdefault(r.get(key), []).append(r)
    return out


def run_view(t, chapter):
    """What chapter used in one master's tables t, or None if it isn't there."""
    t = {name: t.get(name, []) for name in TABLES}  # a table an older master lacks counts as empty
    row = next((r for r in t["m_event_quest_chapter"] if r["EventQuestChapterId"] == chapter), None)
    if row is None:
        return None
    sequences = [g["EventQuestSequenceId"] for g in t["m_event_quest_sequence_group"]
                 if g["EventQuestSequenceGroupId"] == row["EventQuestSequenceGroupId"]]
    quests = [s["QuestId"] for s in sorted((s for s in t["m_event_quest_sequence"] if s["EventQuestSequenceId"] in sequences),
                                           key=lambda s: (sequences.index(s["EventQuestSequenceId"]), s["SortOrder"]))]
    quest = {q["QuestId"]: q for q in t["m_quest"]}
    drop = {d["BattleDropRewardId"]: [d["PossessionType"], d["PossessionId"], d["Count"]] for d in t["m_battle_drop_reward"]}
    pickup = _by(sorted(t["m_quest_pickup_reward_group"], key=lambda p: p["SortOrder"]), "QuestPickupRewardGroupId")
    drops = {}
    for q in quests:
        group = quest.get(q, {}).get("QuestPickupRewardGroupId", 0)
        drops[str(q)] = [drop[p["BattleDropRewardId"]] for p in pickup.get(group, []) if group and p["BattleDropRewardId"] in drop]

    link = next((l for l in t["m_event_quest_link"] if l["EventQuestLinkId"] == row["EventQuestLinkId"]), {})
    # The run's own medals: what its quests drop and what its exchange takes. A
    # bonus effect paying another medal is a stale reuse (an exchange already
    # closed) and is left out.
    own = {d[1] for ds in drops.values() for d in ds if d[0] == 6}
    if link.get("PossessionType") == 6:
        own.add(link["PossessionId"])
    stale = set()
    effects = _by(t["m_quest_bonus_effect_group"], "QuestBonusEffectGroupId")
    pays = _by(t["m_quest_bonus_drop_reward"], "QuestBonusEffectId")

    def paid(effect_group):
        out = []
        for e in effects.get(effect_group, []):
            for d in pays.get(e["QuestBonusEffectId"], []):
                if d["PossessionType"] == 6 and d["PossessionId"] not in own:
                    stale.add(d["PossessionId"])
                    continue
                out.append([d["PossessionType"], d["PossessionId"], d["AdditionalCount"]])
        return out

    bonus_rows = {b["QuestBonusId"]: b for b in t["m_quest_bonus"]}
    groups = {
        "character": (_by(t["m_quest_bonus_character_group"], "QuestBonusCharacterGroupId"), "QuestBonusCharacterGroupId", "CharacterId"),
        "costume_old": (_by(t["m_quest_bonus_costume_group"], "QuestBonusCostumeGroupId"), "QuestBonusCostumeGroupId", "CostumeId"),
        "costume": (_by(t["m_quest_bonus_costume_setting_group"], "QuestBonusCostumeSettingGroupId"), "QuestBonusCostumeSettingGroupId", "CostumeId"),
        "weapon": (_by(t["m_quest_bonus_weapon_group"], "QuestBonusWeaponGroupId"), "QuestBonusWeaponGroupId", "WeaponId"),
    }
    bonuses, bonus_of = {}, {}
    for q in quests:
        b = bonus_rows.get(quest.get(q, {}).get("QuestBonusId", 0))
        if not b:
            continue
        rules = []
        for kind, (rows, key, who) in groups.items():
            if kind == "costume_old" and b.get("QuestBonusCostumeSettingGroupId"):
                continue  # the costume settings replaced this table
            for r in rows.get(b.get(key), []) if b.get(key) else []:
                payout = paid(r["QuestBonusEffectGroupId"])
                if payout:
                    rules.append([kind.replace("_old", ""), r[who], r.get("LimitBreakCountLowerLimit", 0), payout])
        if rules:
            rules.sort(key=lambda r: (r[0], r[1], r[2]))
            name = json.dumps(rules)
            bonus_of[str(q)] = bonuses.setdefault(name, f"b{len(bonuses)}")
    return {"link": row["EventQuestLinkId"], "display": row["EventQuestDisplayItemGroupId"], "quests": quests,
            "link_row": {"shop": link.get("DestinationDomainId"), "possession_type": link.get("PossessionType"),
                         "possession_id": link.get("PossessionId")},
            "drops": drops, "bonus": bonus_of, "bonuses": {v: json.loads(k) for k, v in bonuses.items()},
            "stale_bonus_medals": sorted(stale)}


def _pays(view):
    """A view as what a player gets: exchange, shown medal, quests, drops and each quest's bonus payouts."""
    bonus = {q: view["bonuses"].get(b) for q, b in view["bonus"].items()}
    return (view["link_row"], view["display"], sorted(view["quests"]), view["drops"], bonus)


def chapter_runs(runs, final, view_at):
    """Each run's own data where it differs from the final game data (None where
    it is the same), or None when no run differs. runs: (start, end) in order;
    final: the final game data's view; view_at(run): the view in the master
    published during that run."""
    recorded = []
    for run in runs:
        view = view_at(run)
        recorded.append(view if view and _pays(view) != _pays(final) else None)
    return recorded if any(recorded) else None


def build(masters):
    schemas = ch.dm.load_schemas()
    history = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]["m_event_quest_chapter"]["rows"]
    final = read(*ch.load(masters[-1]), schemas)
    links = {l["EventQuestLinkId"]: l for l in final["m_event_quest_link"]}
    by_time = {ch.file_time(p): p for p in masters if ch.file_time(p) is not None}
    loaded, out = {}, {}
    def view_at(chapter):
        def at(run):
            t = pick(sorted(by_time), run)
            if t not in loaded:
                loaded[t] = read(*ch.load(by_time[t]), schemas)
            view = run_view(loaded[t], chapter)
            return dict(view, master=by_time[t].name[:14]) if view else None
        return at

    for row in final["m_event_quest_chapter"]:
        chapter = row["EventQuestChapterId"]
        last = run_view(final, chapter)
        if links.get(last["link"], {}).get("DestinationDomainType") != LINK_SHOP:
            continue
        # Its runs (calendar_history.json), or the one run the final game data dates.
        # Every recorded run, in order, as the calendar copies them (android_calendar.restore_runs).
        runs = history.get(str(chapter)) or ([(row["StartDatetime"], row["EndDatetime"])]
                                             if ch.LAUNCH <= row["StartDatetime"] < ch.FOREVER else [])
        recorded = chapter_runs(runs, last, view_at(chapter)) if runs else None
        if recorded:
            out[str(chapter)] = recorded
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--masters", type=Path, required=True, help="Folder of global .bin.e files named by date")
    args = parser.parse_args()
    masters = sorted(args.masters.glob("*.bin.e"))
    if not masters:
        raise SystemExit("No .bin.e files in " + str(args.masters))
    runs = build(masters)
    text = json.dumps({"source": f"{len(masters)} global master data files", "copy_step": 10_000_000, "chapters": runs},
                      sort_keys=True, separators=(",", ":")) + "\n"
    for path in (OUT, SERVER_OUT):
        path.write_text(text)
    earlier = sum(len(r) - 1 for r in runs.values())
    print(f"{OUT} and {SERVER_OUT}: {len(runs)} events, {earlier} earlier runs, {len(text) // 1024} KB")


if __name__ == "__main__":
    main()
