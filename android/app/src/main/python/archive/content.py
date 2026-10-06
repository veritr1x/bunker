"""Read-side queries over the Archive index: what each page lists."""
from __future__ import annotations

import contextlib
import html
import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

# The game's own names: Dark Memories (end contents), Recollections of Dusk (limit contents), Character
# Quests, the "Record" events, and Side Stories.
KINDS = {"eid": "Dark Memories", "lid": "Recollections of Dusk", "cid": "Character Quests", "vid": "Events", "sid": "Side Stories"}
_TAG = re.compile(r"<(?!/?i>)/?[a-z][^<>]*>", re.I)
_ANY_TAG = re.compile(r"</?[a-z][^<>]*>", re.I)
_OPEN_ITALIC = re.compile(r"</?i(?![a-z>])", re.I)  # "</I." in one summary: a tag missing its ">"


def rich(text: str) -> str:
    """Game text as safe HTML: italics kept, other markup dropped, newlines kept."""
    safe = html.escape(_TAG.sub("", _OPEN_ITALIC.sub(r"\g<0>>", text or "")), quote=False)
    out, depth = [], 0
    # Some game text opens italics without closing them; keep every tag paired so nothing leaks into the page.
    for part in re.split(r"(&lt;/?i&gt;)", safe, flags=re.I):
        part = part.lower() if re.fullmatch(r"&lt;/?i&gt;", part, re.I) else part
        if part == "&lt;i&gt;":
            depth += 1
            out.append("<i>")
        elif part == "&lt;/i&gt;":
            if depth:
                depth -= 1
                out.append("</i>")
        else:
            out.append(part)
    return "".join(out).replace("\n", "<br>") + "</i>" * depth


def quoted(text: str) -> str:
    """Text in quotation marks, unless it already opens with one."""
    return text if text[:1] in ('"', "“", "「", "『") else f"“{text}”"


def plain(text: str, limit: int | None = None) -> str:
    """Game text as one line without markup; past limit, cut at a word and marked with an ellipsis."""
    text = " ".join(_ANY_TAG.sub("", _OPEN_ITALIC.sub(r"\g<0>>", text or "")).split())
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return text


