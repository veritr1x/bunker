#!/usr/bin/env python3
"""Deck Builder test data (android/tools/test_deckbuilder_*.py).

Writes, under --out (default android/tools/fixtures/deckbuilder):
  decks/<name>.json   one per distinct deck state found in the saves: the
                      user's rows of every table the Force calculation reads,
                      and the power the game itself stored. Game ids, levels
                      and counts only; deck-local uuids are kept for joins.
  decks/video_*.json  Arena lineups read from videos, with the fight's win
                      time where the video shows it.
  turn_order.csv      battle openings read from videos.

Game data is not committed: --master copies the tables Deck Builder reads from
a JSON dump into .build/deckbuilder/master, --master-bin the .bin.e the server
code reads to .build/deckbuilder/master.bin.e, and --names the English names to
.build/deckbuilder/names; the tests look there (or at DECKBUILDER_MASTER,
DECKBUILDER_MASTER_BIN, DECKBUILDER_NAMES) and skip what they lack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "android/tools/fixtures/deckbuilder"
DEFAULT_MASTER_OUT = ROOT / ".build/deckbuilder/master"

# The save tables the Force calculation reads (deckbuilder/power.py).
USER_TABLES = (
    "user_character_board_abilities", "user_character_board_status_ups", "user_characters",
    "user_companions", "user_costume_active_skills", "user_costume_awaken_status_ups",
    "user_costume_lottery_effects", "user_costumes", "user_deck_characters", "user_deck_parts",
    "user_deck_sub_weapons", "user_decks", "user_important_items", "user_parts",
    "user_parts_status_subs", "user_thoughts", "user_weapon_abilities", "user_weapon_awakens",
    "user_weapon_skills", "user_weapons",
)
# Columns that are not game data and are dropped.
DROP_COLUMNS = {"name"}
# Fight end times read from the videos (data-meta/sim_calibration_report.txt).
VIDEO_WIN_SECONDS = {("Fo5jCU4TIxc", 1): 13.0, ("DFMQmpJxA-A", 6): 32.0}


def connect_ro(path: Path) -> sqlite3.Connection:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.execute("select 1 from sqlite_master limit 1").fetchall()
        return con
    except sqlite3.OperationalError:
        return sqlite3.connect(f"file:{path}?immutable=1", uri=True)


def mini_save(con: sqlite3.Connection, user_id: int) -> dict:
    """The user's rows of USER_TABLES, with each table's CREATE statement."""
    con.row_factory = sqlite3.Row
    out = {}
    for table in USER_TABLES:
        row = con.execute("select sql from sqlite_master where type='table' and name=?", (table,)).fetchone()
        if row is None:
            continue
        rows = [dict(r) for r in con.execute(f"select * from {table} where user_id=?", (user_id,))]
        for r in rows:
            for c in DROP_COLUMNS & r.keys():
                if table == "user_decks":
                    r[c] = ""
        out[table] = {"sql": row["sql"], "rows": rows}
    return out


def deck_states(save: Path):
    con = connect_ro(save)
    con.row_factory = sqlite3.Row
    decks = con.execute("select user_id, deck_type, user_deck_number, power, user_deck_character_uuid01 a,"
                        " user_deck_character_uuid02 b, user_deck_character_uuid03 c from user_decks where power > 0").fetchall()
    for d in decks:
        chars = []
        for u in (d["a"], d["b"], d["c"]):
            r = con.execute("select power from user_deck_characters where user_id=? and user_deck_character_uuid=?",
                            (d["user_id"], u)).fetchone() if u else None
            # 0 on a filled slot is not a value the client reported (e.g. the
            # Arena deck Bunker's server copies from a quest deck): None.
            chars.append((int(r["power"]) or None) if r else 0)
        tables = mini_save(con, d["user_id"])
        yield {"user_id": d["user_id"], "deck_type": d["deck_type"], "deck_number": d["user_deck_number"],
               "stored_deck": int(d["power"]), "stored_characters": chars, "inputs": {"tables": tables}}


def write_decks(saves: list[Path], out: Path, stale: set[str]) -> list[str]:
    """decks/save_*.json name the deck and its stored power; the player's rows
    go once into saves/<digest>.json, which the deck file names."""
    (out / "decks").mkdir(parents=True, exist_ok=True)
    (out / "saves").mkdir(parents=True, exist_ok=True)
    seen, written = set(), []
    for save in saves:
        for d in deck_states(save):
            tables = d["inputs"].pop("tables")
            body = json.dumps(tables, sort_keys=True, separators=(",", ":"), default=str)
            snap = hashlib.sha256(body.encode()).hexdigest()[:12]
            name = f"save_{d['deck_type']}_{d['deck_number']}_{d['stored_deck']}"
            key = (snap, d["deck_type"], d["deck_number"])
            if key in seen or name in stale:
                continue
            seen.add(key)
            (out / "saves" / f"{snap}.json").write_text(body)
            d["inputs"].update(save=snap, user_id=d["user_id"], deck_type=d["deck_type"], deck_number=d["deck_number"])
            path = out / "decks" / f"{name}_{snap}.json"
            path.write_text(json.dumps(d, sort_keys=True, indent=1, default=str))
            written.append(path.name)
    return written


SLOT = re.compile(r"^\s+([LMR]): .*\((\d+)\)")
HEAD = re.compile(r"^\s*(\d+)\. \[([\w-]+) @ [^\]]*\] (.*)$")


def write_video_decks(arena_decks: Path, out: Path) -> list[str]:
    written, cur = [], None
    def flush():
        if cur and len(cur["costumes"]) == 3 and "ENEMY" not in cur["title"]:
            name = f"video_{cur['video']}_{cur['n']}.json"
            body = {"video": cur["video"], "n": cur["n"], "title": cur["title"],
                    "costumes": [cur["costumes"][s] for s in "LMR"],
                    "video_win_seconds": VIDEO_WIN_SECONDS.get((cur["video"], cur["n"]))}
            (out / "decks" / name).write_text(json.dumps(body, indent=1))
            written.append(name)
    for line in arena_decks.read_text().splitlines():
        h = HEAD.match(line)
        if h:
            flush()
            cur = {"n": int(h[1]), "video": h[2], "title": h[3], "costumes": {}}
            continue
        s = SLOT.match(line)
        if s and cur is not None:
            cur["costumes"][s[1]] = int(s[2])
    flush()
    return written


def copy_master(src: Path, dst: Path) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(src.glob("EntityM*Table.json")):   # all of it: the simulator reads widely
        shutil.copy2(f, dst / f.name)
        n += 1
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--save", type=Path, action="append", default=[], help="a game.db (read-only); repeat")
    p.add_argument("--stale", action="append", default=[],
                   help="save_<type>_<number>_<stored> names whose stored power predates a gear change")
    p.add_argument("--videos", type=Path, help="arena_decks.txt")
    p.add_argument("--turn-order", type=Path, help="turn_order.csv")
    p.add_argument("--master", type=Path, help="JSON master dump (EntityM*Table.json)")
    p.add_argument("--master-out", type=Path, default=DEFAULT_MASTER_OUT)
    p.add_argument("--master-bin", type=Path, help="the game's 20240404193219.bin.e, for the staging save (bunker-edit)")
    p.add_argument("--names", type=Path, help="extract_names output folder (costumes.json, weapons.json, ...)")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = p.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    if a.save:
        for n in write_decks(a.save, a.out, set(a.stale)):
            print("deck", n)
    if a.videos:
        for n in write_video_decks(a.videos, a.out):
            print("video", n)
    if a.turn_order:
        shutil.copy2(a.turn_order, a.out / "turn_order.csv")
        print("turn_order.csv")
    if a.master:
        print("master tables", copy_master(a.master, a.master_out), "->", a.master_out)
    if a.master_bin:
        a.master_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(a.master_bin, a.master_out.parent / "master.bin.e")
        print("master.bin.e ->", a.master_out.parent)
    if a.names:
        shutil.copytree(a.names, a.master_out.parent / "names", dirs_exist_ok=True)
        print("names ->", a.master_out.parent / "names")


if __name__ == "__main__":
    main()
