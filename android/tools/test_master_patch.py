"""The builders' master data is what Pod Programs makes with nothing picked.

Needs the player's own inputs/20240404193219.bin.e; skipped without it.
"""
from pathlib import Path
import tempfile
import unittest

import assemble_apk

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "inputs/20240404193219.bin.e"
POD_PROGRAMS = ROOT / "android/app/src/main/python/patcher/patch_masterdata.py"


class MasterPatchTests(unittest.TestCase):
    def test_builds_start_with_the_pod_programs_data(self):
        if not ORIGINAL.is_file() or not POD_PROGRAMS.is_file():
            self.skipTest("needs inputs/20240404193219.bin.e and prepared sources (scripts/prepare.py)")
        original = ORIGINAL.read_bytes()
        with tempfile.TemporaryDirectory() as work:
            source, target = Path(work) / "in.bin.e", Path(work) / "out.bin.e"
            source.write_bytes(original)
            assemble_apk.run_cli(assemble_apk.load("pod_programs_patcher", POD_PROGRAMS), "--input", source, "--output", target)
            expected = target.read_bytes()
        self.assertEqual(assemble_apk.patch_master(original), expected)


if __name__ == "__main__":
    unittest.main()
