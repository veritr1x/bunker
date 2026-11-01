#!/usr/bin/env python3
"""The in-game Bunker button: its icon (bunker_icon.py) and its row and tap
rules (bunker_button_layout.c). The icon tests need Pillow; the C tests a host
C compiler (cc)."""
from pathlib import Path
import io, re, shutil, subprocess, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
HEADER = root / "android/app/src/main/cpp/bunker_icon.h"
LAYOUT = root / "android/app/src/main/cpp/bunker_button_layout.c"
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


ASSETS = root / "android/emblem"
IOS_LAUNCHER = root / "ios/launcher"


@unittest.skipUnless(Image, "needs Pillow")
class EmblemElsewhere(unittest.TestCase):
    """The emblem replaces Bunker's other marks: Android's notification and
    shortcut icons, iOS's quick action and the web builder's tab icon."""
    def test_files_match_the_generator(self):
        import bunker_icon
        with tempfile.TemporaryDirectory() as tmp:
            bunker_icon.write_assets(Path(tmp))
            for name, made in bunker_icon.asset_files(Path(tmp)).items():
                self.assertEqual(made.read_bytes(), bunker_icon.asset_files(root)[name].read_bytes(), name)

    def test_notification_icon_is_white_on_transparent(self):
        icon = Image.open(ASSETS / "bunker-emblem-notification.png").convert("RGBA")
        self.assertEqual(icon.size, (96, 96))
        colours = {px[:3] for px in icon.getdata() if px[3] > 0}
        self.assertEqual(colours, {(255, 255, 255)})

    def test_shortcut_icon_has_the_plate_on_paper(self):
        icon = Image.open(ASSETS / "bunker-emblem-shortcut.png").convert("RGBA")
        self.assertEqual(icon.size, (192, 192))
        self.assertEqual(icon.getpixel((4, 4)), (211, 206, 184, 255))  # the launcher's paper, edge to edge (adaptive icon)

    def test_ios_quick_action_template_at_2x_and_3x(self):
        for scale, side in ((2, 70), (3, 105)):
            icon = Image.open(IOS_LAUNCHER / f"BunkerEmblem@{scale}x.png").convert("RGBA")
            self.assertEqual(icon.size, (side, side))
            self.assertEqual(icon.getpixel((0, 0))[3], 0)

    def test_the_apps_use_them(self):
        java = (root / "android/app/src/main/java/org/veritr1x/bunker/Look.java").read_text()
        self.assertIn("bunker-emblem-notification.png", java)
        self.assertIn("bunker-emblem-shortcut.png", java)
        self.assertIn("Look.emblem(this)", (root / "android/app/src/main/java/org/veritr1x/bunker/ServerService.java").read_text())
        self.assertIn("Look.shortcutEmblem(this)", (root / "android/app/src/main/java/org/veritr1x/bunker/MainActivity.java").read_text())
        launcher = (IOS_LAUNCHER / "LunarLauncher.m").read_text()
        self.assertIn('iconWithTemplateImageName:@"BunkerEmblem"', launcher)
        self.assertNotIn("slider.horizontal.3", launcher)
        self.assertIn("BunkerEmblem@", (root / "ios/tools/build_framework.sh").read_text())
        self.assertIn("BunkerEmblem@", (root / "ios/tools/package_ipa.py").read_text())

    def test_web_builder_tab_icon(self):
        import bunker_icon
        page = (root / "web/index.html").read_text()
        self.assertIn('<link rel="icon" href="' + bunker_icon.favicon_data_uri() + '">', page)


@unittest.skipUnless(shutil.which("cc"), "needs a C compiler")
class Rules(unittest.TestCase):
    """Each case runs the C functions through a small driver."""
    def run_c(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "main.c"
            main.write_text('#include <stdio.h>\n#include "bunker_button_layout.h"\nint main(void) {\n' + body + "\nreturn 0; }\n")
            exe = Path(tmp) / "rules"
            subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", "-I", str(LAYOUT.parent), "-o", str(exe), str(main), str(LAYOUT)], check=True)
            return subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.split()

    def gap(self, available, width, buttons, gap, min_gap):
        return float(self.run_c(f'printf("%f", bunker_row_gap({float(available)}f, {float(width)}f, {buttons}, {float(gap)}f, {float(min_gap)}f));')[0])

    def test_gap_unchanged_when_it_fits(self):
        self.assertEqual(self.gap(800, 90, 8, 10, 2), 10)

    def test_gap_tightens_to_fit(self):
        self.assertAlmostEqual(self.gap(760, 90, 8, 10, 2), (760 - 8 * 90) / 7, places=4)

    def test_gap_never_below_minimum(self):
        self.assertEqual(self.gap(700, 90, 8, 10, 2), 2)

    def test_one_button_keeps_its_gap(self):
        self.assertEqual(self.gap(50, 90, 1, 10, 2), 10)

    def test_tap_gate(self):
        out = self.run_c('for (int a = 0; a < 2; a++) for (int b = 0; b < 2; b++) printf("%d ", bunker_tap_allowed(a, b));')
        self.assertEqual(out, ["0", "0", "0", "1"])


if __name__ == "__main__":
    unittest.main()
