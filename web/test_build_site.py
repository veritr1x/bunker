import ast
import hashlib
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
    def test_linux_release_matches_the_browser_kit(self):
        pin = {"reincompVersion": "0.3.1", "bunkerVersion": "1.12.23",
               "asset": "reincomp-linux-x86_64-0.3.1.tar.gz", "size": 123, "sha256": "a" * 64}
        metadata = {"version": "1.12.23", "reincompVersion": "0.3.1"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "linux-release.json"
            path.write_text(json.dumps(pin))
            self.assertEqual(build_site.linux_release(path, metadata), pin)
            for key, value in (("sha256", "bad"), ("size", 0), ("asset", "../other"),
                               ("bunkerVersion", "1.12.22"), ("reincompVersion", "0.3.0")):
                with self.subTest(key=key):
                    path.write_text(json.dumps({**pin, key: value}))
                    with self.assertRaises(ValueError):
                        build_site.linux_release(path, metadata)

    def test_windows_compiler_requires_complete_verified_kit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kit, target = root / "kit", root / "site"
            files = {}
            for name in build_site.WINDOWS_FILES:
                path = kit / name
                path.parent.mkdir(parents=True, exist_ok=True)
                data = name.encode()
                path.write_bytes(data)
                files[name] = hashlib.sha256(data).hexdigest()
            manifest = kit / "kit.json"
            manifest.write_text(json.dumps({"format": 1, "files": {"compiler.mjs": files["compiler.mjs"]}}))
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                build_site.windows_bundle(kit, target, "1.2.3")
            manifest.write_text(json.dumps({"format": 1, "bunkerVersion": "1.2.3", "files": files}))
            with self.assertRaisesRegex(ValueError, "Bunker 1.2.4"):
                build_site.windows_bundle(kit, target, "1.2.4")
            self.assertIsNone(build_site.windows_bundle(kit, target, "1.2.3"))
            info = json.loads(manifest.read_bytes())
            info["reincompVersion"] = "invalid"
            manifest.write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError, "reincomp"):
                build_site.windows_bundle(kit, target, "1.2.3")
            info["reincompVersion"] = "0.2.6"
            manifest.write_text(json.dumps(info))
            self.assertEqual(build_site.windows_bundle(kit, target, "1.2.3"), "0.2.6")
            self.assertEqual((target / "coff.wasm").read_bytes(), b"coff.wasm")
            (kit / "coff.wasm").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "does not match"):
                build_site.windows_bundle(kit, target, "1.2.3")

    def test_prepared_runtime_requires_matching_kit_and_intact_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kit, pack = root / "kit", root / "pack"
            kit.mkdir()
            pack.mkdir()
            kit_file = kit / "kit.json"
            kit_file.write_bytes(b'{"format":1}')
            data = b"example stored bytes"
            digest = hashlib.sha256(data).hexdigest()
            part = pack / "runtime.part001"
            part.write_bytes(data)
            manifest = {"format": 1, "kitSHA256": "0" * 64, "size": 1, "chunks": [digest],
                        "parts": [{"size": len(data), "sha256": digest}]}
            metadata = pack / "runtime.json"
            metadata.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "support"):
                build_site.prepared_windows_runtime(pack, kit, root)
            kit_file.write_bytes(b'{"format":1,"preparedRuntimeFormat":1}')
            with self.assertRaisesRegex(ValueError, "different Windows kit"):
                build_site.prepared_windows_runtime(pack, kit, root)
            manifest["kitSHA256"] = hashlib.sha256(kit_file.read_bytes()).hexdigest()
            metadata.write_text(json.dumps(manifest))
            target = root / "ok"
            target.mkdir()
            self.assertEqual(build_site.prepared_windows_runtime(pack, kit, target),
                             hashlib.sha256(metadata.read_bytes()).hexdigest())
            self.assertEqual((target / "runtime" / part.name).read_bytes(), data)
            part.write_bytes(bytes(len(data)))
            with self.assertRaisesRegex(ValueError, "runtime part 1"):
                build_site.prepared_windows_runtime(pack, kit, root)

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


