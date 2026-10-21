import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import release_assets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "android/tools"))
import build_info  # noqa: E402


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class MakeTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.work = Path(self.t.name)
        self.apk = self.work / "app-debug.apk"
        with zipfile.ZipFile(self.apk, "w") as z:
            z.writestr("AndroidManifest.xml", "m")
            z.writestr("classes.dex", "d")
            z.writestr("lib/arm64-v8a/liblunar.so", "l")
            z.writestr("assets/lunar/bunker-version.txt", "1.2.3\n")
            z.writestr("res/x.png", "unrelated")
        self.framework = self.work / "LunarTear.framework"
        self.framework.mkdir()
        (self.framework / "LunarTear").write_text("bin")
        (self.framework / "build.json").write_text('{"version": "1.2.3"}')
        self.python = self.work / "python-bundle"
        (self.python / "python").mkdir(parents=True)
        (self.python / "python/a.py").write_text("x")
        self.out = self.work / "dist"

    def test_makes_bundles_and_update_json(self):
        update = release_assets.make("1.2.3", self.apk, self.framework, self.python, self.out)
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(names, ["bunker-android-1.2.3.zip", "bunker-ios-framework-1.2.3.zip",
                                 "bunker-ios-python-1.2.3.zip", "update.json"])
        self.assertEqual(json.loads((self.out / "update.json").read_text()), update)
        self.assertEqual(update["version"], "1.2.3")
        self.assertEqual(update["gamePatch"], build_info.GAME_PATCH)
        for key, name in [("android", "bunker-android-1.2.3.zip"), ("iosFramework", "bunker-ios-framework-1.2.3.zip"),
                          ("iosPython", "bunker-ios-python-1.2.3.zip")]:
            path = self.out / name
            self.assertEqual(update["assets"][key], {"name": name, "size": path.stat().st_size, "sha256": sha256(path)})
        with zipfile.ZipFile(self.out / "bunker-android-1.2.3.zip") as z:
            self.assertIn("assets/lunar/bunker-version.txt", z.namelist())
            self.assertNotIn("res/x.png", z.namelist())
        with zipfile.ZipFile(self.out / "bunker-ios-framework-1.2.3.zip") as z:
            self.assertIn("LunarTear.framework/LunarTear", z.namelist())

    def test_includes_the_notice_pack(self):
        pack = self.work / "bunker-notices.zip"
        with zipfile.ZipFile(pack, "w") as z:
            z.writestr("notices.json", "{}")
        update = release_assets.make("1.2.3", self.apk, self.framework, self.python, self.out, notices=pack)
        digest = sha256(pack)
        name = f"bunker-notices-{digest[:12]}.zip"
        self.assertEqual(update["assets"]["notices"], {"name": name, "size": pack.stat().st_size, "sha256": digest})
        self.assertEqual((self.out / name).read_bytes(), pack.read_bytes())

    def test_refuses_master_data(self):
        (self.framework / "20240404193219.bin.e").write_text("master")
        with zipfile.ZipFile(self.apk, "a") as z:
            z.writestr("assets/lunar/original-master.bin.e", "master")
        update = release_assets.make("1.2.3", self.apk, self.framework, self.python, self.out)
        for asset in update["assets"].values():
            with zipfile.ZipFile(self.out / asset["name"]) as z:
                self.assertFalse(any(n.endswith(".bin.e") for n in z.namelist()), asset["name"])

    def test_refuses_mismatched_version(self):
        with self.assertRaises(ValueError):
            release_assets.make("9.9.9", self.apk, self.framework, self.python, self.out)


class ChangelogTests(unittest.TestCase):
    TEXT = "# Changelog\n\nIntro.\n\n## 1.1.0 (2026-11-01)\n\nNew.\n\n### Area\n- thing\n\n## 1.0.0 (2026-10-15)\n\nFirst.\n\n## 2026-10-15\n\n### Old\n- x\n"

    def test_section(self):
        self.assertEqual(release_assets.changelog_section(self.TEXT, "1.1.0"), "New.\n\n### Area\n- thing")
        # A release's notes run to the previous release, dated sections included.
        self.assertEqual(release_assets.changelog_section(self.TEXT, "1.0.0"), "First.\n\n## 2026-10-15\n\n### Old\n- x")

    def test_wrapped_lines_are_joined(self):
        # GitHub release notes break lines where the file does; the file wraps at ~76 columns.
        text = ("## 1.2.0 (2026-11-01)\n\nA paragraph that\nwraps here.\n\n### Area\n- A bullet that\n  wraps twice\n  here. [abc1234]\n"
                "- Next bullet.\n\n```sh\nkeep\nthese\n```\n\n## 1.1.0 (2026-10-01)\n")
        self.assertEqual(release_assets.changelog_section(text, "1.2.0"),
                         "A paragraph that wraps here.\n\n### Area\n- A bullet that wraps twice here. [abc1234]\n- Next bullet.\n\n```sh\nkeep\nthese\n```")

    def test_missing_section(self):
        with self.assertRaises(ValueError):
            release_assets.changelog_section(self.TEXT, "2.0.0")


if __name__ == "__main__":
    unittest.main()
