#!/usr/bin/env python3
"""Generate the server's mission rules from the master data and the game's text.

The master data says what each mission counts (m_mission.MissionClearConditionType)
but not its filter: the "option groups" that name a quest, chapter, costume or
weapon lived only on the original server. Their English names do say it ("Clear
Record: Sunset Port 10 times", "Reach level 30 with Blackbird Dagger"), so this
script reads each name and writes a rule the server can evaluate:

  {"id": mission, "k": kind, "q": quest filter, "c": costumes, "w": weapons, "ch": characters,
   "ex": explore ids, "bh": subjugation boss ids, "bg": Mythic Slab group types, "lt": concert live type}

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
    15: "pvp_play", 16: "pvp_win", 17: "pvp_streak", 21: "shop_buy", 22: "user_level", 23: "login",
    25: "mission_clear", 27: "favorite_character", 28: "max_deck_power",
    30: "all_daily", 31: "mama_tap", 32: "cage_walk", 35: "defeat_boss", 36: "battle_retire",
    37: "battle_annihilated", 38: "data_transfer", 39: "library", 41: "costume_skill_level", 42: "costume_ability_level",
    44: "weapon_skill_level", 45: "weapon_ability_level", 50: "cheer_friend", 51: "big_hunt_play", 52: "big_hunt_knockdown",
    55: "defeat_wizard", 60: "report", 65: "stamina", 67: "login_from_unlock", 68: "all_daily", 69: "pvp_rank",
    70: "weapon_awaken", 72: "lottery_slot", 73: "lottery_draw", 74: "pvp_streak_from_unlock",
}
# Exploration option groups (types 26 and 29), named in the missions: Shooting is explore group 1
# (explores 1 Normal, 11 Hard; the first, from launch), Flying Mama group 2 (2 Normal, 12 Hard; added 2021-08).
# 3/7 are the older "Shooting"/"Flying Mama" missions (Normal only: Hard has its own 26/27); 28/29 the
# later ones, which count either difficulty; 31 "Hard Exploration" either game on Hard.
EXPLORE_OPTIONS = {3: [1], 7: [2], 26: [11], 27: [12], 28: [1, 11], 29: [2, 12], 31: [11, 12]}
# Subjugation bosses by the adjective the missions use, as AttributeType (MBigHuntBoss.AttributeType).
BOSS_ATTRIBUTE = {"fiery": 2, "soggy": 5, "windy": 6, "bright": 3, "bleak": 1}
# Mythic Slab groups by name (characterBoard.group.name.<TextAssetId>; TextAssetId = CharacterBoardGroupType).
BOARD_GROUP = {"stone tower monument": 1, "cursed god monument": 2}
# Concert (rhythm) quests: client enum LiveType Level1 = 2 (the concert in Quest 1), Level4 = 3 (Quest 10).
LIVE_TYPE = {1: 2, 10: 3}
# Kinds that may name one weapon or one costume/character in the mission name.
WEAPON_KINDS = {6: "weapon_skill", 7: "weapon_evolve", 8: "weapon_limit_break", 43: "weapon_level"}
COSTUME_KINDS = {10: "costume_skill", 11: "costume_limit_break", 40: "costume_level", 66: "costume_awaken"}
DIFFICULTY = {"normal": 1, "hard": 2, "very hard": 3, "ex hard": 4}


def load(master: Path, name: str) -> list[dict]:
    return json.loads((master / f"Entity{name}Table.json").read_text())


def norm(text: str) -> str:
    text = text.replace("’", "'").replace("Ⅵ", "VI").replace("Ⅴ", "V").replace("Ⅳ", "IV").replace("Ⅲ", "III")
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"\b(record|variation|dungeon):(?=\S)", r"\1: ", text)  # "Record:Foundation of Fortune"
    return re.sub(r"\b(sun|moon) 1:", r"\1 i:", text)  # "The Moon 1: The Gloaming"


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
        self.event_quests = collections.defaultdict(list)    # (event type, quest name) -> [(quest id, chapter id)]
        self.chapter_characters = collections.defaultdict(set)

        for c in load(master, "MEventQuestChapter"):
            for key in (f"quest.event.chapter_title.{c['NameEventQuestTextId']}",
                        f"quest.event.dungeon.chapter_title.{c['NameEventQuestTextId']}"):
                if key in texts:
                    title = norm(texts[key])
                    self.event_chapters[title].add(c["EventQuestChapterId"])
                    for prefix in ("record: ", "variation: ", "dungeon: "):
                        if title.startswith(prefix):
                            self.event_chapters[title[len(prefix):]].add(c["EventQuestChapterId"])
        quest_names = {q["QuestId"]: texts.get(f"quest.name.{q['NameQuestTextId']}", "") for q in load(master, "MQuest")}
        sequences = collections.defaultdict(list)
        for s in load(master, "MEventQuestSequence"):
            sequences[s["EventQuestSequenceId"]].append(s["QuestId"])
        groups = collections.defaultdict(list)
        for g in load(master, "MEventQuestSequenceGroup"):
            groups[g["EventQuestSequenceGroupId"]].append(g["EventQuestSequenceId"])
        for c in load(master, "MEventQuestChapter"):
            for seq in groups[c["EventQuestSequenceGroupId"]]:
                for q in sequences[seq]:
                    if quest_names.get(q):
                        self.event_quests[(c["EventQuestType"], norm(quest_names[q]))].append((q, c["EventQuestChapterId"]))
        for cc in load(master, "MEventQuestChapterCharacter"):
            self.chapter_characters[cc["EventQuestChapterId"]].add(cc["CharacterId"])
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
        for t in (title, title.removeprefix("the "), "the " + title, title.replace("japanese ", "jp ")):
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
        # "World-Ender (Soulful Lad)" is "The World-Ender"; "False Guardian Assassin" is "F. Guardian Assassin".
        for n in (name, "the " + name, name.replace("false ", "f. ")):
            if n in self.costumes:
                return sorted(self.costumes[n])
        return []

    def dark_memory_quests(self, character: str, quest: str) -> list[int]:
        """A character's Dark Memory quests (event type 7) by the quest's name ("Dark Lair: Hard")."""
        chars = set(self.character_ids(character))
        return sorted(q for q, ch in self.event_quests.get((7, quest), ()) if self.chapter_characters[ch] & chars)

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
    # "Clear Levania Dark Lair: Hard", "Clear Argo's Dark Coin Quest (Easy) 10 times": quests of a character's Dark Memory.
    if m := re.fullmatch(r"clear (.+?)(?:'s)? (dark lair|dark coin quest|ex ticket quest)(?:: | \()(easy|normal|hard)\)?(?: \d+ times?)?", s):
        if ids := n.dark_memory_quests(m[1], f"{m[2]}: {m[3]}"):
            q["quests"] = ids
            return q
        return None
    s = re.sub(r"^complete ", "clear ", s.rstrip("."))
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
        (r"clear a main quest or (a )?story quest", lambda m: q.update(main=True, event_types=[6])),
        (r"clear (a|\d+) story quests?", lambda m: q.setdefault("event_types", [6])),
        (r"clear a guerrilla quest", lambda m: q.setdefault("event_types", [5])),
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
    if m := re.fullmatch(r"clear (?:\d+ )?dark memory quests? for (.+)", s):
        ids = n.character_ids(m[1])
        if not ids:
            return None
        q.update(event_types=[7], characters=ids)
        return q
    # "Clear Dungeon: The Dynast's Memories 1F", "Complete Floor 10 of Dungeon: ...", "Complete Record: X up through Quest 10".
    if m := re.fullmatch(r"clear (.+) (\d+)f|clear floor (\d+) of (.+)|clear (.+) up through quest (\d+)", s):
        title, order = (m[1], m[2]) if m[1] else (m[4], m[3]) if m[4] else (m[5], m[6])
        return q if chapter_quest(title, order) else None
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


def loadout(name: str, n: Names) -> tuple[str, list[int], bool] | None:
    """Missions that need a costume (or a character) in the deck: the rest of the name and the costume ids."""
    s = norm(name)
    m = re.fullmatch(r"(.+?) with (only )?(.+?) in (?:your )?loadout(.*)", s)
    if not m:
        return None
    who = m[3]
    ids = n.costume_ids(who)
    if not ids and (chars := n.character_ids(who)):
        ids = [-c for c in chars]  # negative: any costume of this character
    if not ids:
        return None
    rest = m[1] + m[4]
    # "Clear quests 10 times with X" -> "Clear quests 10 times"; "Clear 10 quests with X" -> "Clear 10 quests".
    return rest, ids, bool(m[2])


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
            only = False
            if found := loadout(name, names):
                text, rule["c"], only = found
            q = quest_filter(text, names, mission["MissionClearConditionOptionGroupId"]) if text else None
            if mission["MissionClearConditionOptionDetailGroupId"] and not only:
                q = None  # extra conditions the name only hints at ("a conditional quest")
            if only:
                rule["co"] = True  # "with only Akeha in your loadout": every costume in the deck
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
        elif kind_type in (26, 29):  # explorations played, exploration high score
            opt = mission["MissionClearConditionOptionGroupId"]
            if opt and opt not in EXPLORE_OPTIONS:
                unknown[kind_type] += 1
                continue
            rule["k"] = "explore_finish" if kind_type == 26 else "explore_score"
            if opt:
                rule["ex"] = EXPLORE_OPTIONS[opt]
        elif kind_type == 54:  # Mythic Slab panels: "Unlock 10 Stone Tower Monument panels for Rion"
            rule["k"] = "board_panel"
            if mission["MissionClearConditionOptionGroupId"]:
                m = re.fullmatch(r"unlock \d+ (.+) panels? for (.+)", norm(name))
                chars = names.character_ids(m[2]) if m else []
                if not chars or m[1] not in BOARD_GROUP:
                    unknown[kind_type] += 1
                    continue
                rule.update(ch=chars, bg=[BOARD_GROUP[m[1]]])
        elif kind_type == 53:  # subjugation score: "... in Manifestation: Fiery Cursed God"
            rule["k"] = "big_hunt_score"
            if mission["MissionClearConditionOptionGroupId"]:
                m = re.search(r"in manifestation: (\w+) cursed god$", norm(name))
                boss = [b["BigHuntBossId"] for b in load(args.master_json, "MBigHuntBoss")
                        if m and b["AttributeType"] == BOSS_ATTRIBUTE.get(m[1])]
                if not boss:
                    unknown[kind_type] += 1
                    continue
                rule["bh"] = boss
        elif kind_type == 61:  # concert taps: "Liven up the concert in Quest 1 of ..." / "... in Quest 10 of ..."
            m = re.search(r"in quest (\d+) of", norm(name))
            if not m or int(m[1]) not in LIVE_TYPE:
                unknown[kind_type] += 1
                continue
            rule.update(k="rhythm_tap", lt=LIVE_TYPE[int(m[1])])
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
