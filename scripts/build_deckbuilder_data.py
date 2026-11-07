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


RANKINGS_OUT = ROOT / "android/app/src/main/python/deckbuilder/data/rankings.json"


def rankings(research: Path) -> dict:
    """Candidate pieces with their static scores (the research's *_ranked.csv):
    weapons [element, weapon type, main score, sub score], companions
    [element, score], debris [element or null, kind, score], memoir sets score,
    costumes score (the research's arena_score: damage, support, status and timing)."""
    import csv
    rd = lambda f: list(csv.DictReader(open(research / f)))
    num = lambda v: round(float(v or 0), 4)
    weapons = {r["weapon_id"]: [r["element"], int(r["weapon_type"]), num(r["main_score_with_status"]), num(r["sub_weapon_score"])]
               for r in rd("weapons_ranked.csv")}
    companions = {r["companion_id"]: [r["element"], num(r["score_with_status"])] for r in rd("companions_ranked.csv")}
    debris = {}
    for r in rd("debris_ranked.csv"):
        text = r["ability_text"]
        m = re.search(r"(fire|water|wind|light|dark)-affinity", text)
        kind = "gauge" if "gauge" in text else ("weapon_stats" if "stats of equipped" in text else "other")
        debris[r["thought_id"]] = [m.group(1) if m else None, kind, num(r["value_with_status"])]
    sets = {r["series_id"]: num(r["set3_with_status"]) for r in rd("memoir_sets_ranked.csv")}
    costumes = {r["costume_id"]: num(r["arena_score"]) for r in rd("costumes_ranked.csv")}
    return {"weapons": weapons, "companions": companions, "debris": debris, "memoir_sets": sets, "costumes": costumes}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--master", type=Path)
    p.add_argument("--texts", type=Path)
    p.add_argument("--rankings", type=Path, help="the research folder with weapons/companions/debris/memoir_sets_ranked.csv")
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    if a.master and a.texts:
        data = build(a.master, a.texts)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
        print(len(data), "abilities with text modifiers ->", a.out)
    if a.rankings:
        r = rankings(a.rankings)
        RANKINGS_OUT.write_text(json.dumps(r, sort_keys=True, separators=(",", ":")))
        print({k: len(v) for k, v in r.items()}, "->", RANKINGS_OUT)


if __name__ == "__main__":
    main()
