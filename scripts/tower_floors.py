#!/usr/bin/env python3
"""Writes how many floors each Abyss Tower had in each of its runs (tower_floors.json).

A tower reran with 10 more floors each time (20, 30, 40, 50) before it stayed
for good (notice 1037). The final game data has every floor, so the Original
calendar needs the count per run: the floors in the tower's sequence in the
newest weekly master published before the run's middle. The runs are the
tower's in calendar_history.json, its base run first.

  tower_floors.py --masters DIR [--out PATH]

Needs pycryptodome, msgpack and lz4.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import calendar_history as ch

OUT = ch.PYTHON / "tower_floors.json"
TOWER_TYPE = 10


def floors_at(toc, blob, schemas, tower):
    """The number of floors a tower's sequence has in one master (0 if absent)."""
    dm = ch.dm

    def table(name):
        if name not in toc:
            return []
        cols = {colname: i for i, _, colname in schemas[name][1]}
        return cols, dm.decompress_table(blob, *toc[name])

    cols, chapters = table("m_event_quest_chapter")
    group = next((r[cols["EventQuestSequenceGroupId"]] for r in chapters if r[cols["EventQuestChapterId"]] == tower), None)
    gcols, groups = table("m_event_quest_sequence_group")
    seq = next((r[gcols["EventQuestSequenceId"]] for r in groups if r[gcols["EventQuestSequenceGroupId"]] == group), None)
    scols, sequences = table("m_event_quest_sequence")
    return sum(1 for r in sequences if r[scols["EventQuestSequenceId"]] == seq)


def pick(times, at):
    """The newest master time at or before at (else the oldest)."""
    before = [t for t in times if t <= at]
    return max(before) if before else min(times)


def build(masters):
    schemas = ch.dm.load_schemas()
    history = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]["m_event_quest_chapter"]["rows"]
    final_toc, final_blob = ch.load(masters[-1])
    cols = {name: i for i, _, name in schemas["m_event_quest_chapter"][1]}
    towers = sorted(r[cols["EventQuestChapterId"]] for r in ch.dm.decompress_table(final_blob, *final_toc["m_event_quest_chapter"])
                    if r[cols["EventQuestType"]] == TOWER_TYPE)
    by_time = {ch.file_time(p): p for p in masters if ch.file_time(p) is not None}
    loaded = {}
    out = {}
    for tower in towers:
        counts = []
        for start, end in history.get(str(tower), []):
            middle = start + (min(end, start + 30 * 86_400_000) - start) // 2
            t = pick(sorted(by_time), middle)
            if t not in loaded:
                loaded[t] = ch.load(by_time[t])
            counts.append(floors_at(*loaded[t], schemas, tower))
        if counts:
            out[str(tower)] = counts
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--masters", type=Path, required=True, help="Folder of global .bin.e files named by date")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    masters = sorted(args.masters.glob("*.bin.e"))
    if not masters:
        raise SystemExit("No .bin.e files in " + str(args.masters))
    floors = build(masters)
    args.out.write_text(json.dumps({"source": f"{len(masters)} global master data files", "floors": floors}, sort_keys=True) + "\n")
    print(f"{args.out}: {floors}")


if __name__ == "__main__":
    main()
