#!/usr/bin/env python3
"""The Archive: scene ordering, text cleanup, safe markup, and (with a dump) a full index build.

The parsing tests need nothing but the repository. Set ARCHIVE_DUMP to an
extracted revisions/0 folder and ARCHIVE_MASTER to 20240404193219.bin.e to also
build the index from real game files and open every page. Needs lz4,
pycryptodome and msgpack; the page test also needs fastapi and jinja2.
"""
from pathlib import Path
import os, re, shutil, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / "android/app/src/main/python"), str(root / "upstream/lunar-base/tools")]
from archive import index  # noqa: E402
from archive.content import plain, rich  # noqa: E402


class Parsing(unittest.TestCase):
    def test_main_scenes_by_season_chapter_and_scene(self):
        self.assertEqual(index.describe_scene("main", "main/season01", "MID_a120_3060g"),
                         {"kind": "mid", "season": 1, "chapter": 12, "group": "a120", "sort": 30600})
        pid = index.describe_scene("main", "main/season01", "PID_a120_3060g")
        self.assertEqual((pid["chapter"], pid["sort"]), (12, 30601))  # right after the matching MID scene
        self.assertEqual(index.describe_scene("main", "main/season02", "2201_003")["chapter"], 1)

    def test_other_scenes_group_by_code(self):
        found = index.describe_scene("sub", "sub/season01", "EID_a01040_1010g")
        self.assertEqual((found["kind"], found["group"], found["season"]), ("eid", "a01040", 1))
        self.assertEqual(index.describe_scene("side", "side", "SID_0000_0010g")["group"], "0000")

    def test_lines_follow_their_numbers(self):
        keys = ["CID_a01040_1010g_00200_01040_1", "CID_a01040_1010g_00110_01040_1", "CID_a01040_1010g_00100_01040_1"]
        ordered = sorted(keys, key=lambda k: index.line_number(k, "CID_a01040_1010g"))
        self.assertEqual(ordered, keys[::-1])

    def test_clean_text(self):
        self.assertEqual(index.clean(r"\nWhere am I?\nWhy?:<TAP>"), "Where am I?\nWhy?")
        self.assertEqual(index.clean("Massive towers.<br><br>The Cage."), "Massive towers.\n\nThe Cage.")

    def test_markup_is_escaped_except_italics(self):
        self.assertEqual(rich("I <i>wasn't</i> human.\n<script>x</script> & <color=red>red</color>"),
                         "I <i>wasn't</i> human.<br>x &amp; red")

    def test_italics_never_leak(self):
        self.assertEqual(rich("<i>Tap. Tap."), "<i>Tap. Tap.</i>")
        self.assertEqual(rich("done</i> here"), "done here")

    def test_upper_case_italics_and_lone_brackets(self):
        self.assertEqual(rich("<I>Hush.</I> Hey Hina! <3"), "<i>Hush.</i> Hey Hina! &lt;3")
        self.assertEqual(rich("<i>charms.</I. As"), "<i>charms.</i>. As")  # a tag missing its ">"

    def test_previews_are_plain_and_cut_at_a_word(self):
        self.assertEqual(plain("<align=center><i>There is someone\nI must see.</i>"), "There is someone I must see.")
        self.assertEqual(plain("Everybody knows them, but nobody knows them well.", 30), "Everybody knows them, but…")

    def test_chapters_follow_the_event_maps_that_play_them(self):
        maps = {"0201002001010c": [["MID_b010_0020g_00100_01060_1", 19008, 0]] * 3,
                "0202002001010c": [["MID_b110_0020g_00100_01060_1", 19008, 0]],
                "0201008011190c": [["MID_b080_0070_00400_01090_1", 0, 0]],  # an ending both routes play
                "0202008011190c": [["MID_b080_0070_00400_01090_1", 0, 0]],
                "0201003001010c": [["MID_a999_0010_00100_00040_0", 0, 0]],  # shared by many chapters
                "0201004001010c": [["MID_a999_0010_00100_00040_0", 0, 0]],
                "0202005001010c": [["MID_a999_0010_00100_00040_0", 0, 0]]}
        self.assertEqual(index.chapter_groups(maps), {"b010": 102, "b110": 202, "b080": 108})

    def test_speakers_from_event_maps_then_the_voice_code(self):
        maps = {"m": [["S_x_00100_01060_1", 19008, 0], ["S_x_00200_01080_1", 2, 61]]}
        lines = [("S_x_00100_01060_1", "S_x", "2"), ("S_x_00200_01080_1", "S_x", "2"),
                 ("S_x_00300_01060_1", "S_x", "2"),  # same voice in the same scene
                 ("S_y_00100_00050_0", "S_y", "2"),  # a system voice: never guessed
                 ("S_x_00100_01060_1", "2201_001", "2")]  # a key from another file: not this line's
        names = {19008: "Hina", 2: "Mama", 61: "Soldier"}
        self.assertEqual(index.line_speakers(lines, maps, names),
                         {"s_x_00100_01060_1": "Hina", "s_x_00200_01080_1": "Soldier", "s_x_00300_01060_1": "Hina"})

    def test_stories_take_their_character_or_event_names(self):
        maps = {"character/0000008001001p": {"paths": ["sub)season01)cid_a02020_1010g"]},
                "endcontents/0008004000001n": {"paths": ["sub)season01)eid_a02020_1010g"]},
                "marathon/0001020001001n": {"paths": ["sub)season01)vid_001020_1"]},
                "side/0001008000001s": {"paths": ["side)sid_0010_0010g", "side)sid_9999_0010g"]},
                "side/0001019000001s": {"paths": ["side)sid_0000_0010g", "side)sid_9999_0010g"]}}
        master = {"m_event_quest_chapter": [{"EventQuestChapterId": 901, "NameEventQuestTextId": 1, "EventQuestSequenceGroupId": 1},
                                            {"EventQuestChapterId": 501, "NameEventQuestTextId": 2, "EventQuestSequenceGroupId": 2}],
                  "m_event_quest_sequence_group": [{"EventQuestSequenceGroupId": 1, "EventQuestSequenceId": 1},
                                                   {"EventQuestSequenceGroupId": 2, "EventQuestSequenceId": 2}],
                  "m_event_quest_sequence": [{"EventQuestSequenceId": 1, "QuestId": 120001}, {"EventQuestSequenceId": 2, "QuestId": 200031}],
                  "m_quest_scene": [{"QuestId": 120001, "EventMapNumberUpper": 8}, {"QuestId": 200031, "EventMapNumberUpper": 1020}],
                  "m_event_quest_chapter_character": [{"EventQuestChapterId": 901, "CharacterId": 1008}]}
        texts = {"character.name.1008": "Rion", "character.name.1019": "Fio", "quest.event.chapter_title.2": "Record: Den of Madness"}
        self.assertEqual(index.story_titles(maps, master, texts),
                         {("cid", "a02020"): "Rion", ("eid", "a02020"): "Rion", ("lid", "a02020"): "Rion",
                          ("vid", "001020"): "Record: Den of Madness", ("sid", "0010"): "Rion", ("sid", "0000"): "Fio",
                          ("sid", "9999"): "Other scenes"})

    def test_library_files_summaries_like_the_game(self):
        texts = {"story.Main.Quest.0002.0016.0305": "S2", "mqt.305p1": "The Bond's Beginning",
                 "quest.main.chapter_number.2.1.2": "The Sun I: The Dawn", "quest.main.chapter_title.2.1.2": "Binding Magick",
                 "quest.event.chapter.story.01.0002.0001": "E", "quest.event.chapter_title.501": "Record: Den of Madness",
                 "quest.event.chapter.story.06.0001.0001": "C", "character.name.1008": "Rion",
                 "limit.content.story.0130003": "L", "character.name.1019": "Fio",
                 "content.story.0005003.000001": "D"}
        master = {"m_main_quest_chapter": [{"MainQuestChapterId": 16, "MainQuestRouteId": 2, "SortOrder": 2}],
                  "m_main_quest_route": [{"MainQuestRouteId": 2, "SortOrder": 1}],
                  "m_event_quest_chapter": [{"EventQuestChapterId": 501, "EventQuestType": 1, "SortOrder": 2, "NameEventQuestTextId": 501,
                                             "EventQuestSequenceGroupId": 0},
                                            {"EventQuestChapterId": 901, "EventQuestType": 6, "SortOrder": 1, "NameEventQuestTextId": 0,
                                             "EventQuestSequenceGroupId": 0},
                                            {"EventQuestChapterId": 500001, "EventQuestType": 11, "SortOrder": 1, "NameEventQuestTextId": 0,
                                             "EventQuestSequenceGroupId": 7}],
                  "m_event_quest_sequence_group": [{"EventQuestSequenceGroupId": 7, "EventQuestSequenceId": 7}],
                  "m_event_quest_sequence": [{"EventQuestSequenceId": 7, "QuestId": 130003}],
                  "m_event_quest_chapter_character": [{"EventQuestChapterId": 901, "CharacterId": 1008},
                                                      {"EventQuestChapterId": 500001, "CharacterId": 1019}]}
        maps = {"endcontents/0005003000001n": {"paths": ["sub)season01)eid_a01040_1010g"]}}
        got = {(section, heading, title, text) for section, heading, _, title, _, text, _ in index.library_entries(texts, master, maps)}
        self.assertEqual(got, {("Season 2", "The Sun I: The Dawn · Binding Magick", "The Bond's Beginning", "S2"),
                               ("Events", "Record: Den of Madness", "", "E"), ("Character Quests", "Rion", "", "C"),
                               ("Recollections of Dusk", "Fio", "", "L"), ("Dark Memories", "a01040", "", "D")})

    def test_models_cover_costumes_weapons_and_more(self):
        from archive.media import Models
        with tempfile.TemporaryDirectory() as folder:
            actors = Path(folder) / "3d" / "actor"
            for asset, bundle in (("ch008001", "sk_ch008001"), ("wp001002", "sk_wp001002"), ("wp005528", "wp005528"),
                                  ("ch019051", "ch019051"), ("cm001001", "sk_cm001001"), ("mt002001", "sk_mt002001"),
                                  ("mt002004", "mt002004"), ("mt042001", "mt042001"), ("oa001001", "sk_oa001001")):
                (actors / asset / "mesh").mkdir(parents=True)
                (actors / asset / "mesh" / f"{bundle}.assetbundle").write_bytes(b"")
            models = Models(Path(folder), Path(folder) / "cache", lambda *a: "")
            # A weapon variant may carry only its prefab (its mesh is a sibling's); a costume may not. An enemy
            # look may borrow its family's skeleton when the family has one. Props (oa) are not shown.
            self.assertEqual([models.has(a) for a in ("ch008001", "wp001002", "wp005528", "ch019051", "../wp001002", "cm001001",
                                                      "mt002004", "mt042001", "oa001001")],
                             [True, True, True, False, False, True, True, False, False])

    def test_mask_name(self):
        base = Path("/a/assetbundle")
        self.assertEqual(index.mask_name(base / "text/en/main/season01/2000_001.assetbundle", base), "text)en)main)season01)2000_001")


