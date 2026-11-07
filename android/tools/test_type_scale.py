"""Pod Programs reads the same on every page, in portrait and landscape, light and dark: one type scale, form
controls large enough that iOS does not zoom in on them, colours that follow the theme."""
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "overlays/python/web"
CSS = (WEB / "static/css/automata.css").read_text()
PAGES = {p.name: p.read_text() for p in (WEB / "templates").glob("*.html")}
EVERY = {"automata.css": CSS, **PAGES}


class TypeScale(unittest.TestCase):
    def test_every_font_size_is_on_the_scale(self):
        for name, text in EVERY.items():
            for m in re.finditer(r"font-size:\s*([^;}\"]+)", text):
                with self.subTest(name=name, value=m.group(1)):
                    self.assertRegex(m.group(1).strip(), r"^(var\(--fs-(label|small|body|lead|display|input)\)|inherit|\d*\.?\d+em)(\s*!important)?$")

    def test_font_shorthands_use_the_scale(self):
        for name, text in EVERY.items():
            for m in re.finditer(r"\bfont:\s*([^;}\"]+)", text):
                with self.subTest(name=name, value=m.group(1)):
                    self.assertNotRegex(m.group(1), r"(^|\s)\d*\.?\d+px")

    def test_two_weights(self):
        for name, text in EVERY.items():
            with self.subTest(name=name):
                self.assertNotRegex(text, r"font-weight:\s*(500|600)\b")
                self.assertNotRegex(text, r"\bfont:\s*(italic\s+)?(500|600)\s")

    def test_nothing_reads_smaller_than_the_label_size(self):
        self.assertIn("--fs-label: 12px;", CSS)

    def test_form_controls_are_16px(self):
        self.assertIn("--fs-input: 16px;", CSS)
        self.assertIn('input[type="text"], input[type="number"], input[type="search"], select, textarea { font-size: var(--fs-input); }', CSS)


class Readable(unittest.TestCase):
    def test_owned_rows_are_not_faded(self):
        self.assertIn(".grant-form.costume.owned, .grant-form.weapon.owned, .grant-form.costume.owned:hover, .grant-form.weapon.owned:hover { opacity: 1; }", CSS)

    def test_template_colours_follow_the_theme(self):
        for name, text in PAGES.items():
            with self.subTest(name=name):
                self.assertNotIn("rgba(220,216,192", text)   # the dark theme's ink, invisible on the light paper
                self.assertNotIn("var(--bg-deep)", text)     # never defined

    def test_gift_categories_wrap_rather_than_cut(self):
        card = re.search(r"\.gift-card\{[^}]*\}", PAGES["gift.html"]).group(0)
        self.assertNotIn("ellipsis", card)

    def test_controls_shrink_to_their_column(self):
        for name in ("memoir_editor.html", "upgrade_manager.html", "user_costumes.html"):
            with self.subTest(name=name):
                self.assertNotRegex(PAGES[name], r"min-width:\s*[2-9]\d\dpx")


if __name__ == "__main__":
    unittest.main()
