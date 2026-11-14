#!/usr/bin/env python3
"""The NieR sign-off, in light and dark themes alike: the Bunker's main page (the launchers) closes with
END OF TRANSMISSION // GLORY TO MANKIND; the programs (Pod Programs, the Archive) with
OPERATOR LINK // STANDING BY. The web builder closes as the main page."""
from pathlib import Path
import re
import unittest

root = Path(__file__).resolve().parents[2]
OPERATOR, END = "OPERATOR LINK // STANDING BY", "END OF TRANSMISSION // GLORY TO MANKIND"


class SignOff(unittest.TestCase):
    def test_launchers_close_the_transmission(self):
        java = (root / "android/app/src/main/java/org/veritr1x/bunker/Look.java").read_text()
        ios = (root / "ios/launcher/LunarLauncher.m").read_text()
        for name, text in (("Look.java", java), ("LunarLauncher.m", ios)):
            self.assertIn(END, text, name)
            self.assertNotIn(OPERATOR, text, name)

    def test_programs_keep_the_operator_link(self):
        for path in ("overlays/python/web/templates/base.html", "android/app/src/main/python/archive/templates/base.html"):
            text = (root / path).read_text()
            footer = re.search(r"<footer>.*?</footer>", text, re.S).group(0).upper()
            self.assertIn(OPERATOR, footer, path)
            self.assertNotIn(END, footer, path)
            self.assertNotIn("sign-dark", text, path)
            self.assertNotIn("sign-light", text, path)
        css = (root / "overlays/python/web/static/css/automata.css").read_text()
        self.assertNotIn("sign-dark", css)

    def test_the_web_builder_closes_the_transmission(self):
        text = (root / "web/index.html").read_text().upper()
        self.assertIn(END, text)
        self.assertNotIn(OPERATOR, text)


if __name__ == "__main__":
    unittest.main()
