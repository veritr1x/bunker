"""Shared setup for android/tools/test_deckbuilder_*.py.

The game's master data is not in the repository. Real-data tests read the JSON
dump from DECKBUILDER_MASTER, or .build/deckbuilder/master (filled by
scripts/build_deckbuilder_fixtures.py --master), and are skipped without it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))

FIX = ROOT / "android/tools/fixtures/deckbuilder"
BUILD = ROOT / ".build/deckbuilder"
MASTER = Path(os.environ.get("DECKBUILDER_MASTER") or BUILD / "master")
MASTER_BIN = Path(os.environ.get("DECKBUILDER_MASTER_BIN") or BUILD / "master.bin.e")
NAMES = Path(os.environ.get("DECKBUILDER_NAMES") or BUILD / "names")
EDIT = BUILD / "bunker-edit"
HAVE_MASTER = (MASTER / "EntityMCostumeTable.json").exists()
needs_master = unittest.skipUnless(HAVE_MASTER, f"no master data in {MASTER} (run scripts/build_deckbuilder_fixtures.py --master)")

_tables = None


def tables():
    global _tables
    if _tables is None:
        from deckbuilder.tables import Tables
        _tables = Tables(MASTER, NAMES if NAMES.exists() else None)
    return _tables


def _edit_tool():
    """bunker-edit, built from the prepared server tree when missing."""
    if not EDIT.exists() and (ROOT / "server/cmd/bunker-edit").exists() and shutil.which("go"):
        subprocess.run(["go", "build", "-o", str(EDIT), "./cmd/bunker-edit"], cwd=ROOT / "server", check=True)
    return EDIT if EDIT.exists() else None


HAVE_STAGE = HAVE_MASTER and MASTER_BIN.exists()
needs_stage = unittest.skipUnless(HAVE_STAGE, "no master.bin.e or server tree for bunker-edit (run scripts/prepare.py and build_deckbuilder_fixtures.py --master-bin)")


def cli_invoke(stage_path: Path):
    """An invoke(payload) -> dict for deckbuilder.stage that runs bunker-edit
    on stage_path, the way the Android bridge's deckbuilder_stage target does."""
    tool = _edit_tool()
    if tool is None:
        raise unittest.SkipTest("bunker-edit could not be built")

    def invoke(payload):
        if payload.get("action") == "stage_new":
            out = subprocess.run([str(tool), "new-stage", str(stage_path)], capture_output=True, text=True)
        else:
            body = dict(payload, db_path=str(stage_path), user_id=1, master_data_path=str(MASTER_BIN))
            body.pop("target", None)
            out = subprocess.run([str(tool)], input=json.dumps(body), capture_output=True, text=True)
        result = json.loads(out.stdout.strip().splitlines()[-1]) if out.stdout.strip() else {"ok": False, "error": out.stderr}
        if not result.get("ok"):
            raise RuntimeError(f"{payload.get('action')}: {result.get('error')}")
        return result
    return invoke


def save_decks():
    """(fixture name, fixture dict, inputs for model.Deck.from_inputs) for every save deck."""
    out = []
    for f in sorted((FIX / "decks").glob("save_*.json")):
        d = json.loads(f.read_text())
        inputs = dict(d["inputs"])
        inputs["tables"] = json.loads((FIX / "saves" / f"{inputs.pop('save')}.json").read_text())
        out.append((f.name, d, inputs))
    return out
