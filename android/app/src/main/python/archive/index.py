"""Builds the Archive index: one SQLite file from the English text bundles and the master data.

The index is rebuilt only when the game files or master data change. Building
reads every English text bundle once (about 6,600 small files); pages then read
only the index.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

import extract_names  # lunar-base: a pure-Python reader for Unity text bundles

FORMAT = 11
SCENE_AREAS = ("main", "sub", "side")
MASTER_TABLES = ("m_report", "m_cage_memory", "m_library_movie", "m_library_movie_category", "m_movie",
                 "m_character", "m_main_quest_season", "m_event_quest_chapter", "m_costume",
                 "m_character_voice_unlock_condition", "m_dokan", "m_dokan_content_group", "m_dokan_text",
                 "m_companion", "m_catalog_companion", "m_parts_group", "m_parts_series")
# Read while building only, to name story groups; not kept in the index.
BUILD_TABLES = ("m_quest_scene", "m_event_quest_sequence", "m_event_quest_sequence_group", "m_event_quest_chapter_character",
                "m_main_quest_chapter", "m_main_quest_route", "m_battle_quest_scene_bgm", "m_battle_bgm_set",
                "m_actor", "m_actor_object", "m_quest_scene_battle", "m_battle_group", "m_battle", "m_battle_npc_deck",
                "m_battle_npc_deck_character", "m_battle_npc_deck_character_type", "m_battle_npc_costume")
# Gallery: (category, folder under assetbundle/, file pattern, group taken from the path)
GALLERY = (
    ("stills", "ui/still", "*/still_main_*.assetbundle", lambda rel: rel.parts[0]),
    ("events", "2d/ev", "*/texture/ev*_c[0-9]*.assetbundle", lambda rel: rel.parts[0][2:8]),  # ev001010…: Record event 001010
    ("library", "ui/library", "*/**/*.assetbundle", lambda rel: rel.parts[0]),
    ("photos", "ui/photo_gallery", "*/*.assetbundle", lambda rel: rel.parts[0]),
)
_MARKER = re.compile(r":<[A-Z_]+>$")
_VOICE_CODE = re.compile(r"_\d{5}_(\d{5})_\d+$")  # MID_b010_0020g_00100_01060_1: 01060 is who voices it
_MAP_GROUP = re.compile(r"(?:mid|pid)_([a-z]\d{3})", re.I)


def mask_name(bundle: Path, assetbundle_root: Path) -> str:
    """The Octo mask name: the path under assetbundle/, without the suffix, joined by ')'."""
    return ")".join(bundle.relative_to(assetbundle_root).with_suffix("").parts)


def read_text_bundle(bundle: Path, assetbundle_root: Path) -> list[tuple[str, str]]:
    """Every (TextAsset name, text) in one bundle."""
    raw = extract_names.decrypt_text_bundle(bundle.read_bytes(), mask_name(bundle, assetbundle_root))
    found = []
    for stream in extract_names.extract_bundle_streams(raw):
        try:
            found.extend(extract_names.extract_text_assets(stream))
        except ValueError:
            continue  # resource streams (.resS) are not serialized files
    return found


def clean(value: str) -> str:
    """Game text to plain lines: escaped newlines become real ones, tap markers go."""
    return _MARKER.sub("", value).replace("\\n", "\n").replace("<br>", "\n").strip("\n")


def line_number(key: str, name: str) -> tuple[int, str]:
    """Order lines by the number after the scene name, e.g. MID_b020_0220_00100_... -> 100."""
    rest = key[len(name):] if key.lower().startswith(name.lower()) else key
    match = re.search(r"\d+", rest)
    return (int(match.group()) if match else 0, key)


def describe_scene(area: str, folder: str, name: str) -> dict:
    """Where a scene file belongs: season, chapter or group, and its order."""
    season = int(m.group(1)) if (m := re.search(r"season(\d+)", folder)) else 0
    lower = name.lower()
    if area == "main":
        if m := re.fullmatch(r"(mid|pid)_([a-z])(\d{3})_(\d+)([a-z]*)", lower):
            number = int(m.group(3))
            return {"kind": m.group(1), "season": season, "chapter": number // 10, "group": m.group(2) + m.group(3),
                    "sort": int(m.group(4)) * 10 + (0 if m.group(1) == "mid" else 1)}
        if m := re.fullmatch(r"2(\d)(\d{2})_(\d+)", lower):
            return {"kind": "narration", "season": season, "chapter": int(m.group(2)), "group": m.group(1) + m.group(2),
                    "sort": int(m.group(3))}
    if m := re.fullmatch(r"([a-z]+)_([a-z]?\d+)_(.+)", lower):
        digits = re.sub(r"\D", "", m.group(3)) or "0"
        return {"kind": m.group(1), "season": season, "chapter": 0, "group": m.group(2), "sort": int(digits[:9])}
    return {"kind": "other", "season": season, "chapter": 0, "group": lower, "sort": 0}


def chapter_groups(maps: dict[str, list]) -> dict[str, int]:
    """Scene group (b010) -> main-story chapter as route * 100 + order (2nd route, 3rd chapter: 203).

    Event maps are named by quest map number, 0 + season + route + chapter order (0202003…), and
    list the lines they play; a group belongs to the chapter whose maps play most of its lines, or
    to the first route's when only routes differ. Groups shared by many chapters (a999) are left out."""
    votes: dict[str, Counter] = {}
    for name, lines in maps.items():
        if not re.fullmatch(r"0\d{6}\d+[a-z]?", name):
            continue
        route, order = int(name[2:4]), int(name[4:7])
        for key, *_ in lines:
            if m := _MAP_GROUP.match(key):
                votes.setdefault(m.group(1).lower(), Counter())[route * 100 + order] += 1
    out = {}
    for group, counter in votes.items():
        chapter, n = counter.most_common(1)[0]
        if n >= 0.6 * sum(counter.values()):
            out[group] = chapter
        elif len({c % 100 for c in counter}) == 1:
            out[group] = min(counter)  # both routes' finales play season 2's endings: file them under the first
    return out