@unittest.skipUnless(os.environ.get("ARCHIVE_DUMP") and os.environ.get("ARCHIVE_MASTER"), "set ARCHIVE_DUMP and ARCHIVE_MASTER")
class RealDump(unittest.TestCase):
    def test_build_and_open_every_page(self):
        revision, master = Path(os.environ["ARCHIVE_DUMP"]), Path(os.environ["ARCHIVE_MASTER"])
        # ARCHIVE_SCENARIO: the JSON the Go library's ScenarioToJSON writes for eventmap/main.
        scenario_json = os.environ.get("ARCHIVE_SCENARIO")
        scenario = (lambda folder, target: shutil.copy(scenario_json, target) and "") if scenario_json else None
        with tempfile.TemporaryDirectory() as folder:
            summary = index.build(revision, master, Path(folder) / "archive.db", scenario=scenario)
            self.assertEqual(summary["failed"], 0)
            self.assertGreater(summary["lines"], 20000)
            self.assertTrue(index.is_current(Path(folder) / "archive.db", revision, master))
            from fastapi.testclient import TestClient
            from archive.app import create_app
            client = TestClient(create_app(revision, master, Path(folder), root / "overlays/python/web/static"))
            for path in ("/", "/story", "/story?tab=sub", "/story?tab=side", "/story?tab=recollections", "/story/main/1/1",
                         "/scene/1", "/records", "/records?tab=reports", "/records?tab=archives", "/records?tab=debris",
                         "/movies", "/search?q=cage", "/characters", "/characters/1008", "/costume/ch008001",
                         "/gallery", "/gallery?tab=events", "/gallery?tab=library", "/gallery?tab=photos", "/gallery/stills/season1",
                         "/image?path=ui/still/season1/still_main_1100101.assetbundle", "/music", "/records?tab=memoirs",
                         "/characters?tab=companions", "/characters?tab=cast", "/characters?tab=enemies", "/companion/cm001001",
                         "/gallery/library/content", "/gallery/library/report"):
                self.assertEqual(client.get(path).status_code, 200, path)
            self.assertEqual(client.get("/media/movie/../list.bin").status_code, 404)
            self.assertEqual(client.get("/media/image/thumb/../list.bin").status_code, 404)
            self.assertGreater(summary["costumes"], 250)
            self.assertGreater(summary["images"], 1000)
            self.assertGreater(summary["voiced"], 20000)
            self.assertGreater(summary["tracks"], 300)
            from archive.content import Archive
            archive = Archive(Path(folder) / "archive.db", revision)
            # bgm_delay_settings is timing data, not a track.
            self.assertTrue(all(t["track"].isdigit() for g in archive.music() for t in g["tracks"]))
            # Weapons carry their art; the game's two "Defective" versions are listed too.
            weapons = {w["name"]: w for w in archive.weapons()}
            self.assertGreater(len(weapons), 600)
            self.assertEqual(weapons["Defective Akagi"]["asset"], "wp001516")
            self.assertTrue(weapons["Akagi"]["art"].endswith("wp001516_full.assetbundle"))
            # Names come from the lowest evolution step a weapon has (wp001043.5), and none is left as an id.
            self.assertIn("Hamelin Prototype Sword II", weapons)
            self.assertFalse([n for n in weapons if n.startswith("wp")])
            # Movies: the seasons' cutscenes and story scenes, the title screen, then announcements by year.
            movies = {g["name"]: g["items"] for g in archive.movies()}
            self.assertEqual(list(movies)[:4], ["Season 1 · Girl", "Season 2 · Sun/Moon", "Season 3 · People/World", "Title screen"])
            self.assertIn("The Moon IV: The Gloaming · Part 1", {m["title"] for m in movies["Season 2 · Sun/Moon"]})
            self.assertIn("2022", " ".join(movies))
            self.assertFalse([m for items in movies.values() for m in items if re.fullmatch(r"m[mv]\w*\d+", m["title"])])
            # Season 1's chapter 8 scene plays its English-voice cut.
            self.assertTrue(any(m["file"] == "mm01010801_envoice_entext.mp4" for m in movies["Season 1 · Girl"]))
            # Music: filed where each track is first heard, with the other places; silence is not a track.
            music = {g["name"]: g["tracks"] for g in archive.music()}
            if scenario:
                self.assertEqual(list(music)[:3], ["Season 1 · Girl", "Season 2 · Sun/Moon", "Season 3 · People/World"])
                self.assertIn("Battle", music)
                hina = next(t for t in music["Season 2 · Sun/Moon"] if t["track"] == "1071")
                self.assertEqual(hina["places"][0], "The Sun: Prologue")
            self.assertNotIn("9999", {t["track"] for tracks in music.values() for t in tracks})
            # A costume without full art shows its large card.
            self.assertTrue(archive.costume("ch051001")["full"].endswith("ch051001_large.assetbundle"))
            # Each costume lists its own signature moves only, and no two motions share a name.
            motions = archive.motions("ch008001")
            self.assertFalse(any("ch008004" in m["clip"] for m in motions))
            self.assertEqual(len({(m["group"], m["label"]) for m in motions}), len(motions))
            if scenario:
                # Chapters carry the game's names, and main-story lines their speakers.
                seasons = {s["season"]: s for s in archive.main_chapters()}
                self.assertEqual(seasons[2]["chapters"][0]["number"], "The Sun: Prologue")
                self.assertNotIn("Chapter", " ".join(c["number"] for s in seasons.values() for c in s["chapters"]))
                self.assertGreater(summary["speakers"], 5000)
                first = archive.scene(next(s for s in archive.scenes(area="main", season=2, chapter=102) if s["name"] == "MID_b010_0020g")["id"])
                narration = archive.scene(archive.scenes(area="main", season=2, chapter=102)[0]["id"])
                self.assertFalse(any(line["speaker"] for line in narration["lines"]))
                self.assertIn("Hina", {line["speaker"] for line in first["lines"]})
                # Stories outside the main one carry their character's or event's name.
                self.assertEqual(archive.group_title("eid", "a02020"), "Rion")
                self.assertTrue(archive.group_title("vid", "001020").startswith("Record:"))
                self.assertTrue(all(g["title"] for k in ("eid", "lid", "cid", "vid", "sid") for g in archive.sub_groups(k)))
                # The Library: every summary filed under a named chapter, event or character.
                library = {s["name"]: s for s in archive.recollections()}
                self.assertEqual(len(library), 7)
                self.assertEqual(sum(len(h["items"]) for s in library.values() for h in s["headings"]), 535)
                self.assertTrue(all(h["name"] for s in library.values() for h in s["headings"]))
                self.assertEqual([h["name"] for h in library["Character Quests"]["headings"]][:2], ["Rion", "Gayle"])
            # Gallery pictures carry names: stills by chapter, Library art by what it goes with.
            stills = archive.gallery_images("stills", "season1")
            self.assertEqual(stills[0]["items"][0]["title"], "Still 1")
            self.assertFalse([i for g in stills for i in g["items"] if "still_main" in g["name"]])
            reports = {g["name"]: g["items"] for g in archive.gallery_images("library", "report")}
            self.assertTrue(all(i["title"] for items in reports.values() for i in items))
            self.assertEqual(archive.group_label("library", "content"), "Dark Memories")
            # Companions, Memoirs and Debris with their art; the other models named where the game names them.
            companions = archive.companions()
            self.assertEqual(len(companions), 53)
            self.assertTrue(all(c["full"] for c in companions))
            memoirs = archive.memoirs()
            self.assertGreater(sum(len(g["items"]) for g in memoirs), 100)
            self.assertTrue(all(i["art"] for g in memoirs for i in g["items"]))
            self.assertGreater(sum(1 for d in archive.debris() if d["art"]), 150)
            cast = {f["family"]: f for f in archive.model_families(("Main cast",))}
            self.assertEqual(cast["ma001"]["name"], "Mama")
            enemies = {f["family"]: f for f in archive.model_families(("Enemies",))}
            self.assertEqual(enemies["mt008"]["name"], "Multi-limb Type")
            self.assertFalse([f for f in enemies.values() if "■" in f["name"]])
            if scenario:
                self.assertTrue(archive.group_label("events", "001010").startswith("Record:"))
                self.assertGreater(sum(1 for s in archive.recollections() for h in s["headings"] for i in h["items"] if i["art"]), 300)
            self.assertEqual(client.get("/media/audio/../list.bin").status_code, 404)
            # The 3D viewer's glTF loader fetches embedded textures from blob: URLs.
            policy = client.get("/").headers["content-security-policy"]
            self.assertIn("connect-src 'self' blob:", policy)
            self.assertIn("img-src 'self' data: blob:", policy)


if __name__ == "__main__":
    unittest.main()
