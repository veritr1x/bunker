#!/usr/bin/env python3
"""Checks the rebuilt notices' facts against the official notices that survive.

For every official 'Event Quest "…" On Now' / 'Crossover Quest "…" On Now'
notice, the run it announced is rebuilt from the game data (event_notice_facts)
and each fact the rebuilt page would show is looked for on the official page:
the exchange, the medal, each exchange character's and weapon's stats, skills,
abilities and barrier skills, and each resonant weapon with its medal counts.

  check_event_notices.py --pack NOTICES.ZIP --masters DIR [--deckbuilder .build/deckbuilder]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from pathlib import Path

import calendar_history as ch
import event_notice_facts as F

TITLE = re.compile(r'^(?:Event|Crossover) Quest "([^"]+)" On Now$')


def plain(body):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))


def expectations(facts):
    """(label, text that must appear on the official page)."""
    out = []
    if facts.get("exchange"):
        out.append(("exchange", facts["exchange"]))
    if facts.get("medal"):
        out.append(("medal", facts["medal"]["name"]))
    for p in facts.get("exclusive") or []:
        c, w = p["costume"], p["weapon"]
        out.append(("costume", c["costume"]))
        out += [(f"costume {k}", f"{k} {v}") for k, v in c["status"].items()]
        if c.get("skill"):
            out += [("costume skill", c["skill"]["name"]), ("costume skill text", c["skill"]["description"])]
        out += [("costume ability", a["name"]) for a in c["abilities"]]
        if w:
            out.append(("weapon", w["name"]))
            out += [(f"weapon {k}", f"{k} {v}") for k, v in w["status"].items()]
            out += [("weapon skill", s["name"]) for s in w["skills"]]
            out += [("weapon cooldown", f"Cooldown: {s['cooldown']} secs") for s in w["skills"]]
            out += [("weapon ability", a["name"]) for a in w["abilities"]]
    for row in facts.get("weapon_bonus") or []:
        out.append(("resonant weapon", row[1]))
    return out


def bonus_rows(body):
    """Official resonant weapon rows: name -> [values] (rowspan cells carried down)."""
    rows, carried = {}, None
    for tr in re.findall(r"<tr>(.*?)</tr>", re.sub(r"\s+", " ", body)):
        name = re.search(r"<th>(?:<img[^>]*>)?\s*([^<]+?)\s*</th>", tr)
        values = [int(v) for v in re.findall(r">\s*\+(\d+)\s*<", tr)]
        if values:
            carried = values
        if name and carried and "weapon_icon" in tr:
            rows[html.unescape(name.group(1))] = values or carried
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--masters", type=Path, required=True)
    parser.add_argument("--deckbuilder", type=Path, default=ch.ROOT / ".build/deckbuilder")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.pack) as z:
        notices = json.loads(z.read("notices.json"))["notices"]
    masters = sorted(args.masters.glob("*.bin.e"))
    facts_of = F.Facts(masters, args.deckbuilder / "master", args.deckbuilder / "names", F.Images(Path("/nonexistent")),
                       [n["title"] for n in notices])
    history = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]["m_event_quest_chapter"]["rows"]
    final = facts_of.tables_at(facts_of.times[-1])
    by_name = {}
    for row in final["m_event_quest_chapter"]:
        by_name.setdefault(facts_of.chapter_name(row), []).append(row)
    report, total, found = [], 0, 0
    for n in notices:
        m = TITLE.match(n["title"])
        if not m or n["id"] >= 1_500_000_000:
            continue
        rows = by_name.get(m.group(1), [])
        run = None
        for row in rows:
            runs = [tuple(r) for r in history.get(str(row["EventQuestChapterId"]), [])] or [(row["StartDatetime"], row["EndDatetime"])]
            run = next(((row["EventQuestChapterId"], r) for r in runs if abs(r[0] - n["publish"]) <= 86_400_000), None) or run
            if run and abs(run[1][0] - n["publish"]) <= 86_400_000:
                break
        if not run or abs(run[1][0] - n["publish"]) > 86_400_000:
            report.append({"notice": n["id"], "title": n["title"], "run": None})
            continue
        facts = facts_of.event(*run)
        if facts is None:
            report.append({"notice": n["id"], "title": n["title"], "run": None})
            continue
        text = plain(n["body"])
        checks = expectations(facts)
        missing = [f"{label}: {want}" for label, want in checks if want and want not in text]
        official_rows = bonus_rows(n["body"])
        for row in facts.get("weapon_bonus") or []:
            name, values = row[1], row[2]
            if name in official_rows and official_rows[name] != values:
                missing.append(f"resonant weapon {name}: {values} vs official {official_rows[name]}")
        total += len(checks)
        found += len(checks) - len(missing)
        report.append({"notice": n["id"], "title": n["title"], "checks": len(checks), "missing": missing})
    for r in report:
        if r.get("run") is None and "checks" not in r:
            print(f"{r['notice']} {r['title']}: no run found")
        elif r["missing"]:
            print(f"{r['notice']} {r['title']}: {r['checks'] - len(r['missing'])}/{r['checks']}")
            for x in r["missing"]:
                print("    missing", x)
        else:
            print(f"{r['notice']} {r['title']}: {r['checks']}/{r['checks']}")
    print(f"facts found on the official pages: {found}/{total}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
