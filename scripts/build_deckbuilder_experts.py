#!/usr/bin/env python3
"""Deck Builder's expert data: android/app/src/main/python/deckbuilder/data/experts.json.

Reduces the community's Arena knowledge to ids and weights (no text is kept):
  --tierlists  nierrein.guide PvP tier lists (resolved to costume ids)
  --loadouts   nierrein.guide community Arena loadouts
  --videos     arena_decks.txt: decks read from Arena videos (L / M / R)
  --names      extract_names output (weapons, companions, thoughts, parts_group_notes)
  --master     the JSON master dump (PartsGroup for memoir sets)

Credit: THIRD-PARTY-NOTICES.md ("Deck Builder expert data").
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "android/app/src/main/python/deckbuilder/data/experts.json"
TIER_WEIGHT = {"X": 1.0, "SSS": 0.9, "SS": 0.8, "S": 0.7, "A": 0.6, "B": 0.5, "C": 0.4}
SUPPORT_TIERS = {"Offensive Support": "support_offense", "Defensive Support": "support_defense",
                 "Agility Support": "support_agility", "Haste Support / Swiftness": "support_haste"}
CATEGORY_ROLE = {"Turret": "turret", "Agility Snipers": "agility", "Support": "support"}
SUPPORT_WEIGHT = 0.85
VIDEO_WEIGHT = 0.8
# The end-of-service top defense, as the tier list's notes place it (Rion right, Sarafa middle, Marie left).
CURATED = [{"name": "Top defense", "costumes": [31032, 35036, 33029], "source": "nierrein:tierlist-note", "role": "defense"}]


def tierlists(path: Path) -> dict:
    out, category, tier = {}, None, None
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            category = CATEGORY_ROLE.get(line[3:].split(" (")[0].strip())
            continue
        if line.startswith("### Tier "):
            tier = line[len("### Tier "):].strip()
            continue
        m = re.match(r"^- (\d+) \|", line)
        if not (m and category and tier):
            continue
        cid = int(m[1])
        if tier in SUPPORT_TIERS:
            role, weight, label = SUPPORT_TIERS[tier], SUPPORT_WEIGHT, tier
        else:
            role, weight, label = category, TIER_WEIGHT.get(tier, 0.4), tier
        rec = out.setdefault(str(cid), {"weight": 0.0, "roles": [], "tiers": []})
        rec["weight"] = max(rec["weight"], weight)
        if role not in rec["roles"]:
            rec["roles"].append(role)
        rec["tiers"].append(f"{category}:{label}")
    return out


def _by_name(names_dir: Path, kind: str) -> dict:
    p = names_dir / f"{kind}.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    recs = data.get("records", data) if isinstance(data, dict) else data
    out = {}
    for r in recs:
        if isinstance(r, dict) and r.get("name") and str(r.get("name_found", True)) != "False":
            out.setdefault(r["name"].lower(), []).append(r)
    return out


ELEMENT_ATTR = {"DARK": 1, "FIRE": 2, "LIGHT": 3, "WATER": 5, "WIND": 6}


def loadouts(path: Path, names_dir: Path, master: Path) -> list:
    weapons, companions, thoughts = _by_name(names_dir, "weapons"), _by_name(names_dir, "companions"), _by_name(names_dir, "thoughts")
    notes = _by_name(names_dir, "parts_group_notes")
    groups = {g["PartsGroupId"]: g["PartsSeriesId"] for g in json.loads((master / "EntityMPartsGroupTable.json").read_text())}
    series_by_name = {}
    for name, recs in notes.items():
        for r in recs:
            sid = groups.get(int(r["id"]))
            if sid:
                series_by_name[name] = sid

    def weapon_id(text):
        m = re.match(r"(.+?) \[(\w+)\]$", text or "")
        if not m:
            return None
        cands = [r for r in weapons.get(m[1].lower(), []) if int(r.get("AttributeType") or 0) == ELEMENT_ATTR.get(m[2])]
        return max((int(r["id"]) for r in cands), default=None)

    def first_id(table, text):
        recs = table.get((text or "").lower(), [])
        return max((int(r["id"]) for r in recs), default=None)

    out, cur, char = [], None, None
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            if cur and len(cur["costumes"]) == 3:
                out.append(cur)
            m = re.match(r"## (.+?) \((\d{4}-\d\d-\d\d), votes (\d+)\) (\S+)", line)
            cur = {"name": m[1], "costumes": [], "loadout": {}, "source": "nierrein:" + m[4], "votes": int(m[3])} if m else None
            continue
        if cur is None:
            continue
        m = re.match(r"^- (\d+) ", line)
        if m:
            char = int(m[1])
            cur["costumes"].append(char)
            cur["loadout"][str(char)] = {}
            continue
        lo = cur["loadout"].get(str(char)) if char else None
        if lo is None:
            continue
        m = re.match(r"^\s+- weapons: \[(.*)\]", line)
        if m:
            ids = [weapon_id(x.strip().strip("'\"")) if x.strip() != "None" else None for x in m[1].split(", ")]
            lo["weapons"] = ids
            continue
        m = re.match(r"^\s+- memoirs: \[(.*)\]", line)
        if m:
            sets = [series_by_name.get(re.sub(r" \(.*\)$", "", x.strip().strip("'\"")).lower()) for x in m[1].split("', '")]
            sets = [s for s in sets if s]
            if sets:
                lo["memoir_set"] = max(set(sets), key=sets.count)
            continue
        m = re.match(r"^\s+- companion: (.+?) \| debris: (.+)$", line)
        if m:
            lo["companion"] = first_id(companions, m[1].strip())
            lo["debris"] = first_id(thoughts, m[2].strip())
    if cur and len(cur["costumes"]) == 3:
        out.append(cur)
    return out


SLOT = re.compile(r"^\s+([LMR]): .*\((\d+)\)")
HEAD = re.compile(r"^\s*(\d+)\. \[([\w-]+) @ [^\]]*\] (.*)$")


def video_decks(path: Path) -> list:
    out, cur = [], None
    def flush():
        if cur and len(cur["slots"]) == 3 and "ENEMY" not in cur["title"]:
            role = "defense" if "defense" in cur["title"].lower() else "attack"
            out.append({"name": f"Video {cur['video']} #{cur['n']}", "costumes": [cur["slots"][s] for s in "LMR"],
                        "source": f"video:{cur['video']}", "role": role})
    for line in path.read_text().splitlines():
        h = HEAD.match(line)
        if h:
            flush()
            cur = {"n": int(h[1]), "video": h[2], "title": h[3], "slots": {}}
            continue
        s = SLOT.match(line)
        if s and cur:
            cur["slots"][s[1]] = int(s[2])
    flush()
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tierlists", type=Path, required=True)
    p.add_argument("--loadouts", type=Path, required=True)
    p.add_argument("--videos", type=Path, required=True)
    p.add_argument("--names", type=Path, required=True)
    p.add_argument("--master", type=Path, required=True)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    costumes = tierlists(a.tierlists)
    vids = video_decks(a.videos)
    for v in vids:
        for c in v["costumes"]:
            rec = costumes.setdefault(str(c), {"weight": 0.0, "roles": [], "tiers": []})
            rec["weight"] = max(rec["weight"], VIDEO_WEIGHT)
            if "video" not in rec["roles"]:
                rec["roles"].append("video")
    lineups = CURATED + vids + loadouts(a.loadouts, a.names, a.master)
    for c in costumes.values():
        c.pop("tiers", None)
    data = {"version": 1, "costumes": dict(sorted(costumes.items(), key=lambda kv: int(kv[0]))), "lineups": lineups}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, indent=1))
    print(len(costumes), "costumes,", len(lineups), "lineups ->", a.out)


if __name__ == "__main__":
    main()
