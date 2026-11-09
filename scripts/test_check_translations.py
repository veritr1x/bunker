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
        self.assertEqual(check_tree(ROOT / "translations"), [])


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
