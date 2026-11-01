#!/usr/bin/env python3
"""The in-game Bunker button: its icon (bunker_icon.py) and its row and tap
rules (bunker_button_layout.c). The icon tests need Pillow; the C tests a host
C compiler (cc)."""
from pathlib import Path
import io, re, shutil, subprocess, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
HEADER = root / "android/app/src/main/cpp/bunker_icon.h"
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from PIL import Image
except ImportError:
    Image = None


def header_png(text):
    data = re.search(r"kBunkerIconPng\[\] = \{(.*?)\};", text, re.S).group(1)
    return bytes(int(x) for x in data.split(","))


@unittest.skipUnless(Image, "needs Pillow")
class Icon(unittest.TestCase):
    def test_icon_header_matches_the_generator(self):
        import bunker_icon
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bunker_icon.h"
            bunker_icon.write_header(out)
            self.assertEqual(out.read_text(), HEADER.read_text())

    def test_icon_is_128_square_with_its_plate(self):
        icon = Image.open(io.BytesIO(header_png(HEADER.read_text())))
        self.assertEqual((icon.size, icon.mode), ((128, 128), "RGBA"))
        self.assertEqual(icon.getpixel((0, 0))[3], 0)  # outside the plate
        self.assertEqual(icon.getpixel((64, 12))[:3], (36, 28, 19))  # the plate, as the game's (measured)
        self.assertEqual(icon.getpixel((64, 12))[3], 196)
        # The upright blade, in the glyph's cream.
        self.assertEqual(icon.getpixel((64, 35))[:3], (231, 224, 205))


if __name__ == "__main__":
    unittest.main()
