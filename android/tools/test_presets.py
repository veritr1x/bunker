#!/usr/bin/env python3
"""Pod Programs › Content presets (android_patcher.arguments): which event
chapters a preset keeps. Needs the Android Python requirements."""
from pathlib import Path
import json, sys, tempfile, unittest
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
import android_patcher as ap  # noqa: E402
from web import config  # noqa: E402

CONFIG = json.loads((root / "android/app/src/main/python/patcher/config.json").read_text())
# EventQuestType: 1 marathon (limited), 6 character, 7 Dark Memories, 8 cage,
# 10 Abyss Tower, 11 Recollections of Dusk, 12 Labyrinth.
CHAPTERS = [{"EventQuestChapterId": 572, "EventQuestType": 1}, {"EventQuestChapterId": 901, "EventQuestType": 6},
            {"EventQuestChapterId": 99001, "EventQuestType": 7}, {"EventQuestChapterId": 300001, "EventQuestType": 8},
            {"EventQuestChapterId": 701, "EventQuestType": 10}, {"EventQuestChapterId": 500001, "EventQuestType": 11},
            {"EventQuestChapterId": 900001, "EventQuestType": 12}]


def kept(arguments):
    ids = set()
    for part in arguments[arguments.index("--event-quests") + 1].split(","):
        part = part.strip()
        if "-" in part:
            low, high = part.split("-")
            ids |= set(range(int(low), int(high) + 1))
        elif part:
            ids.add(int(part))
    return ids


class Presets(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "EntityMEventQuestChapterTable.json").write_text(json.dumps(CHAPTERS))
        self.patch = mock.patch.object(config, "MASTERDATA_DIR", self.dir, create=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_every_preset_keeps_the_permanent_chapters(self):
        # A preset left them out: Dark Memories and Recollections of Dusk were empty.
        for preset, _ in ap.PRESETS + ap.SPLITS:
            self.assertLessEqual({901, 99001, 300001, 701, 500001, 900001}, kept(ap.arguments(preset, CONFIG)), preset)

    def test_limited_events_follow_the_preset(self):
        self.assertNotIn(572, kept(ap.arguments("Clear", CONFIG)))

    def test_the_preset_selection_is_kept(self):
        self.assertIn(501, kept(ap.arguments("Rec_1", CONFIG)))
        self.assertNotIn(501, kept(ap.arguments("Clear", CONFIG)))

    def test_without_game_tables_the_preset_is_as_configured(self):
        (self.dir / "EntityMEventQuestChapterTable.json").unlink()
        self.assertEqual(kept(ap.arguments("Clear", CONFIG)), kept(["--event-quests", ap.expand(CONFIG, "EVENTS_MAIN")]))


class Update(unittest.TestCase):
    """After an update the preset's master data is built again (android_patcher.reapply_preset)."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "saves").mkdir()
        self.master = self.dir / "master.bin.e"
        self.master.write_bytes(b"made by Story")
        self.applied = []
        for p in (mock.patch.object(config, "DATA_DIR", self.dir / "tools", create=True),
                  mock.patch.object(config, "GAME_DB_PATH", self.dir / "saves/game.db", create=True),
                  mock.patch.object(config, "find_master_data_bin", lambda: self.master, create=True),
                  mock.patch.object(ap, "apply_preset", lambda preset, cfg: self.applied.append(preset)),
                  mock.patch.object(ap, "get_config", lambda: CONFIG)):
            p.start()
            self.addCleanup(p.stop)
        (self.dir / "tools").mkdir()

    def made_by(self, label, data=b"made by Story"):
        ap.runtime.write_json(ap.folder() / "active.json", {"label": label, "sha256": ap.runtime.fingerprint(self.master) if data is None else __import__("hashlib").sha256(data).hexdigest()})

    def test_a_preset_is_applied_again_with_the_new_build(self):
        self.made_by("Story")
        self.assertTrue(ap.update_for("1.6.3"))
        self.assertEqual(self.applied, ["Clear"])
        self.assertEqual(ap.updated_file().read_text(), "1.6.3")

    def test_once_per_version(self):
        self.made_by("Record 2")
        ap.update_for("1.6.3")
        self.assertFalse(ap.update_for("1.6.3"))
        self.assertEqual(self.applied, ["Rec_2"])

    def test_master_data_changed_since_is_left_alone(self):
        # Imported or restored after the preset: active.json no longer matches.
        self.made_by("Story", data=b"something else")
        ap.update_for("1.6.3")
        self.assertEqual(self.applied, [])

    def test_restored_snapshot_is_left_alone(self):
        self.made_by("Restored snapshot", data=None)
        ap.update_for("1.6.3")
        self.assertEqual(self.applied, [])

    def test_no_preset_is_left_alone(self):
        self.assertTrue(ap.update_for("1.6.3"))
        self.assertEqual(self.applied, [])

    def test_with_the_calendar_on_the_preset_is_not_applied(self):
        self.made_by("Story")
        with mock.patch("android_calendar.read_state", lambda: {"loop": 1}):
            ap.update_for("1.6.3")
        self.assertEqual(self.applied, [])


if __name__ == "__main__":
    unittest.main()
