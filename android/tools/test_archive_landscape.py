"""The Archive on a phone on its side, as Pod Programs (test_landscape_layout.py): the Android app drops
its bar and draws under the camera hole; the page's tab column carries the title and Close and steps
around the hole. The layout itself is checked on a device."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "android/app/src/main/python/archive"
JAVA = ROOT / "android/app/src/main/java/org/veritr1x/bunker"
QUERY = "(orientation: landscape) and (max-height: 599px)"


class Page(unittest.TestCase):
    def setUp(self):
        self.html = (ARCHIVE / "templates/base.html").read_text()

    def test_tab_column_has_title_and_close(self):
        nav = self.html[self.html.index('<nav class="primary">'):self.html.index("</nav>")]
        self.assertIn('class="shell-head"', nav)
        self.assertIn('href="/bunker/close"', nav)

    def test_page_can_draw_under_the_hole(self):
        self.assertIn("viewport-fit=cover", self.html)

    def test_hole_script_follows_the_tabs(self):
        after = self.html[self.html.index("</nav>") + len("</nav>"):]
        self.assertTrue(after.lstrip().startswith("<script>"))
        script = after[:after.index("</script>")]
        for part in (QUERY, "BunkerShell", "bunkerHoleChanged", "--hole-depth", "--hole-right", "by-hole", "bunker-shell"):
            self.assertIn(part, script)

    def test_title_and_close_only_where_the_app_hid_its_bar(self):
        # iOS keeps the Archive's bar, so the page's own Close shows only in the Android app.
        css = (ARCHIVE / "static/archive.css").read_text()
        self.assertIn("html:not(.bunker-shell) .shell-head", css)

    def test_pod_programs_styles_apply(self):
        # The Archive loads automata.css, whose landscape rules lay out the column and the hole.
        self.assertIn("{{ pod_css }}", self.html)
        css = (ROOT / "overlays/python/web/static/css/automata.css").read_text()
        for rule in ("@media " + QUERY, ".shell-head", ".by-hole", "--hole-right"):
            self.assertIn(rule, css)


class Android(unittest.TestCase):
    def test_archive_hides_its_bar_and_gives_the_hole(self):
        java = (JAVA / "ArchiveActivity.java").read_text()
        for part in ("/bunker/close", "LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES", "BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE",
                     '"BunkerShell"', "Look.cutout(insets", "bunkerHoleChanged", "screenHeightDp<600", "onConfigurationChanged"):
            self.assertIn(part, java)

    def test_both_apps_share_the_hole_json(self):
        look = (JAVA / "Look.java").read_text()
        self.assertIn("static String cutout(android.view.WindowInsets insets,float density)", look)
        self.assertIn("getBoundingRects", look)
        self.assertIn("Look.cutout(insets", (JAVA / "ToolsActivity.java").read_text())


if __name__ == "__main__":
    unittest.main()
