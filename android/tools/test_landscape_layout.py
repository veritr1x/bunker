"""Pod Programs on a phone on its side:
the pieces each part needs. The layout itself is checked on a device."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "overlays/python/web"
QUERY = "(orientation: landscape) and (max-height: 599px)"

# Each page and what it puts beside its content (data-side), and whether it lists sections (data-toc).
PAGES = {
    "patcher.html": True, "users.html": False, "backup.html": False, "display.html": True,
    "gacha.html": True, "mods.html": True, "gift.html": False, "deck_builder.html": False,
    "user_items.html": False, "user_costumes.html": True, "user_weapons.html": True,
    "upgrade_manager.html": True, "memoir_editor.html": True,
}


def read(p):
    return (WEB / p).read_text()


class Base(unittest.TestCase):
    def test_tab_column_has_title_and_close(self):
        html = read("templates/base.html")
        nav = html[html.index('<nav class="primary">'):html.index("</nav>")]
        self.assertIn('class="shell-head"', nav)
        self.assertIn('href="/bunker/close"', nav)

    def test_page_can_draw_under_the_notch(self):
        self.assertIn("viewport-fit=cover", read("templates/base.html"))

    def test_live_notice_has_a_short_form(self):
        html = read("templates/base.html")
        self.assertIn('class="live-short"', html)
        self.assertIn('class="live-long"', html)

    def test_split_script_runs_right_after_main(self):
        html = read("templates/base.html")
        after = html[html.index("</main>") + len("</main>"):]
        self.assertTrue(after.lstrip().startswith("<script>"), "the split script must run before the first paint")
        script = after[:after.index("</script>")]
        for part in ("data-side", "data-toc", QUERY, "bunkerHoleChanged", "BunkerShell", "bunkerCutout"):
            self.assertIn(part, script)


class Css(unittest.TestCase):
    def test_one_query_for_a_phone_on_its_side(self):
        css = read("static/css/automata.css")
        self.assertIn("@media " + QUERY, css)
        self.assertNotIn("max-height: 540px", css)
        for rule in (".page-split", ".page-side", ".page-main", ".shell-head", ".page-toc", ".by-hole", "@container"):
            self.assertIn(rule, css)


class Pages(unittest.TestCase):
    def test_each_page_marks_its_side_column(self):
        for page, toc in PAGES.items():
            with self.subTest(page=page):
                html = read("templates/" + page)
                self.assertRegex(html, r"\sdata-side[\s=>]")
                self.assertEqual(toc, bool(re.search(r"\sdata-toc[\s=>]", html)))


class HoleOverlap(unittest.TestCase):
    def test_only_tabs_whose_text_is_beside_the_hole_step_aside(self):
        # A tab's padding reaching a few pixels into the hole's band moved it (Language, under the hole).
        pages = [ROOT / "overlays/python/web/templates/base.html", ROOT / "android/app/src/main/python/archive/templates/base.html"]
        for page in pages:
            script = page.read_text()
            self.assertIn("const pad = parseFloat(getComputedStyle(a).paddingTop) || 0;", script, page)
            self.assertIn("b.bottom - pad > cut.top && b.top + pad < cut.bottom", script, page)


class Apps(unittest.TestCase):
    def test_android_hides_its_bar_and_gives_the_hole(self):
        java = (ROOT / "android/app/src/main/java/org/veritr1x/bunker/ToolsActivity.java").read_text()
        for part in ("/bunker/close", "LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES", "BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE",
                     '"BunkerShell"', "Look.cutout(insets", "bunkerHoleChanged"):
            self.assertIn(part, java)
        # The hole's JSON is shared with the Archive (test_archive_landscape.py).
        look = (ROOT / "android/app/src/main/java/org/veritr1x/bunker/Look.java").read_text()
        self.assertIn("getBoundingRects", look)
        # The tabs hug the hole itself (its shape, Android 12+), not the wider band around it.
        self.assertIn("getCutoutPath()", look)

    def test_ios_hides_its_bar_and_gives_the_hole(self):
        m = (ROOT / "ios/launcher/LunarTools.m").read_text()
        for part in ("/bunker/close", "prefersStatusBarHidden", "prefersHomeIndicatorAutoHidden", "bunkerCutout", "bunkerHoleChanged"):
            self.assertIn(part, m)


if __name__ == "__main__":
    unittest.main()
