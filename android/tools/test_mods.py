#!/usr/bin/env python3
"""Pod Programs > Mods: mods.json, its presets and the page. Every mod is off
without the file. Needs fastapi and jinja2."""
from pathlib import Path
import json, sys, tempfile, unittest, unittest.mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
import android_mods  # noqa: E402
import android_runtime  # noqa: E402


class Settings(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "mods.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_no_file_means_every_mod_off(self):
        s = android_mods.read_settings(self.path)
        self.assertEqual(s, android_mods.OFF)
        self.assertEqual(s["rewardMultiplier"], 1)
        self.assertFalse(any(v for k, v in s.items() if android_mods.KIND[k] == "bool"))
        self.assertTrue(all(v == 1 for k, v in s.items() if android_mods.KIND[k] != "bool"))
        self.assertEqual(android_mods.preset_of(s), "original")

    def test_saving_and_reading_back(self):
        android_mods.write_settings({"staminaFree": True, "rewardMultiplier": 4}, self.path)
        saved = json.loads(self.path.read_text())
        self.assertTrue(saved["staminaFree"])
        self.assertEqual(saved["rewardMultiplier"], 4)
        # Every key the server knows is written, so the file says what is off too.
        self.assertEqual(set(saved), set(android_mods.KEYS))
        s = android_mods.read_settings(self.path)
        self.assertTrue(s["staminaFree"])
        self.assertFalse(s["shopUnlimited"])
        self.assertIsNone(android_mods.preset_of(s))

    def test_turning_everything_off_removes_the_file(self):
        android_mods.write_settings({"shopUnlimited": True}, self.path)
        self.assertTrue(self.path.exists())
        android_mods.write_settings({}, self.path)
        self.assertFalse(self.path.exists())

    def test_comfort_preset_is_the_comfort_mods_eight(self):
        _, _, values = android_mods.PRESETS["comfort"]
        android_mods.write_settings(values, self.path)
        s = android_mods.read_settings(self.path)
        self.assertEqual(android_mods.preset_of(s), "comfort")
        self.assertEqual(s["rewardMultiplier"], android_mods.MAX_MULTIPLIER)
        on = {k for k, v in s.items() if v is True}
        self.assertEqual(on, {"staminaFree", "staminaItemsToGold", "ticketsToGems", "shopUnlimited", "lostItemGems",
                              "noDuplicateFourStar", "pityRewards"})
        self.assertEqual(s["expMultiplier"], 1)
        self.assertEqual(s["hardEnemies"], 1)

    def test_everything_preset(self):
        _, _, values = android_mods.PRESETS["everything"]
        android_mods.write_settings(values, self.path)
        s = android_mods.read_settings(self.path)
        self.assertEqual(android_mods.preset_of(s), "everything")
        for key, kind, *_ in (m for g, mods in android_mods.GROUPS if g != "Challenges" for m in mods):
            self.assertEqual(s[key], True if kind == "bool" else android_mods.MAX_MULTIPLIER, key)
        self.assertEqual((s["hardEnemies"], s["weaknessOnly"], s["slowSkills"]), (1, False, False))

    def test_groups_and_order(self):
        groups = {g: [m[0] for m in mods] for g, mods in android_mods.GROUPS}
        self.assertEqual(list(groups), ["Quests", "Items & shops", "Summons", "World", "Challenges"])
        self.assertEqual(groups["Quests"], ["staminaFree", "unlimitedDailyPlays", "freeSkips", "rewardMultiplier", "expMultiplier"])
        self.assertEqual(groups["Items & shops"], ["staminaItemsToGold", "ticketsToGems", "shopUnlimited", "lostItemGems"])
        self.assertEqual(groups["Summons"], ["noDuplicateFourStar", "pityRewards"])
        self.assertEqual(groups["World"], ["storyFriends"])
        self.assertEqual(groups["Challenges"], ["hardEnemies", "weaknessOnly", "slowSkills"])
        self.assertEqual(android_mods.CHALLENGE_KEYS, ("hardEnemies", "weaknessOnly", "slowSkills"))

    def test_validate_new_ranges(self):
        for bad in ({"expMultiplier": 11}, {"expMultiplier": 0}, {"hardEnemies": 4}, {"hardEnemies": 0.5}):
            with self.assertRaises(ValueError, msg=bad):
                android_mods.write_settings(bad, self.path)
        for ok in ({"expMultiplier": 10}, {"hardEnemies": 1.5}, {"hardEnemies": 5}):
            android_mods.write_settings(ok, self.path)

    def test_old_file_keeps_its_mods(self):
        self.path.write_text('{"staminaFree": true, "rewardMultiplier": 10}')
        s = android_mods.read_settings(self.path)
        self.assertTrue(s["staminaFree"])
        self.assertEqual(s["rewardMultiplier"], 10)
        self.assertEqual((s["expMultiplier"], s["hardEnemies"], s["freeSkips"], s["storyFriends"]), (1, 1, False, False))

    def test_challenge_bonus_matches_go(self):
        b = android_mods.challenge_bonus
        on = lambda **kw: {**android_mods.OFF, **kw}
        self.assertEqual(b(on(), False), 1)
        self.assertEqual(b(on(hardEnemies=2), False), 3)
        self.assertEqual(b(on(hardEnemies=5, weaknessOnly=True), False), 10)
        self.assertEqual(b(on(hardEnemies=1.5, slowSkills=True), False), 4)
        self.assertEqual(b(on(weaknessOnly=True, slowSkills=True), False), 4)
        self.assertEqual(b(on(hardEnemies=2, storyFriends=True), False), 3)
        self.assertEqual(b(on(hardEnemies=2, freeSkips=True), False), 1)
        self.assertEqual(b(on(hardEnemies=2, expMultiplier=2), False), 1)
        self.assertEqual(b(on(hardEnemies=2, rewardMultiplier=2), False), 1)
        self.assertEqual(b(on(hardEnemies=2), True), 1)

    def test_out_of_range_or_unknown_settings_are_refused(self):
        for bad in ({"rewardMultiplier": 0}, {"rewardMultiplier": 11}, {"somethingElse": True}):
            with self.assertRaises(ValueError, msg=bad):
                android_mods.write_settings(bad, self.path)
        self.assertFalse(self.path.exists())
        # A broken file reads as no mods, like the server.
        self.path.write_text('{"rewardMultiplier": 50, "staminaFree": true}')
        self.assertEqual(android_mods.read_settings(self.path), android_mods.OFF)

    def test_keys_match_the_server(self):
        server = (root / "overlays/server/internal/mods/mods.go").read_text()
        for key in android_mods.KEYS:
            self.assertIn(f'`json:"{key}"`', server, key)


class Page(unittest.TestCase):
    def test_the_page_renders_every_mod_and_credits_the_comfort_mod(self):
        html = self.render()
        for _, mods in android_mods.GROUPS:
            for key, _kind, title, *_ in mods:
                self.assertIn(f'name="{key}"', html)
                self.assertIn(title, html)
        self.assertIn("NavHobbyDev", html)
        self.assertIn(android_mods.COMFORT_MOD, html)
        # The credit is in the Comfort preset's info, not a line on the page.
        comfort = html[html.index('value="comfort"'):]
        comfort = comfort[:comfort.index("</details>")]
        self.assertIn("NavHobbyDev", comfort)
        self.assertIn(android_mods.COMFORT_MOD, comfort)
        self.assertNotIn('<p class="credit" data-side>Most mods', html)

    def render(self, settings=None, paused=False):
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(root / "overlays/python/web/templates")), autoescape=True)  # as the app
        import bunker_text
        bunker_text.install(env)
        settings = {**android_mods.OFF, **(settings or {})}
        return env.get_template("mods.html").render(active="mods", settings=settings, groups=android_mods.GROUPS,
            presets=android_mods.PRESETS, current=android_mods.preset_of(settings), max_multiplier=10,
            hard_enemies=android_mods.HARD_ENEMIES, source=android_mods.COMFORT_MOD, message="", error="",
            **android_mods.bonus_view(settings, paused))

    def test_page_groups_render_and_fold(self):
        import re
        html = self.render()
        for group in ["Preset"] + [g for g, _ in android_mods.GROUPS]:
            name = re.escape(group.replace("&", "&amp;"))
            self.assertRegex(html, r'<details class="mods-group" data-group="%s" open[^>]*>\s*<summary[^>]*>[^<]*%s' % (name, name), group)
        self.assertIn("localStorage", html)  # which groups are folded, per viewer
        self.assertIn("Everything", html)

    def test_bonus_line(self):
        self.assertIn("Turn on a challenge to earn it.", self.render())
        html = self.render({"hardEnemies": 2})
        self.assertIn('id="bonus-x">×3<', html)
        self.assertIn("Earned on every quest clear.", html)
        self.assertIn("Paused: a Quests, Items &amp; shops or Summons mod is on.", self.render({"hardEnemies": 2, "freeSkips": True}))
        self.assertIn("Paused until tomorrow: you started a new day.", self.render({"hardEnemies": 2}, paused=True))
        self.assertIn('<option value="2" selected>Enemies ×2 — rewards ×3</option>', html)

    def test_the_live_bonus_line_knows_about_a_new_day(self):
        # Loaded with no challenge on, or with a comfort mod on, the page must
        # still pause the bonus once a challenge is ticked or the mod unticked.
        for settings in ({}, {"hardEnemies": 2, "freeSkips": True}):
            self.assertIn("PAUSED_TODAY = true", self.render(settings, paused=True), settings)
            self.assertIn("PAUSED_TODAY = false", self.render(settings), settings)

    def test_saved_message_says_what_happened_to_the_challenges(self):
        with unittest.mock.patch.object(android_runtime, "next_step", lambda: "NEXT"):
            self.assertEqual(android_mods.saved_message("Saved.", False, {**android_mods.OFF}),
                             "Saved. The mods apply from the game's next action.")
            self.assertEqual(android_mods.saved_message("Saved.", True, {**android_mods.OFF, "slowSkills": True}),
                             "Saved. Challenges are on. NEXT")
            self.assertEqual(android_mods.saved_message("Saved.", True, {**android_mods.OFF}),
                             "Saved. Challenges are off. NEXT")

    def test_saving_keeps_pod_programs_answering(self):
        # A challenge change rewrites the game data for seconds: that runs
        # off the event loop, so other pages keep loading meanwhile.
        import asyncio

        class Request:
            def __init__(self, form):
                self._form = form

            async def form(self):
                return self._form
        ran = []

        def save_settings(settings):
            try:
                asyncio.get_running_loop()
                ran.append("on the event loop")
            except RuntimeError:
                ran.append("off it")
            return False
        with unittest.mock.patch.object(android_mods, "save_settings", save_settings), \
                unittest.mock.patch.object(android_mods, "read_settings", lambda: dict(android_mods.OFF)):
            asyncio.run(android_mods.save(Request({})))
            asyncio.run(android_mods.preset(Request({"name": "original"})))
        self.assertEqual(ran, ["off it", "off it"])

    def test_changing_mods_leaves_the_game_running(self):
        # The server reads mods.json as each mod is used: nothing to restart.
        self.assertIn("/mods", android_runtime.LIVE_SAFE)
        self.assertIn("/mods/preset", android_runtime.LIVE_SAFE)


if __name__ == "__main__":
    unittest.main()
