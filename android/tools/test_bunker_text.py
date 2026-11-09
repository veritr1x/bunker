"""Bunker's own text (bunker_text.py): the English catalogue (translations/bunker/en.json) and the chosen
language pack's "bunker" texts, with English wherever a translation is missing or broken."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
import bunker_text  # noqa: E402


class Catalogue(unittest.TestCase):
    def setUp(self):
        self.addCleanup(bunker_text.use, None)
        bunker_text.use(None)

    def test_english_by_default(self):
        english = json.loads((ROOT / "translations/bunker/en.json").read_text(encoding="utf-8"))
        self.assertEqual(bunker_text.english(), english)
        self.assertEqual(bunker_text.t("common.close"), english["common.close"])

    def test_translation_used(self):
        bunker_text.use({"common.close": "Fechar"})
        self.assertEqual(bunker_text.t("common.close"), "Fechar")

    def test_missing_key_falls_back_to_english(self):
        bunker_text.use({"common.save": "Salvar"})
        self.assertEqual(bunker_text.t("common.close"), "Close")

    def test_empty_or_non_text_translation_falls_back(self):
        bunker_text.use({"common.close": "", "common.save": 3})
        self.assertEqual(bunker_text.t("common.close"), "Close")
        self.assertEqual(bunker_text.t("common.save"), "Save")

    def test_unknown_key_returns_key(self):
        self.assertEqual(bunker_text.t("no.such.key"), "no.such.key")

    def test_params_formatted(self):
        with bunker_text.extra({"test.items": "{n} items"}):
            self.assertEqual(bunker_text.t("test.items", n=3), "3 items")
            bunker_text.use({"test.items": "{n} itens"})
            self.assertEqual(bunker_text.t("test.items", n=3), "3 itens")

    def test_bad_translation_falls_back(self):
        with bunker_text.extra({"test.items": "{n} items"}):
            for broken in ("{n", "{other} itens", "{n} itens }"):
                bunker_text.use({"test.items": broken})
                self.assertEqual(bunker_text.t("test.items", n=3), "3 items", broken)

    def test_count_forms(self):
        with bunker_text.extra({"test.costume.one": "{n} costume", "test.costume.other": "{n} costumes"}):
            self.assertEqual(bunker_text.t_count("test.costume", 1), "1 costume")
            self.assertEqual(bunker_text.t_count("test.costume", 3), "3 costumes")
            self.assertEqual(bunker_text.t_count("test.costume", 0), "0 costumes")


class Reload(unittest.TestCase):
    def setUp(self):
        self.addCleanup(bunker_text.use, None)
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.active = self.dir / "active.json"

    def test_reads_the_active_packs_bunker_texts(self):
        self.active.write_text(json.dumps({"format": 1, "language": "pt", "bunker": {"common.close": "Fechar"}}))
        bunker_text.reload(self.active)
        self.assertEqual(bunker_text.t("common.close"), "Fechar")

    def test_no_pack_or_unreadable_pack_is_english(self):
        bunker_text.use({"common.close": "Fechar"})
        bunker_text.reload(self.active)  # missing
        self.assertEqual(bunker_text.t("common.close"), "Close")
        self.active.write_text("{not json")
        bunker_text.reload(self.active)
        self.assertEqual(bunker_text.t("common.close"), "Close")
        self.active.write_text(json.dumps({"format": 1, "language": "pt", "bunker": ["x"]}))
        bunker_text.reload(self.active)
        self.assertEqual(bunker_text.t("common.close"), "Close")


if __name__ == "__main__":
    unittest.main()
