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

    def test_repository_catalogue_wins_over_a_prepared_copy(self):
        # prepare.py copies the catalogue beside bunker_text.py; in the repository that copy goes stale as keys
        # are added, so the source catalogue comes first (a device has only the copy).
        self.assertEqual(bunker_text._CATALOGUES[0], ROOT / "translations/bunker/en.json")
        self.assertEqual(bunker_text._CATALOGUES[-1].name, "bunker_en.json")

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

    def test_format_specs_must_match_the_english(self):
        # A loaded pack is untrusted: "{n:99999999}" would make a page build a huge string.
        with bunker_text.extra({"test.items": "{n} items"}):
            for hostile in ("{n:99999999} itens", "{n!r} itens", "{n:>{n}} itens"):
                bunker_text.use({"test.items": hostile})
                self.assertEqual(bunker_text.t("test.items", n=3), "3 items", hostile)

    def test_count_forms(self):
        with bunker_text.extra({"test.costume.one": "{n} costume", "test.costume.other": "{n} costumes"}):
            self.assertEqual(bunker_text.t_count("test.costume", 1), "1 costume")
            self.assertEqual(bunker_text.t_count("test.costume", 3), "3 costumes")
            self.assertEqual(bunker_text.t_count("test.costume", 0), "0 costumes")

    def test_around_splits_at_the_slot(self):
        # A sentence around a control or a link: the text before and after its {slot}, markup put between.
        with bunker_text.extra({"test.allow": "Allow up to {select} pieces to be added."}):
            self.assertEqual(bunker_text.t_around("test.allow", "select"), ("Allow up to ", " pieces to be added."))

    def test_around_a_translation_moves_the_slot(self):
        with bunker_text.extra({"test.allow": "Allow up to {select} pieces to be added."}):
            bunker_text.use({"test.allow": "{select} Teile dürfen dazukommen."})
            self.assertEqual(bunker_text.t_around("test.allow", "select"), ("", " Teile dürfen dazukommen."))

    def test_around_a_translation_without_the_slot_falls_back(self):
        with bunker_text.extra({"test.allow": "Allow up to {select} pieces to be added."}):
            for broken in ("Teile dürfen dazukommen.", "{select} und {select}", "{select"):
                bunker_text.use({"test.allow": broken})
                self.assertEqual(bunker_text.t_around("test.allow", "select"), ("Allow up to ", " pieces to be added."), broken)

    def test_around_formats_its_params(self):
        with bunker_text.extra({"test.of": "{n} of {link} by {who}."}):
            self.assertEqual(bunker_text.t_around("test.of", "link", n=2, who="Nav"), ("2 of ", " by Nav."))


