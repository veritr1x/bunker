#!/usr/bin/env python3
"""Pod Programs → Display, and the instructions display_patch.c rewrites.

The settings tests need fastapi (the Android Python requirements) and the
prepared Tools sources (scripts/prepare.py). The binary test runs when
BUNKER_GAME_LIB points at the original 3.7.1 ARM64 libil2cpp.so.
"""
from pathlib import Path
import os, re, struct, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))


class Settings(unittest.TestCase):
    def setUp(self):
        import android_display
        self.display = android_display
        self.dir = tempfile.TemporaryDirectory()
        self.conf = Path(self.dir.name) / "display.conf"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_keeps_the_game_defaults(self):
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "default"})

    def test_saved_choices_are_read_back(self):
        self.display.write_settings("60", "native", self.conf)
        self.assertEqual(self.conf.read_text(), "fps=60\nresolution=native\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "60", "resolution": "native"})

    def test_unknown_values_are_refused_and_ignored(self):
        with self.assertRaises(ValueError):
            self.display.write_settings("240", "native", self.conf)
        self.conf.write_text("fps=240\nresolution=8k\nnoise\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "default"})


def patch_sites():
    """(rva, original word) for every site in display_patch.c."""
    source = (root / "android/app/src/main/cpp/display_patch.c").read_text()
    return [(int(rva, 16), int(word, 16)) for rva, word in re.findall(r"\(Site\)\{(0x[0-9A-F]+), (0x[0-9a-f]+)u", source)]


@unittest.skipUnless(os.environ.get("BUNKER_GAME_LIB"), "set BUNKER_GAME_LIB to the original 3.7.1 libil2cpp.so")
class GameBinary(unittest.TestCase):
    def test_every_site_holds_the_expected_instruction(self):
        data = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        sites = patch_sites()
        self.assertEqual(len(sites), 7)
        for rva, original in sites:
            # The library's first segment maps at address 0 with file offset 0.
            self.assertEqual(struct.unpack_from("<I", data, rva)[0], original, hex(rva))


if __name__ == "__main__":
    unittest.main()
