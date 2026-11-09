"""Pod Programs' explanations wait behind a small round "i" (templates/_info.html), in portrait and landscape,
beside the heading, label or control they explain. Only what the page needs to be used stays out."""
import re
import sys
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "overlays/python/web"
BASE = (WEB / "templates/base.html").read_text()
INFO = (WEB / "templates/_info.html").read_text()
PAGE = lambda name: (WEB / "templates" / name).read_text()
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "android/app/src/main/python"))


def RENDER(name, **context):
    """A page as the player sees it, in English (the app's templates get t from bunker_text)."""
    import jinja2
    import bunker_text
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(WEB / "templates")), autoescape=True)
    bunker_text.install(env)
    return env.get_template(name).render(**context)
PAGES = sorted(p.name for p in (WEB / "templates").glob("*.html") if p.name not in ("base.html", "_info.html"))


class InfoIcon(unittest.TestCase):
    def render(self, source):
        import jinja2
        import bunker_text
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(WEB / "templates")), autoescape=True)
        bunker_text.install(env)  # the icon's label is catalogue text
        return env.from_string('{% from "_info.html" import info %}' + source).render()

    def test_on_its_side_the_card_opens_beside_the_tabs(self):
        # The card along the bottom started at the screen's left edge, under the 148px tab column.
        self.assertIn("@media (orientation: landscape) and (max-height: 599px) {\n"
                      "    details.info > div { left: calc(148px + 12px); right: max(16px, var(--hole-right, 0px)); }", BASE)

    def test_landscape_text_is_one_size(self):
        # On a phone on its side the right column was a size larger than the left: everything in it, fields
        # included, uses the page title's size. The viewport stops an iPhone zooming in on a small field.
        css = (WEB / "static/css/automata.css").read_text()
        landscape = css[css.rindex("@media (orientation: landscape) and (max-height: 599px) {"):]
        self.assertIn("main, main label, main p, .bracket-header, summary.bracket-header, .setting label, .setting strong, "
                      ".choice strong,\n  main input, main input[type=\"text\"], main input[type=\"number\"], main input[type=\"search\"], "
                      "main select, main textarea { font-size: var(--fs-small); }", landscape)
        self.assertIn("maximum-scale=1", BASE)

    def test_a_choice_name_keeps_its_icon_beside_it(self):
        # A block <strong> pushed the "i" after "Original calendar" onto a line of its own.
        css = (WEB / "static/css/automata.css").read_text()
        rule = re.search(r"^\.choice strong \{([^}]*)\}", css, re.M).group(1)
        self.assertNotIn("display: block", rule)

    def test_a_button_row_keeps_space_below(self):
        # Without it a panel after Save (Language › Load a pack) sat on the button in landscape.
        css = (WEB / "static/css/automata.css").read_text()
        rule = re.search(r"^\.actions \{([^}]*)\}", css, re.M).group(1)
        self.assertRegex(rule, r"margin: 16px 0;")

    def test_the_icon_overrides_the_general_summary_style(self):
        # automata.css styles every <summary> (12px padding, uppercase, letter spacing): on the icon that
        # pushed the "i" below its circle and made it a capital I.
        rule = re.search(r"details\.info > summary \{([^}]*)\}", BASE).group(1)
        for declaration in ("padding: 0", "text-transform: none", "letter-spacing: 0"):
            self.assertIn(declaration, rule)

    def test_the_macro_is_a_details_with_a_labelled_summary(self):
        html = self.render('{{ info("Short <why>.") }}')
        self.assertEqual(html, '<details class="info"><summary aria-label="More information">i</summary>'
                               '<div>Short &lt;why&gt;.</div></details>')
        html = self.render('{% call info() %}<p>One</p>{% endcall %}{{ info("x", "best-only") }}')
        self.assertIn('<div><p>One</p></div>', html)
        self.assertIn('<details class="info best-only">', html)

    def test_closed_until_asked_and_closed_by_a_tap_elsewhere(self):
        self.assertNotRegex(INFO, r"<details[^>]* open")                       # closed when the page opens
        self.assertIn("details.info > summary::-webkit-details-marker { display: none; }", BASE)
        self.assertIn('document.querySelectorAll("details.info[open]").forEach(d => { if (!d.contains(e.target)) d.open = false; });', BASE)
        self.assertIn('if (e.key === "Escape")', BASE)
        # a phone, upright or on its side: a card along the bottom of the screen, never off its edge
        self.assertIn("@media (max-width: 600px), (orientation: landscape) and (max-height: 599px) {", BASE)
        self.assertRegex(BASE, r"details\.info > div \{ position: fixed; top: auto; left: 16px; right: 16px;")

    def test_the_old_scripted_buttons_are_gone(self):
        self.assertNotIn("function infoButtons()", BASE)
        for name in PAGES:
            with self.subTest(name=name):
                page = PAGE(name)
                self.assertNotIn('data-side="intro"', page)
                self.assertNotIn("data-info=", page)

    def test_every_page_using_it_imports_it(self):
        for name in PAGES:
            page = PAGE(name)
            if "info(" in page:
                with self.subTest(name=name):
                    self.assertIn('{% from "_info.html" import info %}', page)

    def test_a_contents_link_leaves_the_explanation_out(self):
        self.assertIn('plain.querySelectorAll("details.info").forEach(d => d.remove());', BASE)

    def test_explanations_sit_beside_what_they_explain(self):
        self.assertIn('<h1 data-side>{{ t("pods.display.title") }}{{ info(t("pods.display.info")) }}', PAGE("display.html"))
        self.assertIn('<label for="fps">{{ t("pods.display.frame_rate") }}{{ info(t("pods.display.frame_rate_info")) }}', PAGE("display.html"))
        self.assertIn('<h1 data-side>{{ t("pods.gacha.title") }}{{ info(t("pods.gacha.title_info")) }}', PAGE("gacha.html"))
        db = PAGE("deck_builder.html")
        self.assertIn('<div class="db-lbl" id="lbl-mode">{{ t("pods.decks.build_from") }}{{ info(t("pods.decks.all_maxed_info"), "best-only") }}'
                      '{{ info(t("pods.decks.what_i_own_info"), "owned-only") }}</div>', db)
        self.assertIn('<p class="help owned-only">{{ allow[0] }}<select id="allow">', db)      # it holds the Allow menu
        upgrades = RENDER("upgrade_manager.html", user_id=1, karma_options={}, karma_defaults={})
        self.assertRegex(upgrades, r'id="karma-fill-name">Fill All Karma Slots</span>')
        self.assertRegex(upgrades, r'<details class="info"><summary[^>]*>i</summary><div><p>Sets every unlocked karma slot.*\[R40/30/20\]')
        self.assertIn('<span>{{ t("pods.mods.bonus") }}{{ info(t("pods.mods.bonus_info")) }}', PAGE("mods.html"))
        # never inside a <summary>: a tap would fold it too
        for name in PAGES:
            with self.subTest(name=name):
                self.assertNotRegex(PAGE(name), r"<summary[^>]*>[^<]*\{\{ info\(")


