#!/usr/bin/env python3
"""Generate the server's mission rules from the master data and the game's text.

The master data says what each mission counts (m_mission.MissionClearConditionType)
but not its filter: the "option groups" that name a quest, chapter, costume or
weapon lived only on the original server. Their English names do say it ("Clear
Record: Sunset Port 10 times", "Reach level 30 with Blackbird Dagger"), so this
script reads each name and writes a rule the server can evaluate:

  {"id": mission, "k": kind, "q": quest filter, "c": costumes, "w": weapons, "ch": characters}

A mission whose name doesn't match a known pattern gets no rule and stays at 0.

Usage:
  python3.11 scripts/gen_mission_rules.py --master-json DIR --text-db archive.db
    [--output overlays/server/internal/missions/rules.json]

DIR holds the master data as JSON (lunar-base tools/dump_masterdata.py).
archive.db is the Bunker Archive index, which holds the game's English text.
"""
import argparse
import collections
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# MissionClearConditionType values from the game client.
SIMPLE = {
    5: "weapon_enhance", 9: "costume_enhance", 12: "companion_enhance", 13: "parts_enhance",
    21: "shop_buy", 22: "user_level", 23: "login", 25: "mission_clear", 27: "favorite_character", 28: "max_deck_power",
    30: "all_daily", 31: "mama_tap", 32: "cage_walk", 35: "defeat_boss", 36: "battle_retire",
    37: "battle_annihilated", 39: "library", 41: "costume_skill_level", 42: "costume_ability_level",
    44: "weapon_skill_level", 45: "weapon_ability_level", 51: "big_hunt_play", 52: "big_hunt_knockdown",
    55: "defeat_wizard", 60: "report", 65: "stamina", 67: "login_from_unlock", 68: "all_daily",
    70: "weapon_awaken", 72: "lottery_slot", 73: "lottery_draw",
}
# Kinds that may name one weapon or one costume/character in the mission name.
WEAPON_KINDS = {6: "weapon_skill", 7: "weapon_evolve", 8: "weapon_limit_break", 43: "weapon_level"}
COSTUME_KINDS = {10: "costume_skill", 11: "costume_limit_break", 40: "costume_level", 66: "costume_awaken"}
DIFFICULTY = {"normal": 1, "hard": 2, "very hard": 3, "ex hard": 4}


def load(master: Path, name: str) -> list[dict]:
    return json.loads((master / f"Entity{name}Table.json").read_text())


def norm(text: str) -> str:
    text = text.replace("’", "'").replace("Ⅵ", "VI").replace("Ⅴ", "V").replace("Ⅳ", "IV").replace("Ⅲ", "III")
    return re.sub(r"\s+", " ", text).strip().lower()


