import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from check_translations import check_file, check_tree, load_coverage, main

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = {"a": "Hello {0}", "b": "<i>Hi</i> there\\nnow", "c": "Plain"}


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name) / "translations"
        self.write("languages.json", {code: {"name": code, "ship": False} for code in ("pt", "pt-BR", "pl")})
        self.write("game/ui/en.json", TEMPLATE)

    def write(self, rel, data, raw=None):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if raw is not None:
            path.write_bytes(raw)
        else:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def problems(self, data=None, raw=None, name="pt"):
        return check_file(self.write(f"game/ui/{name}.json", data, raw), TEMPLATE)

    def test_good_translation_passes(self):
        self.assertEqual(self.problems({"a": "Olá {0}", "b": "Oi <i>lá</i>", "c": ""}), [])

    def test_unknown_key(self):
        found = self.problems({"zz": "x"})
        self.assertEqual(len(found), 1)
        self.assertIn("zz", found[0])

    def test_value_not_text(self):
        self.assertEqual(len(self.problems({"a": 5})), 1)
        self.assertEqual(len(self.problems({"a": None})), 1)

    def test_not_an_object(self):
        for raw in (b'["x"]', b'"x"', b"not json {"):
            self.assertEqual(len(self.problems(raw=raw)), 1, raw)

    def test_duplicate_keys(self):
        found = self.problems(raw='{"a": "Olá {0}", "a": "Oi {0}"}'.encode())
        self.assertEqual(len(found), 1)
        self.assertIn("a", found[0])

    def test_real_line_break(self):
        self.assertEqual(len(self.problems({"c": "one\ntwo"})), 1)
        self.assertEqual(len(self.problems({"c": "one\rtwo"})), 1)

    def test_markup_kept(self):
        self.assertEqual(self.problems({"b": "lá <i>Oi</i>"}), [])  # order may change
        self.assertEqual(len(self.problems({"a": "Olá"})), 1)  # {0} dropped
        self.assertEqual(len(self.problems({"b": "Oi lá"})), 1)  # <i> dropped
        self.assertEqual(len(self.problems({"b": "< i>Oi</i>"})), 1)  # misspelt
        self.assertEqual(len(self.problems({"a": "Olá {0} {1}"})), 1)  # added

    def test_escaped_line_breaks_may_differ(self):
        self.assertEqual(self.problems({"b": "<i>Oi</i>"}), [])

    def test_encoding(self):
        self.assertEqual(len(self.problems(raw='{"c": "Olá"}'.encode("latin-1"))), 1)
        self.assertEqual(len(self.problems(raw=b"\xef\xbb\xbf" + '{"c": "Olá"}'.encode())), 1)

    def test_folder_without_template(self):
        self.write("game/invented/pt.json", {"a": "x"})
        found = check_tree(self.root)
        self.assertEqual(len(found), 1)
        self.assertIn("invented", found[0])

    def test_bad_file_name(self):
        self.write("game/ui/pt_BR.json", {"c": "x"})
        self.write("game/ui/pt-BR.json", {"c": "x"})
        found = check_tree(self.root)
        self.assertEqual(len(found), 1)
        self.assertIn("pt_BR", found[0])

    def test_languages_json(self):
        for bad in ({"pt_BR": {"name": "P", "ship": False}}, {"ja": {"name": "日本語", "ship": False}},
                    {"pl": {"name": 5, "ship": "yes"}}, [], {"pl": "Polski"}):
            self.write("languages.json", bad)
            self.assertTrue(check_tree(self.root), bad)
        self.write("languages.json", {"pl": {"name": "Polski", "ship": False}})
        self.assertEqual(check_tree(self.root), [])

    def test_context_files_are_not_translations(self):
        self.write("game/ui/ja.json", {"a": "こんにちは", "only.ja": "x"})
        self.write("game/ui/ko.json", {"a": "안녕"})
        self.assertEqual(check_tree(self.root), [])

    def test_master_folder(self):
        self.write("master/en.json", {"m_gift_text.1": "Gift"})
        self.write("master/pt.json", {"m_gift_text.1": "Presente", "m_gift_text.9": "x"})
        self.assertEqual(len(check_tree(self.root)), 1)

    def test_line_break_message_says_two_backslashes(self):
        self.assertIn("\\\\n", self.problems({"c": "one\ntwo"})[0])

    def test_master_texts_may_have_real_line_breaks(self):
        self.write("master/en.json", {"m.1": "Line one\nLine two"})
        self.write("master/pt.json", {"m.1": "Linha um\nLinha dois"})
        self.write("languages.json", {"pt": {"name": "Português", "ship": False}})
        self.assertEqual(check_tree(self.root), [])

    def test_broken_escape(self):
        self.assertEqual(len(self.problems(raw=b'{"c": "Zwyk\\ud83d"}')), 1)

    def test_stray_braces(self):
        self.assertEqual(len(self.problems({"a": "Olá {0} {"})), 1)
        self.assertEqual(len(self.problems({"a": "Olá {0} }"})), 1)

    def test_whitespace_only(self):
        self.assertEqual(len(self.problems({"c": "   "})), 1)

    def test_language_must_be_listed(self):
        self.write("languages.json", {})
        self.write("game/ui/pt.json", {"c": "x"})
        found = check_tree(self.root)
        self.assertEqual(len(found), 1)
        self.assertIn("languages.json", found[0])
        self.write("languages.json", {"pt": {"name": "Português", "ship": False}})
        self.assertEqual(check_tree(self.root), [])

    def test_languages_json_missing(self):
        (self.root / "languages.json").unlink()
        self.assertTrue(check_tree(self.root))

    def test_codes_differing_only_in_case(self):
        self.write("languages.json", {"pt-BR": {"name": "P", "ship": False}, "pt-br": {"name": "P", "ship": False}})
        self.assertTrue(check_tree(self.root))
        self.write("languages.json", {"EN": {"name": "English", "ship": False}})
        self.assertTrue(check_tree(self.root))

    def test_folders_outside_the_layout(self):
        self.write("languages.json", {"pl": {"name": "Polski", "ship": False}})
        self.write("game/ui/sub/en.json", {"a": "A"})
        self.write("game/ui/sub/pl.json", {"a": "x"})
        self.write("other/en.json", {"a": "A"})
        self.write("other/pl.json", {"a": "x"})
        self.assertEqual(len([p for p in check_tree(self.root) if "folder" in p]), 2)

    def test_odd_files_get_messages(self):
        self.write("languages.json", {"pl": {"name": "Polski", "ship": False}})
        (self.root / "game/ui/pl.json").mkdir(parents=True)  # a folder named like a file
        self.write("game/bad/en.json", None, raw=b"{not json")
        self.write("game/bad/pl.json", {"a": "x"})
        self.write("game/ui/ko.json", None, raw=b"[" * 200000)
        found = check_tree(self.root)
        self.assertTrue(any("pl.json" in p for p in found))
        self.assertTrue(any("bad/en.json" in p for p in found))

    def test_symlinks_refused(self):
        self.write("languages.json", {"pl": {"name": "Polski", "ship": False}})
        (self.root / "game/ui/pl.json").symlink_to(self.root / "game/ui/en.json")
        (self.root / "game/ui/de.json").symlink_to(self.root / "missing.json")
        found = check_tree(self.root)
        self.assertEqual(len([p for p in found if "link" in p]), 2)

    def test_report_is_capped(self):
        self.write("game/ui/pt.json", {f"zz{i}": "x" for i in range(300)})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([str(self.root)])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 1)
        self.assertEqual(len(lines), 201)
        self.assertIn("100 more", lines[-1])

    def test_ok_message(self):
        self.write("game/ui/pt.json", {"c": "Simples"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([str(self.root)]), 0)
        self.assertIn("Translations OK: 1 language file checked.", out.getvalue())

    def test_repo_passes(self):
        self.assertEqual(check_tree(ROOT / "translations", load_coverage(ROOT / "fonts/coverage.json")), [])

    def test_english_passes_its_own_check(self):
        # Every rule must accept the game's own English, which translators copy from.
        coverage = load_coverage(ROOT / "fonts/coverage.json")
        templates = sorted((ROOT / "translations").glob("game/*/en.json")) + [ROOT / "translations/master/en.json"]
        for english in templates:
            copy = self.root / "game/ui/xx.json"
            copy.write_bytes(english.read_bytes())
            template = json.loads(english.read_text(encoding="utf-8"))
            line_breaks = english.parent.name == "master"
            self.assertEqual(check_file(copy, template, line_breaks=line_breaks, coverage=coverage)[:3], [], english)

    def test_main_applies_the_font_check(self):
        self.write("game/ui/pt.json", {"c": "ภ"})
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main([str(self.root)]), 1)
        self.assertIn("the game's fonts cannot show ภ", out.getvalue())