def line_speakers(lines: list[tuple[str, str, str]], maps: dict[str, list], names: dict[int, str]) -> dict[str, str]:
    """Line key -> speaker name, for (key, scene name, season) lines.

    Event maps name the actor (or the speaker shown instead) for the lines they play. A line no
    map names takes the actor its voice code has elsewhere in the scene, or failing that across
    the season when that code is nearly always one actor. Codes below 01000 are narration and
    system voices, never filled in, and only lines keyed by their own scene's name are named."""
    direct = {}
    for lines_of_map in maps.values():
        for key, actor, speaker in lines_of_map:
            if speaker or actor:
                direct[key.lower()] = speaker or actor
    in_scene, in_season = {}, {}
    for key, scene, season in lines:
        if not key.lower().startswith(scene.lower() + "_"):
            continue
        actor, code = direct.get(key.lower()), (m.group(1) if (m := _VOICE_CODE.search(key)) else None)
        if actor and code:
            in_scene.setdefault((scene, code), Counter())[actor] += 1
            in_season.setdefault((season, code), Counter())[actor] += 1
    out = {}
    for key, scene, season in lines:
        if not key.lower().startswith(scene.lower() + "_"):
            continue  # chapter narrations reuse keys like 001_00002_0_v across files: no speaker to trust
        actor = direct.get(key.lower())
        code = m.group(1) if (m := _VOICE_CODE.search(key)) else None
        if not actor and code and code >= "01000":
            for votes, share, least in ((in_scene.get((scene, code)), 0.75, 1), (in_season.get((season, code)), 0.9, 10)):
                if votes:
                    best, n = votes.most_common(1)[0]
                    if n >= share * sum(votes.values()) and n >= least:
                        actor = best
                        break
        if actor and names.get(actor):
            out[key.lower()] = names[actor]
    return out


def story_titles(maps: dict[str, dict], master: dict[str, list[dict]], texts: dict[str, str]) -> dict[tuple, str]:
    """(kind, group) -> name for the stories outside the main one.

    Event maps are named by quest map number and list the text files they read. Character
    Quests, Dark Memories and Recollections of Dusk share a code per character (cid_a02020,
    eid_a02020, lid_a02020: Rion); the Character Quest's event chapter names the character.
    Events (vid) take their event's title, side stories (sid) are numbered by character."""
    chapters = {c["EventQuestChapterId"]: c for c in master.get("m_event_quest_chapter", [])}
    sequences = {}
    for r in master.get("m_event_quest_sequence_group", []):
        sequences.setdefault(r["EventQuestSequenceGroupId"], []).append(r["EventQuestSequenceId"])
    chapter_of_quest = {}
    sequence_quests = {}
    for r in master.get("m_event_quest_sequence", []):
        sequence_quests.setdefault(r["EventQuestSequenceId"], []).append(r["QuestId"])
    for cid, c in chapters.items():
        for s in sequences.get(c["EventQuestSequenceGroupId"], []):
            for q in sequence_quests.get(s, []):
                chapter_of_quest.setdefault(q, cid)
    chapter_of_upper = {}
    for r in master.get("m_quest_scene", []):
        if r["EventMapNumberUpper"] and r["QuestId"] in chapter_of_quest:
            chapter_of_upper.setdefault(r["EventMapNumberUpper"], Counter())[chapter_of_quest[r["QuestId"]]] += 1
    characters = {}
    for r in master.get("m_event_quest_chapter_character", []):
        characters.setdefault(r["EventQuestChapterId"], r["CharacterId"])
    votes: dict[tuple, Counter] = {}
    for name, m in maps.items():
        number = name.rsplit("/", 1)[-1][:7]
        if not number.isdigit():
            continue
        for path in m.get("paths", []):
            parts = path.split(")")
            where = describe_scene(parts[0], "", parts[-1])
            if where["kind"] in ("cid", "vid", "sid"):
                votes.setdefault((where["kind"], where["group"]), Counter())[int(number)] += 1
    character_of_code, out = {}, {}
    for (kind, group), counter in votes.items():
        upper, n = counter.most_common(1)[0]
        if n < 0.6 * sum(counter.values()):
            out[(kind, group)] = "Other scenes"  # battle prompts every map shares, like the main story's a999
            continue
        if kind == "sid":
            character = upper  # side story maps are numbered by character
        else:
            found = chapter_of_upper.get(upper)
            chapter = found.most_common(1)[0][0] if found else None
            if kind == "vid":
                title = texts.get(f"quest.event.chapter_title.{chapters[chapter]['NameEventQuestTextId']}") if chapter else None
                if title:
                    out[(kind, group)] = title
                continue
            character = characters.get(chapter)
        name = texts.get(f"character.name.{character}")
        if name:
            out[(kind, group)] = name
            if kind == "cid":
                character_of_code[group] = name
    for code, name in character_of_code.items():
        for kind in ("eid", "lid"):
            out[(kind, code)] = name
    return out


