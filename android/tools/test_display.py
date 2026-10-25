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
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "default", "screen": "full", "textures": "full"})

    def test_saved_choices_are_read_back(self):
        self.display.write_settings("60", "native", "full", self.conf)
        self.assertEqual(self.conf.read_text(), "fps=60\nresolution=native\nscreen=full\ntextures=full\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "60", "resolution": "native", "screen": "full", "textures": "full"})
        self.display.write_settings("max", "1440", "safe", self.conf)
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "max", "resolution": "1440", "screen": "safe", "textures": "full"})

    def test_lower_resolutions_and_texture_sizes_are_saved(self):
        self.display.write_settings("30", "540", "full", self.conf, textures="quarter")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "540", "screen": "full", "textures": "quarter"})
        self.display.write_settings("60", "640", "safe", self.conf, textures="half")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "60", "resolution": "640", "screen": "safe", "textures": "half"})
        with self.assertRaises(ValueError):
            self.display.write_settings("30", "default", "full", self.conf, textures="tiny")

    def test_settings_saved_before_the_screen_choice_use_the_full_screen(self):
        self.conf.write_text("fps=60\nresolution=native\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "60", "resolution": "native", "screen": "full", "textures": "full"})

    def test_unknown_values_are_refused_and_ignored(self):
        with self.assertRaises(ValueError):
            self.display.write_settings("240", "native", "safe", self.conf)
        with self.assertRaises(ValueError):
            self.display.write_settings("60", "native", "wide", self.conf)
        self.conf.write_text("fps=240\nresolution=8k\nscreen=wide\nnoise\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "default", "screen": "full", "textures": "full"})


class Encodings(unittest.TestCase):
    def test_highest_preset_immediates(self):
        """orr x11, x11, #(size << 32) for each size display_patch.c can choose."""
        source = (root / "android/app/src/main/cpp/display_patch.c").read_text()
        body = re.search(r"static uint32_t orr_x11_size\(int size\) \{(.*?)\n\}", source, re.S).group(1)
        chosen = {name: int(word, 16) for name, word in re.findall(r"case (\w+): return 0x([0-9a-f]+)u;", body)}
        sizes = {"H540": 3, "H640": 4, "FullHD": 6, "WQHD": 7}
        self.assertEqual(set(chosen), set(sizes))
        for name, word in chosen.items():
            self.assertEqual(word, orr_x11(sizes[name] << 32), name)


def orr_x11(value):
    """The A64 instruction orr x11, x11, #value, for a value that is one run of set bits."""
    ones = bin(value).count("1")
    low = (value & -value).bit_length() - 1
    assert value == ((1 << ones) - 1) << low
    return 0xb2400000 | ((64 - low) % 64) << 16 | (ones - 1) << 10 | 11 << 5 | 11


def patch_sites():
    """(rva, original word) for every site in display_patch.c."""
    source = (root / "android/app/src/main/cpp/display_patch.c").read_text()
    return [(int(rva, 16), int(word, 16)) for rva, word in re.findall(r"\(Site\)\{(0x[0-9A-F]+), (0x[0-9a-f]+)u", source)]


def hook_sites():
    """(rva, four original words) for each hook in display_patch.c."""
    source = (root / "android/app/src/main/cpp/display_patch.c").read_text()
    words = {name: [int(w, 16) for w in re.findall(r"0x([0-9a-f]{8})u", body)]
             for name, body in re.findall(r"static const uint32_t (\w+)\[4\] = \{([^}]*)\}", source)}
    return [(int(rva, 16), words[name]) for rva, name in re.findall(r"\{(0x[0-9A-F]+), (k\w+)\}", source)]


@unittest.skipUnless(os.environ.get("BUNKER_GAME_LIB"), "set BUNKER_GAME_LIB to the original 3.7.1 libil2cpp.so")
class GameBinary(unittest.TestCase):
    def test_every_site_holds_the_expected_instruction(self):
        data = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        sites = patch_sites()
        self.assertEqual(len(sites), 6)
        for rva, original in sites:
            # The library's first segment maps at address 0 with file offset 0.
            self.assertEqual(struct.unpack_from("<I", data, rva)[0], original, hex(rva))

    def test_every_hook_finds_its_original_instructions(self):
        data = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        hooks = hook_sites()
        self.assertEqual(len(hooks), 4)
        for rva, original in hooks:
            self.assertEqual(list(struct.unpack_from("<4I", data, rva)), original, hex(rva))

    def test_event_zone_methods_are_where_the_patch_calls_them(self):
        data = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        prologue = [0xf81d0ff5, 0xa9014ff4, 0xa9027bfd, 0x910083fd]
        # EventTriggerOnStayCollision.OnStateBegin and OnStay.
        for rva in (0x2984210, 0x2984420):
            self.assertEqual(list(struct.unpack_from("<4I", data, rva)), prologue, hex(rva))
        # StateConductor.OnStateUpdate, the empty virtual the patch replaces: "ret".
        self.assertEqual(struct.unpack_from("<I", data, 0x3A05C64)[0], 0xd65f03c0)


if __name__ == "__main__":
    unittest.main()