class Names:
    """English names of quests' chapters, costumes, weapons and characters, to look up ids by name."""

    def __init__(self, master: Path, texts: dict[str, str]):
        self.texts = texts
        self.event_chapters = collections.defaultdict(set)   # name -> event chapter ids
        self.main_chapters = collections.defaultdict(set)    # name -> main chapter ids
        self.main_by_number = {}                              # season-1 chapter number -> main chapter id
        self.costumes = collections.defaultdict(set)          # "rion (yuletide exile)", "yuletide exile" -> ids
        self.weapons = collections.defaultdict(set)
        self.characters = collections.defaultdict(set)
        self.character_quest_chapters = collections.defaultdict(list)  # character id -> event chapters

        for c in load(master, "MEventQuestChapter"):
            for key in (f"quest.event.chapter_title.{c['NameEventQuestTextId']}",
                        f"quest.event.dungeon.chapter_title.{c['NameEventQuestTextId']}"):
                if key in texts:
                    title = norm(texts[key])
                    self.event_chapters[title].add(c["EventQuestChapterId"])
                    for prefix in ("record: ", "variation: ", "dungeon: "):
                        if title.startswith(prefix):
                            self.event_chapters[title[len(prefix):]].add(c["EventQuestChapterId"])
        routes = {r["MainQuestRouteId"]: r for r in load(master, "MMainQuestRoute")}
        for c in load(master, "MMainQuestChapter"):
            route = routes[c["MainQuestRouteId"]]
            where = f"{route['MainQuestSeasonId']}.{route['SortOrder']}.{c['SortOrder']}"
            for key in (f"quest.main.chapter_number.{where}", f"quest.main.chapter_title.{where}"):
                if key in texts:
                    name = norm(texts[key])
                    self.main_chapters[name].add(c["MainQuestChapterId"])
                    # "Ch. 4 Flowing Water" is also written "Chapter 4: Flowing Water".
                    if m := re.fullmatch(r"ch\. (\d+) (.+)", name):
                        self.main_chapters[f"chapter {m[1]}: {m[2]}"].add(c["MainQuestChapterId"])
                        self.main_chapters[f"ch. {m[1]}: {m[2]}"].add(c["MainQuestChapterId"])
                        if route["MainQuestSeasonId"] == 1:
                            self.main_by_number[int(m[1])] = c["MainQuestChapterId"]

        names = {}
        for ch in load(master, "MCharacter"):
            for key in (f"character.name.{ch['NameCharacterTextId']}", f"character.name.{ch['NameCharacterTextId']}.1"):
                if key in texts:
                    names[ch["CharacterId"]] = texts[key]
                    self.characters[norm(texts[key])].add(ch["CharacterId"])
        for c in load(master, "MCostume"):
            asset = f"ch{c['ActorSkeletonId']:03d}{c['AssetVariationId']:03d}"
            if name := texts.get(f"costume.name.{asset}"):
                self.costumes[norm(name)].add(c["CostumeId"])
                if who := names.get(c["CharacterId"]):
                    self.costumes[norm(f"{who} ({name})")].add(c["CostumeId"])
        for w in load(master, "MWeapon"):
            asset = f"wp{w['WeaponType']:03d}{w['AssetVariationId']:03d}"
            for stage in ("", ".1", ".2", ".3"):
                if name := texts.get(f"weapon.name.{asset}{stage}"):
                    self.weapons[norm(name)].add(w["WeaponId"])

    def chapters(self, table: dict, title: str) -> set[int]:
        """Chapters by title, also when the title abbreviates a word ("Variation: T. Senior Officer")."""
        for t in (title, title.removeprefix("the ")):
            if t in table:
                return table[t]
        words = title.split()
        for name, ids in table.items():
            parts = name.split()
            if len(parts) == len(words) and all(
                    a == b or (a.endswith(".") and len(a) == 2 and b.startswith(a[0])) for a, b in zip(parts, words)):
                return ids
        return set()

    def costume_ids(self, name: str) -> list[int]:
        name = norm(name)
        if name in self.costumes:
            return sorted(self.costumes[name])
        return []

    def character_ids(self, name: str) -> list[int]:
        return sorted(self.characters.get(norm(name), ()))


