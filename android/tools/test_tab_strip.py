#!/usr/bin/env python3
"""Pod Programs' tab strip in a real browser (headless Chromium, via Playwright).

On a phone the tabs scroll sideways (on its side, down a column). Each tab is a
page of its own, so the strip used to start from the first tab on every page:
the tab just opened could be out of view and the next had to be found again.
It keeps its place from page to page, and the open tab is always in view.

Deck Builder reloads itself once its pieces are ready. A tab tapped while they
were being prepared waited on the server, and that reload cancelled it: the
tap did nothing. A tab tapped first now wins.

Pages are rendered from overlays/python/web/templates with stand-in answers.
Needs playwright and jinja2 (scripts/requirements-web-tests.txt) and a browser;
skipped without them.
"""
from pathlib import Path
from urllib.parse import urlparse
import unittest

root = Path(__file__).resolve().parents[2]
TEMPLATES = root / "overlays/python/web/templates"
STATIC = root / "overlays/python/web/static"
TABS = {"/": "home", "/patcher": "patcher", "/users": "users", "/backups": "backups", "/display": "display",
        "/language": "language", "/gacha": "gacha", "/mods": "mods", "/gift": "gift", "/items": "items",
        "/costumes": "costumes", "/weapons": "weapons", "/upgrades": "upgrades", "/memoirs": "memoirs", "/story": "story"}

try:
    from jinja2 import DictLoader, Environment, FileSystemLoader, ChoiceLoader
    from playwright.sync_api import Error as PlaywrightError, sync_playwright
except ImportError:  # pragma: no cover - the browser tests are optional
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "needs playwright and jinja2 (scripts/requirements-web-tests.txt)")
class TabStrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(root / "android/app/src/main/python"))
        import bunker_text
        cls.env = Environment(loader=ChoiceLoader([
            DictLoader({"plain.html": '{% extends "base.html" %}{% block content %}<h1 id="page">{{ active }}</h1>{% endblock %}'}),
            FileSystemLoader(str(TEMPLATES))]))
        bunker_text.install(cls.env)
        cls.playwright = sync_playwright().start()
        cls.browser = None
        for options in ({}, {"channel": "chrome"}):
            try:
                cls.browser = cls.playwright.chromium.launch(headless=True, **options)
                break
            except PlaywrightError:
                continue
        if cls.browser is None:
            cls.playwright.stop()
            raise unittest.SkipTest("no browser: python -m playwright install chromium")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def page(self, width=390, height=844, held=()):
        """A phone-sized page; requests for paths in held wait in self.held until the test answers them."""
        self.held = {}
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)

        def answer(route):
            path = urlparse(route.request.url).path
            if path in held:
                self.held[path] = route
            elif path.startswith("/static/"):
                route.fulfill(path=str(STATIC / path[len("/static/"):]))
            elif path == "/decks":
                route.fulfill(body=self.env.get_template("deck_builder.html").render(
                    active="decks", players=[(1, "P")], user=1, preparing=True, bosses=[], opponents=[], slots=[], request=None),
                    content_type="text/html")
            elif path in TABS:
                route.fulfill(body=self.env.get_template("plain.html").render(active=TABS[path]), content_type="text/html")
            elif path == "/decks/prepare":
                route.fulfill(json={"ok": True})
            else:
                route.fulfill(json={})

        page.route("**/*", answer)
        return page

    def strip(self, page):
        return page.evaluate("""() => {
            const nav = document.querySelector("nav.primary"), n = nav.getBoundingClientRect();
            const a = nav.querySelector("a.active").getBoundingClientRect();
            return {left: nav.scrollLeft, scrolls: nav.scrollWidth > nav.clientWidth, shown: a.left >= n.left - 1 && a.right <= n.right + 1};
        }""")

    def test_the_strip_keeps_its_place_from_page_to_page(self):
        page = self.page()
        page.goto("http://bunker.test/gacha")
        self.assertTrue(self.strip(page)["scrolls"], "the tabs should overflow a phone's width")
        page.evaluate("document.querySelector('nav.primary').scrollLeft = 420")
        page.wait_for_timeout(100)
        page.evaluate("document.querySelector('nav.primary a[href=\"/mods\"]').click()")
        page.wait_for_selector("#page:text('mods')")
        s = self.strip(page)
        self.assertTrue(s["shown"])
        self.assertAlmostEqual(s["left"], 420, delta=2)

    def test_the_open_tab_is_in_view(self):
        page = self.page()
        page.goto("http://bunker.test/story")
        s = self.strip(page)
        self.assertTrue(s["shown"])
        self.assertGreater(s["left"], 0)

    def test_a_tab_tapped_while_deck_builder_prepares_opens(self):
        page = self.page(held=("/decks/prepare", "/items"))
        page.goto("http://bunker.test/decks")
        page.wait_for_function("document.querySelector('nav.primary a[href=\"/items\"]')")
        for _ in range(50):
            if "/decks/prepare" in self.held:
                break
            page.wait_for_timeout(50)
        page.evaluate("document.querySelector('nav.primary a[href=\"/items\"]').click()")
        for _ in range(50):
            if "/items" in self.held:
                break
            page.wait_for_timeout(50)
        self.assertIn("/items", self.held)
        self.held.pop("/decks/prepare").fulfill(json={"ok": True})
        page.wait_for_timeout(300)
        route = self.held.pop("/items", None)
        if route:
            route.fulfill(body=self.env.get_template("plain.html").render(active="items"), content_type="text/html")
        page.wait_for_timeout(500)
        self.assertEqual(urlparse(page.url).path, "/items")


if __name__ == "__main__":
    unittest.main()
