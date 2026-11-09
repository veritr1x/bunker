import io
import unittest

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

import game_fonts


def cff_font(chars: dict[str, int], upem: int = 1000, name: str = "Test") -> bytes:
    """A CFF (OTTO) font: one square per character, with the given advance widths."""
    order = [".notdef"] + [f"uni{ord(c):04X}" for c in chars]
    builder = FontBuilder(upem, isTTF=False)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({ord(c): f"uni{ord(c):04X}" for c in chars})
    strings, metrics = {}, {}
    for glyph, width in [(".notdef", upem // 2)] + [(f"uni{ord(c):04X}", w) for c, w in chars.items()]:
        pen = T2CharStringPen(width, None)
        pen.moveTo((10, 0)); pen.lineTo((10, upem // 2)); pen.lineTo((width - 10, upem // 2)); pen.lineTo((width - 10, 0))
        pen.closePath()
        strings[glyph] = pen.getCharString()
        metrics[glyph] = (width, 10)
    builder.setupCFF(name, {"FullName": name}, strings, {})
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=upem * 4 // 5, descent=-upem // 5)
    builder.setupNameTable({"familyName": name, "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    out = io.BytesIO()
    builder.save(out)
    return out.getvalue()


def advance(font: bytes | TTFont, char: str) -> int:
    font = font if isinstance(font, TTFont) else TTFont(io.BytesIO(font))
    return font["hmtx"][font.getBestCmap()[ord(char)]][0]


def has_mark(font: bytes) -> bool:
    return any(game_fonts.MARK in str(r) for r in TTFont(io.BytesIO(font))["name"].names)


class MergeFont(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sans = game_fonts.noto("NotoSans-600.ttf")
        cls.han = game_fonts.noto("NotoSansSC-600.ttf")
        cls.merged = game_fonts.merge_font(cff_font({"A": 600, "Ж": 1000}), cls.sans)

    def test_cff_becomes_truetype(self):
        font = TTFont(io.BytesIO(self.merged))
        self.assertIn("glyf", font)
        self.assertNotIn("CFF ", font)

    def test_replaced_letters_come_from_noto(self):
        self.assertEqual(advance(self.merged, "Ж"), advance(self.sans, "Ж"))
        self.assertNotEqual(advance(self.merged, "Ж"), 1000)
        self.assertEqual(advance(self.merged, "A"), 600)
        cmap = TTFont(io.BytesIO(self.merged)).getBestCmap()
        for c in "żệά":
            self.assertIn(ord(c), cmap, c)

    def test_added_letters_only_fill_gaps(self):
        merged = game_fonts.merge_font(cff_font({"A": 600, "简": 777}), self.sans, self.han)
        self.assertEqual(advance(merged, "简"), 777)
        self.assertEqual(advance(merged, "们"), advance(self.han, "们"))

    def test_other_units_per_em(self):
        merged = game_fonts.merge_font(cff_font({"A": 1200, "Ж": 2048}, upem=2048), self.sans)
        self.assertEqual(TTFont(io.BytesIO(merged))["head"].unitsPerEm, 2048)
        self.assertAlmostEqual(advance(merged, "Ж"), advance(self.sans, "Ж") * 2048 / 1000, delta=1)

    def test_merge_is_idempotent(self):
        self.assertTrue(has_mark(self.merged))
        self.assertEqual(game_fonts.merge_font(self.merged, self.sans), self.merged)

    def test_layout_tables_dropped(self):
        font = TTFont(io.BytesIO(self.merged))
        for tag in ("GSUB", "GPOS", "vmtx", "VORG"):
            self.assertNotIn(tag, font, tag)

    def test_game_glyph_kept_where_noto_has_none(self):
        # U+03E2 (Coptic Ϣ) is in the replaced Greek range, but Noto Sans has no glyph for it.
        merged = game_fonts.merge_font(cff_font({"A": 600, "Ϣ": 555}), self.sans)
        self.assertEqual(advance(merged, "Ϣ"), 555)


if __name__ == "__main__":
    unittest.main()