def quest_filter(name: str, n: Names, opt: int) -> dict | None:
    """The quests a quest-clear mission counts, from its name; None when unknown."""
    s = norm(name)
    s = re.sub(r" \(skip tickets cannot be used\.?\)\.?$", "", s)
    q: dict = {}
    # Day-of-week, guerrilla and Dark Memory quests count difficulty from Easy.
    if m := re.fullmatch(r"clear (?:(monday|tuesday|wednesday|thursday|friday|saturday|sunday) quest|(.+) guerrilla|1 dark memory quest) ?(?:on )?\(?(easy|normal|hard)\)?", s):
        q["diff"] = [{"easy": 1, "normal": 2, "hard": 3}[m[3]]]
        q["event_types"] = [4] if m[1] else [5] if m[2] else [7]
        return q
    if m := re.fullmatch(r"clear dungeon (\d+)f", s):
        q.update(event_types=[3], order=int(m[1]))
        return q
    # Difficulty: "on Hard", "(Normal)", "Hard", "on Hard or Very Hard".
    if "hard or very hard" in s:
        q["diff"] = [2, 3]
        s = s.replace(" on hard or very hard", "")
    else:
        for word, value in sorted(DIFFICULTY.items(), key=lambda x: -len(x[0])):
            if re.search(rf"(\bon {word}\b|\({word}\)| {word}$)", s):
                q["diff"] = [value]
                s = re.sub(rf"( on {word}\b| ?\({word}\)| {word}$)", "", s)
                break
    s = re.sub(r" \d+ times?(\(s\))?$| \d+ time\(s\)$| once$", "", s)

    def chapter_quest(title: str, order: str | None) -> bool:
        title = title.strip()
        if order:
            q["order"] = int(order)
        if ids := n.chapters(n.event_chapters, title):
            q["event_chapters"] = sorted(ids)
            return True
        if ids := n.chapters(n.main_chapters, title):
            q["main_chapters"] = sorted(ids)
            return True
        return False

    rules = [
        (r"clear (a|\d+) main quests?( on hard)?", lambda m: q.setdefault("main", True)),
        (r"clear main quests?", lambda m: q.setdefault("main", True)),
        (r"clear a main quest or story quest", lambda m: q.update(main=True, event_types=[6])),
        (r"clear (a|\d+) (subquests?|event quests?)", lambda m: q.setdefault("event", True)),
        (r"clear (a|\d+) normal event quest|clear (a|\d+) hard event quest|clear (a|\d+) very hard event quest",
         lambda m: q.setdefault("event", True)),
        (r"clear (a )?daily quests?", lambda m: q.setdefault("event_types", [4])),
        (r"clear (\d+ )?daily challenges?", lambda m: q.setdefault("event_types", [4])),
        (r"clear guerrilla quests?", lambda m: q.setdefault("event_types", [5])),
        (r"clear (a|\d+) dungeons?", lambda m: q.setdefault("event_types", [3])),
        (r"clear (a|\d+) dark memory quests?", lambda m: q.setdefault("event_types", [7])),
        (r"clear (a|\d+) abyss tower event quests?", lambda m: q.setdefault("event_types", [10])),
        (r"clear (a|\d+) fate board event quests?", lambda m: q.setdefault("event_types", [12])),
        (r"clear (\d+ )?recollections of dusk quests?", lambda m: q.setdefault("event_types", [11])),
        (r"clear character quests?", lambda m: q.setdefault("event_types", [6])),
        (r"clear once per day quests?", lambda m: q.setdefault("daily_limited", True)),
        (r"clear (a|\d+) quests?|clear quests", lambda m: True),
    ]
    # Main quest chapter: "Clear Main Quest: Chapter 4", "Clear Main Quest Ch 4", "Clear Quest 10 of Main Quest, Chapter 6".
    if m := re.fullmatch(r"clear (?:quest (\d+) of )?main quest(?:,|:)? (?:chapter|ch\.?) (\d+)", s):
        if m[1]:
            q["order"] = int(m[1])
        if (cid := n.main_by_number.get(int(m[2]))) is None:
            return None
        q["main_chapters"] = [cid]
        return q
    # "Complete character quest 4 for Priyet", "Clear 1 Recollections of Dusk quest for Fio".
    if m := re.fullmatch(r"(?:complete|clear) character quest (\d+) for (.+)", s):
        ids = n.character_ids(m[2])
        if not ids:
            return None
        q.update(event_types=[6], characters=ids, order=int(m[1]))
        return q
    if m := re.fullmatch(r"clear (?:\d+ )?recollections of dusk quests? for (.+)", s):
        ids = n.character_ids(m[1])
        if not ids:
            return None
        q.update(event_types=[11], characters=ids)
        return q
    # "Clear Quest 10 of Record: Sunset Port", "Clear Quest 10Record: Covetous Grove", "Clear Quest 1 of Chapter 4: Flowing Water".
    if m := re.fullmatch(r"clear quest (\d+) ?(?:of )?(.+)", s):
        return q if chapter_quest(m[2], m[1]) else None
    # "Clear The Sun II: Noontide Quest 1".
    if m := re.fullmatch(r"clear (.+) quest (\d+)", s):
        if chapter_quest(m[1], m[2]):
            return q
    # "Clear 1 Dark Memory quest", generic kinds.
    for pattern, apply in rules:
        if re.fullmatch(pattern, s):
            apply(None)
            return q
    # "Clear Record: Sunset Port", "Clear the Garden of Benediction quest", "Clear Variation: X quests".
    if m := re.fullmatch(r"clear (?:the )?(.+?)(?: quests?)?", s):
        if chapter_quest(m[1], None):
            return q
    return None


