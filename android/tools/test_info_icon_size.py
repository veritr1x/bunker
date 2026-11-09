"""The "i" that opens an explanation looks the same everywhere: an 18px circle with a thin border and a bold
italic serif "i", with a 44px tap area around it (Pod Programs, the Archive, the Android and iOS launchers)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POD = (ROOT / "overlays/python/web/templates/base.html").read_text()
POD_CSS = (ROOT / "overlays/python/web/static/css/automata.css").read_text()
ARCHIVE = (ROOT / "android/app/src/main/python/archive/static/archive.css").read_text()
LOOK = (ROOT / "android/app/src/main/java/org/veritr1x/bunker/Look.java").read_text()
IOS = (ROOT / "ios/launcher/LunarLauncher.m").read_text()


def rule(css: str, selector: str) -> str:
    return re.search(re.escape(selector) + r" \{([^}]*)\}", css).group(1)


class InfoIconSize(unittest.TestCase):
    def test_web_pages_draw_the_same_18px_circle(self):
        for css in (POD, ARCHIVE):
            summary = rule(css, "details.info > summary")
            for part in ("width: 18px", "height: 18px", "border: 1px solid"):
                self.assertIn(part, summary)
            self.assertIn("inset: -13px", rule(css, "details.info > summary::before"))  # 44px to tap

    def test_no_other_size_for_the_icon(self):
        self.assertNotIn("#bunker-live details.info > summary", POD)
        self.assertNotIn("intro-info", POD_CSS)  # the old scripted button is gone

    def test_android_draws_the_same_circle(self):
        self.assertIn("INFO_DP=18", LOOK)
        self.assertIn("Typeface.create(Typeface.SERIF,Typeface.BOLD_ITALIC)", LOOK)

    def test_ios_draws_the_same_circle(self):
        self.assertNotIn("UIButtonTypeInfoLight", IOS)
        self.assertIn("kInfoSize = 18", IOS)
        self.assertIn('fontWithName:@"Georgia-BoldItalic" size:12', IOS)


if __name__ == "__main__":
    unittest.main()
