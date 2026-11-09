#!/usr/bin/env python3
"""The NieR sign-off under every Bunker screen: both lines, in light and dark themes alike,
OPERATOR LINK // STANDING BY first, then END OF TRANSMISSION // GLORY TO MANKIND."""
from pathlib import Path
import re
import unittest

root = Path(__file__).resolve().parents[2]
FIRST, SECOND = "OPERATOR LINK // STANDING BY", "END OF TRANSMISSION // GLORY TO MANKIND"


class SignOff(unittest.TestCase):
    def assert_both_in_order(self, text, name):
        upper = text.upper()
        self.assertIn(FIRST, upper, name)
        self.assertIn(SECOND, upper, name)
        self.assertLess(upper.index(FIRST), upper.index(SECOND), name)

    def test_launchers_show_both_whatever_the_theme(self):
        java = (root / "android/app/src/main/java/org/veritr1x/bunker/Look.java").read_text()
        ios = (root / "ios/launcher/LunarLauncher.m").read_text()
        for name, text in (("Look.java", java), ("LunarLauncher.m", ios)):
            self.assert_both_in_order(text, name)
            self.assertNotRegex(text, r"dark\s*\?\s*@?\"OPERATOR LINK", name)

    def test_pages_show_both_whatever_the_theme(self):
        for path in ("overlays/python/web/templates/base.html", "android/app/src/main/python/archive/templates/base.html",
                     "web/index.html"):
            text = (root / path).read_text()
            footer = re.search(r"Operator link.*?mankind", text, re.S | re.I).group(0)
            self.assert_both_in_order(footer, path)
            self.assertNotIn("sign-dark", text, path)
            self.assertNotIn("sign-light", text, path)
        css = (root / "overlays/python/web/static/css/automata.css").read_text()
        self.assertNotIn("sign-dark", css)


if __name__ == "__main__":
    unittest.main()
