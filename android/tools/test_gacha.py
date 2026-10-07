#!/usr/bin/env python3
"""Pod Programs → Summon rates. Needs fastapi and the prepared Tools sources (scripts/prepare.py)."""
from pathlib import Path
import json, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))


class Rates(unittest.TestCase):
    def setUp(self):
        import android_gacha
        self.gacha = android_gacha
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "gacha_rates.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_means_the_defaults(self):
        self.assertEqual(self.gacha.read_settings(self.path), self.gacha.DEFAULTS)

    def test_saved_rates_are_read_back(self):
        s = {**self.gacha.DEFAULTS, "fourStarPercent": 12.5, "featuredPercent": 100.0, "multiMinRarity": 4, "stepUpBoost": False}
        self.gacha.write_settings(s, self.path)
        self.assertEqual(json.loads(self.path.read_text())["fourStarPercent"], 12.5)
        self.assertEqual(self.gacha.read_settings(self.path), s)
        self.gacha.reset(self.path)
        self.assertFalse(self.path.exists())

    def test_invalid_rates_are_refused_and_ignored(self):
        with self.assertRaises(ValueError):
            self.gacha.write_settings({**self.gacha.DEFAULTS, "fourStarPercent": 80.0, "threeStarPercent": 30.0}, self.path)
        self.path.write_text('{"fourStarPercent": 0, "multiMinRarity": 7}')
        self.assertEqual(self.gacha.read_settings(self.path), self.gacha.DEFAULTS)
        self.path.write_text("not json")
        self.assertEqual(self.gacha.read_settings(self.path), self.gacha.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
