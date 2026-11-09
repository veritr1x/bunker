import json
import tempfile
import unittest
from pathlib import Path

from export_translations import game_catalogue, write_catalogue
from game_text import Text

EMPTY_MASTER = {"en": {}, "ja": {}, "ko": {}}


class GameCatalogueTest(unittest.TestCase):
    def test_catalogue_by_area_with_context(self):
        en = {"ui.a": Text("A", "ui"), "skill.b": Text("B", "skill/skill_0000010")}
        ja = {"ui.a": Text("エー", "ui"), "only.ja": Text("x", "ui")}
        cat = game_catalogue(en, {"ja": ja, "ko": {}})
        self.assertEqual(cat["ui"]["en"], {"ui.a": "A"})
        self.assertEqual(cat["ui"]["ja"], {"ui.a": "エー"})
        self.assertEqual(cat["skill"]["en"], {"skill.b": "B"})
        self.assertEqual(cat["skill"]["ja"], {})
        self.assertNotIn("only.ja", cat["ui"]["ja"])
        self.assertEqual(cat["ui"]["ko"], {})

    def test_context_follows_the_english_area(self):
        # the Japanese text sits in another bundle, but the key belongs to its English area
        cat = game_catalogue({"k": Text("K", "skill")}, {"ja": {"k": Text("ケー", "ui")}, "ko": {}})
        self.assertEqual(cat["skill"]["ja"], {"k": "ケー"})
        self.assertNotIn("ui", cat)


class WriteCatalogueTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.out = Path(self.dir.name)

    def test_files_and_format(self):
        game = {"ui": {"en": {"b": "ō…", "a": "x"}, "ja": {}, "ko": {}}}
        written = write_catalogue(self.out, game, {"en": {"m_gift_text.1": "G"}, "ja": {}, "ko": {}})
        text = (self.out / "game/ui/en.json").read_text(encoding="utf-8")
        self.assertEqual(text, '{\n  "a": "x",\n  "b": "ō…"\n}\n')
        self.assertEqual(json.loads((self.out / "master/en.json").read_text(encoding="utf-8")), {"m_gift_text.1": "G"})
        self.assertEqual(sorted(p.relative_to(self.out).as_posix() for p in written), [
            "game/ui/en.json", "game/ui/ja.json", "game/ui/ko.json",
            "master/en.json", "master/ja.json", "master/ko.json"])

    def test_rerun_is_byte_identical(self):
        # The same texts in another order write the same bytes (sorted keys), so a re-export makes no diff.
        game = {"ui": {"en": {"z": "1", "a": "日本"}, "ja": {"a": "日本"}, "ko": {}}}
        reordered = {"ui": {"ko": {}, "ja": {"a": "日本"}, "en": {"a": "日本", "z": "1"}}}
        first = {p: p.read_bytes() for p in write_catalogue(self.out, game, EMPTY_MASTER)}
        second = {p: p.read_bytes() for p in write_catalogue(self.out, reordered, EMPTY_MASTER)}
        self.assertEqual(first, second)

    def test_templates_of_a_dropped_area_are_removed(self):
        write_catalogue(self.out, {"ui": {"en": {"a": "one"}, "ja": {}, "ko": {}},
                                   "old": {"en": {"b": "two"}, "ja": {}, "ko": {}}}, EMPTY_MASTER)
        theirs = self.out / "game/old/pt-BR.json"
        theirs.write_bytes(b'{"b": "dois"}')
        write_catalogue(self.out, {"ui": {"en": {"a": "one"}, "ja": {}, "ko": {}}}, EMPTY_MASTER)
        for lang in ("en", "ja", "ko"):
            self.assertFalse((self.out / f"game/old/{lang}.json").exists(), lang)
            self.assertTrue((self.out / f"game/ui/{lang}.json").exists(), lang)
        # A translation of the dropped area stays, so the check names it (no en.json to translate).
        self.assertEqual(theirs.read_bytes(), b'{"b": "dois"}')

    def test_leaves_translator_files_alone(self):
        theirs = self.out / "game/ui/pt-BR.json"
        theirs.parent.mkdir(parents=True)
        theirs.write_bytes(b'{"a": "um"}')
        write_catalogue(self.out, {"ui": {"en": {"a": "one"}, "ja": {}, "ko": {}}}, EMPTY_MASTER)
        self.assertEqual(theirs.read_bytes(), b'{"a": "um"}')

    def test_escaped_newline_kept(self):
        write_catalogue(self.out, {"ui": {"en": {"a": "a\\nb"}, "ja": {}, "ko": {}}}, EMPTY_MASTER)
        raw = (self.out / "game/ui/en.json").read_text(encoding="utf-8")
        self.assertIn('"a\\\\nb"', raw)
        self.assertEqual(json.loads(raw)["a"], "a\\nb")


if __name__ == "__main__":
    unittest.main()
