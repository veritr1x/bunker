#!/usr/bin/env python3
"""Writes the runs that the final game data lost (calendar_history.json).

The game data keeps one date range per row. When the live service reran an
event, or parked something it was done with (dates moved to 2030, 2040 or
2099), the new range replaced the old one. The Original calendar replays the
final game data, so it never shows the old run. This tool reads a series of
global master data files. One file per week is enough: a run lasts at least a
few days and stays in the data until it is replaced. For each row of the
calendar's rotating tables that lost a run, it records every range the row was
live in after global launch. android_calendar.py adds these runs back when it
builds a loop.

  calendar_history.py --masters DIR [--out PATH]

Needs pycryptodome, msgpack and lz4.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "android/app/src/main/python"
sys.path.insert(0, str(PYTHON))
# tools/ there is copied from the lunar-base submodule by prepare.py; a fresh
# checkout (CI's unit tests) has only the submodule.
if not (PYTHON / "tools/dump_masterdata.py").exists():
    sys.path.insert(0, str(ROOT / "upstream/lunar-base"))
from tools import dump_masterdata as dm  # noqa: E402

LAUNCH = 1627437600000      # 28 July 2021, 02:00 UTC
REAL = 1609459200000        # earlier dates are placeholders
FOREVER = 1717200000000     # 1 June 2024: later dates mean "never ends" or "never starts"


def rotating():
    """The calendar's rotating tables, read from android_calendar.py without importing it."""
    tree = ast.parse((PYTHON / "android_calendar.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ROTATING" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise SystemExit("ROTATING not found in android_calendar.py")


def load(path):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    import msgpack
    plain = unpad(AES.new(bytes.fromhex(dm.DEFAULT_KEY), AES.MODE_CBC, bytes.fromhex(dm.DEFAULT_IV)).decrypt(Path(path).read_bytes()), 16)
    try:
        msgpack.unpackb(plain, raw=False, strict_map_key=False)
        raise ValueError(f"{path}: no tables")
    except msgpack.ExtraData as exc:
        toc, blob = exc.unpacked, exc.extra
    return toc, blob


# Runs an official notice dates otherwise than the weekly masters recorded:
# (table, key, the run's start) -> its end. Seat of Shadow (Resurrected) ends
# Dec. 2 17:59 PST (notices 1442, 1445); the last master before it closed moved
# the end a day later without a notice.
CORRECTIONS = {
    ("m_event_quest_chapter", "507", 1700186400000): 1701568799000,
}


def apply_corrections(tables):
    for (table, key, start), end in CORRECTIONS.items():
        for run in tables.get(table, {}).get("rows", {}).get(key, []):
            if run[0] == start:
                run[-1] = end
    return tables


def key_columns(rows, dates):
    """The fewest leading non-date columns that tell the rows apart."""
    width = max((len(r) for r in rows), default=1)
    for n in range(1, width + 1):
        cols = [i for i in range(n) if i not in dates]
        if len({tuple(r[i] for i in cols) for r in rows}) == len(rows):
            return cols
    return [i for i in range(width) if i not in dates]


def live(dates):
    start, end = dates[0], dates[-1]
    return REAL <= start < FOREVER and end > LAUNCH


def file_time(path):
    """When a master data file was published, from its name (YYYYMMDDhhmmss, UTC)."""
    try:
        return int(datetime.strptime(Path(path).name[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError:
        return None


def was_live(run, live_at, times):
    """Whether a run really ran: some file published during it had the row live
    then, whatever end date it gave (live_at: the times of the files that had
    the row live). A run no file falls in cannot be checked and counts. One
    that every file published during it had missing or parked was a
    placeholder (item 29 dated 31 August to 12 September 2021, missing from the
    files of those weeks)."""
    start, end = run[0], run[-1]
    inside = [t for t in times if start <= t < end]
    return not inside or any(t in live_at for t in inside)


def build(masters):
    schemas = dm.load_schemas()
    tables = [t for t in rotating() if t in schemas]
    final_toc, final_blob = load(masters[-1])
    shape = {}
    for table in tables:
        dates = [i for i, kind, name in schemas[table][1] if kind == "long" and "Datetime" in name]
        # Start and end only: single dates (medal expiry) follow the summon rules instead.
        if table not in final_toc or len(dates) != 2:
            continue
        rows = dm.decompress_table(final_blob, *final_toc[table])
        shape[table] = (key_columns(rows, set(dates)), dates, {tuple(r[i] for i in key_columns(rows, set(dates))): tuple(r[i] for i in dates) for r in rows})
    seen = {table: {} for table in shape}
    # The times of the files that had each (table, key) live when published.
    live_at, times = {}, [t for t in map(file_time, masters) if t is not None]
    for path in masters:
        toc, blob = load(path)
        published = file_time(path)
        for table, (keys, dates, _) in shape.items():
            if table not in toc:
                continue
            for row in dm.decompress_table(blob, *toc[table]):
                if len(row) <= max(dates):
                    continue
                value = tuple(row[i] for i in dates)
                if live(value):
                    key = tuple(row[i] for i in keys)
                    seen[table].setdefault(key, set()).add(value)
                    if published is not None and value[0] <= published < value[-1]:
                        live_at.setdefault((table, key), set()).add(published)
        print(Path(path).name, file=sys.stderr)
    out = {}
    for table, (keys, dates, final) in shape.items():
        rows = {}
        for key, runs in seen[table].items():
            if key not in final:
                continue
            lost = {run for run in runs if run != final[key] and (not live(final[key]) or run[-1] < final[key][0])
                    and was_live(run, live_at.get((table, key), set()), times)}
            if lost:
                kept = sorted(lost | ({final[key]} if live(final[key]) else set()))
                rows["|".join(map(str, key))] = [list(run) for run in kept]
        if rows:
            out[table] = {"key": keys, "dates": dates, "rows": dict(sorted(rows.items()))}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--masters", type=Path, required=True, help="Folder of global .bin.e files named by date")
    parser.add_argument("--out", type=Path, default=PYTHON / "calendar_history.json")
    args = parser.parse_args()
    masters = sorted(args.masters.glob("*.bin.e"))
    if not masters:
        raise SystemExit("No .bin.e files in " + str(args.masters))
    tables = apply_corrections(build(masters))
    data = {"source": f"{len(masters)} global master data files, {masters[0].name[:8]} to {masters[-1].name[:8]}", "tables": tables}
    args.out.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"{args.out}: {sum(len(t['rows']) for t in tables.values())} rows in {len(tables)} tables")


if __name__ == "__main__":
    main()
