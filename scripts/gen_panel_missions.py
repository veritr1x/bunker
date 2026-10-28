#!/usr/bin/env python3
"""Generate the Anecdote panel sheets the server plays (panel_missions.json).

Anecdotes were web panel missions: each page a sheet of panels ("Clear a
dungeon 10 times: XL Weapon Enhancement x100") whose web page and data lived on
the old web server. scripts/anecdote_sheets.json holds the sheets as recorded:
nierrein.guide for Stars, The Moon, Emperor and Doll; gameplay videos for
Empress, The World, Judgment and Tower (Tower from its Japanese run). This
script turns each panel's wording into a mission rule the server's missions
engine counts (the same rule format as rules.json, from gen_mission_rules.py)
and each reward into an item.

Each sheet also gets its panels' words (shown where a panel opens and in bold
in the story; read from the same videos) and where it scatters the card's
pieces (anecdote_parts.json).

A few panels name what the sources don't record or a Japanese-only event
("Clear a conditional quest", "Record: Garden of Blessing"); they get the
nearest rule Bunker can count and "standin": true, and keep their own wording.

  python3.11 scripts/gen_panel_missions.py --master-json DIR --text-db archive.db
    [--output overlays/server/internal/missions/panel_missions.json]
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

import gen_mission_rules as G

ROOT = Path(__file__).resolve().parents[1]
SHEETS = Path(__file__).with_name("anecdote_sheets.json")
# Where each sheet scatters the card's 45 pieces (one layout for every sheet).
PARTS = Path(__file__).with_name("anecdote_parts.json")

# The Anecdotes' web panel missions (m_webview_mission ids).
MISSIONS = {"Stars": 1, "Tower": 2, "Empress": 3, "The Moon": 4, "The World": 5, "Emperor": 6, "Judgment": 7, "Doll": 8}

POSSESSION = {"material": 5, "consumable_item": 6, "companion": 3, "weapon": 2}
FREE_GEM = 12
DIFFICULTY = {"normal": 1, "hard": 2, "very hard": 3}
HARD_EXPLORES = [11, 12]


def count(text, default=1):
    m = re.search(r"(\d+) times?|(\d+) (?:bosses|items|stamina|arena|dark memor|story|chapter|times)", text)
    return int(next(g for g in m.groups() if g)) if m else default


def chapter_quest(text, names):
    """'Clear Quest 3 of Chapter 5 (Very Hard): Flowing Water' (the sheets number chapters their own way): by title."""
    m = re.fullmatch(r"clear quest (\d+) of chapter \d+(?: \(([a-z ]+)\))?: (.+)", G.norm(text))
    if not m:
        return None
    title = m[3]
    chapters = sorted({c for key, ids in names.main_chapters.items() if key.endswith(" " + title) or key == title for c in ids})
    if not chapters:
        return None
    return {"diff": [DIFFICULTY[m[2] or "normal"]], "order": int(m[1]), "main_chapters": chapters}


def rule(text, names):
    """(rule, target, standin) for a panel's wording."""
    s = G.norm(text)
    n = count(s)
    if s.startswith("clear a conditional quest") or s.startswith("clear a specified hard main quest"):
        return {"k": "quest", "q": {"main": True, "diff": [2]}}, 1, True  # a Hard main quest, as the Tower sheet's detail reads
    if s.startswith("clear a designed quest"):
        return {"k": "quest", "q": {}}, 10, True
    if "garden of blessing" in s:
        return {"k": "quest", "q": {"event_types": [1]}}, n, True  # a Japanese-only Record: any Record quest
    if q := chapter_quest(text, names):
        return {"k": "quest", "q": q}, 1, False
    if "exploration" in s:
        r = {"k": "explore_finish"}
        if "hard exploration" in s:
            r["ex"] = HARD_EXPLORES
        return r, n, False
    simple = [
        (r"defeat \d+ bosses", "defeat_boss"), (r"use \d+ stamina|using \d+ stamina", "stamina"),
        (r"item shop", "shop_buy"), (r"chapter summons", "gacha_draw"), (r"win \d+ arena", "pvp_win"),
        (r"play \d+ arena", "pvp_play"), (r"tap mama", "mama_tap"), (r"favorite character", "favorite_character"),
        (r"update (?:your )?profile", "user_message"), (r"awaken a character", "costume_awaken"),
    ]
    for pattern, kind in simple:
        if re.search(pattern, s):
            r = {"k": kind}
            if kind == "gacha_draw":
                r["g"] = "chapter"
            if kind == "stamina":
                n = int(re.search(r"(\d+) stamina", s)[1])
            return r, n, False
    q = G.quest_filter(re.sub(r" \d+ times?$", " 10 times", text), names, 0)
    if q is not None and s.startswith("clear"):
        return {"k": "quest", "q": q}, n, False
    raise ValueError(f"no rule for panel {text!r}")


