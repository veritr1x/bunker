#!/usr/bin/env python3
"""When the launchers update the game data before the server starts
(DataUpdate.java on Android, LunarTools.m on iOS). The Java test needs a JDK
(javac and java on PATH)."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest

root = Path(__file__).resolve().parents[2]
JAVA = root / "android/app/src/main/java/org/veritr1x/bunker/DataUpdate.java"
IOS = root / "ios/launcher/LunarTools.m"
PYTHON = root / "android/app/src/main/python/android_patcher.py"


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "needs a JDK")
class Android(unittest.TestCase):
    def needed(self, saves={}, tools={}):
        with tempfile.TemporaryDirectory() as tmp:
            for folder, files in (("saves", saves), ("tools", tools)):
                for name, text in files.items():
                    (Path(tmp) / folder / name).parent.mkdir(parents=True, exist_ok=True)
                    (Path(tmp) / folder / name).write_text(text)
            main = Path(tmp) / "Main.java"
            main.write_text("package org.veritr1x.bunker;\npublic class Main { public static void main(String[] args) {\n"
                            "System.out.println(DataUpdate.needed(new java.io.File(args[0]), new java.io.File(args[1]), args[2]));\n} }\n")
            subprocess.run(["javac", "-d", tmp, str(JAVA), str(main)], check=True)
            out = subprocess.run(["java", "-cp", tmp, "org.veritr1x.bunker.Main", f"{tmp}/saves", f"{tmp}/tools", "1.6.3"],
                                 check=True, capture_output=True, text=True).stdout.strip()
        return out == "true"

    def test_no_calendar_and_no_preset_needs_nothing(self):
        self.assertFalse(self.needed())

    def test_calendar_never_updated_needs_an_update(self):
        self.assertTrue(self.needed({"calendar.json": "{}"}))

    def test_preset_never_updated_needs_an_update(self):
        self.assertTrue(self.needed(tools={"patcher/active.json": "{}"}))

    def test_shipped_language_never_updated_needs_an_update(self):
        # Pod Programs › Language: a shipped pack the update may have revised
        self.assertTrue(self.needed(tools={"language.json": "{}"}))

    def test_updated_for_another_version_needs_an_update(self):
        self.assertTrue(self.needed({"calendar.json": "{}", "data.updated": "1.6.2"}))

    def test_updated_for_this_version_needs_nothing(self):
        self.assertFalse(self.needed({"data.updated": "1.6.3\n"}, {"patcher/active.json": "{}"}))


class Platforms(unittest.TestCase):
    def test_ios_and_python_use_the_same_files(self):
        java, ios = JAVA.read_text(), IOS.read_text()
        for name in ("calendar.json", "patcher/active.json", "language.json", "data.updated"):
            self.assertIn(f'"{name}"', java)
            self.assertIn(f'@"{name}"', ios)
        self.assertIn('config.GAME_DB_PATH.parent / "data.updated"', PYTHON.read_text())
        self.assertIn('folder() / "active.json"', PYTHON.read_text())


if __name__ == "__main__":
    unittest.main()