# Where music plays, in the order the Music page lists it.
MUSIC_SECTIONS = ("Season 1", "Season 2", "Season 3", "Character stories", "Events", "Side stories", "Battle")
STORY_KINDS = {"cid": "Character Quest", "eid": "Dark Memories", "lid": "Recollections of Dusk"}


def music_uses(maps: dict[str, dict], master: dict[str, list[dict]], texts: dict[str, str],
               titles: dict[tuple, str]) -> set[tuple]:
    """(track, section, order, place) for every place a track starts: an event map's music, placed by
    the map (a main-story chapter from its quest map number, else the story whose text it reads), and
    the battle music tables."""
    out = set()
    for name, m in maps.items():
        folder, _, number = name.partition("/")
        place = None
        if folder == "main" and number[:7].isdigit():
            season, route, order = int(number[1]), int(number[2:4]), int(number[4:7])
            label = texts.get(f"quest.main.chapter_number.{season}.{route}.{order}")
            if 1 <= season <= 3 and label:
                place = (MUSIC_SECTIONS.index(f"Season {season}"), route * 100 + order, label)
        elif folder in ("battle", "pt"):
            place = (MUSIC_SECTIONS.index("Battle"), 0, "Battle")
        else:
            for path in m.get("paths", []):
                where = describe_scene(path.split(")")[0], "", path.split(")")[-1])
                title = titles.get((where["kind"], where["group"]))
                if not title or title == "Other scenes":
                    continue
                if where["kind"] in STORY_KINDS:
                    place = (MUSIC_SECTIONS.index("Character stories"), 0, f"{title} · {STORY_KINDS[where['kind']]}")
                elif where["kind"] == "vid":
                    place = (MUSIC_SECTIONS.index("Events"), int(where["group"][:6]) if where["group"][:6].isdigit() else 0, title)
                elif where["kind"] == "sid":
                    place = (MUSIC_SECTIONS.index("Side stories"), 0, f"{title} · Side Story")
                if place:
                    break
        if place:
            for track, _ in m.get("music", []):
                out.add((str(track), *place))
    for row in master.get("m_battle_quest_scene_bgm", []):
        out.add((str(row["BgmId"]), MUSIC_SECTIONS.index("Battle"), 0, "Battle"))
    for row in master.get("m_battle_bgm_set", []):
        out.add((str(row["BgmAssetId"]), MUSIC_SECTIONS.index("Battle"), 0, "Battle"))
    return out


# The Library's sections, in the game's order.
LIBRARY_SECTIONS = ("Season 1", "Season 2", "Season 3", "Events", "Character Quests", "Recollections of Dusk", "Dark Memories")


def library_entries(texts: dict[str, str], master: dict[str, list[dict]], maps: dict[str, dict]) -> list[tuple]:
    """The Library's summaries as (section, heading, heading order, title, order, text).

    story.Main.Quest.<season>.<main quest chapter>.<quest>: under the chapter's own name, titled by the quest.
    quest.event.chapter.story.01|06.<n>.<part>: the Record event or Character Quest whose SortOrder is n.
    limit.content.story.<quest>: a Recollection of Dusk, under the character of the quest's event chapter.
    content.story.<map number>: a Dark Memory, under the scene group its event map plays (named later)."""
    chapters = {c["EventQuestChapterId"]: c for c in master.get("m_event_quest_chapter", [])}
    characters = {r["EventQuestChapterId"]: r["CharacterId"] for r in master.get("m_event_quest_chapter_character", [])}

    def character(chapter):
        return texts.get(f"character.name.{characters.get(chapter)}", "")

    sequences, quests = {}, {}
    for r in master.get("m_event_quest_sequence_group", []):
        sequences.setdefault(r["EventQuestSequenceGroupId"], []).append(r["EventQuestSequenceId"])
    for r in master.get("m_event_quest_sequence", []):
        quests.setdefault(r["EventQuestSequenceId"], []).append(r["QuestId"])
    chapter_of_quest = {}
    for cid, c in sorted(chapters.items()):
        for s in sequences.get(c["EventQuestSequenceGroupId"], []):
            for q in quests.get(s, []):
                chapter_of_quest.setdefault(q, cid)
    by_sort = {(c["EventQuestType"], c["SortOrder"]): cid for cid, c in chapters.items()}
    main_chapters = {c["MainQuestChapterId"]: c for c in master.get("m_main_quest_chapter", [])}
    routes = {r["MainQuestRouteId"]: r for r in master.get("m_main_quest_route", [])}
    dark = {}  # Dark Memory event map number (0005003000001) -> the scene group it plays (eid_a01040)
    for name, m in maps.items():
        folder, _, number = name.partition("/")
        if folder == "endcontents":
            for path in m.get("paths", []):
                dark.setdefault(number.rstrip("abcdefghijklmnopqrstuvwxyz"), describe_scene("sub", "", path.split(")")[-1])["group"])
    out = []
    for key, text in texts.items():
        parts = key.split(".")
        if key.startswith("story.Main.Quest.") and len(parts) >= 6:
            season, chapter, quest = int(parts[3]), int(parts[4]), int(parts[5])
            heading, order = chapter_heading(texts, main_chapters, routes, season, chapter)
            part = int(parts[6]) if len(parts) > 6 else 0
            out.append((f"Season {season}", heading, order, texts.get(f"mqt.{quest}p1", ""), quest * 100 + part, text, key))
        elif key.startswith("quest.event.chapter.story.") and len(parts) == 7:
            kind, n, part = int(parts[4]), int(parts[5]), int(parts[6])
            chapter = by_sort.get((kind, n))
            if kind == 1:
                name = texts.get(f"quest.event.chapter_title.{chapters[chapter]['NameEventQuestTextId']}", "") if chapter else ""
                out.append(("Events", name or f"Event {n}", n, "", part, text, key))
            elif kind == 6:
                out.append(("Character Quests", character(chapter) or f"Character {n}", n, "", part, text, key))
        elif key.startswith("limit.content.story.") and parts[-1].isdigit():
            quest = int(parts[-1])
            chapter = chapter_of_quest.get(quest)
            out.append(("Recollections of Dusk", character(chapter) or "Other", chapter or 0, "", quest, text, key))
        elif key.startswith("content.story.") and len(parts) == 4:
            out.append(("Dark Memories", dark.get(parts[2] + parts[3], ""), int(parts[2]), "", int(parts[3]), text, key))
    return out


