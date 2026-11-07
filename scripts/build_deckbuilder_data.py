#!/usr/bin/env python3
"""Deck Builder's shipped data that is read from game text (numbers only, no
text is shipped):

  android/app/src/main/python/deckbuilder/data/ability_mods.json
      per AbilityDetailId, the damage modifiers its English description states
      and no data field holds: damage up below/above an HP ratio, chain
      (pursuit) bonuses, a full-HP bonus, and a permanent self agility %.

Usage: build_deckbuilder_data.py --master <JSON dump dir> --texts <texts_en.json>
(texts_en.json: the English text bundles as {text key: string}).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "android/app/src/main/python/deckbuilder/data/ability_mods.json"


def text_mods(text: str) -> dict:
    """The research prototype's reading (sim_units.text_mods), plus self agility."""
    m = dict(low_static=[], low_dyn=0.0, high_static=[], high_dyn=0.0, pursuit=[], full_hp=0.0, agi_pct=0.0)
    for x in re.finditer(r"Damage up by ([\d.]+)% when HP is below (\d+)%", text):
        m["low_static"].append((float(x.group(1)) / 100, int(x.group(2)) / 100))
    for x in re.finditer(r"up to ([\d.]+)% when your HP is 70% or lower", text):
        m["low_dyn"] += float(x.group(1)) / 100
    for x in re.finditer(r"for a max of ([\d.]+)%", text):
        m["low_dyn"] += float(x.group(1)) / 100
    for x in re.finditer(r"Damage up by ([\d.]+)% when HP is above (\d+)%", text):
        m["high_static"].append((float(x.group(1)) / 100, int(x.group(2)) / 100))
    for x in re.finditer(r"(?:by up to|max) ([\d.]+)%\)? when your HP is 70% or higher|70% or higher, dmg up the higher your HP \(max ([\d.]+)%\)", text):
        m["high_dyn"] += float(x.group(1) or x.group(2)) / 100
    for x in re.finditer(r"Damage up by ([\d.]+)% on chain attacks of (\d) or more", text):
        m["pursuit"].append((float(x.group(1)) / 100, int(x.group(2))))
    for x in re.finditer(r"Damage up by ([\d.]+)% when HP is at 100%", text):
        m["full_hp"] += float(x.group(1)) / 100
    for x in re.finditer(r"(?<!All allies' )[Aa]gility up by ([\d.]+)%(?! for)", text):
        m["agi_pct"] += float(x.group(1)) / 100
    return {k: v for k, v in m.items() if v}


def build(master: Path, texts: Path) -> dict:
    tx = json.loads(texts.read_text())
    out = {}
    for d in json.loads((master / "EntityMAbilityDetailTable.json").read_text()):
        text = tx.get("ability.description.long.%d" % d["DescriptionAbilityTextId"], "")
        mods = text_mods(text) if text else {}
        if mods:
            out[str(d["AbilityDetailId"])] = mods
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--master", type=Path, required=True)
    p.add_argument("--texts", type=Path, required=True)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    data = build(a.master, a.texts)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
    print(len(data), "abilities with text modifiers ->", a.out)


if __name__ == "__main__":
    main()