def reward(text, items, names):
    m = re.fullmatch(r"(.+?)\s*x\s*(\d+)", text.strip())
    name, n = (m[1].strip(), int(m[2])) if m else (text.strip(), 1)
    if name == "Gems":
        return {"t": FREE_GEM, "id": 0, "n": n}
    if name in items:
        t, i = items[name]
        return {"t": t, "id": i, "n": n}
    if ids := names.weapon_ids(name):
        return {"t": POSSESSION["weapon"], "id": ids[0], "n": n}
    raise ValueError(f"no item for reward {text!r}")


def item_names(master, texts):
    """English item names -> (possession type, id): materials, consumables and companions."""
    out = {}
    # Item names are keyed by their art (asset category and variation): a
    # material's id is the same number, a consumable's is not.
    consumables = {f"{c['AssetCategoryId']}{c['AssetVariationId']:03d}": c["ConsumableItemId"] for c in G.load(master, "MConsumableItem")}
    for key, value in texts.items():
        kind, _, rest = key.partition(".name.")
        if kind == "material" and rest.isdigit():
            out.setdefault(value, (POSSESSION[kind], int(rest)))
        elif kind == "consumable_item" and rest in consumables:
            out.setdefault(value, (POSSESSION[kind], consumables[rest]))
    for c in G.load(master, "MCompanion"):
        if name := texts.get(f"companion.name.cm{c['ActorSkeletonId']:03d}{c['AssetVariationId']:03d}"):
            out.setdefault(name, (POSSESSION["companion"], c["CompanionId"]))
    return out


def build(master, texts):
    names = G.Names(master, texts)
    items = item_names(master, texts)
    sheets = json.loads(SHEETS.read_text())
    out = {}
    for name, mission in MISSIONS.items():
        anecdote = sheets[name]
        pages = []
        for sheet in anecdote["sheets"]:
            panels = []
            for p in sheet["panels"]:
                r, target, standin = rule(p["condition"], names)
                panel = {"text": p["condition"], "rule": r, "n": target, "rewards": [reward(x, items, names) for x in p["rewards"]]}
                if standin:
                    panel["standin"] = True
                panels.append(panel)
            pages.append({"page": sheet["sheet"], "panels": panels, "complete": [reward(x, items, names) for x in sheet.get("complete", [])],
                          "words": sheet.get("words", [])})
        out[str(mission)] = {"name": f"Anecdote: {name}", "source": anecdote.get("source", ""), "pages": pages}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--master-json", type=Path, required=True)
    p.add_argument("--text-db", type=Path, required=True)
    p.add_argument("--output", type=Path, default=ROOT / "overlays/server/internal/missions/panel_missions.json")
    args = p.parse_args()
    texts = dict(sqlite3.connect(args.text_db).execute("SELECT key, value FROM text"))
    missions = build(args.master_json, texts)
    args.output.write_text(json.dumps({"version": 1, "parts": json.loads(PARTS.read_text())["parts"], "missions": missions}, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    panels = sum(len(pg["panels"]) for m in missions.values() for pg in m["pages"])
    standins = sum(1 for m in missions.values() for pg in m["pages"] for p in pg["panels"] if p.get("standin"))
    print(f"{args.output}: {len(missions)} Anecdotes, {panels} panels ({standins} stand-ins)")


if __name__ == "__main__":
    main()
