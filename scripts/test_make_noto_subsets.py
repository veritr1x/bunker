import json
from pathlib import Path
import unittest

from fontTools.ttLib import TTFont

import make_noto_subsets as subsets

NOTO = Path(__file__).resolve().parents[1] / "fonts/noto"
LATIN = ("NotoSans-400.ttf", "NotoSans-600.ttf", "NotoSerif-400.ttf")
HAN = ("NotoSansSC-400.ttf", "NotoSansSC-600.ttf")


class Codepoints(unittest.TestCase):
    def test_simplified_only(self):
        han = subsets.simplified_only()
        self.assertIn(0x7B80, han)  # 简
        self.assertIn(0x4EEC, han)  # 们
        self.assertNotIn(0x65E5, han)  # 日
        self.assertNotIn(0x6F22, han)  # 漢
        self.assertTrue(all(0x4E00 <= c <= 0x9FFF for c in han))
        self.assertTrue(2000 < len(han) < 4000, len(han))

    def test_replaced_codepoints(self):
        replaced = subsets.replaced_codepoints()
        for c in "żćğşệụάώЖї":
            self.assertIn(ord(c), replaced, c)
        self.assertNotIn(ord("A"), replaced)
        self.assertNotIn(ord("é"), replaced)


class CommittedFiles(unittest.TestCase):
    def test_committed_files_are_static_truetype(self):
        for name in LATIN + HAN:
            font = TTFont(NOTO / name)
            self.assertIn("glyf", font, name)
            for tag in ("CFF ", "fvar", "GSUB"):
                self.assertNotIn(tag, font, f"{name} {tag}")
            self.assertEqual(font["head"].unitsPerEm, 1000, name)
        sources = json.loads((NOTO / "sources.json").read_text())
        self.assertRegex(sources["commit"], r"^[0-9a-f]{40}$")
        for entry in sources["files"].values():
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual([tuple(r) for r in sources["ranges"]], list(subsets.REPLACE_RANGES))

    def test_committed_coverage(self):
        replaced = subsets.replaced_codepoints()
        for name in LATIN:
            cmap = set(TTFont(NOTO / name).getBestCmap())
            self.assertTrue(cmap <= replaced, name)
            for c in "żğệάЖ":
                self.assertIn(ord(c), cmap, f"{name} {c}")
        han = subsets.simplified_only()
        for name in HAN:
            cmap = set(TTFont(NOTO / name).getBestCmap())
            self.assertTrue(cmap <= han, name)
            self.assertIn(0x7B80, cmap)
            self.assertGreater(len(cmap), len(han) * 0.95, name)
        total = 0
        for path in NOTO.glob("*.ttf"):
            self.assertLess(path.stat().st_size, 1_500_000, path.name)
            total += path.stat().st_size
        self.assertLess(total, 4_000_000)
        self.assertIn("SIL OPEN FONT LICENSE", (NOTO / "OFL.txt").read_text().upper())


if __name__ == "__main__":
    unittest.main()