class BackupNote(unittest.TestCase):
    def test_kept_backups_are_counted(self):
        # The retention is a setting: one backup kept reads "backup", not "backups".
        page = lambda n: RENDER("backup.html", request=None, active="backups", backups=[], retention=n, game_db_exists=True,
                                lunar_tear_running="")
        self.assertIn("The latest 1 backup is kept.", page(1))
        self.assertIn("The latest 10 backups are kept.", page(10))


class PlayerLinks(unittest.TestCase):
    def test_editor_links_are_a_spaced_row(self):
        # Inline links in a paragraph: wrapped rows touched. They sit in an .actions row, plain names.
        from types import SimpleNamespace
        u = SimpleNamespace(user_id=1, player_id=1, uuid="x", name="", message="", level=1, exp=0, register_at=None,
                            last_login_at=None, total_login_count=0, paid_gem=0, free_gem=0, inventory_counts=[],
                            stackables=[])
        page = RENDER("user_detail.html", u=u)
        row = page[page.index('<div class="actions">'):]
        row = row[:row.index("</div>")]
        for name in ("Items", "Costumes", "Weapons", "Upgrades", "Memoirs", "Story Jump"):
            self.assertIn(f'class="button">{name}</a>', row)
        self.assertNotIn("[ EDIT", page)


if __name__ == "__main__":
    unittest.main()
