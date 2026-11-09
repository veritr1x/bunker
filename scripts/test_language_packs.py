import json
import tempfile
import unittest
from pathlib import Path

from language_packs import build_pack, write_shipped


class LanguagePacksTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.translations = Path(self.dir.name) / "translations"
        self.out = Path(self.dir.name) / "out"

    def put(self, rel, data):
        path = self.translations / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_pack_merges_areas_and_master(self):
        self.put("game/ui/pt-BR.json", {"a": "x"})
        self.put("game/skill/pt-BR.json", {"b": "y", "c": ""})
        self.put("game/ui/en.json", {"a": "A"})
        self.put("master/pt-BR.json", {"m_gift_text.1": "z"})
        pack = build_pack(self.translations, "pt-BR", "Português")
        self.assertEqual(pack["format"], 1)
        self.assertEqual(pack["language"], "pt-BR")
        self.assertEqual(pack["name"], "Português")
        self.assertEqual(pack["game"], {"a": "x", "b": "y"})
        self.assertEqual(pack["master"], {"m_gift_text.1": "z"})

    def test_version_follows_the_content(self):
        self.put("game/ui/pt-BR.json", {"a": "x"})
        first = build_pack(self.translations, "pt-BR", "P")["version"]
        self.assertEqual(first, build_pack(self.translations, "pt-BR", "P")["version"])
        self.assertRegex(first, r"^[0-9a-f]{12}$")
        self.put("game/ui/pt-BR.json", {"a": "y"})
        self.assertNotEqual(first, build_pack(self.translations, "pt-BR", "P")["version"])

    def test_only_shipped_languages_are_written(self):
        self.put("languages.json", {"pt-BR": {"name": "Português", "ship": True}, "pl": {"name": "Polski", "ship": False}})
        self.put("game/ui/pt-BR.json", {"a": "x"})
        self.put("game/ui/pl.json", {"a": "y"})
        self.out.mkdir()
        (self.out / "fr.json").write_text("{}")
        written = write_shipped(self.translations, self.out)
        self.assertEqual([p.name for p in written], ["pt-BR.json"])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["pt-BR.json"])
        pack = json.loads((self.out / "pt-BR.json").read_text(encoding="utf-8"))
        self.assertEqual((pack["language"], pack["game"]), ("pt-BR", {"a": "x"}))

    def test_game_languages_are_never_shipped(self):
        self.put("languages.json", {"ja": {"name": "日本語", "ship": True}, "en": {"name": "English", "ship": True}})
        self.put("game/ui/ja.json", {"a": "エー"})
        self.assertEqual(write_shipped(self.translations, self.out), [])

    def test_no_languages(self):
        self.put("languages.json", {})
        self.assertEqual(write_shipped(self.translations, self.out), [])


if __name__ == "__main__":
    unittest.main()
