#!/usr/bin/env python3
"""The Lunar Tear status chip says the same things on Android (MainActivity.java) and iOS (LunarLauncher.m):
STANDING BY when the game files are ready and the server is stopped, WAITING FOR FILES without them,
NOT RUNNING only after a failure."""
from pathlib import Path
import re
import unittest

root = Path(__file__).resolve().parents[2]
JAVA = (root / "android/app/src/main/java/org/veritr1x/bunker/MainActivity.java").read_text()
IOS = (root / "ios/launcher/LunarLauncher.m").read_text()
WORDS = {"STANDING BY", "WAITING FOR FILES", "NOT RUNNING", "RUNNING", "STARTING", "POD PROGRAMS OPEN"}


class StatusChip(unittest.TestCase):
    def test_android_says_each(self):
        # Android's words come from the catalogue (launcher.chip.<id>), shown in capitals.
        import json
        english = json.loads((root / "translations/bunker/en.json").read_text())
        line = re.search(r"String chip=tools\?.*", JAVA).group(0)
        ids = set(re.findall(r'"([a-z_]+)"', line))
        said = {english[f"launcher.chip.{i}"].upper() for i in ids if f"launcher.chip.{i}" in english}
        self.assertIn('Texts.upper(this,Texts.t(this,"launcher.chip."+chip))', JAVA)
        self.assertEqual(said - {"STOPPING"}, WORDS)

    def test_ios_says_each(self):
        # iOS's words come from the same catalogue keys (launcher.chip.<id>), shown in capitals.
        import json
        english = json.loads((root / "translations/bunker/en.json").read_text())
        block = re.search(r"if \(gToolsOpen\) SetChip\(self\.server.*?\n(?:.*SetChip\(self\.server.*\n)+", IOS).group(0)
        said = {english[f"launcher.chip.{i}"].upper() for i in re.findall(r'TUpper\(T\(@"launcher\.chip\.([a-z_]+)"\)\)', block)}
        self.assertEqual(said - {"RESTART THE GAME"}, WORDS)

    def test_ios_says_not_running_only_after_a_failure(self):
        self.assertRegex(IOS, r'\[state isEqual:@"error"\]\) SetChip\(self\.server, TUpper\(T\(@"launcher\.chip\.not_running"\)\)')


if __name__ == "__main__":
    unittest.main()
