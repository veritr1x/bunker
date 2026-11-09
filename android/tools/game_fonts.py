#!/usr/bin/env python3
"""Add the letters the game's fonts lack, from the Noto subsets in fonts/noto/.

The game draws text only with its own fonts (it falls back among them, never to
the phone's). Rodin (menus), Talking (story) and Californian (English menus)
get Latin Extended, Vietnamese, Greek and Cyrillic from Noto, replacing the
game's full-width Cyrillic and Greek, and Rodin and Talking get the Simplified
Chinese characters Japanese does not use. Only fontTools is used, so this also
runs in the browser builder (Pyodide).
"""
import io
import json
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
NOTO = ROOT / "fonts/noto"
MARK = "Bunker letters 1"
# Tables the game's text system does not use; layout tables cannot be merged across these fonts.
DROP = ("GSUB", "GPOS", "GDEF", "BASE", "vhea", "vmtx", "VORG", "kern", "JSTF", "MATH", "DSIG", "STAT",
        "HVAR", "MVAR", "meta")


class GameFont(NamedTuple):
    name: str  # the Unity Font object's m_Name
    replace: str  # Noto file whose letters in the replaced ranges win over the game's
    add: str | None  # Noto file that only fills characters the game lacks


GAME_FONTS = (
    GameFont("FOT-RodinPro-DB", "NotoSans-600.ttf", "NotoSansSC-600.ttf"),
    GameFont("A-OTF-TalkingStd-Regular", "NotoSans-400.ttf", "NotoSansSC-400.ttf"),
    GameFont("MPFBCalifornianText-Roman", "NotoSerif-400.ttf", None),
)


def noto(name: str) -> bytes:
    return (NOTO / name).read_bytes()


def _replace_ranges() -> frozenset[int]:
    ranges = json.loads((NOTO / "sources.json").read_text())["ranges"]
    return frozenset(c for first, last in ranges for c in range(first, last + 1))


def _open(data: bytes):
    from fontTools.ttLib import TTFont
    return TTFont(io.BytesIO(data))


def _bytes(font) -> bytes:
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def _marked(font) -> bool:
    return "name" in font and any(MARK in str(record) for record in font["name"].names)


def _to_glyf(font):
    """CFF outlines to TrueType ones (as fontTools' otf2ttf snippet), for fonts the merger can combine."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable

    if "glyf" in font:
        return font
    order = font.getGlyphOrder()
    glyph_set = font.getGlyphSet()
    glyphs = {}
    for name in order:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyphs[name] = pen.glyph()
    font["loca"] = newTable("loca")
    font["glyf"] = glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = glyphs
    del font["CFF "]
    font["maxp"] = maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    for attr in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                 "maxStackElements", "maxSizeOfInstructions", "maxComponentElements", "maxPoints", "maxContours",
                 "maxCompositePoints", "maxCompositeContours", "maxComponentDepth"):
        setattr(maxp, attr, 0)
    maxp.maxZones = 1
    font["head"].glyphDataFormat = 0
    font["post"].formatType = 3.0
    font.sfntVersion = "\x00\x01\x00\x00"
    return font


def _cut(data: bytes, codepoints: set[int], units_per_em: int):
    """The Noto font reduced to codepoints and scaled to the game font's units per em."""
    from fontTools import subset
    from fontTools.ttLib.scaleUpem import scale_upem

    font = _open(data)
    for tag in DROP:
        if tag in font:
            del font[tag]
    options = subset.Options()
    options.layout_features = []
    options.notdef_outline = True
    options.name_IDs = []
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    if font["head"].unitsPerEm != units_per_em:
        scale_upem(font, units_per_em)
    return io.BytesIO(_bytes(font))


def merge_font(game: bytes, replace: bytes, add: bytes | None = None) -> bytes:
    """game with replace's letters in the replaced ranges and add's letters it lacks, as TrueType.

    A font that already carries MARK is returned unchanged."""
    from fontTools.merge import Merger

    font = _open(game)
    if _marked(font):
        return game
    for tag in DROP:
        if tag in font:
            del font[tag]
    font = _to_glyf(font)
    units = font["head"].unitsPerEm
    # Only what Noto really has replaces the game's glyphs: a gap in Noto never loses a game letter.
    replaced = set(_open(replace).getBestCmap()) & _replace_ranges()
    for table in font["cmap"].tables:
        if hasattr(table, "cmap"):
            for code in [c for c in table.cmap if c in replaced]:
                del table.cmap[code]
    have = set(font.getBestCmap())
    pieces = [io.BytesIO(_bytes(font)), _cut(replace, replaced, units)]
    if add is not None:
        missing = set(_open(add).getBestCmap()) - have - replaced
        if missing:
            pieces.append(_cut(add, missing, units))
    merged = Merger().merge(pieces)
    name = merged["name"]
    version = name.getDebugName(5) or ""
    name.setName(f"{version}; {MARK}" if version else MARK, 5, 3, 1, 0x409)
    return _bytes(merged)
