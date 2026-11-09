import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from check_translations import check_file, check_tree, main

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = {"a": "Hello {0}", "b": "<i>Hi</i> there\\nnow", "c": "Plain"}


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name) / "translations"
        self.write("languages.json", {})
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


if __name__ == "__main__":
    unittest.main()
