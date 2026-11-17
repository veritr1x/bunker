import ast
import unittest
import json
from pathlib import Path
import tempfile
import zipfile

import build_site


def added_paths(source):
    """Folders a file puts on sys.path as Path(__file__).resolve().parents[N] / "name"."""
    folders = []
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and isinstance(node.right, ast.Constant) \
                and isinstance(node.left, ast.Subscript) and isinstance(node.left.value, ast.Attribute) \
                and node.left.value.attr == "parents" and isinstance(node.left.slice, ast.Constant):
            folders.append(source.resolve().parents[node.left.slice.value] / node.right.value)
    return [f for f in folders if f.is_dir()]


class SiteFilesTest(unittest.TestCase):
    def test_notice_parts_preserve_the_archive_and_fit_the_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("notices/notices.json", b"[]" * 100)
            for limit in (64, source.stat().st_size):
                out = Path(tmp) / str(limit)
                build_site.notice_bundle(source, out, part_size=limit)
                manifest = json.loads((out / "notices.json").read_text())
                chunks = [(out / name).read_bytes() for name in manifest["parts"]]
                self.assertTrue(all(len(chunk) <= limit for chunk in chunks))
                self.assertEqual(b"".join(chunks), source.read_bytes())
                self.assertEqual(manifest["size"], source.stat().st_size)
                if limit == source.stat().st_size:
                    self.assertEqual(manifest["parts"], ["notices.zip"])

    def test_split_notices_cannot_publish_master_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("private/master.bin.e", b"private")
            with self.assertRaisesRegex(SystemExit, "master data"):
                build_site.notice_bundle(source, Path(tmp) / "out", part_size=16)

    def test_every_local_import_is_published(self):
        published = {path for path in build_site.PYTHON if path.endswith(".py")}
        missing = []
        for path in sorted(published):
            folders = [(build_site.ROOT / path).parent] + added_paths(build_site.ROOT / path)
            for node in ast.walk(ast.parse((build_site.ROOT / path).read_text())):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    module = next((f / (name.split(".")[0] + ".py") for f in folders if (f / (name.split(".")[0] + ".py")).exists()), None)
                    if module:
                        relative = module.relative_to(build_site.ROOT).as_posix()
                        if relative not in published:
                            missing.append(f"{path} imports {relative}")
        self.assertEqual(missing, [])


class FontsTest(unittest.TestCase):
    def test_fonts_are_published(self):
        # game_fonts.py reads fonts/noto/ next to the repo's other files (/repo in the browser).
        published = set(build_site.PYTHON)
        self.assertIn("android/tools/game_fonts.py", published)
        noto = sorted(p.relative_to(build_site.ROOT).as_posix() for p in (build_site.ROOT / "fonts/noto").iterdir())
        self.assertIn("fonts/noto/OFL.txt", noto)
        self.assertEqual([p for p in noto if p not in published], [])

    def test_worker_loads_fonttools(self):
        worker = (build_site.ROOT / "web/worker.js").read_text()
        load = next(line for line in worker.splitlines() if "loadPackage(" in line)
        self.assertIn('"fonttools"', load)


class WorkerFetchTest(unittest.TestCase):
    def test_worker_revalidates_what_it_downloads(self):
        # A release must not run with Python files or bundles a browser cached from the last one.
        worker = (build_site.ROOT / "web/worker.js").read_text()
        fetches = [line for line in worker.splitlines() if "await fetch(" in line]
        self.assertTrue(fetches)
        self.assertEqual([line for line in fetches if 'cache: "no-cache"' not in line], [])




MESSAGES = {
    ("appId", "android"): "The App ID must be at least two parts separated by dots, each starting with a letter and using only letters, digits and _ (Android).",
    ("appId", "ios"): "The App ID must be at least two parts separated by dots, using only letters, digits and - (iOS).",
    ("appId", "long"): "The App ID is too long.",
    ("appId", "game"): "That is the game's own ID: leave the field empty for it.",
    ("appName", None): "The name must be 30 characters or fewer, without control characters.",
    ("portOffset", None): "A second copy needs a port offset other than 0, and different from the other copy's (for example 10000).",
}
HERE = Path(__file__).resolve().parent


def expected_messages(case):
    if case["field"] != "appId":
        return {MESSAGES[(case["field"], None)]}
    return {MESSAGES[("appId", case["platform"])], MESSAGES[("appId", "long")], MESSAGES[("appId", "game")]}


class AppIdentityTest(unittest.TestCase):
    cases = json.loads((HERE / "app_identity_cases.json").read_text())

    def test_app_identity_python_matches_cases(self):
        import webbuild
        for case in self.cases:
            with self.subTest(case=case):
                args = (case["platform"], case["appId"], case["appName"], case["portOffset"])
                if case["ok"]:
                    app_id, app_name = webbuild.check_app_identity(*args)
                    self.assertEqual(app_id, case["appId"].strip() or None)
                    self.assertEqual(app_name, case["appName"].strip() or None)
                else:
                    with self.assertRaises(ValueError) as caught:
                        webbuild.check_app_identity(*args)
                    self.assertIn(str(caught.exception), expected_messages(case))

    def test_app_identity_js_matches_cases(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        script = ("const {checkAppIdentity}=require(process.argv[1]); const cases=require(process.argv[2]);"
                  "console.log(JSON.stringify(cases.map(c=>checkAppIdentity(c.platform,c.appId,c.appName,c.portOffset))))")
        out = subprocess.run(["node", "-e", script, str(HERE / "app_identity.js"), str(HERE / "app_identity_cases.json")],
                             capture_output=True, text=True, check=True).stdout
        for case, result in zip(self.cases, json.loads(out)):
            with self.subTest(case=case):
                if case["ok"]:
                    self.assertEqual(result["errors"], {})
                    self.assertEqual(result["appId"], case["appId"].strip() or None)
                    self.assertEqual(result["appName"], case["appName"].strip() or None)
                else:
                    self.assertEqual(list(result["errors"]), [case["field"]])
                    self.assertIn(result["errors"][case["field"]], expected_messages(case))

    def test_app_identity_messages_are_the_same_in_both(self):
        python, js = (HERE / "webbuild.py").read_text(), (HERE / "app_identity.js").read_text()
        for message in MESSAGES.values():
            self.assertIn(json.dumps(message)[1:-1].replace("\\'", "'"), python)
            self.assertIn(message, js)

    def test_app_identity_js_is_published(self):
        self.assertIn('"app_identity.js"', (HERE / "build_site.py").read_text())
        page = (HERE / "index.html").read_text()
        self.assertLess(page.index('<script src="app_identity.js"></script>'), page.index('<script src="app.js"></script>'))


if __name__ == "__main__":
    unittest.main()
