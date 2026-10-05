#!/usr/bin/env python3
"""The Archive: scene ordering, text cleanup, safe markup, and (with a dump) a full index build.

The parsing tests need nothing but the repository. Set ARCHIVE_DUMP to an
extracted revisions/0 folder and ARCHIVE_MASTER to 20240404193219.bin.e to also
build the index from real game files and open every page. Needs lz4,
pycryptodome and msgpack; the page test also needs fastapi and jinja2.
"""
from pathlib import Path
import os, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / "android/app/src/main/python"), str(root / "upstream/lunar-base/tools")]
from archive import index  # noqa: E402
from archive.content import rich  # noqa: E402


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

    def test_mask_name(self):
        base = Path("/a/assetbundle")
        self.assertEqual(index.mask_name(base / "text/en/main/season01/2000_001.assetbundle", base), "text)en)main)season01)2000_001")


@unittest.skipUnless(os.environ.get("ARCHIVE_DUMP") and os.environ.get("ARCHIVE_MASTER"), "set ARCHIVE_DUMP and ARCHIVE_MASTER")
class RealDump(unittest.TestCase):
    def test_build_and_open_every_page(self):
        revision, master = Path(os.environ["ARCHIVE_DUMP"]), Path(os.environ["ARCHIVE_MASTER"])
        with tempfile.TemporaryDirectory() as folder:
            summary = index.build(revision, master, Path(folder) / "archive.db")
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
                         "/image?path=ui/still/season1/still_main_1100101.assetbundle", "/music"):
                self.assertEqual(client.get(path).status_code, 200, path)
            self.assertEqual(client.get("/media/movie/../list.bin").status_code, 404)
            self.assertEqual(client.get("/media/image/thumb/../list.bin").status_code, 404)
            self.assertGreater(summary["costumes"], 250)
            self.assertGreater(summary["images"], 1000)
            self.assertGreater(summary["voiced"], 20000)
            self.assertGreater(summary["tracks"], 300)
            self.assertEqual(client.get("/media/audio/../list.bin").status_code, 404)


if __name__ == "__main__":
    unittest.main()