def chapter_heading(texts: dict[str, str], chapters: dict[int, dict], routes: dict[int, dict], season: int,
                    chapter: int) -> tuple[str, int]:
    """A main-quest chapter's name ("Ch. 1 · Windblown Sand") and its place in the season."""
    c = chapters.get(chapter)
    route, order = (routes.get(c["MainQuestRouteId"], {}).get("SortOrder", 1), c["SortOrder"]) if c else (1, chapter)
    number = texts.get(f"quest.main.chapter_number.{season}.{route}.{order}") or f"Chapter {order}"
    title = texts.get(f"quest.main.chapter_title.{season}.{route}.{order}", "")
    return number + (f" · {title}" if title and title != number else ""), route * 100 + order


def library_art(key: str) -> str:
    """The picture the Library shows with a summary, found by the summary's key ("" when it has none)."""
    parts = key.split(".")
    if key.startswith("quest.event.chapter.story.") and len(parts) == 7 and parts[4] in ("01", "06"):
        return f"ui/library/event_quest_type_{parts[4]}/bg{parts[5]}{parts[6]}.assetbundle"
    if key.startswith("limit.content.story.") and parts[-1].isdigit():
        return f"ui/library/limit_content/bg{parts[-1]}.assetbundle"
    if key.startswith("content.story.") and len(parts) == 4:
        return f"ui/library/content/bg{parts[2]}{parts[3]}.assetbundle"
    return ""


def gallery_rows(rows: list[tuple], texts: dict[str, str], master: dict[str, list[dict]],
                 library: dict[str, tuple], events: dict[str, str]) -> list[tuple]:
    """Each picture (category, group, name, path) as (category, group, name, path, title, section, order), named
    for what it shows where that can be told: a still by its main-story chapter (still_main_<season><route>
    <chapter id><n>); an event scene by its Record event's part and cut; Library art by the summary it sits
    beside (library: path -> (heading, heading order, order)), or the report, Lost Archive, movie or record."""
    chapters = {c["MainQuestChapterId"]: c for c in master.get("m_main_quest_chapter", [])}
    routes = {r["MainQuestRouteId"]: r for r in master.get("m_main_quest_route", [])}
    reports = {r["ReportAssetId"]: r for r in master.get("m_report", [])}
    cages = {r["CageMemoryAssetId"]: r for r in master.get("m_cage_memory", [])}
    movies = {r["LibraryMovieId"]: r for r in master.get("m_library_movie", [])}
    event_parts = {}  # Record event -> its parts' codes (0101, 0401, …), from the folder after the event code
    for category, grp, name, path in rows:
        if category == "events":
            event_parts.setdefault(grp, set()).add(path.split("/")[2][8:])
    glass = sorted({name[13:19] for category, grp, name, path in rows if grp == "stained_glass"})
    placed = []
    for category, grp, name, path in rows:
        title, section, order = "", "", 0
        variant = ""
        if name.endswith(("_full", "_standard")):
            name_id, variant = name.rsplit("_", 1)
            variant = " · card" if variant == "standard" else ""
        else:
            name_id = name
        if category == "stills":
            m = re.fullmatch(r"still_main_(\d)\d(\d{3})\d{2}", name)
            section, order = chapter_heading(texts, chapters, routes, int(m[1]), int(m[2])) if m else ("Other", 99999)
        elif category == "events":
            code = path.split("/")[2][8:]
            order = sorted(event_parts[grp]).index(code) + 1
            section = f"Part {order}"
            cut = re.search(r"_c(\d+)_?(.*)$", name)
            title = f"Cut {int(cut[1])}" + (f" · {cut[2].replace('_', ' ')}" if cut[2] else "") if cut else ""
        elif category == "photos":
            title = "Photo"
        elif path in library:
            section, heading_order, order = library[path]
            order = heading_order * 100000 + order
            title = "Part"
        elif grp == "report" and name_id[6:].isdigit():
            r = reports.get(int(name_id[6:]))
            if r:
                section, order = texts.get(f"character.name.{r['CharacterId']}", ""), r["MainQuestSeasonId"] * 100000 + r["CharacterId"]
                title = texts.get(f"report.title.{r['ReportAssetId']}", "") + variant
        elif grp == "cage_memory" and name_id[11:].isdigit():
            r = cages.get(int(name_id[11:]))
            if r:
                section, order = f"Season {r['MainQuestSeasonId']}", r["MainQuestSeasonId"] * 1000 + r["SortOrder"]
                title = texts.get(f"cage.memory.title.{r['CageMemoryAssetId']}", "") + variant
        elif grp == "stained_glass" and name[13:19] in glass:
            order = glass.index(name[13:19]) + 1
            section, title = f"Stained glass {order}", name[20:].capitalize()
        elif grp == "movie" and name[5:].isdigit():
            r = movies.get(int(name[5:]))
            title = texts.get(f"movie.title.name.{r['TitleLibraryTextId']}", "") if r else ""
            order = int(name[5:])
        elif grp == "record" and name[6:].isdigit():
            title, order = texts.get(f"record.title.name.{name[6:]}", ""), int(name[6:])
        placed.append([category, grp, name, path, title, section, order])
    # Numbered names count within their section: Still 1, Part 2, Photo 3.
    counts = Counter()
    for row in sorted(placed, key=lambda r: (r[0], r[1], r[6], r[5], r[2])):
        if row[4] in ("", "Still", "Part", "Photo") or row[0] == "stills":
            word = {"stills": "Still", "photos": "Photo"}.get(row[0], "Part" if row[4] == "Part" else "Picture")
            counts[(row[0], row[1], row[5])] += 1
            row[4] = f"{word} {counts[(row[0], row[1], row[5])]}"
    return [tuple(r) for r in placed]


