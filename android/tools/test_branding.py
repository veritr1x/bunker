import struct
import unittest
from pathlib import Path

import axml
import branding


class BrandingTests(unittest.TestCase):
    def test_resource_pool_preserves_strings_and_styles(self):
        for utf8 in [False, True]:
            with self.subTest(utf8=utf8):
                original = axml._encode_pool(["old", "other"], utf8)
                header = bytearray(original[:28])
                # One style entry and its opaque span payload, as in a game ARSC.
                start = struct.unpack_from("<I", header, 20)[0]
                style = struct.pack("<6I", 1, 0, 2, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
                struct.pack_into("<I", header, 4, len(original) + 4 + len(style))
                struct.pack_into("<I", header, 12, 1)
                struct.pack_into("<II", header, 20, start + 4, len(original) + 4)
                styled = bytes(header) + original[28:start] + bytes(4) + original[start:] + style
                result, index = branding._append_string(styled, branding.ICON_PATH)
                self.assertEqual(index, 2)
                strings, _, size = axml._read_pool(result, 0)
                self.assertEqual(strings, ["old", "other", branding.ICON_PATH])
                self.assertEqual(size, len(result))
                style_at = struct.unpack_from("<I", result, 24)[0]
                self.assertEqual(result[style_at:], style)
                self.assertEqual(struct.unpack_from("<I", result, 12)[0], 1)

    def test_resource_package_is_idempotent_and_keeps_game_package(self):
        pool = axml._encode_pool(["res/game.xml"], True)
        types = axml._encode_pool(["string"], True)
        keys = axml._encode_pool(["firebase_build_id"], True)
        name = "game".encode("utf-16-le").ljust(256, b"\0")
        header = struct.pack("<HHII", 0x0200, 288, 288 + len(types) + len(keys), 0x7F) + name
        header += struct.pack("<5I", 288, 1, 288 + len(types), 1, 0)
        game = header + types + keys
        original = struct.pack("<HHII", 2, 12, 12 + len(pool) + len(game), 1) + pool + game
        result = branding.resources(original)
        self.assertIn(name, result)
        self.assertIn(b"firebase_build_id", result)
        self.assertEqual(struct.unpack_from("<I", result, 8)[0], 1)
        self.assertEqual(branding.ICON_ID >> 24, 0x7F)
        self.assertEqual(branding.resources(result), result)

    def test_icon_matches_upstream_emblem_and_standalone_launcher(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(branding.icon(), (root / "android/emblem/bunker-emblem-shortcut.png").read_bytes())
        self.assertEqual(branding.icon(), (root / "android/app/src/main/res/drawable/bunker_icon.png").read_bytes())

    def test_web_android_refuses_missing_notices_before_writing(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web"))
        import webbuild
        with self.assertRaisesRegex(ValueError, "notice pack is missing"):
            webbuild.build_android("missing.apk", "missing-master", "missing-bundle", "unused.apk")


if __name__ == "__main__":
    unittest.main()
