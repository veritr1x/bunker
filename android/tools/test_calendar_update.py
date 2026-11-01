#!/usr/bin/env python3
"""When the launchers update the Original calendar's game data before the server
starts (CalendarUpdate.java on Android, LunarTools.m on iOS). The Java test
needs a JDK (javac and java on PATH)."""
from pathlib import Path
import re, shutil, subprocess, tempfile, unittest

root = Path(__file__).resolve().parents[2]
JAVA = root / "android/app/src/main/java/org/veritr1x/bunker/CalendarUpdate.java"
IOS = root / "ios/launcher/LunarTools.m"
PYTHON = root / "android/app/src/main/python/android_calendar.py"


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "needs a JDK")
class Android(unittest.TestCase):
    def needed(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "saves"
            data.mkdir()
            for name, text in files.items():
                (data / name).write_text(text)
            main = Path(tmp) / "Main.java"
            main.write_text("package org.veritr1x.bunker;\npublic class Main { public static void main(String[] args) {\n"
                            "System.out.println(CalendarUpdate.needed(new java.io.File(args[0]), args[1]));\n} }\n")
            subprocess.run(["javac", "-d", tmp, str(JAVA), str(main)], check=True)
            out = subprocess.run(["java", "-cp", tmp, "org.veritr1x.bunker.Main", str(data), "1.6.2"],
                                 check=True, capture_output=True, text=True).stdout.strip()
        return out == "true"

    def test_calendar_off_needs_nothing(self):
        self.assertFalse(self.needed({}))

    def test_calendar_never_updated_needs_an_update(self):
        self.assertTrue(self.needed({"calendar.json": "{}"}))

    def test_calendar_updated_for_another_version_needs_an_update(self):
        self.assertTrue(self.needed({"calendar.json": "{}", "calendar.updated": "1.6.1"}))

    def test_calendar_updated_for_this_version_needs_nothing(self):
        self.assertFalse(self.needed({"calendar.json": "{}", "calendar.updated": "1.6.2\n"}))


class Platforms(unittest.TestCase):
    def test_ios_and_python_use_the_same_files(self):
        java = JAVA.read_text()
        for name in ("calendar.json", "calendar.updated"):
            self.assertIn(f'"{name}"', java)
            self.assertIn(f'@"{name}"', IOS.read_text())
        self.assertIn('with_name("calendar.updated")', PYTHON.read_text())
        self.assertTrue(re.search(r"def state_path\(\):\s+return config\.GAME_DB_PATH\.parent / \"calendar\.json\"", PYTHON.read_text()))


if __name__ == "__main__":
    unittest.main()