class LunarTearLicenceTest(unittest.TestCase):
    def test_repo_licence_path_serves_lunar_tears(self):
        # Release tags up to 1.12.23 read /repo/LICENSE as Lunar Tear's licence: never Bunker's.
        self.assertIn("LICENSE", build_site.PYTHON)
        self.assertIn("upstream/lunar-tear/LICENSE", build_site.PYTHON)
        self.assertEqual(build_site.SOURCES["LICENSE"], "upstream/lunar-tear/LICENSE")
        upstream = (build_site.ROOT / "upstream/lunar-tear/LICENSE").read_bytes()
        self.assertIn(b"Ilya Groshev", upstream)


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
}
PORT_WARNING = ("With port offset 0 this copy uses the same ports as the other: only one can run at a time. Stop the other "
                "copy's server before opening this one, or give this copy its own offset (for example 10000).")
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
                    warnings = []
                    app_id, app_name = webbuild.check_app_identity(*args, log=warnings.append)
                    self.assertEqual(app_id, case["appId"].strip() or None)
                    self.assertEqual(app_name, case["appName"].strip() or None)
                    self.assertEqual(warnings, [PORT_WARNING] if case.get("warn") == "portOffset" else [])
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
                    self.assertEqual(result["warnings"].get("portOffset"), PORT_WARNING if case.get("warn") == "portOffset" else None)
                    self.assertEqual(result["appId"], case["appId"].strip() or None)
                    self.assertEqual(result["appName"], case["appName"].strip() or None)
                else:
                    self.assertEqual(list(result["errors"]), [case["field"]])
                    self.assertIn(result["errors"][case["field"]], expected_messages(case))

    def test_app_identity_messages_are_the_same_in_both(self):
        python, js = (HERE / "webbuild.py").read_text(), (HERE / "app_identity.js").read_text()
        for message in MESSAGES.values():
            self.assertIn(message, python)
            self.assertIn(message, js)
        import webbuild
        self.assertEqual(webbuild.PORT_WARNING, PORT_WARNING)
        self.assertIn(PORT_WARNING, js)

    def test_page_has_second_copy_fields(self):
        page = (HERE / "index.html").read_text()
        for needle in ('id="app-id"', 'id="app-name"', 'maxlength="30"', "EXPERIMENTAL :: CUSTOM NAME", 'id="app-id-error"',
                       'id="app-name-error"', 'id="port-offset-error"'):
            self.assertIn(needle, page)

    def test_field_messages_are_announced_politely_and_only_when_they_change(self):
        page, app = (HERE / "index.html").read_text(), (HERE / "app.js").read_text()
        self.assertNotIn('class="field-error" id="app-id-error" role="alert"', page)
        for field in ("app-id", "app-name", "port-offset"):
            self.assertRegex(page, f'class="field-error" id="{field}-error" aria-live="polite"')
        self.assertIn('if (box.textContent !== message) box.textContent = message;', app)

    def test_worker_passes_app_identity(self):
        worker = (HERE / "worker.js").read_text()
        self.assertRegex(worker, r"const \{[^}]*appId = null, appName = null[^}]*\} = data")
        self.assertIn("handOver, log, portOffset, notices, appId, appName);", worker)
        self.assertEqual(worker.count("portOffset, notices, appId, appName"), 2)
        app = (HERE / "app.js").read_text()
        self.assertIn("checkAppIdentity(", app)
        self.assertRegex(app, r"worker\.postMessage\(\{[^}]*appId[^}]*appName")

    def test_builds_refuse_a_bad_identity_before_work(self):
        import webbuild
        with self.assertRaises(ValueError) as caught:
            webbuild.build_android("missing.apk", "m", "c", "o", port_offset=10000, notices="n", app_id="bad")
        self.assertIn("(Android)", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            webbuild.build_ios("missing.ipa", "m", "f", "p", "o", port_offset=10000, app_id="com.example.nier_2")
        self.assertIn("(iOS)", str(caught.exception))

    def test_app_identity_js_is_published(self):
        self.assertIn('"app_identity.js"', (HERE / "build_site.py").read_text())
        page = (HERE / "index.html").read_text()
        self.assertLess(page.index('<script src="app_identity.js"></script>'), page.index('<script src="app.js"></script>'))


if __name__ == "__main__":
    unittest.main()
