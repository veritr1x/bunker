#!/usr/bin/env python3
"""Mods › Challenges in every game data the game loads: activate (presets,
calendar loops, restores, the gift text), the calendar's next-loop and
original-dates files, and a change on the Mods page. A challenge is applied
once, never twice, and turning them off gives back the game data exactly.
Uses the real master data; skipped without it."""
from pathlib import Path
import shutil, sys, tempfile, unittest
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
import android_calendar as cal  # noqa: E402
import android_challenges as ch  # noqa: E402
import android_mods  # noqa: E402
import android_patcher as patcher  # noqa: E402
import android_runtime  # noqa: E402
from web import config  # noqa: E402

ORIGINAL = root / "inputs/20240404193219.bin.e"


class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORIGINAL.is_file():
            raise unittest.SkipTest("needs inputs/20240404193219.bin.e")
        toc, blob = cal.read_master(ORIGINAL)
        linear = ch.linear_enemy_costumes(toc, blob, {})
        cls.probe = next(i for i, r in enumerate(ch.records(toc, blob, {}, "m_battle_npc_costume"))
                         if r["CostumeId"] in linear and r["Level"] > 0)
        cls.level = ch.records(toc, blob, {}, "m_battle_npc_costume")[cls.probe]["Level"]

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.master = self.dir / "release" / "20240404193219.bin.e"
        self.master.parent.mkdir()
        shutil.copyfile(ORIGINAL, self.master)
        (self.dir / "data").mkdir()
        (self.dir / "save").mkdir()
        for obj, name, value in ((config, "DATA_DIR", self.dir / "data"), (config, "GAME_DB_PATH", self.dir / "save" / "game.db"),
                                 (config, "RELEASE_DIR", self.master.parent), (config, "find_master_data_bin", lambda: self.master),
                                 (android_runtime, "prepare_data", lambda: None), (patcher, "validate_master", lambda path: None)):
            p = mock.patch.object(obj, name, value, create=True)
            p.start()
            self.addCleanup(p.stop)

    def mods(self, **kw):
        android_mods.write_settings(kw)

    def live_level(self, path=None):
        toc, blob = cal.read_master(path or self.master)
        return ch.records(toc, blob, {}, "m_battle_npc_costume")[self.probe]["Level"]

    def activate_copy_of(self, source, label="Test"):
        candidate = patcher.folder() / "candidate.bin.e"
        shutil.copyfile(source, candidate)
        patcher.activate(candidate, label)

    def test_activate_applies_challenges(self):
        self.mods(hardEnemies=2)
        self.activate_copy_of(ORIGINAL)
        self.assertEqual(self.live_level(), self.level * 2)
        self.assertEqual(ch.unchallenged_master().read_bytes(), ORIGINAL.read_bytes())

    def test_restore_and_gift_never_double_challenge(self):
        self.mods(hardEnemies=2)
        self.activate_copy_of(ORIGINAL)
        self.activate_copy_of(self.master, "Imported master data")  # the live (challenged) file handed back
        self.assertEqual(self.live_level(), self.level * 2)
        import android_gift
        android_gift._add_gift_text_to_game()
        self.assertEqual(self.live_level(), self.level * 2)
        toc, blob = cal.read_master(self.master)  # has_gift_text reads the prepared catalog, stubbed here
        self.assertTrue(any(r["GiftTextId"] == android_gift.GIFT_TEXT_ID for r in ch.records(toc, blob, {}, "m_gift_text")))
        for snapshot in patcher.master_history():  # snapshots hold unchallenged game data
            self.assertEqual(self.live_level(snapshot), self.level)
        self.activate_copy_of(patcher.master_history()[-1], "Restored snapshot")
        self.assertEqual(self.live_level(), self.level * 2)

    def test_off_restores_exactly(self):
        self.activate_copy_of(ORIGINAL)
        for settings in ({"hardEnemies": 2}, {"hardEnemies": 5}, {"hardEnemies": 5, "weaknessOnly": True}, {}):
            self.mods(**settings)
            ch.reapply()
        self.assertEqual(self.master.read_bytes(), ORIGINAL.read_bytes())
        self.assertFalse(list(patcher.folder().glob("unchallenged-*")))

    def test_calendar_next_and_view_are_challenged(self):
        self.mods(hardEnemies=2)
        self.activate_copy_of(ORIGINAL)
        nxt = self.master.parent / cal.NEXT_NAME
        shutil.copyfile(ORIGINAL, nxt)
        ch.finish(nxt)
        self.assertEqual(self.live_level(nxt), self.level * 2)
        # The server rolls over to the next loop by itself: the copy is still known.
        shutil.copyfile(nxt, self.master)
        self.assertEqual(ch.unchallenged_master().read_bytes(), ORIGINAL.read_bytes())

    def test_mods_save_reapplies_only_on_challenge_change(self):
        self.activate_copy_of(ORIGINAL)
        before = self.master.read_bytes()
        self.assertFalse(android_mods.save_settings({"staminaFree": True}))
        self.assertEqual(self.master.read_bytes(), before)
        self.assertTrue(android_mods.save_settings({"staminaFree": True, "slowSkills": True}))
        self.assertNotEqual(self.master.read_bytes(), before)
        self.assertFalse(android_mods.save_settings({"staminaFree": False, "slowSkills": True}))
        self.assertTrue(android_mods.save_settings({}))
        self.assertEqual(self.master.read_bytes(), before)

    def test_failed_reapply_keeps_the_settings_and_retries(self):
        self.activate_copy_of(ORIGINAL)
        with mock.patch.object(ch, "reapply", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                android_mods.save_settings({"hardEnemies": 2})
        self.assertEqual(android_mods.read_settings()["hardEnemies"], 1)  # mods.json is as the game data
        self.assertEqual(self.live_level(), self.level)
        # The same choice again is applied, not taken as already done.
        self.mods(hardEnemies=2)  # e.g. written by an older build, or a save that failed after writing
        self.assertTrue(android_mods.save_settings({"hardEnemies": 2}))
        self.assertEqual(self.live_level(), self.level * 2)

    def test_rollback_keeps_the_challenges(self):
        self.mods(hardEnemies=2)
        self.activate_copy_of(ORIGINAL)
        calls = []

        def prepare():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("catalog failed")
        with mock.patch.object(android_runtime, "prepare_data", prepare):
            with self.assertRaises(RuntimeError):
                self.activate_copy_of(ORIGINAL, "Preset")
        self.assertEqual(self.live_level(), self.level * 2)


if __name__ == "__main__":
    unittest.main()