# The other people and creatures the game shows in 3D, by the first letters of their model.
MODEL_SECTIONS = ("Main cast", "Story characters", "Enemies")
MODEL_FAMILIES = {"ma": 0, "np": 1, "pc": 1, "pe": 1, "sp": 1, "um": 1, "mt": 2}


def readable(name: str) -> bool:
    """False for names the game garbles on purpose (■ blocks, "&f33", "%ol13##") or that came out as mojibake."""
    return bool(name) and name != "-" and not re.search(r"[■&%#$*]", name) and all(ord(c) < 0x2000 for c in name)


def enemy_names(master: dict[str, list[dict]], texts: dict[str, str]) -> dict[str, Counter]:
    """Enemy model (mt008101) -> how often each boss name is given to it. A quest's boss name
    (quest.boss.name.<quest>) goes to the boss-type member of the enemy decks its battles field:
    quest -> scenes -> battle groups -> battles -> deck -> member -> costume -> skeleton and variation."""
    costumes = {r["CostumeId"]: r for r in master.get("m_costume", [])}
    npc_costumes = {(r["BattleNpcId"], r["BattleNpcCostumeUuid"]): r["CostumeId"] for r in master.get("m_battle_npc_costume", [])}
    members = {(r["BattleNpcId"], r["BattleNpcDeckCharacterUuid"]): r["BattleNpcCostumeUuid"]
               for r in master.get("m_battle_npc_deck_character", [])}
    bosses = {(r["BattleNpcId"], r["BattleNpcDeckCharacterUuid"]) for r in master.get("m_battle_npc_deck_character_type", [])
              if r["BattleEnemyType"] == 2}
    decks = {(r["BattleNpcId"], r["DeckType"], r["BattleNpcDeckNumber"]): r for r in master.get("m_battle_npc_deck", [])}
    battles, groups, scene_groups, scenes = {}, {}, {}, {}
    for r in master.get("m_battle", []):
        battles.setdefault(r["BattleId"], []).append(r)
    for r in master.get("m_battle_group", []):
        groups.setdefault(r["BattleGroupId"], []).append(r["BattleId"])
    for r in master.get("m_quest_scene_battle", []):
        scene_groups.setdefault(r["QuestSceneId"], []).append(r["BattleGroupId"])
    for r in master.get("m_quest_scene", []):
        scenes.setdefault(r["QuestId"], []).append(r["QuestSceneId"])
    out = {}
    for key, name in texts.items():
        quest = key.rsplit(".", 1)[-1]
        if not key.startswith("quest.boss.name.") or not quest.isdigit() or not readable(name):
            continue
        for scene in scenes.get(int(quest), []):
            for group in scene_groups.get(scene, []):
                for battle in (b for g in groups.get(group, []) for b in battles.get(g, [])):
                    deck = decks.get((battle["BattleNpcId"], battle["DeckType"], battle["BattleNpcDeckNumber"]))
                    for slot in ("01", "02", "03") if deck else ():
                        member = (battle["BattleNpcId"], deck["BattleNpcDeckCharacterUuid" + slot])
                        c = costumes.get(npc_costumes.get((battle["BattleNpcId"], members.get(member))))
                        if member in bosses and c and c["CostumeAssetCategoryType"] == 2:
                            out.setdefault(f"mt{c['ActorSkeletonId']:03d}{c['AssetVariationId']:03d}", Counter())[name] += 1
    return out


