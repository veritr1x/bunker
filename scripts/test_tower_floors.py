#!/usr/bin/env python3
"""Which master tower_floors.py reads a run's floors from."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tower_floors as tf  # noqa: E402


class Pick(unittest.TestCase):
    def test_the_newest_master_before_the_run(self):
        self.assertEqual(tf.pick([10, 20, 30], 25), 20)

    def test_a_run_before_every_master_takes_the_oldest(self):
        self.assertEqual(tf.pick([10, 20, 30], 5), 10)


if __name__ == "__main__":
    unittest.main()
