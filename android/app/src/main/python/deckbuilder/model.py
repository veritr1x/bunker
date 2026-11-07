"""Decks as Deck Builder holds them.

A deck is always backed by save rows: the player's real save (read-only), or
an in-memory copy of the tables the game reads, so the exact Force port
(deckbuilder.power) and the save writer see the same thing.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass


def connect_ro(path) -> sqlite3.Connection:
    """Open a save read-only. A WAL-mode file with no -shm beside it cannot be
    opened with mode=ro by every SQLite build; then fall back to immutable=1,
    which is exact when no -wal file exists."""
    path = str(path)
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.execute("select 1 from sqlite_master limit 1").fetchall()
        return con
    except sqlite3.OperationalError:
        if os.path.exists(path + "-wal") and os.path.getsize(path + "-wal") > 0:
            raise
        return sqlite3.connect(f"file:{path}?immutable=1", uri=True)


def rows_to_db(tables: dict) -> sqlite3.Connection:
    """An in-memory save from {table: {"sql": CREATE ..., "rows": [...]}}."""
    con = sqlite3.connect(":memory:")
    for name, t in tables.items():
        con.execute(t["sql"])
        rows = t["rows"]
        if rows:
            cols = list(rows[0])
            con.executemany(f"insert into {name} ({','.join(cols)}) values ({','.join('?' * len(cols))})",
                            [tuple(r[c] for c in cols) for r in rows])
    return con


class Save:
    """One user's rows: q() and one() bind user_id first."""

    def __init__(self, con: sqlite3.Connection, user_id: int):
        self.db = con
        self.db.row_factory = sqlite3.Row
        self.uid = user_id

    def q(self, sql, *a):
        return [dict(r) for r in self.db.execute(sql, (self.uid,) + a)]

    def one(self, sql, *a):
        r = self.q(sql, *a)
        return r[0] if r else None


@dataclass
class Deck:
    save: Save
    deck_type: int
    deck_number: int

    @classmethod
    def from_inputs(cls, inputs: dict) -> "Deck":
        con = rows_to_db(inputs["tables"])
        return cls(Save(con, inputs["user_id"]), inputs["deck_type"], inputs["deck_number"])

    @classmethod
    def from_save(cls, db_path, user_id, deck_type, deck_number, tables=None) -> "Deck":
        return cls(Save(connect_ro(db_path), user_id), deck_type, deck_number)