def model_rows(assets: list[str], master: dict[str, list[dict]], texts: dict[str, str]) -> list[tuple]:
    """(asset, section, family, family name, name) for each model of MODEL_FAMILIES. A model is named by the
    actors that use it (actor.object.name via m_actor_object and m_actor) or, for an enemy, by the bosses it
    plays; its family (the first five letters: mt008) by the name most of its models share, an enemy's
    without the element ("Multi-limb Type: Fire" is a Multi-limb Type)."""
    actors = {r["ActorId"]: r["ActorAssetId"] for r in master.get("m_actor", [])}
    named = {}
    for r in sorted(master.get("m_actor_object", []), key=lambda r: r["ActorObjectId"]):
        name = texts.get(f"actor.object.name.{r['ActorObjectId']}", "")
        if r["ActorId"] in actors and readable(name):
            named.setdefault(actors[r["ActorId"]], Counter())[name] += 1
    for asset, names in enemy_names(master, texts).items():
        named[asset] = names
    own = {a: named[a].most_common(1)[0][0] for a in assets if a in named}
    families = {}
    for a in assets:
        if a in own:
            families.setdefault(a[:5], Counter())[own[a].split(": ")[0] if a.startswith("mt") else own[a]] += 1
    out = []
    for a in assets:
        family = families.get(a[:5])
        out.append((a, MODEL_FAMILIES[a[:2]], a[:5], family.most_common(1)[0][0] if family else "", own.get(a, "")))
    return out


def apply_scenario(db, event_maps: Path, target: Path, scenario, master: dict[str, list[dict]]) -> tuple[int, dict]:
    """Regroup main-story scenes by quest chapter, name speakers and stories; returns the lines named and the maps."""
    target.unlink(missing_ok=True)
    error = str(scenario(str(event_maps), str(target)) or "")
    if error or not target.is_file():
        return 0, {}
    try:
        found = json.loads(target.read_text(encoding="utf-8"))
    finally:
        target.unlink(missing_ok=True)
    texts = dict(db.execute("SELECT key, value FROM text WHERE key LIKE 'character.name.%' OR key LIKE 'quest.event.chapter_title.%'"))
    db.executemany("INSERT OR REPLACE INTO story_group VALUES (?,?,?)",
                   [(kind, group, title) for (kind, group), title in story_titles(found, master, texts).items()])
    # The main story's maps, by name alone, with the lines they play.
    maps = {name.split("/", 1)[1]: m.get("lines", []) for name, m in found.items() if name.startswith("main/")}
    groups = chapter_groups(maps)
    for scene, kind, season, chapter, grp in db.execute("SELECT id, kind, season, chapter, grp FROM scene WHERE area='main'").fetchall():
        if kind == "narration":  # 2201_001: season 2's intro narration for the chapter whose scenes are b010
            grp = "abc"[season - 1] + f"{chapter:02d}0" if 1 <= season <= 3 else ""
        if grp in groups:
            db.execute("UPDATE scene SET chapter=? WHERE id=?", (groups[grp], scene))
    db.execute("INSERT INTO meta VALUES ('chapters', 'quest')")
    names = {int(k.rsplit(".", 1)[1]): v for k, v in db.execute("SELECT key, value FROM text WHERE key LIKE 'actor.object.name.%'")
             if k.rsplit(".", 1)[1].isdigit() and v and v != "-"}
    rows = db.execute("SELECT line.rowid, line.key, scene.name, scene.season FROM line JOIN scene ON scene.id = line.scene "
                      "WHERE scene.area='main'").fetchall()
    named = line_speakers([(key, scene, str(season)) for _, key, scene, season in rows], maps, names)
    updates = [(named[key.lower()], rowid) for rowid, key, *_ in rows if key.lower() in named]
    db.executemany("UPDATE line SET speaker=? WHERE rowid=?", updates)
    return len(updates), found


def load_master(master_path: Path) -> dict[str, list[dict]]:
    """The few master-data tables the Archive needs, as lists of rows."""
    import dump_masterdata
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    import msgpack
    key, iv = bytes.fromhex(dump_masterdata.DEFAULT_KEY), bytes.fromhex(dump_masterdata.DEFAULT_IV)
    decoded = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(master_path.read_bytes()), AES.block_size)
    try:
        toc, blob = msgpack.unpackb(decoded, raw=False, strict_map_key=False), b""
    except msgpack.ExtraData as exc:
        toc, blob = exc.unpacked, exc.extra
    schemas = dump_masterdata.load_schemas()
    tables = {}
    for table in MASTER_TABLES + BUILD_TABLES:
        if table in toc and table in schemas:
            offset, length = toc[table]
            rows = dump_masterdata.decompress_table(blob, offset, length)
            tables[table] = dump_masterdata.rows_to_dicts(rows, schemas[table][1])
    return tables


def signature(revision: Path, master: Path) -> dict:
    stat = lambda p: [p.stat().st_size, int(p.stat().st_mtime)] if p.exists() else None
    return {"format": FORMAT, "catalog": stat(revision / "list.bin"), "master": stat(master)}


def is_current(db_path: Path, revision: Path, master: Path) -> bool:
    try:
        with contextlib.closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as db:
            row = db.execute("SELECT value FROM meta WHERE key='signature'").fetchone()
        return bool(row) and json.loads(row[0]) == signature(revision, master)
    except sqlite3.Error:
        return False


