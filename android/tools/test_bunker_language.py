#!/usr/bin/env python3
"""Pod Programs › Language: language packs on the device (no FastAPI needed)."""
from pathlib import Path
import json, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))

import bunker_language
from bunker_language import ENGLISH_TEXTS, MAX_PACK_BYTES, Languages, PackError, PackInfo, read_pack


def pack(language="pt-BR", game=None, **extra):
    return json.dumps({"format": 1, "language": language, "name": "Português", "version": "1",
                       "game": {"a": "x"} if game is None else game, **extra}, ensure_ascii=False).encode()


class ReadPackTest(unittest.TestCase):
    def test_reads_a_pack(self):
        info = read_pack(pack(game={"a": "x", "b": "", "c": "l\nl", "d": 7, "e": "r\rx"}))
        self.assertEqual((info.language, info.name, info.version, info.texts), ("pt-BR", "Português", "1", 1))

    def test_refuses_what_is_not_a_pack(self):
        for data in (b"PK\x03\x04", b"{}", json.dumps({"format": 2, "language": "pt", "game": {}}).encode(),
                     json.dumps({"a": "x"}).encode(), json.dumps({"format": 1, "language": "pt", "game": [1]}).encode(),
                     b"\xff\xfe not text"):
            with self.assertRaises(PackError, msg=data[:20]):
                read_pack(data)

    def test_refuses_what_the_server_refuses(self):
        # pack.go reads name and version as strings, refuses NaN, and matches keys ignoring case
        for data in (b'{"format":1,"language":"pt","name":5,"game":{}}',
                     b'{"format":1,"language":"pt","version":1,"game":{}}',
                     b'{"format":1,"language":"pt","game":{"a":NaN}}',
                     b'{"format":1,"FORMAT":2,"language":"pt","game":{}}',
                     b'{"format":1,"language":"pt","Game":{"a":"x"},"game":{}}',
                     b"[" * 200000):
            with self.assertRaises(PackError, msg=data[:40]):
                read_pack(data)

    def test_refuses_an_oversized_pack(self):
        with self.assertRaisesRegex(PackError, "too large"):
            read_pack(b" " * (MAX_PACK_BYTES + 1))

    def test_refuses_a_path_as_language(self):
        for language in ("../../x", "pt/../../y", "", "p", "pt BR", "pt-BR/x", "pt\n"):
            with self.assertRaises(PackError, msg=language):
                read_pack(pack(language=language))

    def test_percent(self):
        info = lambda n: PackInfo("loaded", "pt", "P", "1", n, Path("x"))
        self.assertEqual([info(ENGLISH_TEXTS).percent, info(1436).percent, info(0).percent, info(ENGLISH_TEXTS * 2).percent], [100, 1, 0, 100])


class LanguagesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.translation, self.shipped = base / "translation", base / "shipped"
        self.languages = Languages(self.translation, self.shipped)
        self.active = self.translation / "active.json"

    def test_load_choose_and_active(self):
        data = pack()
        info = self.languages.load(data)
        self.assertEqual((info.source, info.language), ("loaded", "pt-BR"))
        self.assertEqual(self.languages.active(), "en")
        self.languages.choose("loaded:pt-BR")
        self.assertEqual(self.active.read_bytes(), data)
        self.assertEqual(self.languages.active(), "loaded:pt-BR")
        self.languages.choose("en")
        self.assertFalse(self.active.exists())
        self.assertEqual(self.languages.active(), "en")

    def test_loading_again_replaces_the_pack(self):
        self.languages.load(pack(version="1"))
        self.languages.load(pack(game={"a": "x", "b": "y"}))
        self.assertEqual([(p.language, p.texts) for p in self.languages.packs()], [("pt-BR", 2)])

    def test_refused_file_stores_nothing(self):
        with self.assertRaises(PackError):
            self.languages.load(b"PK\x03\x04")
        self.assertEqual(self.languages.packs(), [])

    def test_shipped_pack_chosen(self):
        self.shipped.mkdir(parents=True)
        (self.shipped / "pl.json").write_bytes(pack(language="pl"))
        self.languages.load(pack())
        self.assertEqual([(p.source, p.language) for p in self.languages.packs()], [("shipped", "pl"), ("loaded", "pt-BR")])
        self.languages.choose("shipped:pl")
        self.assertEqual(self.languages.active(), "shipped:pl")

    def test_missing_shipped_folder(self):
        self.assertEqual(self.languages.packs(), [])

    def test_removing_the_active_pack_goes_english(self):
        self.languages.load(pack())
        self.languages.choose("loaded:pt-BR")
        self.languages.remove("pt-BR")
        self.assertFalse((self.translation / "packs/pt-BR.json").exists())
        self.assertFalse(self.active.exists())

    def test_removing_another_pack_keeps_the_choice(self):
        self.languages.load(pack())
        self.languages.load(pack(language="pl"))
        self.languages.choose("loaded:pt-BR")
        self.languages.remove("pl")
        self.assertEqual(self.languages.active(), "loaded:pt-BR")

    def test_unknown_active_pack(self):
        self.translation.mkdir(parents=True)
        self.active.write_bytes(pack(language="fr"))
        self.assertEqual(self.languages.active(), "other")
        self.languages.choose("en")
        self.assertEqual(self.languages.active(), "en")

    def test_choose_refuses_unknown(self):
        for choice in ("loaded:xx", "shipped:../a", "loaded:../../active", "fr", ""):
            with self.assertRaises(PackError, msg=choice):
                self.languages.choose(choice)
        self.assertFalse(self.active.exists())

    def test_remove_refuses_a_path(self):
        with self.assertRaises(PackError):
            self.languages.remove("../active")

    def test_updated_shipped_pack_reaches_its_players(self):
        choice = Path(self.dir.name) / "tools" / "language.json"
        languages = Languages(self.translation, self.shipped, choice)
        self.shipped.mkdir(parents=True)
        (self.shipped / "pl.json").write_bytes(pack(language="pl"))
        languages.choose("shipped:pl")
        self.assertTrue(choice.is_file())
        newer = pack(language="pl", game={"a": "x", "b": "y"})
        (self.shipped / "pl.json").write_bytes(newer)  # a Bunker update ships a revised pack
        self.assertTrue(languages.refresh())
        self.assertEqual(self.active.read_bytes(), newer)
        self.assertEqual(languages.active(), "shipped:pl")
        self.assertFalse(languages.refresh())  # already current

    def test_refresh_leaves_other_choices_alone(self):
        choice = Path(self.dir.name) / "tools" / "language.json"
        languages = Languages(self.translation, self.shipped, choice)
        languages.load(pack())
        languages.choose("loaded:pt-BR")
        self.assertFalse(choice.exists())
        self.assertFalse(languages.refresh())
        languages.choose("en")
        self.assertFalse(languages.refresh())
        self.assertFalse(self.active.exists())

    def test_shipped_language_dropped_keeps_its_last_copy(self):
        choice = Path(self.dir.name) / "tools" / "language.json"
        languages = Languages(self.translation, self.shipped, choice)
        self.shipped.mkdir(parents=True)
        (self.shipped / "pl.json").write_bytes(pack(language="pl"))
        languages.choose("shipped:pl")
        (self.shipped / "pl.json").unlink()
        self.assertFalse(languages.refresh())
        self.assertTrue(self.active.is_file())

    def test_status(self):
        self.assertEqual(self.languages.status(), {"state": "off"})
        self.translation.mkdir(parents=True)
        (self.translation / "status.json").write_text("garbage")
        self.assertEqual(self.languages.status(), {"state": "off"})
        (self.translation / "status.json").write_text('{"state":"ready","bundles":1}')
        self.assertEqual(self.languages.status(), {"state": "ready", "bundles": 1})


if __name__ == "__main__":
    unittest.main()
