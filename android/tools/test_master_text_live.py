#!/usr/bin/env python3
"""The pack's master texts in every game data the game loads, with Mods › Challenges: chosen, they reach the game
data in use and the calendar's files; English gives back the game data exactly; with challenges, each is applied
once and turning either off rebuilds from the untouched copy. Uses the real master data; skipped without it."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
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
PACK = {"format": 1, "language": "de", "name": "Deutsch", "version": "1", "game": {},
        "master": {"m_dokan_text.100": "⟦Dimos⟧", "m_navi_cut_in_text.1": 7},
        "bunker": {"pods.gift.sender_in_game": "Von Bunker, mit Liebe."}}


class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORIGINAL.is_file():
            raise unittest.SkipTest("needs inputs/20240404193219.bin.e")
        toc, blob = cal.read_master(ORIGINAL)
        linear = ch.linear_enemy_costumes(toc, blob, {})
        cls.probe = next(i for i, r in enumerate(ch.records(toc, blob, {}, "m_battle_npc_costume")) if r["CostumeId"] in linear and r["Level"] > 0)
        cls.level = ch.records(toc, blob, {}, "m_battle_npc_costume")[cls.probe]["Level"]

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.master = self.dir / "assets" / "release" / "20240404193219.bin.e"
        self.master.parent.mkdir(parents=True)
        shutil.copyfile(ORIGINAL, self.master)
        (self.dir / "data").mkdir()
        (self.dir / "save").mkdir()
        for obj, name, value in ((config, "DATA_DIR", self.dir / "data"), (config, "GAME_DB_PATH", self.dir / "save" / "game.db"),
                                 (config, "ASSETS_DIR", self.dir / "assets"), (config, "RELEASE_DIR", self.master.parent),
                                 (config, "find_master_data_bin", lambda: self.master),
                                 (android_runtime, "prepare_data", lambda: None), (patcher, "validate_master", lambda path: None)):
            p = mock.patch.object(obj, name, value, create=True)
            p.start()
            self.addCleanup(p.stop)
        self.active = self.dir / "translation" / "active.json"

    def choose(self, pack):
        if pack is None:
            self.active.unlink(missing_ok=True)
        else:
            self.active.parent.mkdir(exist_ok=True)
            self.active.write_text(json.dumps(pack))  # escaped, as a pack may carry a lone surrogate

    def dokan(self, path=None):
        toc, blob = cal.read_master(path or self.master)
        return {r["LanguageType"]: r["Text"] for r in ch.records(toc, blob, {}, "m_dokan_text") if r["DokanTextId"] == 100}

    def level_now(self, path=None):
        toc, blob = cal.read_master(path or self.master)
        return ch.records(toc, blob, {}, "m_battle_npc_costume")[self.probe]["Level"]

    def activate_copy_of(self, source, label="Test"):
        candidate = patcher.folder() / "candidate.bin.e"
        shutil.copyfile(source, candidate)
        patcher.activate(candidate, label)

    def test_a_chosen_pack_reaches_the_game_data_once(self):
        english = self.dokan()
        self.choose(PACK)
        self.assertTrue(ch.reapply_texts())
        self.assertEqual(self.dokan()[2], "⟦Dimos⟧")
        self.assertEqual(self.dokan()[1], english[1])
        self.assertFalse(ch.reapply_texts())  # nothing changed since
        self.assertEqual(ch.unchallenged_master().read_bytes(), ORIGINAL.read_bytes())

    def test_english_gives_back_the_game_data_exactly(self):
        self.choose(PACK)
        ch.reapply_texts()
        self.choose(None)
        self.assertTrue(ch.reapply_texts())
        self.assertEqual(self.master.read_bytes(), ORIGINAL.read_bytes())
        self.assertFalse(list(patcher.folder().glob("unchallenged-*")))

    def test_with_challenges_each_off_rebuilds_from_the_untouched_copy(self):
        android_mods.write_settings({"hardEnemies": 2})
        self.activate_copy_of(ORIGINAL)
        self.choose(PACK)
        ch.reapply_texts()
        self.assertEqual((self.level_now(), self.dokan()[2]), (self.level * 2, "⟦Dimos⟧"))
        android_mods.write_settings({})
        ch.reapply()
        self.assertEqual((self.level_now(), self.dokan()[2]), (self.level, "⟦Dimos⟧"))
        android_mods.write_settings({"hardEnemies": 2})
        ch.reapply()
        self.choose(None)
        ch.reapply_texts()
        self.assertEqual(self.level_now(), self.level * 2)
        self.assertNotEqual(self.dokan()[2], "⟦Dimos⟧")
        android_mods.write_settings({})
        ch.reapply()
        self.assertEqual(self.master.read_bytes(), ORIGINAL.read_bytes())

    def test_presets_restores_and_calendar_files_keep_the_texts(self):
        self.choose(PACK)
        self.activate_copy_of(ORIGINAL, "Restored snapshot")
        self.assertEqual(self.dokan()[2], "⟦Dimos⟧")
        for snapshot in patcher.master_history():  # snapshots hold the game data without the layer
            self.assertNotEqual(self.dokan(snapshot)[2], "⟦Dimos⟧")
        nxt = self.master.parent / cal.NEXT_NAME
        shutil.copyfile(ORIGINAL, nxt)
        ch.finish(nxt)
        self.assertEqual(self.dokan(nxt)[2], "⟦Dimos⟧")

    def test_the_bunker_gift_follows_the_pack(self):
        import android_gift
        self.choose(PACK)
        android_gift._add_gift_text_to_game()
        toc, blob = cal.read_master(self.master)
        gift = {r["LanguageType"]: r["Text"] for r in ch.records(toc, blob, {}, "m_gift_text") if r["GiftTextId"] == android_gift.GIFT_TEXT_ID}
        self.assertEqual((gift[2], gift[1]), ("Von Bunker, mit Liebe.", "From Bunker, with love."))

    def test_a_hostile_pack_never_stops_the_game_data(self):
        self.choose({**PACK, "master": {"m_dokan_text.²": "x", "m_dokan_text.100": "a\ud800b", "m_dokan_text.101": "⟦ok⟧"}})
        ch.reapply_texts()
        self.activate_copy_of(ORIGINAL)  # presets, restores, the gift text keep working
        self.assertNotIn("\ud800", self.dokan()[2])

    def test_a_pack_the_server_would_refuse_brings_no_texts(self):
        self.choose({**PACK, "format": 2})
        self.assertFalse(ch.reapply_texts())
        self.assertEqual(self.master.read_bytes(), ORIGINAL.read_bytes())

    def test_words_that_change_nothing_leave_the_game_data_as_it_is(self):
        self.choose({**PACK, "master": {"m_dokan_text.99999": "x"}, "bunker": {}})
        ch.reapply_texts()
        self.assertEqual(self.master.read_bytes(), ORIGINAL.read_bytes())
        self.assertFalse(list(patcher.folder().glob("unchallenged-*")))

    def test_game_data_imported_by_a_launcher_gets_the_texts(self):
        # FilesStore.importMaster / ImportMaster put a new master in place without Pod Programs
        self.choose(PACK)
        ch.reapply_texts()
        shutil.copyfile(ORIGINAL, self.master)
        self.assertTrue(ch.reapply_texts())
        self.assertEqual(self.dokan()[2], "⟦Dimos⟧")

    def test_the_language_alone_does_not_make_a_mods_save_rebuild(self):
        self.activate_copy_of(ORIGINAL)
        self.choose(PACK)  # chosen, not yet applied
        self.assertFalse(android_mods.save_settings({}))

    def test_switching_back_and_forth_keeps_one_snapshot_of_the_same_data(self):
        self.activate_copy_of(ORIGINAL)
        before = len(patcher.master_history())
        for pack in (PACK, None, PACK, None):
            self.choose(pack)
            ch.reapply_texts()
        self.assertEqual(len(patcher.master_history()), before)

    def test_no_game_data_yet_nothing_to_rebuild(self):
        self.master.unlink()
        self.choose(PACK)
        self.assertFalse(ch.reapply_texts())
        self.assertFalse(self.master.exists())

    def test_a_pack_too_large_or_broken_changes_nothing(self):
        self.active.parent.mkdir(exist_ok=True)
        self.active.write_bytes(b"{not json")
        self.assertFalse(ch.reapply_texts())
        self.assertEqual(self.master.read_bytes(), ORIGINAL.read_bytes())


class LauncherImports(unittest.TestCase):
    """Master data imported from a launcher's ⋮ menu (no Pod Programs involved) gets its layers at once."""

    def test_android_layers_an_imported_master(self):
        service = (root / "android/app/src/main/java/org/veritr1x/bunker/ServerService.java").read_text()
        self.assertRegex(service, r"else if\(MASTER\.equals\(action\)\) \{ FilesStore\.importMaster\(this,uri,progress\);"
                                  r" ToolsRuntime\.layerGameData\(this\); \}")
        tools = (root / "android/app/src/main/java/org/veritr1x/bunker/ToolsRuntime.java").read_text()
        self.assertIn('callAttr("layer_game_data"', tools)
        runtime = (root / "android/app/src/main/python/android_runtime.py").read_text()
        body = runtime[runtime.index("def layer_game_data("):]
        self.assertIn("reapply_texts()", body[:body.index("\ndef ", 1)])

    def test_ios_layers_an_imported_master(self):
        launcher = (root / "ios/launcher/LunarLauncher.m").read_text()
        importing = launcher[launcher.index("- (void)importMaster:(NSURL *)picked {"):]
        importing = importing[:importing.index("\n- (")]
        helper = launcher[launcher.index("static void LayerImportedMaster(void) {"):]
        self.assertIn("LTLayerGameData(", helper[:helper.index("\n}\n")])
        self.assertIn('CallRuntime(@"layer_game_data"', (root / "ios/launcher/LunarTools.m").read_text())
        # the import automation (LUNAR_IMPORT_MASTER) does what the picker does
        automated = launcher[launcher.index("if (masterSource) {"):]
        automated = automated[:automated.index("NSString *update = @\"\";")]
        self.assertIn("LayerImportedMaster(", automated)
        self.assertIn("LayerImportedMaster(", importing)
        self.assertIn("NSString *LTLayerGameData(", (root / "ios/launcher/LunarTools.h").read_text())
        runtime = (root / "ios/python/ios_runtime.py").read_text()
        body = runtime[runtime.index("def layer_game_data("):]
        self.assertIn("reapply_texts()", body[:body.index("\ndef ", 1)])


