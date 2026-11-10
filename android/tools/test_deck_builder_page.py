#!/usr/bin/env python3
"""Pod Programs › Deck Builder in a real browser (headless Chromium, via Playwright).

The page is rendered from overlays/python/web/templates with stand-in answers to its
requests, so neither the server nor game files are needed. Needs playwright and jinja2
(scripts/requirements-web-tests.txt) and a browser: Playwright's Chromium
(python -m playwright install chromium), or Google Chrome. Skipped without them.
"""
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import unittest

root = Path(__file__).resolve().parents[2]
TEMPLATES = root / "overlays/python/web/templates"
DECKS = 30
# A 1x1 PNG, served with no-store: a portrait loaded again would be asked for again.
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")

try:
    from jinja2 import Environment, FileSystemLoader
    from playwright.sync_api import Error as PlaywrightError, sync_playwright
except ImportError:  # pragma: no cover - the browser tests are optional
    sync_playwright = None


def deck(i):
    tile = lambda n: {"element": "fire", "new": False, "name": f"C{n}", "id": n, "slot": n}
    return {"key": f"k{i}", "rank": i + 1, "title": f"Deck {i + 1}", "strategy": "Burst", "win_pct": 50, "force": 100000,
            "tiles": [tile(1), tile(2), tile(3)]}


COSTUMES = [{"id": 100 + i, "name": f"Name{i} Costume", "character": f"Name{i}", "element": "fire"} for i in range(12)]


@unittest.skipIf(sync_playwright is None, "needs playwright and jinja2 (scripts/requirements-web-tests.txt)")
class DeckBuilderPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
        cls.html = env.get_template("deck_builder.html").render(
            players=[(1, "P")], user=1, preparing=False, bosses=[], opponents=[], slots=[], request=None)
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

    def page(self, width, height):
        self.portraits = []
        page = self.browser.new_page(viewport={"width": width, "height": height})
        self.addCleanup(page.close)

        def answer(route):
            url = urlparse(route.request.url)
            if url.path == "/decks/results":
                q = parse_qs(url.query)
                offset, limit = int(q["offset"][0]), int(q["limit"][0])
                route.fulfill(json={"total": DECKS, "items": [deck(i) for i in range(offset, min(offset + limit, DECKS))],
                                    "exhausted": offset + limit >= DECKS})
            elif url.path == "/decks/costumes":
                route.fulfill(json=COSTUMES)
            elif url.path.startswith("/decks/portrait"):
                self.portraits.append(url.path)
                route.fulfill(body=PNG, content_type="image/png", headers={"Cache-Control": "no-store"})
            elif url.path == "/":
                route.fulfill(body=self.html, content_type="text/html")
            else:
                route.fulfill(status=404, body="")

        page.route("**/*", answer)
        page.goto("http://bunker.test/")
        return page

    def decks(self, page):
        return page.locator("#cards .rc").count()

    def scroll_to_the_end(self, page):
        for _ in range(12):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(250)

    def test_a_tall_screen_keeps_loading_decks(self):
        # On a TV the first six fit with room to spare: the list stopped at six, with nothing to scroll.
        page = self.page(3008, 1692)
        page.wait_for_function(f"document.querySelectorAll('#cards .rc').length > 6", timeout=10_000)
        self.scroll_to_the_end(page)
        page.wait_for_function(f"document.querySelectorAll('#cards .rc').length === {DECKS}", timeout=10_000)

    def test_a_phone_loads_six_then_more_on_scrolling(self):
        page = self.page(390, 844)
        page.wait_for_function("document.querySelectorAll('#cards .rc').length === 6", timeout=10_000)
        page.wait_for_timeout(500)
        self.assertEqual(self.decks(page), 6)
        self.scroll_to_the_end(page)
        page.wait_for_function(f"document.querySelectorAll('#cards .rc').length === {DECKS}", timeout=10_000)

    def test_tapping_a_character_keeps_the_portraits(self):
        page = self.page(1210, 834)
        page.click(".open-filters")
        page.wait_for_function(f"document.querySelectorAll('#f-chars .fc img').length === {len(COSTUMES)}", timeout=10_000)
        page.evaluate("document.querySelectorAll('#f-chars img').forEach(i => i.dataset.same = '1')")
        tile = page.locator("#f-chars .fc").nth(2)
        for mark, state in (("✓", "inc"), ("✕", "exc"), ("✓", None)):
            tile.click()
            classes = tile.get_attribute("class").split()
            self.assertEqual(tile.locator(".mark").inner_text(), mark)
            self.assertEqual([c for c in classes if c in ("inc", "exc")], [state] if state else [])
        self.assertTrue(page.evaluate("[...document.querySelectorAll('#f-chars img')].every(i => i.dataset.same === '1')"))
        page.wait_for_timeout(500)
        # Portraits load lazily, so some first loads come late; none may be asked for twice.
        self.assertEqual(sorted(self.portraits), sorted(set(self.portraits)))


if __name__ == "__main__":
    unittest.main()