class PluralFormsTest(unittest.TestCase):
    setUp = CheckTest.setUp
    write = CheckTest.write

    def test_a_counted_text_takes_its_languages_forms(self):
        self.write("bunker/en.json", {"pods.x.files.one": "{n} file", "pods.x.files.other": "{n} files", "pods.x.close": "Close"})
        self.write("bunker/pl.json", {"pods.x.files.one": "{n} plik", "pods.x.files.few": "{n} pliki",
                                       "pods.x.files.many": "{n} plików", "pods.x.files.other": "{n} pliku"})
        self.assertEqual(check_tree(self.root), [])

    def test_only_counted_texts_take_extra_forms(self):
        self.write("bunker/en.json", {"pods.x.files.one": "{n} file", "pods.x.files.other": "{n} files", "pods.x.close": "Close"})
        self.write("bunker/pl.json", {"pods.x.close.few": "Zamknij", "pods.x.files.lots": "{n} plików"})
        found = check_tree(self.root)
        self.assertEqual(len(found), 2, found)
        self.assertTrue(all("not a key of en.json" in line for line in found), found)

    def test_extra_forms_keep_the_placeholders(self):
        self.write("bunker/en.json", {"pods.x.files.one": "{n} file", "pods.x.files.other": "{n} files"})
        self.write("bunker/pl.json", {"pods.x.files.few": "{count} pliki", "pods.x.files.one": "jeden plik"})
        found = check_tree(self.root)
        self.assertEqual(len(found), 1, found)  # a form may leave {n} out ("one file"), not bring its own
        self.assertIn("pods.x.files.few", found[0])


