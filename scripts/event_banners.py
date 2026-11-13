#!/usr/bin/env python3
"""Writes the banner each event run showed (event_banners.json).

The final game data keeps one banner per event chapter, its last run's; a
rerun usually got a new banner, drawn with "Resurrected" in it. The Original
calendar replays every run (each later run a copy of the chapter row,
android_calendar.py), so each run's copy gets the banner it had: the chapter's
BannerAssetId in the newest weekly master published before the run's middle.

Home-screen banners (m_mom_banner) are rows of their own; the calendar
restores a row's first run. A row the live game reused later shows the final
row's image in that run; each restored row gets the image it had then (its
destination stays: those ids point into tables that changed over the years).

Only banners whose images the game files have are recorded (--list, the
resource dump's list.bin): a run whose image is gone keeps the final one.

  event_banners.py --masters DIR --list LIST.BIN [--out PATH]

Needs pycryptodome, msgpack and lz4.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import calendar_history as ch

OUT = ch.PYTHON / "event_banners.json"
LANGUAGES = ("en", "ja", "ko")
EVENT_HOME = "event_mom_banner_"
DAY = 86_400_000


def pick(times, at):
    """The newest master time at or before at (else the oldest)."""
    before = [t for t in times if t <= at]
    return max(before) if before else min(times)


def middle(start, end):
    return start + (min(end, start + 30 * DAY) - start) // 2


def bundle_paths(list_bin: Path) -> set[str]:
    """Every asset bundle path list.bin names (ui)quest)en)banner)event_banner_509 …)."""
    data = list_bin.read_bytes()

    def uvarint(b, i):
        r = s = 0
        while True:
            x = b[i]
            i += 1
            r |= (x & 0x7F) << s
            s += 7
            if x < 0x80:
                return r, i

    def fields(b):
        i = 0
        while i < len(b):
            tag, i = uvarint(b, i)
            number, wire = tag >> 3, tag & 7
            if wire == 0:
                value, i = uvarint(b, i)
            elif wire == 2:
                length, i = uvarint(b, i)
                value, i = b[i:i + length], i + length
            elif wire == 1:
                value, i = None, i + 8
            elif wire == 5:
                value, i = None, i + 4
            else:
                raise ValueError(f"wire type {wire}")
            yield number, wire, value

    paths = set()
    for number, wire, value in fields(data):
        if number == 2 and wire == 2:
            for n, w, v in fields(value):
                if n == 3 and w == 2:
                    paths.add(bytes(v).decode())
                    break
    return paths


def has_banner(paths, banner_id):
    return all(f"ui)quest){lang})banner)event_banner_{banner_id}" in paths for lang in LANGUAGES)


def has_home(paths, name):
    return all(f"ui)quest){lang})mom_banner){name}" in paths for lang in LANGUAGES)


def chapter_banners(history, final, at_time, paths):
    """chapter -> the banner of each run in history order, None where the final one stands."""
    out = {}
    for chapter, runs in history.items():
        if int(chapter) not in final:
            continue
        banners = []
        for start, end in runs:
            banner = at_time(middle(start, end)).get(int(chapter), final[int(chapter)])
            banners.append(banner if banner != final[int(chapter)] and has_banner(paths, banner) else None)
        if any(b is not None for b in banners):
            out[chapter] = banners
    return out


def home_rows(history, final, at_time, paths, unrestored=()):
    """Home row -> its first run's image, where it differs from the final row's."""
    out = {}
    for row, runs in history.items():
        if int(row) in unrestored or int(row) not in final or not runs:
            continue
        start, end = min(tuple(r) for r in runs)  # the run the calendar restores (android_calendar.runs)
        then = at_time(middle(start, end)).get(int(row))
        if not then or then == final[int(row)] or not then.startswith(EVENT_HOME) or not has_home(paths, then):
            continue
        out[row] = then
    return out


def build(masters, paths):
    import sys
    sys.path.insert(0, str(ch.PYTHON))
    import android_calendar as cal
    schemas = ch.dm.load_schemas()
    history = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]
    by_time = {ch.file_time(p): p for p in masters if ch.file_time(p) is not None}
    times = sorted(by_time)
    loaded = {}

    def table(t, name, key, *fields):
        if t not in loaded:
            loaded[t] = ch.load(by_time[t])
        toc, blob = loaded[t]
        cols = {colname: i for i, _, colname in schemas[name][1]}
        rows = ch.dm.decompress_table(blob, *toc[name]) if name in toc else []
        pick_fields = lambda r: r[cols[fields[0]]] if len(fields) == 1 else tuple(r[cols[f]] for f in fields)
        return {r[cols[key]]: pick_fields(r) for r in rows}

    last = times[-1]
    chapters = chapter_banners(history["m_event_quest_chapter"]["rows"],
                               table(last, "m_event_quest_chapter", "EventQuestChapterId", "BannerAssetId"),
                               lambda at: table(pick(times, at), "m_event_quest_chapter", "EventQuestChapterId", "BannerAssetId"), paths)
    home = home_rows(history["m_mom_banner"]["rows"], table(last, "m_mom_banner", "MomBannerId", "BannerAssetName"),
                     lambda at: table(pick(times, at), "m_mom_banner", "MomBannerId", "BannerAssetName"), paths,
                     unrestored=cal.UNRESTORED_BANNERS)
    return chapters, home


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--masters", type=Path, required=True, help="Folder of global .bin.e files named by date")
    parser.add_argument("--list", type=Path, required=True, help="The resource dump's revisions/0/list.bin")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    masters = sorted(args.masters.glob("*.bin.e"))
    if not masters:
        raise SystemExit("No .bin.e files in " + str(args.masters))
    chapters, home = build(masters, bundle_paths(args.list))
    args.out.write_text(json.dumps({"source": f"{len(masters)} global master data files", "chapters": chapters, "home": home},
                                   sort_keys=True) + "\n")
    print(f"{args.out}: {len(chapters)} chapters, {sum(b is not None for v in chapters.values() for b in v)} runs, {len(home)} home rows")


if __name__ == "__main__":
    main()
