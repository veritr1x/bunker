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

FORMAT = 6
SCENE_AREAS = ("main", "sub", "side")
MASTER_TABLES = ("m_report", "m_cage_memory", "m_library_movie", "m_library_movie_category", "m_movie",
                 "m_character", "m_main_quest_season", "m_event_quest_chapter", "m_costume",
                 "m_character_voice_unlock_condition")
# Gallery: (category, folder under assetbundle/, file pattern, group taken from the path)
GALLERY = (
    ("stills", "ui/still", "*/still_main_*.assetbundle", lambda rel: rel.parts[0]),
    ("events", "2d/ev", "*/texture/ev*_c[0-9]*.assetbundle", lambda rel: rel.parts[0]),
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


def apply_scenario(db, event_maps: Path, target: Path, scenario) -> int:
    """Regroup main-story scenes by quest chapter and name speakers; returns the lines named."""
    target.unlink(missing_ok=True)
    error = str(scenario(str(event_maps), str(target)) or "")
    if error or not target.is_file():
        return 0
    try:
        maps = json.loads(target.read_text(encoding="utf-8"))
    finally:
        target.unlink(missing_ok=True)
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
    return len(updates)


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
    for table in MASTER_TABLES:
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
        CREATE TABLE image(category TEXT, grp TEXT, name TEXT, path TEXT PRIMARY KEY);
        CREATE TABLE character_voice(character INT, kind TEXT, seq INT, path TEXT);
        CREATE TABLE music(track TEXT, part INT, path TEXT PRIMARY KEY);
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
    speakers = 0
    event_maps = assetbundle / "eventmap" / "main"
    if scenario is not None and event_maps.is_dir():
        progress(len(bundles), len(bundles), "Speakers and chapters")
        speakers = apply_scenario(db, event_maps, db_path.with_name("scenario.json"), scenario)
    progress(len(bundles), len(bundles), "Master data")
    for table, rows in load_master(master).items():
        db.execute("INSERT INTO meta VALUES (?,?)", ("master:" + table, json.dumps(rows, ensure_ascii=False)))
    costumes = json.loads(db.execute("SELECT value FROM meta WHERE key='master:m_costume'").fetchone()[0])
    costume_art = assetbundle / "ui" / "costume"
    have = {d.name for d in costume_art.iterdir()} if costume_art.is_dir() else set()
    for row in sorted(costumes, key=lambda r: r["CostumeId"]):
        asset = f"ch{row['ActorSkeletonId']:03d}{row['AssetVariationId']:03d}"
        if row["CostumeAssetCategoryType"] == 1 and asset in have:
            db.execute("INSERT OR IGNORE INTO costume VALUES (?,?,?,?)", (asset, row["CharacterId"], row["CostumeId"], row["RarityType"]))
    progress(len(bundles), len(bundles), "Gallery")
    for category, folder, pattern, group in GALLERY:
        root = assetbundle / folder
        if root.is_dir():
            rows = [(category, group(f.relative_to(root)), f.stem, f.relative_to(assetbundle).as_posix())
                    for f in sorted(root.glob(pattern))]
            db.executemany("INSERT OR IGNORE INTO image VALUES (?,?,?,?)", rows)
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