class PluralForms(unittest.TestCase):
    """Each language's own forms (CLDR categories, whole numbers): English one/other; a translation may add
    zero, two, few or many."""
    FORMS = {"test.file.one": "{n} file", "test.file.other": "{n} files"}

    def setUp(self):
        self.addCleanup(bunker_text.use, None)
        self.enterContext(bunker_text.extra(self.FORMS))

    def test_categories(self):
        cases = {
            "en": {0: "other", 1: "one", 2: "other", 11: "other"},
            "fr": {0: "one", 1: "one", 2: "other"},
            "pt-BR": {0: "one", 1: "one", 2: "other"},
            "de": {0: "other", 1: "one", 5: "other"},
            "ru": {1: "one", 21: "one", 2: "few", 24: "few", 5: "many", 11: "many", 12: "many", 111: "many", 0: "many"},
            "uk": {1: "one", 3: "few", 7: "many"},
            "pl": {1: "one", 2: "few", 22: "few", 12: "many", 5: "many", 21: "many", 0: "many"},
            "cs": {1: "one", 2: "few", 4: "few", 5: "other", 0: "other"},
            "ar": {0: "zero", 1: "one", 2: "two", 3: "few", 10: "few", 11: "many", 99: "many", 100: "other", 102: "other"},
            "lt": {1: "one", 21: "one", 2: "few", 11: "other", 10: "other"},
            "ro": {1: "one", 0: "few", 19: "few", 20: "other"},
            "ja": {0: "other", 1: "other"}, "zh-Hans": {1: "other"}, "vi": {1: "other"},
            "tr": {1: "one", 2: "other"}, "he": {1: "one", 2: "two", 3: "other"},
        }
        for language, numbers in cases.items():
            for n, category in numbers.items():
                self.assertEqual(bunker_text.plural_category(language, n), category, (language, n))

    def test_translation_with_more_forms(self):
        bunker_text.use({"test.file.one": "{n} plik", "test.file.few": "{n} pliki", "test.file.many": "{n} plików",
                         "test.file.other": "{n} pliku"}, language="pl")
        self.assertEqual([bunker_text.t_count("test.file", n) for n in (1, 3, 5, 22)],
                         ["1 plik", "3 pliki", "5 plików", "22 pliki"])

    def test_a_missing_form_falls_back_to_english_for_the_whole_text(self):
        bunker_text.use({"test.file.one": "{n} plik", "test.file.other": "{n} pliku"}, language="pl")
        # "few" and "many" missing: English for every count, never half a translation
        self.assertEqual(bunker_text.t_count("test.file", 5), "5 files")
        self.assertEqual(bunker_text.t_count("test.file", 1), "1 file")

    def test_forms_for_scripts(self):
        bunker_text.use({"test.file.one": "{n} plik", "test.file.few": "{n} pliki", "test.file.many": "{n} plików",
                         "test.file.other": "{n} pliku"}, language="pl")
        self.assertEqual(bunker_text.language(), "pl")
        self.assertEqual(bunker_text.plural_forms("test.file"),
                         {"one": "{n} plik", "few": "{n} pliki", "many": "{n} plików", "other": "{n} pliku"})
        bunker_text.use(None)
        self.assertEqual(bunker_text.language(), "en")
        self.assertEqual(bunker_text.plural_forms("test.file"), {"one": "{n} file", "other": "{n} files"})

    def test_reload_takes_the_packs_language(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        active = folder / "active.json"
        active.write_text(json.dumps({"format": 1, "language": "ru", "bunker": {"common.close": "Закрыть"}}))
        bunker_text.reload(active)
        self.assertEqual(bunker_text.language(), "ru")


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


class Templates(unittest.TestCase):
    def setUp(self):
        self.addCleanup(bunker_text.use, None)
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.dir / "page.html").write_text('{{ t("common.close") }}|{{ t_count("test.n", 2) }}'
                                            '{% if t_around is defined %}|{{ t_around("common.close", "x")[0] }}{% endif %}')

    def render(self, templates):
        return templates.get_template("page.html").render()

    def test_templates_get_t(self):
        from fastapi.templating import Jinja2Templates
        bunker_text.install_everywhere()
        bunker_text.install_everywhere()  # twice is harmless
        with bunker_text.extra({"test.n.one": "{n} thing", "test.n.other": "{n} things"}):
            self.assertEqual(self.render(Jinja2Templates(directory=str(self.dir))), "Close|2 things|Close")

    def test_install_one(self):
        import jinja2
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(self.dir)), autoescape=True)
        bunker_text.install(env)
        bunker_text.use({"common.close": "Fechar"})
        self.assertEqual(env.get_template("page.html").render().split("|")[0], "Fechar")

    def test_translation_is_escaped(self):
        from fastapi.templating import Jinja2Templates
        bunker_text.install_everywhere()
        bunker_text.use({"common.close": "<b>&"})
        self.assertTrue(self.render(Jinja2Templates(directory=str(self.dir))).startswith("&lt;b&gt;&amp;|"))

    def test_apps_install_it(self):
        # Pod Programs (every Jinja2Templates, its own and lunar-base's) and the Archive (built only from a
        # real dump, so checked here by its source) get t, and follow the applied pack on every request.
        runtime = (ROOT / "android/app/src/main/python/android_runtime.py").read_text()
        self.assertIn("bunker_text.install_everywhere()", runtime)
        self.assertIn("bunker_text.reload()", runtime)
        archive = (ROOT / "android/app/src/main/python/archive/app.py").read_text()
        self.assertIn("bunker_text.install(templates)", archive)
        self.assertIn("bunker_text.reload(language)", archive)
        self.assertIn("language=active_pack(asset_root)", (ROOT / "android/app/src/main/python/android_archive.py").read_text())

    def test_archive_reads_the_pack_pod_programs_applies(self):
        # The Archive's asset_root is the server folder that holds assets/ (revision_root) and translation/.
        import android_archive
        import bunker_language
        from types import SimpleNamespace
        server = self.dir / "server"
        config = SimpleNamespace(ASSETS_DIR=server / "assets", DATA_DIR=self.dir / "tools")
        self.assertEqual(android_archive.active_pack(server), bunker_language.for_config(config).active_path)


if __name__ == "__main__":
    unittest.main()