def loadout(name: str, n: Names) -> tuple[str, list[int]] | None:
    """Missions that need a costume (or a character) in the deck: the rest of the name and the costume ids."""
    s = norm(name)
    m = re.fullmatch(r"(.+?) with (?:only )?(.+?) in your loadout(.*)", s)
    if not m:
        return None
    who = m[2]
    ids = n.costume_ids(who)
    if not ids and (chars := n.character_ids(who)):
        ids = [-c for c in chars]  # negative: any costume of this character
    if not ids:
        return None
    rest = m[1] + m[3]
    # "Clear quests 10 times with X" -> "Clear quests 10 times"; "Clear 10 quests with X" -> "Clear 10 quests".
    return rest, ids


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--master-json", type=Path, required=True)
    p.add_argument("--text-db", type=Path, required=True)
    p.add_argument("--output", type=Path, default=ROOT / "overlays/server/internal/missions/rules.json")
    args = p.parse_args()

    texts = dict(sqlite3.connect(args.text_db).execute("SELECT key, value FROM text"))
    names = Names(args.master_json, texts)
    rules, unknown = [], collections.Counter()
    for mission in load(args.master_json, "MMission"):
        kind_type = mission["MissionClearConditionType"]
        name = texts.get(f"mission.name.{mission['NameMissionTextId']}", "")
        rule: dict = {"id": mission["MissionId"]}
        if kind_type in (1, 2, 62):
            text = name
            if found := loadout(name, names):
                text, rule["c"] = found
            q = quest_filter(text, names, mission["MissionClearConditionOptionGroupId"]) if text else None
            if mission["MissionClearConditionOptionDetailGroupId"]:
                q = None  # extra conditions the name only hints at ("a conditional quest")
            if q is None:
                unknown[kind_type] += 1
                continue
            rule["k"] = "quest"
            if q:
                rule["q"] = q
            if kind_type == 62 or "skip tickets cannot be used" in norm(name):
                rule["ns"] = True
        elif kind_type in SIMPLE:
            rule["k"] = SIMPLE[kind_type]
        elif kind_type in WEAPON_KINDS:
            rule["k"] = WEAPON_KINDS[kind_type]
            if mission["MissionClearConditionOptionGroupId"]:
                m = re.search(r"(?:with|enhance|evolve|ascend) (.+?)(?:'s)?(?: skills)?(?: \d+ times?| once| 1 time)?$", norm(name))
                ids = sorted(names.weapons.get(m[1], ())) if m else []
                if not ids:
                    unknown[kind_type] += 1
                    continue
                rule["w"] = ids
        elif kind_type in COSTUME_KINDS:
            rule["k"] = COSTUME_KINDS[kind_type]
            if mission["MissionClearConditionOptionGroupId"]:
                m = re.search(r"(?:with|enhance|ascend|awaken) (.+?)(?:'s)?(?: \(([^)]*)\))?(?:'s)?(?: skills)?(?: \d+ times?| once| 1 time)?$", norm(name))
                ids = []
                if m:
                    ids = names.costume_ids(f"{m[1]} ({m[2]})" if m[2] else m[1])
                if not ids:
                    unknown[kind_type] += 1
                    continue
                rule["c"] = ids
        elif kind_type == 71:  # Exalt <character>
            m = re.search(r"exalt (.+?)(?: \d+ times?| once| 1 time)?$", norm(name))
            ids = names.character_ids(m[1]) if m else []
            if not ids:
                unknown[kind_type] += 1
                continue
            rule.update(k="character_rebirth", ch=ids)
        elif kind_type == 18:  # summons
            s = norm(name)
            rule["k"] = "gacha_draw"
            if "daily summon" in s:
                rule["g"] = "daily"
            elif "chapter summon" in s:
                rule["g"] = "chapter"
            elif mission["MissionClearConditionOptionGroupId"]:
                unknown[kind_type] += 1
                continue
        elif kind_type == 26:  # explorations
            if mission["MissionClearConditionOptionGroupId"] not in (0, 3):
                unknown[kind_type] += 1
                continue
            rule["k"] = "explore_finish"
        elif kind_type == 54:  # Mythic Slab panels
            if mission["MissionClearConditionOptionGroupId"]:
                unknown[kind_type] += 1
                continue
            rule["k"] = "board_panel"
        elif kind_type == 53:  # subjugation score
            if mission["MissionClearConditionOptionGroupId"]:
                unknown[kind_type] += 1
                continue
            rule["k"] = "big_hunt_score"
        else:
            unknown[kind_type] += 1
            continue
        rules.append(rule)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    body = ",\n".join(json.dumps(r, separators=(",", ":"), sort_keys=True) for r in rules)
    args.output.write_text("[\n" + body + "\n]\n")
    total = len(rules) + sum(unknown.values())
    print(f"{len(rules)} of {total} missions have a rule; without one, by clear condition type: {dict(unknown.most_common())}")


if __name__ == "__main__":
    main()
