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


if __name__ == "__main__":
    unittest.main()