def build(revision: Path, master: Path, db_path: Path, progress=lambda done, total, step: None, scenario=None) -> dict:
    """Write the index next to db_path, then swap it in. Returns a summary.

    scenario(event_map_folder, target_json) returns "" or an error, writing what ScenarioToJSON in the
    Go library writes; with it, main-story chapters follow the game's quests and lines get speakers."""
    assetbundle = revision / "assetbundle"
    text_root = assetbundle / "text" / "en"
    if not text_root.is_dir():
        raise FileNotFoundError("The game files have no English text. Choose the game files in the Bunker first.")
    if not master.is_file():
        raise FileNotFoundError("Master data is missing.")
    started = time.time()
    pending = db_path.with_name(db_path.name + ".pending")
    pending.unlink(missing_ok=True)
    db = sqlite3.connect(pending)
    db.executescript("""
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE text(key TEXT PRIMARY KEY, value TEXT, folder TEXT);
        CREATE TABLE scene(id INTEGER PRIMARY KEY, area TEXT, kind TEXT, season INT, chapter INT, grp TEXT,
                           name TEXT, sort INT, lines INT);
        CREATE TABLE line(scene INT, seq INT, text TEXT, voice TEXT, key TEXT, speaker TEXT);
        CREATE TABLE movie(name TEXT PRIMARY KEY, file TEXT, size INT);
        CREATE TABLE costume(asset TEXT PRIMARY KEY, character INT, costume INT, rarity INT);
        CREATE TABLE image(category TEXT, grp TEXT, name TEXT, path TEXT PRIMARY KEY, title TEXT, section TEXT, sort INT);
        CREATE TABLE character_voice(character INT, kind TEXT, seq INT, path TEXT);
        CREATE TABLE music(track TEXT, part INT, path TEXT PRIMARY KEY);
        CREATE TABLE story_group(kind TEXT, grp TEXT, title TEXT, PRIMARY KEY(kind, grp));
        CREATE TABLE library(section INT, heading TEXT, heading_sort INT, title TEXT, sort INT, text TEXT, art TEXT);
        CREATE TABLE model(asset TEXT PRIMARY KEY, section INT, family TEXT, family_name TEXT, name TEXT);
        CREATE TABLE music_use(track TEXT, section INT, sort INT, place TEXT);
    """)
    # Spoken lines: voice/en/…/<line key>.assetbundle, named like the text line they voice.
    voice_root = assetbundle / "voice" / "en"
    voices = {f.stem.lower(): f.relative_to(assetbundle).as_posix() for f in voice_root.rglob("*.assetbundle")} if voice_root.is_dir() else {}
    bundles = sorted(text_root.rglob("*.assetbundle"))
    failures = 0
    progress(0, len(bundles), "Story text")
    for done, bundle in enumerate(bundles, 1):
        folder = bundle.relative_to(text_root).parent.as_posix()
        area = folder.split("/")[0]
        try:
            assets = read_text_bundle(bundle, assetbundle)
        except Exception:
            failures += 1
            continue
        for name, text in assets:
            entries = extract_names.parse_text_asset_lines(text)
            if area in SCENE_AREAS:
                where = describe_scene(area, folder, name)
                keys = sorted((k for k in entries if not k.startswith("//")), key=lambda k: line_number(k, name))
                cursor = db.execute("INSERT INTO scene(area, kind, season, chapter, grp, name, sort, lines) VALUES (?,?,?,?,?,?,?,?)",
                                    (area, where["kind"], where["season"], where["chapter"], where["group"], name, where["sort"], len(keys)))
                db.executemany("INSERT INTO line VALUES (?,?,?,?,?,NULL)",
                               [(cursor.lastrowid, i, clean(entries[k]), voices.get(k.lower()), k) for i, k in enumerate(keys)])
            else:
                db.executemany("INSERT OR REPLACE INTO text VALUES (?,?,?)", [(k, clean(v), folder) for k, v in entries.items()])
        if done % 50 == 0 or done == len(bundles):
            progress(done, len(bundles), "Story text")
    progress(len(bundles), len(bundles), "Master data")
    tables = load_master(master)
    if "m_dokan_text" in tables:  # announcement captions: English only (LanguageType 2)
        tables["m_dokan_text"] = [r for r in tables["m_dokan_text"] if r.get("LanguageType") == 2]
    for table, rows in tables.items():
        if table not in BUILD_TABLES:
            db.execute("INSERT INTO meta VALUES (?,?)", ("master:" + table, json.dumps(rows, ensure_ascii=False)))
    speakers, maps = 0, {}
    event_maps = assetbundle / "eventmap"
    if scenario is not None and event_maps.is_dir():
        progress(len(bundles), len(bundles), "Speakers and chapters")
        speakers, maps = apply_scenario(db, event_maps, db_path.with_name("scenario.json"), scenario, tables)
    texts = dict(db.execute("SELECT key, value FROM text WHERE key LIKE 'story.Main.Quest.%' OR key LIKE 'quest.event.chapter%' "
                            "OR key LIKE 'limit.content.story.%' OR key LIKE 'content.story.%' OR key LIKE 'quest.main.chapter_%' "
                            "OR key LIKE 'mqt.%' OR key LIKE 'character.name.%' OR key LIKE 'report.title.%' "
                            "OR key LIKE 'cage.memory.title.%' OR key LIKE 'movie.title.name.%' OR key LIKE 'record.title.name.%' "
                            "OR key LIKE 'actor.object.name.%' OR key LIKE 'quest.boss.name.%'"))
    if maps:
        titles = {(k, g): t for k, g, t in db.execute("SELECT kind, grp, title FROM story_group")}
        db.executemany("INSERT INTO music_use VALUES (?,?,?,?)", sorted(music_uses(maps, tables, texts, titles)))
    dark_names = dict(db.execute("SELECT grp, title FROM story_group WHERE kind='eid'"))
    rows = []
    for section, heading, heading_sort, title, sort, text, key in library_entries(texts, tables, maps):
        if section in LIBRARY_SECTIONS:
            art = library_art(key)
            rows.append((LIBRARY_SECTIONS.index(section), dark_names.get(heading, "") if section == "Dark Memories" else heading,
                         heading_sort, title, sort, text, art if art and (assetbundle / art).is_file() else ""))
    db.executemany("INSERT INTO library VALUES (?,?,?,?,?,?,?)", rows)
    costumes = json.loads(db.execute("SELECT value FROM meta WHERE key='master:m_costume'").fetchone()[0])
    costume_art = assetbundle / "ui" / "costume"
    have = {d.name for d in costume_art.iterdir()} if costume_art.is_dir() else set()
    for row in sorted(costumes, key=lambda r: r["CostumeId"]):
        asset = f"ch{row['ActorSkeletonId']:03d}{row['AssetVariationId']:03d}"
        if row["CostumeAssetCategoryType"] == 1 and asset in have:
            db.execute("INSERT OR IGNORE INTO costume VALUES (?,?,?,?)", (asset, row["CharacterId"], row["CostumeId"], row["RarityType"]))
    progress(len(bundles), len(bundles), "Gallery")
    rows = []
    for category, folder, pattern, group in GALLERY:
        root = assetbundle / folder
        if root.is_dir():
            rows += [(category, group(f.relative_to(root)), f.stem, f.relative_to(assetbundle).as_posix())
                     for f in sorted(root.glob(pattern))]
    library = {art: (heading, heading_sort, sort) for art, heading, heading_sort, sort
               in db.execute("SELECT art, heading, heading_sort, sort FROM library WHERE art != ''")}
    events = dict(db.execute("SELECT grp, title FROM story_group WHERE kind='vid'"))
    db.executemany("INSERT OR IGNORE INTO image VALUES (?,?,?,?,?,?,?)", gallery_rows(rows, texts, tables, library, events))
    actors = assetbundle / "3d" / "actor"
    assets = sorted(d.name for d in actors.iterdir() if d.name[:2] in MODEL_FAMILIES and re.fullmatch(r"[a-z]{2}\d{6}", d.name)) \
        if actors.is_dir() else []
    db.executemany("INSERT INTO model VALUES (?,?,?,?,?)", model_rows(assets, tables, texts))
    # A character's own lines (outside the story) sit in voice/en/outgame/<VoiceAssetId>/.
    rows = json.loads(db.execute("SELECT value FROM meta WHERE key='master:m_character_voice_unlock_condition'").fetchone()[0])
    for character, asset in sorted({(r["CharacterId"], r["VoiceAssetId"]) for r in rows}):
        folder = voice_root / "outgame" / f"{asset:05d}"
        for seq, f in enumerate(sorted(folder.glob("*.assetbundle")) if folder.is_dir() else []):
            db.execute("INSERT INTO character_voice VALUES (?,?,?,?)", (character, f.stem.split("_")[0], seq, f.relative_to(assetbundle).as_posix()))
    bgm = assetbundle / "audio" / "bgm"
    for f in sorted(bgm.glob("bgm_*.assetbundle")) if bgm.is_dir() else []:
        track, _, part = f.stem.removeprefix("bgm_").rpartition("_")
        if not track.isdigit():
            continue  # bgm_delay_settings holds timing data, not music
        db.execute("INSERT INTO music VALUES (?,?,?)", (track, int(part) if part.isdigit() else 0, f.relative_to(assetbundle).as_posix()))
    resources = revision / "resources"
    if resources.is_dir():
        for file in sorted(resources.glob("*.mp4")):
            db.execute("INSERT INTO movie VALUES (?,?,?)", (file.stem, file.name, file.stat().st_size))
    db.execute("CREATE INDEX line_scene ON line(scene, seq)")
    db.execute("CREATE INDEX scene_place ON scene(area, season, chapter, grp)")
    db.execute("CREATE INDEX image_place ON image(category, grp, name)")
    db.execute("CREATE INDEX costume_character ON costume(character, costume)")
    summary = {"bundles": len(bundles), "failed": failures, "seconds": round(time.time() - started, 1),
               "scenes": db.execute("SELECT count(*) FROM scene").fetchone()[0],
               "lines": db.execute("SELECT count(*) FROM line").fetchone()[0],
               "costumes": db.execute("SELECT count(*) FROM costume").fetchone()[0],
               "images": db.execute("SELECT count(*) FROM image").fetchone()[0],
               "voiced": db.execute("SELECT count(*) FROM line WHERE voice IS NOT NULL").fetchone()[0],
               "tracks": db.execute("SELECT count(DISTINCT track) FROM music").fetchone()[0],
               "speakers": speakers}
    db.execute("INSERT INTO meta VALUES ('signature', ?)", (json.dumps(signature(revision, master)),))
    db.execute("INSERT INTO meta VALUES ('summary', ?)", (json.dumps(summary),))
    db.execute("INSERT INTO meta VALUES ('built', ?)", (time.strftime("%Y-%m-%d %H:%M"),))
    db.commit()
    db.close()
    os.replace(pending, db_path)
    return summary
