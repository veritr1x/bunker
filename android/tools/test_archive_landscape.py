"""The Archive on a phone on its side, as Pod Programs (test_landscape_layout.py): the Android app drops
its bar and draws under the camera hole; the page's tab column carries the title and Close and steps
around the hole. The layout itself is checked on a device."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "android/app/src/main/python/archive"
JAVA = ROOT / "android/app/src/main/java/org/veritr1x/bunker"
QUERY = "(orientation: landscape) and (max-height: 599px) and (min-width: 560px)"


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

    def test_close_across_window_sizes(self):
        try:
            from jinja2 import Environment, FileSystemLoader
            from playwright.sync_api import Error, sync_playwright
        except ImportError:
            self.skipTest("needs playwright and jinja2 (scripts/requirements-web-tests.txt)")
        template = Environment(loader=FileSystemLoader(ARCHIVE / "templates")).get_template("base.html")
        html = template.render(text_language=lambda: "en", t=lambda key: key, asset=lambda _: "/archive.css",
                               pod_css="/automata.css", sections=[("home", "Home", "/")])
        styles = {"/archive.css": (ARCHIVE / "static/archive.css").read_text(encoding="utf-8"),
                  "/automata.css": (ROOT / "overlays/python/web/static/css/automata.css").read_text(encoding="utf-8")}
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except Error:
                try:
                    browser = playwright.chromium.launch(channel="chrome")
                except Error:
                    self.skipTest("no Chromium installation")
            for host, bridge in (("desktop", "window.chrome = {webview: {}}"),
                                 ("android", "window.BunkerShell = {cutout: () => 'null'}"), ("ios", "")):
                page = browser.new_page()
                page.add_init_script(bridge)
                def respond(route):
                    path = route.request.url.removeprefix("http://archive.test")
                    if path in styles:
                        route.fulfill(content_type="text/css", body=styles[path])
                    else:
                        route.fulfill(content_type="text/html", body=html)
                page.route("http://archive.test/**", respond)
                page.goto("http://archive.test/")
                close = page.locator('nav a[href="/bunker/close"]')
                for width, height in ((440, 700), (559, 320), (560, 320), (820, 599), (820, 600), (1440, 850)):
                    with self.subTest(host=host, viewport=(width, height)):
                        page.set_viewport_size({"width": width, "height": height})
                        sidebar = width >= 560 and width > height and height <= 599
                        expected = host == "desktop" or (host == "android" and sidebar)
                        self.assertEqual(close.is_visible(), expected)
                        if expected:
                            close.click(trial=True)
                if host == "desktop":
                    close.click()
                    page.wait_for_url("**/bunker/close")
                page.close()
            browser.close()

    def test_bottom_bars_start_beside_the_tab_column(self):
        # The music player and the pager are fixed to the bottom; from the left edge, the 148px tab column
        # covered their play button and title.
        css = (ARCHIVE / "static/archive.css").read_text()
        landscape = css[css.index("@media (orientation: landscape) and (max-height: 599px) and (min-width: 560px) {"):]
        self.assertIn("footer.player-bar, footer.pager { left: 148px; }", landscape)

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
                     '"BunkerShell"', "Look.cutout(insets", "bunkerHoleChanged", "screenHeightDp<600&&config.screenWidthDp>=560", "compact&&web.getVisibility()==View.VISIBLE", "onConfigurationChanged"):
            self.assertIn(part, java)

    def test_both_apps_share_the_hole_json(self):
        look = (JAVA / "Look.java").read_text()
        self.assertIn("static String cutout(android.view.WindowInsets insets,float density)", look)
        self.assertIn("getBoundingRects", look)
        self.assertIn("Look.cutout(insets", (JAVA / "ToolsActivity.java").read_text())


if __name__ == "__main__":
    unittest.main()
