"""Shared setup for android/tools/test_deckbuilder_*.py.

The game's master data is not in the repository. Real-data tests read the JSON
dump from DECKBUILDER_MASTER, or .build/deckbuilder/master (filled by
scripts/build_deckbuilder_fixtures.py --master), and are skipped without it.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))

FIX = ROOT / "android/tools/fixtures/deckbuilder"
MASTER = Path(os.environ.get("DECKBUILDER_MASTER") or ROOT / ".build/deckbuilder/master")
HAVE_MASTER = (MASTER / "EntityMCostumeTable.json").exists()
needs_master = unittest.skipUnless(HAVE_MASTER, f"no master data in {MASTER} (run scripts/build_deckbuilder_fixtures.py --master)")

_tables = None


def tables():
    global _tables
    if _tables is None:
        from deckbuilder.tables import Tables
        _tables = Tables(MASTER)
    return _tables


def save_decks():
    """(fixture name, fixture dict, inputs for model.Deck.from_inputs) for every save deck."""
    out = []
    for f in sorted((FIX / "decks").glob("save_*.json")):
        d = json.loads(f.read_text())
        inputs = dict(d["inputs"])
        inputs["tables"] = json.loads((FIX / "saves" / f"{inputs.pop('save')}.json").read_text())
        out.append((f.name, d, inputs))
    return out
