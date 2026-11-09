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
        line = re.search(r"String state=tools\?.*", JAVA).group(0)
        self.assertEqual({w for w in WORDS if f'"{w}"' in line}, WORDS)

    def test_ios_says_each(self):
        block = re.search(r"if \(gToolsOpen\) SetChip\(self\.server.*?\n(?:.*SetChip\(self\.server.*\n)+", IOS).group(0)
        self.assertEqual({w for w in WORDS if f'@"{w}"' in block}, WORDS)

    def test_ios_says_not_running_only_after_a_failure(self):
        self.assertRegex(IOS, r'\[state isEqual:@"error"\]\) SetChip\(self\.server, @"NOT RUNNING"')


if __name__ == "__main__":
    unittest.main()