class GuardedChange(unittest.TestCase):
    """Choosing a language while the game runs beside Pod Programs: the server stops for the change, the game
    data is rebuilt, the server starts again and the game goes back to its title (as a Mods change)."""

    def test_the_change_runs_between_pause_and_resume(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import android_challenges
        import android_language
        calls = []
        app = FastAPI()
        android_runtime.install_game_guard(app, live=lambda: True, close=lambda: "",
                                           pause=lambda: calls.append("pause") or "",
                                           resume=lambda title=True: calls.append(f"resume title={title}") or "")
        app.include_router(android_language.router)
        langs = mock.Mock(active=mock.Mock(return_value="en"), choose=mock.Mock(side_effect=lambda c: calls.append("choose")))
        with mock.patch.object(android_language, "languages", return_value=langs), \
                mock.patch.object(android_language, "supported", return_value=True), \
                mock.patch.object(android_language, "_choice_files", return_value={}), \
                mock.patch.object(android_challenges, "reapply_texts", side_effect=lambda: calls.append("rebuild") or True):
            response = TestClient(app, follow_redirects=False).post("/language", data={"choice": "loaded:de"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(calls, ["pause", "choose", "rebuild", "resume title=True"])


class Wiring(unittest.TestCase):
    def test_every_change_of_language_rebuilds_the_texts(self):
        language = (root / "android/app/src/main/python/android_language.py").read_text()
        self.assertGreaterEqual(language.count("challenges.reapply_texts()"), 2)  # choose, remove the one in use
        for runtime in ("android/app/src/main/python/android_runtime.py", "ios/python/ios_runtime.py"):
            text = (root / runtime).read_text()
            # after the preset or calendar update (which already brings the texts), and never stopping the update
            body = text[text.index("def update_data"):]
            body = body[:body.index("\ndef ", 1)]
            self.assertLess(body.index("update_for(version)"), body.index("reapply_texts()"), runtime)
            self.assertIn("except Exception", body[body.index("update_for(version)"):], runtime)
        self.assertNotIn('"/language"', (root / "android/app/src/main/python/android_runtime.py").read_text().split("LIVE_SAFE")[1].split(")")[0])


if __name__ == "__main__":
    unittest.main()
