#!/usr/bin/env python3
"""Pod Programs' timeline links that open the Archive (ArchiveLinks.java on
Android, LunarTools.m on iOS). The Java test needs a JDK (javac and java on PATH)."""
from pathlib import Path
import re, shutil, subprocess, tempfile, unittest

root = Path(__file__).resolve().parents[2]
JAVA = root / "android/app/src/main/java/org/veritr1x/bunker/ArchiveLinks.java"
IOS = root / "ios/launcher/LunarTools.m"

CASES = {
    "bunker-archive:/schedule/summon/46": "/schedule/summon/46",
    "bunker-archive:/schedule/event/120": "/schedule/event/120",
    "bunker-archive:/setup": None,
    "bunker-archive:/schedule/summon/46?x=1": None,
    "bunker-archive:/schedule/shop/7": None,
    "bunker-archive://evil/schedule/summon/1": None,
    "bunker-archive:/schedule/summon/": None,
    "http://127.0.0.1/schedule/summon/1": None,
}


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "needs a JDK")
class Android(unittest.TestCase):
    def test_only_summon_and_event_pages_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "Main.java"
            # Each argument is a link; "-" stands for none.
            main.write_text("package org.veritr1x.bunker;\npublic class Main { public static void main(String[] args) {\n"
                            "for (String a : args) System.out.println(ArchiveLinks.path(a.equals(\"-\") ? null : a));\n} }\n")
            subprocess.run(["javac", "-d", tmp, str(JAVA), str(main)], check=True)
            out = subprocess.run(["java", "-cp", tmp, "org.veritr1x.bunker.Main", *CASES, "-"],
                                 check=True, capture_output=True, text=True).stdout.split("\n")[:-1]
        self.assertEqual(out, [str(v) if v else "null" for v in CASES.values()] + ["null"])


class Platforms(unittest.TestCase):
    def test_ios_uses_the_same_rule(self):
        java = re.search(r'Pattern\.compile\("(.*?)"\)', JAVA.read_text()).group(1).replace("\\\\", "\\")
        ios = re.search(r'kArchiveLink = @"(.*?)";', IOS.read_text()).group(1).replace("\\\\", "\\")
        self.assertEqual(java, ios)


if __name__ == "__main__":
    unittest.main()