class ProseAndOrderTest(unittest.TestCase):
    setUp = CheckTest.setUp
    write = CheckTest.write

    def test_angle_brackets_in_prose_are_not_tags(self):
        path = self.write("game/ui/pt.json", {"c": "a < b, 3 > 2, <3 e < x >"})
        self.assertEqual(check_file(path, TEMPLATE), [])

    def test_reversed_tags(self):
        path = self.write("game/ui/pt.json", {"b": "</i>Oi<i> lá"})
        found = check_file(path, TEMPLATE)
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].endswith(": b: a closing tag comes before its opening tag (</i>)"), found[0])

    def test_tags_differing_in_case_still_pair(self):
        path = self.write("game/ui/pt.json", {"b": "<I>Oi</i> lá"})
        self.assertEqual(check_file(path, {"b": "<I>Hi</i> there"}), [])

    def test_order_the_english_has_is_allowed(self):
        # Some English lines close a tag opened in an earlier line.
        path = self.write("game/ui/pt.json", {"d": "fim</i> e <i>começo"})
        self.assertEqual(check_file(path, {"d": "end</i> and <i>start"}), [])

    def test_path_shown_from_the_last_translations_folder(self):
        root = Path(self.dir.name) / "translations/repo/translations"
        path = root / "game/ui/pt.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"zz": "x"}')
        (found,) = check_file(path, TEMPLATE)
        self.assertTrue(found.startswith("translations/game/ui/pt.json: "), found)


SHOWN = frozenset(range(0x20, 0x7F)) | frozenset(map(ord, "ąĄéЖあ"))


class FontCoverageTest(unittest.TestCase):
    setUp = CheckTest.setUp
    write = CheckTest.write
    def test_unshowable_letters(self):
        path = self.write("game/ui/pt.json", {"c": "ภารกิจ"})
        found = check_file(path, TEMPLATE, coverage=SHOWN)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].endswith(": c: the game's fonts cannot show ภ า ร (U+0E20 U+0E32 U+0E23)"), found[0])

    def test_coverage_passes_ordinary_text(self):
        path = self.write("game/ui/pt.json", {"b": "Ąé Ж\\nあ <i>x</i>", "a": "{0}"})
        self.assertEqual(check_file(path, TEMPLATE, coverage=SHOWN), [])

    def test_invisible_format_characters_pass(self):
        # The game's own English uses U+2060 (word joiner); no font draws it, and none needs to.
        path = self.write("game/ui/pt.json", {"c": "A⁠B C​D"})
        self.assertEqual(check_file(path, TEMPLATE, coverage=SHOWN), [])

    def test_separate_accent_marks(self):
        # The game drops the fonts' accent positioning: e + U+0301 shows the accent beside the e.
        path = self.write("game/ui/pt.json", {"c": "Tiéng Việt"})
        found = check_file(path, TEMPLATE, coverage=SHOWN | {0x301, 0x302, 0x323})
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].endswith(": c: has accents typed as separate marks (U+0301 U+0323 U+0302); "
                                          "type each accented letter as one character"), found[0])

    def test_composed_accents_pass(self):
        path = self.write("game/ui/pt.json", {"c": "Ąé"})
        self.assertEqual(check_file(path, TEMPLATE, coverage=SHOWN), [])

    def test_unshowable_letters_and_markup_both_reported(self):
        path = self.write("game/ui/pt.json", {"a": "ภ"})
        self.assertEqual(len(check_file(path, TEMPLATE, coverage=SHOWN)), 2)

    def test_bunker_texts_not_font_checked(self):
        self.write("bunker/en.json", {"c": "Plain"})
        self.write("bunker/pt.json", {"c": "ภารกิจ"})
        self.write("game/ui/pt.json", {"c": "ภารกิจ"})
        found = check_tree(self.root, coverage=SHOWN)
        self.assertEqual(len(found), 1)
        self.assertIn("game/ui/pt.json", found[0])

    def test_repo_coverage_file(self):
        shown = load_coverage(ROOT / "fonts/coverage.json")
        for c in "żğệάЖ简あ":
            self.assertIn(ord(c), shown, c)
        for c in "ภاम":
            self.assertNotIn(ord(c), shown, c)


if __name__ == "__main__":
    unittest.main()
