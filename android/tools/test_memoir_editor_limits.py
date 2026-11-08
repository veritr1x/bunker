#!/usr/bin/env python3
"""Pod Programs › Memoir Editor (lunar-base's, web/services/memoir_service.py): as shipped it writes whatever it is
given (four maxed sub stats, any value). Its "Game-legal only" toggle limits it to memoirs the original game could
make: at most four sub stats, each a different stat and a percentage, crit or agility one (the guide lists no flat
sub stat), none past its top (25% crit rate, 36% crit damage, 12.5% HP/ATK/DEF, 72 agility), within the rolls a
memoir gets (each its largest starting value; up to 6 on one sub stat, 9 in all: deckbuilder/raise_.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app/src/main/python"))
from web.services import memoir_service as ms   # noqa: E402

sub = lambda slot, key, value=None: {"slot": slot, "sub_key": key, **({"value": value} if value is not None else {})}
MAXED = [sub(1, "crit_rate", 250), sub(2, "crit_dmg", 360), sub(3, "atk_pct", 125), sub(4, "hp_flat", 6500)]


class AsShippedTest(unittest.TestCase):
    def test_without_the_toggle_it_writes_what_it_is_given(self):
        self.assertEqual([s["value"] for s in ms._build_subs_for_shim(MAXED)], [250, 360, 125, 6500])
        self.assertEqual(ms._build_subs_for_shim([sub(1, "crit_rate", 9999)])[0]["value"], 9999)
        self.assertIn("hp_flat", ms.SUB_BY_KEY)


class GameLegalTest(unittest.TestCase):
    build = staticmethod(lambda subs: ms._build_subs_for_shim(subs, legal=True))

    def test_a_full_legal_memoir_is_accepted(self):
        out = self.build([sub(1, "crit_rate", 250), sub(2, "crit_dmg", 60), sub(3, "atk_pct", 50), sub(4, "hp_pct", 25)])
        self.assertEqual([s["value"] for s in out], [250, 60, 50, 25])

    def test_every_top_is_reachable_alone(self):
        for key, top in (("crit_rate", 250), ("crit_dmg", 360), ("atk_pct", 125), ("hp_pct", 125), ("def_pct", 125), ("agility", 72)):
            self.assertEqual(self.build([sub(1, key, top)])[0]["value"], top)

    def test_four_maxed_sub_stats_are_refused(self):
        with self.assertRaisesRegex(ms.MemoirError, "rolls"):
            self.build([sub(1, "crit_rate", 250), sub(2, "crit_dmg", 360), sub(3, "atk_pct", 125), sub(4, "hp_pct", 125)])

    def test_a_value_past_its_top_is_refused(self):
        with self.assertRaisesRegex(ms.MemoirError, "top"):
            self.build([sub(1, "crit_rate", 9999)])

    def test_flat_sub_stats_are_refused(self):
        with self.assertRaisesRegex(ms.MemoirError, "flat"):
            self.build([sub(1, "hp_flat", 6500)])

    def test_one_stat_twice_is_refused(self):
        with self.assertRaisesRegex(ms.MemoirError, "twice"):
            self.build([sub(1, "crit_rate", 50), sub(2, "crit_rate", 50)])

    def test_a_legal_default_fill_exists(self):
        out = self.build([sub(i, k, ms.LEGAL_DEFAULTS[k]) for i, k in enumerate(ms.LEGAL_SUB_ORDER, 1)])
        self.assertEqual(len(out), 4)

    def test_a_main_must_fit_its_place_in_the_set(self):
        """The first memoir of a set mains ATK, DEF or HP; the second may also main crit; the third may also main agility."""
        ms.check_legal_main("atk_pct", 0)
        ms.check_legal_main("crit_rate", 1)
        ms.check_legal_main("agility", 2)
        for key, index in (("crit_rate", 0), ("crit_dmg", 2), ("agility", 0), ("agility", 1)):
            with self.assertRaisesRegex(ms.MemoirError, "memoir"):
                ms.check_legal_main(key, index)
        self.assertEqual(ms.LEGAL_PRIMARY_DEFAULTS, ["atk_pct", "crit_rate", "atk_pct"])
        for i, key in enumerate(ms.LEGAL_PRIMARY_DEFAULTS):
            ms.check_legal_main(key, i)

    def test_both_write_paths_take_the_toggle(self):
        import inspect
        self.assertIn("legal", inspect.signature(ms.grant_set).parameters)
        self.assertIn("legal", inspect.signature(ms.fix_slots).parameters)


if __name__ == "__main__":
    unittest.main()


class ToggleTest(unittest.TestCase):
    """The page: a "Game-legal only" toggle, off by default, that both write paths send."""
    PAGE = (Path(__file__).resolve().parents[2] / "overlays/python/web/templates/memoir_editor.html").read_text()
    ROUTE = (Path(__file__).resolve().parents[1] / "app/src/main/python/web/routes/memoir_editor.py").read_text()

    def test_the_toggle_is_there_and_off(self):
        self.assertIn('<input type="checkbox" id="legal-only">', self.PAGE)

    def test_both_requests_send_it(self):
        self.assertEqual(self.PAGE.count("legal: legalOnly()"), 2)

    def test_its_options_come_from_the_service(self):
        self.assertIn('"legal_subs"', self.ROUTE)
        self.assertIn('"primaries"', self.ROUTE)
        self.assertIn("const LEGAL = {{ legal_subs|tojson }};", self.PAGE)