class Archive:
    def __init__(self, db_path: Path, revision: Path):
        self.db_path, self.revision = Path(db_path), Path(revision)

    @contextlib.contextmanager
    def db(self):
        """A read-only connection, closed when the block ends."""
        db = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    @lru_cache(maxsize=None)
    def master(self, table: str) -> list[dict]:
        with self.db() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", ("master:" + table,)).fetchone()
        return json.loads(row[0]) if row else []

    def text(self, key: str, default: str = "") -> str:
        with self.db() as db:
            row = db.execute("SELECT value FROM text WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def texts(self, prefix: str) -> dict[str, str]:
        with self.db() as db:
            return dict(db.execute("SELECT key, value FROM text WHERE key >= ? AND key < ?", (prefix, prefix + "￿")).fetchall())

    def meta(self, key: str, default=None):
        with self.db() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    # ---- Story ----------------------------------------------------------------
    def season_title(self, season: int) -> str:
        return self.text(f"quest.main.season_title.{season}", f"Season {season}")

    def chapter_label(self, season: int, chapter: int) -> tuple[str, str]:
        """(number, title) for a main-story chapter. Chapters regrouped by quest are route * 100 + order and
        named by the game's own labels; without that, Season 1 maps by its 'Ch. N' labels."""
        if chapter >= 100:
            route, order = divmod(chapter, 100)
            number = self.text(f"quest.main.chapter_number.{season}.{route}.{order}")
            title = self.text(f"quest.main.chapter_title.{season}.{route}.{order}")
            return (number or f"Chapter {order}"), (title if title and title != number else "")
        if chapter == 0:
            return "Prologue", ""
        if chapter == 99:
            return "Other scenes", ""
        if season == 1:
            numbers = self.texts("quest.main.chapter_number.1.1.")
            for key, label in numbers.items():
                if re.match(rf"Ch\. {chapter}\b", label):
                    return label, self.text(key.replace("chapter_number", "chapter_title"))
        return f"Chapter {chapter}", ""

    def main_chapters(self) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT season, chapter, count(*) scenes, sum(lines) lines FROM scene WHERE area='main' "
                              "GROUP BY season, chapter ORDER BY season, chapter = 99, chapter").fetchall()
        seasons = {}
        for r in rows:
            number, title = self.chapter_label(r["season"], r["chapter"])
            seasons.setdefault(r["season"], {"season": r["season"], "title": self.season_title(r["season"]), "chapters": []})
            seasons[r["season"]]["chapters"].append({"chapter": r["chapter"], "number": number, "title": title,
                                                     "scenes": r["scenes"], "lines": r["lines"],
                                                     "preview": self.first_line("main", r["season"], r["chapter"])})
        return list(seasons.values())

    def first_line(self, area, season, chapter) -> str:
        with self.db() as db:
            row = db.execute("SELECT line.text FROM scene JOIN line ON line.scene = scene.id WHERE area=? AND season=? AND chapter=? "
                             "AND kind != 'narration' AND length(line.text) > 12 ORDER BY sort, seq LIMIT 1", (area, season, chapter)).fetchone()
        return plain(row[0] if row else "", 90)

    def sub_groups(self, kind: str) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT scene.grp, season, count(*) scenes, sum(lines) lines, min(id) first, story_group.title FROM scene "
                              "LEFT JOIN story_group ON story_group.kind = scene.kind AND story_group.grp = scene.grp "
                              "WHERE scene.kind=? GROUP BY scene.grp ORDER BY season, scene.grp", (kind,)).fetchall()
            out = []
            for r in rows:
                line = db.execute("SELECT text FROM line WHERE scene=? AND length(text) > 12 ORDER BY seq LIMIT 1", (r["first"],)).fetchone()
                out.append({**dict(r), "preview": plain(line[0] if line else "", 90)})
        return out

    def group_title(self, kind: str, grp: str) -> str:
        """The story's name (a character, an event), or "" when the index has none."""
        with self.db() as db:
            row = db.execute("SELECT title FROM story_group WHERE kind=? AND grp=?", (kind, grp)).fetchone()
        return row[0] if row else ""

    def scenes(self, *, area=None, season=None, chapter=None, kind=None, grp=None) -> list[dict]:
        where, args = [], []
        for column, value in (("area", area), ("season", season), ("chapter", chapter), ("kind", kind), ("grp", grp)):
            if value is not None:
                where.append(column + "=?"); args.append(value)
        with self.db() as db:
            rows = db.execute("SELECT * FROM scene WHERE " + " AND ".join(where) + " ORDER BY grp, sort, name", args).fetchall()
            out = []
            for r in rows:
                line = db.execute("SELECT text FROM line WHERE scene=? AND length(text) > 3 ORDER BY seq LIMIT 1", (r["id"],)).fetchone()
                out.append({**dict(r), "preview": plain(line[0] if line else "", 100)})
        return out

    def scene(self, scene_id: int) -> dict | None:
        with self.db() as db:
            row = db.execute("SELECT * FROM scene WHERE id=?", (scene_id,)).fetchone()
            if not row:
                return None
            lines = [{"text": r[0], "voice": r[1], "speaker": r[2]}
                     for r in db.execute("SELECT text, voice, speaker FROM line WHERE scene=? ORDER BY seq", (scene_id,))]
            if row["area"] == "main":
                siblings = db.execute("SELECT id FROM scene WHERE area='main' AND season=? AND chapter=? ORDER BY grp, sort, name",
                                      (row["season"], row["chapter"])).fetchall()
            else:
                siblings = db.execute("SELECT id FROM scene WHERE kind=? AND grp=? ORDER BY sort, name", (row["kind"], row["grp"])).fetchall()
        ids = [s[0] for s in siblings]
        at = ids.index(scene_id)
        return {**dict(row), "lines": lines, "position": at + 1, "count": len(ids),
                "previous": ids[at - 1] if at > 0 else None, "next": ids[at + 1] if at + 1 < len(ids) else None}

    def recollections(self) -> list[dict]:
        """The Library's chapter summaries, with their titles."""
        groups = []
        main = self.texts("story.Main.Quest.")
        titles = self.texts("mqt.")
        if main:
            items = []
            for key, value in sorted(main.items()):
                number = key.rsplit(".", 1)[-1].lstrip("0")
                items.append({"title": titles.get(f"mqt.{number}p1", ""), "subtitle": titles.get(f"mqt.{number}p2", ""), "text": value})
            groups.append({"name": "Main story", "items": items})
        for prefix, name in (("quest.event.chapter.story.01.", "Event stories"), ("quest.event.chapter.story.06.", "Character stories"),
                             ("limit.content.story.", "Limited content"), ("content.story.", "End contents")):
            entries = self.texts(prefix)
            if entries:
                groups.append({"name": name, "items": [{"title": "", "subtitle": "", "text": v} for _, v in sorted(entries.items())]})
        return groups

    # ---- Records --------------------------------------------------------------
    def weapons(self) -> list[dict]:
        names = self.texts("weapon.name.wp")
        stories = self.texts("weapon.story.wp")
        weapons = {}
        for key, value in stories.items():
            wp, index = key.split(".")[2], key.split(".")[3]
            weapons.setdefault(wp, {"id": wp, "name": names.get(f"weapon.name.{wp}.1") or names.get(f"weapon.name.{wp}.2") or wp, "stories": {}})
            weapons[wp]["stories"][int(index)] = value
        out = []
        for w in sorted(weapons.values(), key=lambda w: w["name"]):
            w["stories"] = [w["stories"][i] for i in sorted(w["stories"])]
            out.append(w)
        return out

    def character_name(self, character_id) -> str:
        name = self.text(f"character.name.{character_id}") or self.text(f"character.name.{character_id}.1")
        if name:
            return name
        # Story-only characters have no name of their own; their costume's name stands in.
        with self.db() as db:
            assets = [r[0] for r in db.execute("SELECT asset FROM costume WHERE character=? ORDER BY costume", (character_id,))]
        for asset in assets:
            costume = self.text(f"costume.name.{asset}")
            if costume and costume != "-":
                return costume
        return "Unnamed"

    def reports(self) -> list[dict]:
        groups = {}
        for row in sorted(self.master("m_report"), key=lambda r: (r["MainQuestSeasonId"], r["CharacterId"], r["ReportNumber"])):
            asset = row["ReportAssetId"]
            body = self.text(f"report.description.{asset}")
            if not body:
                continue
            group = groups.setdefault((row["MainQuestSeasonId"], row["CharacterId"]),
                                      {"season": row["MainQuestSeasonId"], "character": self.character_name(row["CharacterId"]), "items": []})
            group["items"].append({"title": self.text(f"report.title.{asset}", f"No. {row['ReportNumber']:02d}"), "text": body})
        return list(groups.values())

    def lost_archives(self) -> list[dict]:
        out = []
        for row in sorted(self.master("m_cage_memory"), key=lambda r: (r["MainQuestSeasonId"], r["SortOrder"])):
            asset = row["CageMemoryAssetId"]
            body = self.text(f"cage.memory.description.{asset}")
            if body:
                out.append({"season": row["MainQuestSeasonId"], "title": self.text(f"cage.memory.title.{asset}", str(asset)), "text": body})
        return out

    def debris(self) -> list[dict]:
        names = self.texts("thought.name.")
        return [{"title": v, "text": self.text("thought.description." + k.rsplit(".", 1)[-1])} for k, v in sorted(names.items())]

    # ---- Movies ---------------------------------------------------------------
    def movie_files(self) -> dict[str, dict]:
        with self.db() as db:
            return {r["name"]: dict(r) for r in db.execute("SELECT * FROM movie")}

    def pick_movie(self, base: str, files: dict) -> dict | None:
        """The English cut when there is one, else the default."""
        return files.get(base + "_en") or files.get(base)

    def movies(self) -> list[dict]:
        files = self.movie_files()
        assets = {m["MovieId"]: m["AssetId"] for m in self.master("m_movie")}
        categories = {c["LibraryMovieCategoryId"]: c for c in self.master("m_library_movie_category")}
        library, used = {}, set()
        for row in sorted(self.master("m_library_movie"), key=lambda r: (r["LibraryMovieCategoryId"], r["SortOrder"])):
            asset = assets.get(row["MovieId"])
            if asset is None:
                continue
            base = f"mv_prm{asset:03d}" if asset < 100 else f"mv{asset}"
            file = self.pick_movie(base, files)
            if not file:
                continue
            used.add(base)
            category = categories.get(row["LibraryMovieCategoryId"], {})
            # The game's own key is spelled "catagory".
            name = (self.text(f"movie.catagory.{category.get('NameLibraryTextId')}")
                    or self.text(f"movie.catagory.{100 + row['LibraryMovieCategoryId']}") or "Library movies")
            library.setdefault(row["LibraryMovieCategoryId"], {"name": name, "items": []})["items"].append(
                {"title": self.text(f"movie.title.name.{row['TitleLibraryTextId']}", base), "file": file["file"], "size": file["size"]})
        groups = list(library.values())
        bases = sorted({re.sub(r"_(en|ko|ja)$", "", n) for n in files})
        scenes = [b for b in bases if b.startswith("mm") and "voice" not in b]
        promos = [b for b in bases if b.startswith("mv") and b not in used]
        for name, items in (("Story scenes", scenes), ("Other movies", promos)):
            entries = [{"title": b, "file": f["file"], "size": f["size"]} for b in items if (f := self.pick_movie(b, files))]
            if entries:
                groups.append({"name": name, "items": entries})
        return groups

    # ---- Search ---------------------------------------------------------------
    def search(self, query: str, limit: int = 60) -> dict:
        query = query.strip()
        if len(query) < 2:
            return {"lines": [], "records": []}
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with self.db() as db:
            lines = db.execute("SELECT scene.id, scene.area, scene.kind, scene.season, scene.chapter, scene.name, line.text, story_group.title "
                               "FROM line JOIN scene ON scene.id = line.scene LEFT JOIN story_group ON story_group.kind = scene.kind "
                               "AND story_group.grp = scene.grp WHERE line.text LIKE ? ESCAPE '\\' LIMIT ?", (like, limit)).fetchall()
            records = db.execute("SELECT key, value FROM text WHERE (key LIKE 'weapon.story.%' OR key LIKE 'report.description.%' "
                                 "OR key LIKE 'cage.memory.description.%') AND value LIKE ? ESCAPE '\\' LIMIT ?", (like, limit)).fetchall()
        return {"lines": [dict(r) for r in lines], "records": [dict(r) for r in records]}

    # ---- Characters -----------------------------------------------------------
    def characters(self) -> list[dict]:
        order = {r["CharacterId"]: r.get("SortOrder", 0) for r in self.master("m_character")}
        with self.db() as db:
            rows = db.execute("SELECT character, count(*) costumes, min(costume) first FROM costume GROUP BY character").fetchall()
            out = []
            for r in rows:
                first = db.execute("SELECT asset FROM costume WHERE character=? ORDER BY costume LIMIT 1", (r["character"],)).fetchone()[0]
                out.append({"id": r["character"], "name": self.character_name(r["character"]), "costumes": r["costumes"],
                            "icon": f"ui/costume/{first}/{first}_portrait.assetbundle"})
        # Characters with names of their own come first; story-only ones (named by a costume) last.
        named = lambda c: bool(self.text(f"character.name.{c['id']}") or self.text(f"character.name.{c['id']}.1"))
        return sorted(out, key=lambda c: (not named(c), order.get(c["id"], 0), c["id"]))

    def character(self, character_id: int) -> dict | None:
        with self.db() as db:
            rows = db.execute("SELECT * FROM costume WHERE character=? ORDER BY costume", (character_id,)).fetchall()
        if not rows:
            return None
        costumes = []
        for r in rows:
            asset = r["asset"]
            name = self.text(f"costume.name.{asset}")
            costumes.append({"asset": asset, "name": name if name and name != "-" else asset, "rarity": r["rarity"],
                             "story": self.text(f"costume.description.{asset}"),
                             "portrait": f"ui/costume/{asset}/{asset}_portrait.assetbundle",
                             "full": self.costume_art(asset)})
        with self.db() as db:
            rows = db.execute("SELECT kind, path FROM character_voice WHERE character=? ORDER BY seq", (character_id,)).fetchall()
        voices, counts = [], {}
        for kind, path in rows:
            counts[kind] = counts.get(kind, 0) + 1
            voices.append({"label": f"{self.VOICE_KINDS.get(kind, kind)} {counts[kind]}", "path": path})
        return {"id": character_id, "name": self.character_name(character_id), "costumes": costumes, "voices": voices}

    # Out-of-game voice files carry no text; their name prefix says where the game plays them.
    VOICE_KINDS = {"pfv": "Profile", "enh": "Upgrade", "bkt": "Line"}

    # ---- Music -------------------------------------------------------------------
    def music(self) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT track, part, path FROM music ORDER BY track, part").fetchall()
        tracks = {}
        for r in rows:
            tracks.setdefault(r["track"], {"track": r["track"], "parts": []})["parts"].append({"part": r["part"], "path": r["path"]})
        return list(tracks.values())

    def costume_art(self, asset: str) -> str | None:
        """The costume's full art; a few costumes have only the large card."""
        for kind in ("full", "large"):
            path = f"ui/costume/{asset}/{asset}_{kind}.assetbundle"
            if (self.revision / "assetbundle" / path).is_file():
                return path
        return None

    def costume(self, asset: str) -> dict | None:
        with self.db() as db:
            row = db.execute("SELECT character FROM costume WHERE asset=?", (asset,)).fetchone()
        if not row:
            return None
        found = self.character(row[0])
        at = next(i for i, c in enumerate(found["costumes"]) if c["asset"] == asset)
        siblings = found["costumes"]
        return {**siblings[at], "character": found, "position": at + 1, "count": len(siblings),
                "previous": siblings[at - 1]["asset"] if at > 0 else None,
                "next": siblings[at + 1]["asset"] if at + 1 < len(siblings) else None}

    # ---- Gallery ----------------------------------------------------------------
    GALLERY_TABS = (("stills", "Stills"), ("events", "Event scenes"), ("library", "Library art"), ("photos", "Photos"))
    LIBRARY_GROUPS = {"stained_glass": "Stained glass", "report": "Report art", "cage_memory": "Lost Archives",
                      "content": "End contents", "limit_content": "Limited contents", "event_quest_type_01": "Event backdrops",
                      "event_quest_type_06": "Character story backdrops", "movie": "Movie covers", "record": "Record covers"}

    def group_label(self, category: str, grp: str) -> str:
        if category == "stills":
            return grp.replace("season", "Season ")
        if category == "library":
            return self.LIBRARY_GROUPS.get(grp, grp.replace("_", " ").capitalize())
        if category == "photos":
            return "Photos"
        return grp.upper()

    def gallery(self, category: str) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT grp, count(*) n, min(path) cover FROM image WHERE category=? GROUP BY grp ORDER BY grp", (category,)).fetchall()
        return [{"grp": r["grp"], "label": self.group_label(category, r["grp"]), "count": r["n"], "cover": r["cover"]} for r in rows]

    def gallery_images(self, category: str, grp: str) -> list[dict]:
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM image WHERE category=? AND grp=? ORDER BY name", (category, grp))]

    def image(self, path: str) -> dict | None:
        with self.db() as db:
            row = db.execute("SELECT * FROM image WHERE path=?", (path,)).fetchone()
            if not row:
                return None
            names = [r[0] for r in db.execute("SELECT path FROM image WHERE category=? AND grp=? ORDER BY name", (row["category"], row["grp"]))]
        at = names.index(path)
        return {**dict(row), "label": self.group_label(row["category"], row["grp"]), "position": at + 1, "count": len(names),
                "previous": names[at - 1] if at > 0 else None, "next": names[at + 1] if at + 1 < len(names) else None}

    # ---- 3D motions -------------------------------------------------------------
    MOTION_GROUPS = {"tw": "field", "bt": "battle"}

    def motions(self, asset: str) -> list[dict]:
        """The body motions for a costume's skeleton family (ch008001 -> ch008): field first, then battle."""
        family = asset[:5]
        folder = self.revision / "assetbundle" / "3d" / "motion" / family / "general"
        out = []
        for f in sorted(folder.glob("anim_*.assetbundle")) if folder.is_dir() else []:
            m = re.fullmatch(rf"anim_(tw|bt)_{family}_(.+)", f.stem)
            if not m:
                continue
            parts = m.group(2).split("_")
            if any(re.fullmatch(r"ch\d{6}", w) and w != asset for w in parts):
                continue  # another costume's own version of a move
            words = [w for w in parts if not w.isdigit() and not re.fullmatch(r"ch\d{6}", w) and w not in ("lp", "st", "en")]
            label = " ".join(words).capitalize() or m.group(2)
            numbers = [w.lstrip("0") or "0" for w in parts if w.isdigit()]
            if numbers and numbers != ["1"]:
                label += " " + ".".join(numbers)
            phases = {"st": "start", "lp": "loop", "en": "end"}
            ending = [phases[w] for w in parts[-2:] if w in phases]
            out.append({"clip": f.stem, "group": self.MOTION_GROUPS[m.group(1)], "label": label + (f" ({', '.join(ending)})" if ending else "")})
        # Names that still collide (rare spellings of one move) get a number each.
        seen = {}
        for m in out:
            key = (m["group"], m["label"])
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                m["label"] += f" · {seen[key]}"
        return sorted(out, key=lambda m: (m["group"] != "field", not m["label"].lower().startswith("idle"), m["label"]))
