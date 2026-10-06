"""Read-side queries over the Archive index: what each page lists."""
from __future__ import annotations

import contextlib
import html
import json
import re
import sqlite3
import time
from collections import Counter
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

    LIBRARY_SECTIONS = ("Season 1", "Season 2", "Season 3", "Events", "Character Quests", "Recollections of Dusk", "Dark Memories")

    def recollections(self) -> list[dict]:
        """The Library's summaries as the game files them: each season by chapter, events by name, and the
        Character Quests, Recollections of Dusk and Dark Memories by character."""
        with self.db() as db:
            rows = db.execute("SELECT section, heading, title, text, art FROM library ORDER BY section, heading_sort, heading, sort").fetchall()
        sections = []
        for section, heading, title, text, art in rows:
            name = self.LIBRARY_SECTIONS[section]
            if name.startswith("Season "):
                name += f" · {self.season_title(int(name.split()[1]))}"
            if not sections or sections[-1]["name"] != name:
                unit = "chapter" if name.startswith("Season ") else "event" if name == "Events" else "character"
                sections.append({"name": name, "unit": unit, "headings": []})
            headings = sections[-1]["headings"]
            if not headings or headings[-1]["name"] != heading:
                headings.append({"name": heading, "items": []})
            headings[-1]["items"].append({"title": title, "text": text, "art": art})
        return sections

    # ---- Records --------------------------------------------------------------
    def weapons(self) -> list[dict]:
        """Every weapon with stories, with its art (ui/weapon/<id>/<id>_full) and model asset. The game keeps
        two "Defective" versions under weapon.story.replace.<id>; they share their weapon's art and model."""
        names = self.weapon_names()
        weapons = {}
        for key, value in self.texts("weapon.story.").items():
            parts = key.split(".")
            prefix = "replace." if parts[2] == "replace" else ""
            asset, index = parts[-2], parts[-1]
            # Skip placeholders ("-": wp004512) and a stray copy keyed wp00650529.
            if not index.isdigit() or not re.fullmatch(r"wp\d{6}", asset) or value.strip() in ("", "-"):
                continue
            name = names.get(prefix + asset) or asset
            weapons.setdefault(prefix + asset, {"id": prefix + asset, "asset": asset, "name": name, "art": self.weapon_art(asset), "stories": {}})
            weapons[prefix + asset]["stories"][int(index)] = value
        out = []
        for w in sorted(weapons.values(), key=lambda w: w["name"]):
            w["stories"] = [w["stories"][i] for i in sorted(w["stories"])]
            out.append(w)
        return out

    def weapon_art(self, asset: str) -> str | None:
        path = f"ui/weapon/{asset}/{asset}_full.assetbundle"
        return path if (self.revision / "assetbundle" / path).is_file() else None

    def weapon_names(self) -> dict[str, str]:
        """Weapon (or replace.<weapon>) -> name. Keys end in the weapon's evolution step, which
        need not start at 1 (Hamelin Prototype Sword II is wp001043.5-7), so take the lowest."""
        found = {}
        for key, value in self.texts("weapon.name.").items():
            head, _, step = key.removeprefix("weapon.name.").rpartition(".")
            if step.isdigit() and value and (head not in found or int(step) < found[head][0]):
                found[head] = (int(step), value)
        return {head: value for head, (_, value) in found.items()}

    def weapon_name(self, asset: str) -> str:
        return self.weapon_names().get(asset, "")

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
        """Each Debris with its picture (ui/thought/thought<id>/thought<id>_standard)."""
        out = []
        for key, name in sorted(self.texts("thought.name.").items()):
            number = key.rsplit(".", 1)[-1]
            art = f"ui/thought/thought{number}/thought{number}_standard.assetbundle"
            out.append({"title": name, "text": self.text(f"thought.description.{number}"),
                        "art": art if (self.revision / "assetbundle" / art).is_file() else None})
        return out

    def memoirs(self) -> list[dict]:
        """Memoirs by series, in the game's order; each with its text and picture (ui/memory/memory<asset>)."""
        series = {r["PartsSeriesId"]: r for r in self.master("m_parts_series")}
        groups = {}
        for row in sorted(self.master("m_parts_group"), key=lambda r: (r["PartsSeriesId"], r["SortOrder"], r["PartsGroupId"])):
            text = self.text(f"parts.group.description.{row['PartsGroupId']}")
            name = self.text(f"parts.group.name.{row['PartsGroupId']}")
            if not name or not text:
                continue
            s = series.get(row["PartsSeriesId"], {})
            group = groups.setdefault(row["PartsSeriesId"], {"name": self.text(f"parts.series.name.{s.get('PartsSeriesAssetId', row['PartsSeriesId'])}")
                                                             or "Other", "items": []})
            asset = f"memory{row['PartsGroupAssetId']:03d}"
            art = next((p for kind in ("full", "standard") if (self.revision / "assetbundle" / (p := f"ui/memory/{asset}/{asset}_{kind}.assetbundle")).is_file()), None)
            group["items"].append({"title": name, "text": text, "art": art})
        return list(groups.values())

    # ---- Movies ---------------------------------------------------------------
    def movie_files(self) -> dict[str, dict]:
        with self.db() as db:
            return {r["name"]: dict(r) for r in db.execute("SELECT * FROM movie")}

    # A movie's files: plain, _en/_ko/_ja cuts, or <voice>voice_<text>text variants. English first.
    MOVIE_CUTS = ("_envoice_entext", "_en", "", "_javoice_entext", "_ja", "_envoice_kotext", "_javoice_kotext", "_ko")

    def pick_movie(self, base: str, files: dict) -> dict | None:
        """The English cut when there is one, else the default, else whatever language there is."""
        for cut in self.MOVIE_CUTS:
            if base + cut in files:
                return files[base + cut]
        return None

    @staticmethod
    def movie_base(name: str) -> str:
        """mm01010801_envoice_entext -> mm01010801; the doubled mmmm02010101 is mm02010101."""
        name = re.sub(r"_(?:(?:en|ja|ko)voice_(?:en|ja|ko)text|en|ja|ko)$", "", name)
        return re.sub(r"^mmmm", "mm", name)

    def movies(self) -> list[dict]:
        """Each season's Library cutscenes and story scenes, the title-screen movies, then the clips the game's
        announcements played (summons, new areas, anniversaries) by year, titled by their caption."""
        files = {}
        for name, f in self.movie_files().items():
            files[name] = f
            base = self.movie_base(name)
            if base != name and name.startswith("mmmm"):  # keep the doubled name findable under its real one
                files.setdefault("mm" + name[4:], f)
        bases = sorted({self.movie_base(n) for n in files})
        season_groups = {}

        def season_group(season):
            return season_groups.setdefault(season, {"name": f"Season {season} · {self.season_title(season)}", "items": []})

        assets = {m["MovieId"]: m["AssetId"] for m in self.master("m_movie")}
        used = set()
        # The Library's cutscenes: categories 1-3 are the seasons ("2020", "2021", and an unnamed 2022);
        # 101 is the title-screen movies.
        title_screen = {"name": "Title screen", "items": []}
        for row in sorted(self.master("m_library_movie"), key=lambda r: (r["LibraryMovieCategoryId"], r["SortOrder"])):
            asset = assets.get(row["MovieId"], row["MovieId"])
            base = f"mv_prm{asset:03d}" if asset < 100 else f"mv{asset}"
            file = self.pick_movie(base, files)
            if not file:
                continue
            used.add(base)
            category = row["LibraryMovieCategoryId"]
            title = self.text(f"movie.title.name.{row['TitleLibraryTextId']}") or ("Untitled title-screen movie" if category >= 100 else base)
            item = {"title": title, "file": file["file"], "size": file["size"]}
            (title_screen if category >= 100 else season_group(category))["items"].append(item)
        for base in bases:  # title-screen movies the Library does not list (mv103)
            if re.fullmatch(r"mv1\d\d", base) and base not in used and (file := self.pick_movie(base, files)):
                used.add(base)
                title = self.text(f"movie.title.name.{100000 + int(base[2:]) - 100}") or base
                title_screen["items"].append({"title": title, "file": file["file"], "size": file["size"]})
        title_screen["items"].sort(key=lambda m: m["file"])
        # Story scenes: mm + season + route + chapter order + part, named by the chapter.
        for base in bases:
            m = re.fullmatch(r"mm(\d\d)(\d\d)(\d\d)(\d\d)", base)
            file = self.pick_movie(base, files)
            if not m or not file:
                continue
            used.add(base)
            season, route, order, part = (int(x) for x in m.groups())
            chapter = self.text(f"quest.main.chapter_number.{season}.{route}.{order}") or f"Chapter {order}"
            season_group(season)["items"].append({"title": f"{chapter} · Part {part}", "file": file["file"], "size": file["size"]})
        groups = [season_groups[s] for s in sorted(season_groups)] + ([title_screen] if title_screen["items"] else [])
        # Announcements: the clip, its caption, and when it ran.
        captions = {r["DokanTextId"]: r["Text"] for r in self.master("m_dokan_text")}
        starts = {r["DokanContentGroupId"]: r["StartDatetime"] for r in self.master("m_dokan")}
        rows = {}
        for r in sorted(self.master("m_dokan_content_group"), key=lambda r: (r["DokanContentGroupId"], r["ContentIndex"])):
            rows.setdefault(r["DokanContentGroupId"], []).append(r)
        seen = Counter(plain(captions.get(r["DokanTextId"], "")) for group in rows.values() for r in group)
        names = {v for k, v in self.texts("character.name.").items() if v and len(v) > 2}

        def caption(own, lines):
            # The most telling line: one naming a character ("a new costume for Dimos"), else one this pop-up
            # alone has, else the clip's own; the game reuses lines like "Summons have started" everywhere.
            candidates = [own] + [line for line in lines if line != own]
            candidates = [line for line in candidates if line not in ("", "-")]
            return max(candidates, key=lambda line: (any(n in line for n in names), seen[line] == 1), default="")

        announced = {}
        for group, contents in sorted(rows.items(), key=lambda g: starts.get(g[0], 0)):
            lines = [plain(captions.get(r["DokanTextId"], "")) for r in contents]
            for r in contents:
                base = f"mv_prm{r['MovieId']:03d}"
                if not r["MovieId"] or base in used or base in announced or not (file := self.pick_movie(base, files)):
                    continue
                title = caption(plain(captions.get(r["DokanTextId"], "")), lines)
                start = starts.get(group, 0)
                year = time.gmtime(start / 1000).tm_year if start else 0
                first = re.match(r"(.+?[.!?])\s", title + " ")  # its first sentence carries it
                announced[base] = {"title": plain(first.group(1) if first and len(first.group(1)) > 15 else title, 90),
                                   "file": file["file"], "size": file["size"],
                                   "when": time.strftime("%b %Y", time.gmtime(start / 1000)) if start and year < 2090 else "",
                                   "year": year if year < 2090 else 0}
        by_year, others = {}, []
        for base, item in announced.items():
            if item["year"] and item["title"]:
                by_year.setdefault(item["year"], []).append(item)
            else:
                others.append((base, item))
        for year in sorted(by_year):
            groups.append({"name": f"Announcements · {year}", "items": by_year[year]})
        used.update(announced)
        others += [(b, {"title": "", "file": f["file"], "size": f["size"]}) for b in bases
                   if b not in used and not b.startswith("mmmm") and (f := self.pick_movie(b, files))]
        if others:  # clips no announcement dates or captions
            number = lambda base: int(re.sub(r"\D", "", base) or 0)  # noqa: E731 (no backslashes in f-strings before 3.12)
            groups.append({"name": "Other clips", "items": [
                {**item, "title": item["title"] or f"Untitled clip {number(base)}"} for base, item in sorted(others)]})
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
    MUSIC_SECTIONS = ("Season 1", "Season 2", "Season 3", "Character stories", "Events", "Side stories", "Battle")

    def music(self) -> list[dict]:
        """The soundtrack, each track filed under where it is first heard (the game has no titles for it):
        a season's chapter, a character's stories, an event, a side story, or battle; with the other places."""
        with self.db() as db:
            rows = db.execute("SELECT track, part, path FROM music ORDER BY track, part").fetchall()
            uses = db.execute("SELECT track, section, sort, place FROM music_use ORDER BY section, sort, place").fetchall()
        tracks = {}
        for r in rows:
            if r["track"] == "9999":
                continue  # 8 s of silence (3.9 KB of Vorbis) that maps play to stop the music
            tracks.setdefault(r["track"], {"track": r["track"], "parts": [], "places": [], "where": []})["parts"].append(
                {"part": r["part"], "path": r["path"]})

        def section_name(index):
            name = self.MUSIC_SECTIONS[index] if index is not None else "Other"
            return name + (f" · {self.season_title(int(name.split()[1]))}" if name.startswith("Season ") else "")

        first = {}
        for r in uses:
            track = tracks.get(r["track"])
            if not track or r["place"] in track["places"]:
                continue
            first.setdefault(r["track"], (r["section"], r["sort"]))
            track["places"].append(r["place"])
            # Every place, grouped by section, for the list a track opens.
            name = section_name(r["section"])
            if not track["where"] or track["where"][-1]["name"] != name:
                track["where"].append({"name": name, "places": []})
            track["where"][-1]["places"].append(r["place"])
        sections = {}
        for track in sorted(tracks.values(), key=lambda t: (first.get(t["track"], (99, 0)), int(t["track"]) if t["track"].isdigit() else 0)):
            name = section_name(first.get(track["track"], (None,))[0])
            sections.setdefault(name, {"name": name, "tracks": []})["tracks"].append(track)
        return list(sections.values())

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

    # ---- Companions ---------------------------------------------------------------
    def companions(self) -> list[dict]:
        """The companions in the game's catalogue order, with their art (ui/companion/<asset>/<asset>_<kind>)."""
        order = {r["CompanionId"]: r["SortOrder"] for r in self.master("m_catalog_companion")}
        out, seen = [], set()
        for row in sorted(self.master("m_companion"), key=lambda r: (order.get(r["CompanionId"], 1 << 40), r["CompanionId"])):
            asset = f"cm{row['ActorSkeletonId']:03d}{row['AssetVariationId']:03d}"
            name = self.text(f"companion.name.{asset}")
            if asset in seen or not name or row["CompanionId"] not in order:
                continue
            seen.add(asset)
            art = {kind: path for kind in ("full", "large", "standard")
                   if (self.revision / "assetbundle" / (path := f"ui/companion/{asset}/{asset}_{kind}.assetbundle")).is_file()}
            out.append({"asset": asset, "name": name, "text": self.text(f"companion.description.{asset}"),
                        "card": art.get("standard") or art.get("large"), "full": art.get("full") or art.get("large")})
        return out

    def companion(self, asset: str) -> dict | None:
        found = self.companions()
        at = next((i for i, c in enumerate(found) if c["asset"] == asset), None)
        if at is None:
            return None
        return {**found[at], "position": at + 1, "count": len(found),
                "previous": found[at - 1]["asset"] if at > 0 else None, "next": found[at + 1]["asset"] if at + 1 < len(found) else None}

    # ---- Other models -------------------------------------------------------------
    MODEL_SECTIONS = ("Main cast", "Story characters", "Enemies")
    MODEL_TABS = {"cast": ("Main cast", "Story characters"), "enemies": ("Enemies",)}

    def model_families(self, tab: str, keep=lambda asset: True) -> list[dict]:
        """A Characters tab's other models (those keep() allows), family by family (mt008: Multi-limb Type and its
        looks). Families the game never names come last, numbered, in an "Unnamed" section."""
        sections = self.MODEL_TABS[tab]
        with self.db() as db:
            rows = db.execute("SELECT * FROM model WHERE section IN (%s) ORDER BY section, family, asset" % ",".join("?" * len(sections)),
                              [self.MODEL_SECTIONS.index(s) for s in sections]).fetchall()
        out = []
        for r in rows:
            if not keep(r["asset"]):
                continue
            if not out or out[-1]["family"] != r["family"]:
                out.append({"family": r["family"], "section": self.MODEL_SECTIONS[r["section"]], "name": r["family_name"], "models": []})
            out[-1]["models"].append({"asset": r["asset"], "name": r["name"]})
        unnamed = 0
        for family in out:
            if len(family["models"]) == 1 and family["models"][0]["name"]:
                family["name"] = family["models"][0]["name"]  # one look: its own name (Cursed God: Wind)
            if not family["name"]:
                unnamed += 1
                family["section"], family["name"] = "Unnamed", f"{'Enemy' if tab == 'enemies' else 'Figure'} {unnamed}"
            # Each look is named for itself where it can be, else numbered.
            names = [m["name"] or family["name"] for m in family["models"]]
            for i, m in enumerate(family["models"]):
                m["label"] = names[i] if names.count(names[i]) == 1 else f"{names[i]} · {names[:i + 1].count(names[i])}"
        return [f for f in out if f["section"] != "Unnamed"] + [f for f in out if f["section"] == "Unnamed"]

    def model(self, asset: str, keep=lambda asset: True) -> dict | None:
        with self.db() as db:
            row = db.execute("SELECT section, family FROM model WHERE asset=?", (asset,)).fetchone()
        if not row:
            return None
        tab = next(t for t, sections in self.MODEL_TABS.items() if self.MODEL_SECTIONS[row["section"]] in sections)
        family = next((f for f in self.model_families(tab, keep) if f["family"] == row["family"]), None)
        model = next((m for m in family["models"] if m["asset"] == asset), None) if family else None
        return {"tab": tab, "family": family, "model": model} if model else None

    # ---- Gallery ----------------------------------------------------------------
    GALLERY_TABS = (("stills", "Stills"), ("events", "Event scenes"), ("library", "Library art"), ("photos", "Photos"))
    LIBRARY_GROUPS = {"stained_glass": "Stained glass", "report": "Reports", "cage_memory": "Lost Archives",
                      "content": "Dark Memories", "limit_content": "Recollections of Dusk", "event_quest_type_01": "Events",
                      "event_quest_type_06": "Character Quests", "movie": "Movie covers", "record": "Record covers"}

    def group_label(self, category: str, grp: str) -> str:
        if category == "stills":
            return grp.replace("season", "Season ")
        if category == "library":
            return self.LIBRARY_GROUPS.get(grp, grp.replace("_", " ").capitalize())
        if category == "photos":
            return "Photos"
        return self.group_title("vid", grp) or f"Event {grp}"  # event scenes: their Record event

    def gallery(self, category: str) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT grp, count(*) n, min(path) cover FROM image WHERE category=? GROUP BY grp ORDER BY grp", (category,)).fetchall()
        return [{"grp": r["grp"], "label": self.group_label(category, r["grp"]), "count": r["n"], "cover": r["cover"]} for r in rows]

    def gallery_images(self, category: str, grp: str) -> list[dict]:
        """A group's pictures in order, gathered under their sections (a chapter, a part, a character)."""
        with self.db() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM image WHERE category=? AND grp=? ORDER BY sort, section, name", (category, grp))]
        sections = []
        for r in rows:
            if not sections or sections[-1]["name"] != r["section"]:
                sections.append({"name": r["section"], "items": []})
            sections[-1]["items"].append(r)
        return sections

    def image(self, path: str) -> dict | None:
        with self.db() as db:
            row = db.execute("SELECT * FROM image WHERE path=?", (path,)).fetchone()
            if not row:
                return None
            names = [r[0] for r in db.execute("SELECT path FROM image WHERE category=? AND grp=? ORDER BY sort, section, name",
                                              (row["category"], row["grp"]))]
        at = names.index(path)
        heading = " · ".join(p for p in (row["section"], row["title"]) if p) or row["name"]
        return {**dict(row), "heading": heading, "label": self.group_label(row["category"], row["grp"]), "position": at + 1, "count": len(names),
                "previous": names[at - 1] if at > 0 else None, "next": names[at + 1] if at + 1 < len(names) else None}

    # ---- 3D motions -------------------------------------------------------------
    MOTION_GROUPS = {"tw": "field", "bt": "battle"}

    def motions(self, asset: str) -> list[dict]:
        """The body motions for a model's skeleton family (ch008001 -> ch008): field first, then battle."""
        family = asset[:5]
        folder = self.revision / "assetbundle" / "3d" / "motion" / family / "general"
        out = []
        for f in sorted(folder.glob("anim_*.assetbundle")) if folder.is_dir() else []:
            m = re.fullmatch(rf"anim_(tw|bt)_{family}_(.+)", f.stem)
            if not m:
                continue
            parts = m.group(2).split("_")
            if any(re.fullmatch(r"[a-z]{2}\d{6}", w) and w != asset for w in parts):
                continue  # another costume's own version of a move
            words = [w for w in parts if not w.isdigit() and not re.fullmatch(r"[a-z]{2}\d{6}", w) and w not in ("lp", "st", "en")]
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
