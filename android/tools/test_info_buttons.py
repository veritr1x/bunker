"""Pod Programs' explanations wait behind an ⓘ, in portrait and landscape: a page's intro beside its title, a longer
note beside what it explains. Only what the page needs to be used stays out."""
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "overlays/python/web"
CSS = (WEB / "static/css/automata.css").read_text()
BASE = (WEB / "templates/base.html").read_text()
PAGE = lambda name: (WEB / "templates" / name).read_text()


class InfoButtons(unittest.TestCase):
    def test_every_orientation_hides_them_until_asked(self):
        self.assertIn('[data-side="intro"]:not(.open), [data-info]:not(.open) { display: none !important; }', CSS)
        self.assertIn(".intro-info { flex: none; width: 28px; height: 28px;", CSS)
        # made once for the page, not only when a phone turns on its side
        head = BASE.index("function infoButtons()")
        self.assertLess(head, BASE.index("query.addEventListener"))
        self.assertIn('document.querySelectorAll(\'[data-side="intro"], [data-info]\')', BASE)
        self.assertNotIn('main.querySelectorAll(".intro-info").forEach(b => b.remove());', BASE)

    def test_a_page_with_several_players_keeps_its_intro_behind_the_button(self):
        for name in ("deck_builder.html", "gift.html"):
            with self.subTest(name=name):
                page = PAGE(name)
                self.assertNotIn('data-side{% if players|length <= 1 %}="intro"{% endif %}', page)
                self.assertRegex(page, r'<p data-side="intro">')

    def test_longer_notes_sit_behind_a_button(self):
        db = PAGE("deck_builder.html")
        self.assertIn('<div class="db-lbl" id="lbl-mode">Build from</div>', db)
        self.assertIn('<p class="help best-only" data-info="lbl-mode">All maxed ranks', db)
        self.assertIn('<p class="help owned-only">What I own uses your costumes', db)      # it holds the Allow menu
        self.assertIn('<p data-side="intro">Higher frame rates', PAGE("display.html"))
        self.assertIn('<p data-side="intro">Applies to regular and multi-step summons', PAGE("gacha.html"))
        self.assertRegex(PAGE("upgrade_manager.html"), r'id="karma-fill-name">Fill All Karma Slots</span>')
        self.assertRegex(PAGE("upgrade_manager.html"), r'<p data-info="karma-fill-name"[^>]*>\s*\[R40/30/20\]')
        self.assertIn('<p class="credit" data-info="challenges-head"', PAGE("mods.html"))

    def test_a_button_beside_a_fold_does_not_fold_it(self):
        self.assertRegex(BASE, r"e\.preventDefault\(\); e\.stopPropagation\(\);")


if __name__ == "__main__":
    unittest.main()
