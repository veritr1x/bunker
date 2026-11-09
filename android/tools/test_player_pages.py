"""The player's pages (Players, the editors, Upgrade Manager) count in the catalogue's plural forms: one costume,
two costumes; never "costume(s)", which only English can read."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
import bunker_text  # noqa: E402


def render(name, **context):
    import jinja2
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / "overlays/python/web/templates")),
                             autoescape=True)
    bunker_text.install(env)
    return env.get_template(name).render(**context)


def messages(html):
    """The page script's MSG object."""
    return json.loads(re.search(r"const MSG = (\{.*?\});\n", html, re.S).group(1))


EDITORS = {
    "user_items.html": dict(user_id=1, tabs=[], paid_gem=0, free_gem=0),
    "user_costumes.html": dict(user_id=1, groups=[], karma_pools_json={}, karma_costume_slots_json={},
                               karma_state_json={}),
    "user_weapons.html": dict(user_id=1, groups=[], inventory_cap=1),
    "memoir_editor.html": dict(user_id=1, sets=[], primary_options=[], sub_options=[], default_sub_order=[],
                               legal_subs={}),
}


class Plurals(unittest.TestCase):
    def forms(self, page, name):
        return messages(render(page, **EDITORS[page]))[name]

    def test_editor_messages_have_one_and_other(self):
        expected = {
            ("user_items.html", "granted"): ["Granted {n} item.", "Granted {n} items."],
            ("user_items.html", "max_done"): ["{action} done: {n} grant.", "{action} done: {n} grants."],
            ("user_costumes.html", "granted"): ["Granted {n} costume.", "Granted {n} costumes."],
            ("user_costumes.html", "karma_confirm"): ["Update karma effects on {n} costume? A backup is taken first.",
                                                      "Update karma effects on {n} costumes? A backup is taken first."],
            ("user_costumes.html", "karma_done"): ["Updated karma on {n} costume.", "Updated karma on {n} costumes."],
            ("user_costumes.html", "missing_done"): ["Granted {n} missing costume.", "Granted {n} missing costumes."],
            ("user_weapons.html", "granted"): ["Granted {n} weapon.", "Granted {n} weapons."],
            ("user_weapons.html", "missing_done"): ["Granted {n} missing weapon.", "Granted {n} missing weapons."],
            ("memoir_editor.html", "granted"): ["Granted {name}: {n} memoir. Reload to refresh.",
                                                "Granted {name}: {n} memoirs. Reload to refresh."],
            ("memoir_editor.html", "upgraded"): ["Upgraded {n} memoir to level 15.", "Upgraded {n} memoirs to level 15."],
        }
        for (page, name), forms in expected.items():
            with self.subTest(page=page, name=name):
                self.assertEqual(self.forms(page, name), dict(zip(("one", "other"), forms)))

    def test_scripts_pick_the_form_by_count(self):
        for page in EDITORS:
            with self.subTest(page=page):
                html = render(page, **EDITORS[page])
                self.assertRegex(html, r'const PLURAL = new Intl\.PluralRules\("en"\);|'
                                       r'const LOCALE = "en";\n  const PLURAL = new Intl\.PluralRules\(LOCALE\);')
                self.assertNotIn("en-US", html)   # numbers are written in the page's language
                self.assertIn("const plural = (forms, n) => forms[PLURAL.select(n)] ?? forms.other;", html)

    def test_scripts_carry_every_form_of_the_language(self):
        # Polish counts one / few / many / other: the page hands its script all four and Polish's rules.
        polish = {"one": "Dodano {n} kostium.", "few": "Dodano {n} kostiumy.", "many": "Dodano {n} kostiumów.",
                  "other": "Dodano {n} kostiumu."}
        bunker_text.use({f"pods.costumes.granted.{form}": text for form, text in polish.items()}, language="pl")
        try:
            html = render("user_costumes.html", **EDITORS["user_costumes.html"])
        finally:
            bunker_text.use(None)
        self.assertEqual(messages(html)["granted"], polish)
        self.assertIn('const PLURAL = new Intl.PluralRules("pl");', html)

    def test_item_amounts_are_written_in_the_page_language(self):
        bunker_text.use({"pods.items.heading": "Edytor przedmiotów"}, language="pl")
        try:
            html = render("user_items.html", **EDITORS["user_items.html"])
        finally:
            bunker_text.use(None)
        self.assertIn('const LOCALE = "pl";', html)
        self.assertEqual(html.count("toLocaleString(LOCALE)"), 2)
        self.assertIn('display.textContent.replace(/\\D/g, "")', html)  # reads "27,730" and "27 730" alike

    def test_slab_panels_count_both_numbers(self):
        def line(panels, characters):
            html = render("upgrade_manager.html", user_id=1, karma_options={}, karma_defaults={},
                          panel_total=panels, owned_character_count=characters)
            return re.search(r"(\d+ panels? across \d+ owned characters?)", html).group(1)
        self.assertEqual(line(1, 1), "1 panel across 1 owned character")
        self.assertEqual(line(3, 2), "3 panels across 2 owned characters")
        self.assertEqual(line(1, 2), "1 panel across 2 owned characters")

    def test_owned_counts_follow_the_count(self):
        def upgrades(**counts):
            context = dict(user_id=1, karma_options={}, karma_defaults={}, exalt_targets=0, owned_character_count=2,
                           owned_companion_count=2, companions_to_upgrade=0, owned_weapon_count=2,
                           owned_costume_count=2)
            context.update(counts)
            return render("upgrade_manager.html", **context)
        page = upgrades(exalt_targets=1, owned_character_count=1, companions_to_upgrade=1, owned_companion_count=1,
                        owned_weapon_count=1, owned_costume_count=1)
        self.assertIn("1 of 1 owned character below the max (5)", page)
        self.assertIn("1 of 1 owned companion below max level 50", page)
        self.assertIn(">1 owned weapon<", page)
        self.assertIn(">1 owned costume<", page)
        page = upgrades(exalt_targets=1, owned_character_count=3, companions_to_upgrade=0, owned_companion_count=4,
                        owned_weapon_count=5, owned_costume_count=6)
        self.assertIn("1 of 3 owned characters below the max (5)", page)
        self.assertIn("0 of 4 owned companions below max level 50", page)
        self.assertIn(">5 owned weapons<", page)
        self.assertIn(">6 owned costumes<", page)
        memoirs = dict(EDITORS["memoir_editor.html"], inventory_cap=9)
        self.assertIn(">1 owned memoir<", render("memoir_editor.html", owned_count=1, **memoirs))
        self.assertIn(">2 owned memoirs<", render("memoir_editor.html", owned_count=2, **memoirs))


if __name__ == "__main__":
    unittest.main()
