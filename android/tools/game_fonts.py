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
import logging
import os
import re
import shutil
import struct
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


def _top(font, char: str) -> float | None:
    """The top of a character's outline, or None if the font lacks it."""
    from fontTools.pens.boundsPen import BoundsPen

    name = font.getBestCmap().get(ord(char))
    if name is None:
        return None
    glyphs = font.getGlyphSet()
    pen = BoundsPen(glyphs)
    glyphs[name].draw(pen)
    return pen.bounds[3] if pen.bounds else None


def _letter_heights(font, capital: str, small: str) -> tuple[float, float] | None:
    """A font's capital and x-height, measured on two letters."""
    cap, x = _top(font, capital), _top(font, small)
    return (cap, x) if cap and x else None


def _match_heights(font, game: tuple[float, float]) -> None:
    """Scales each Noto letter so capitals reach the game font's capital height and lowercase its x-height.

    Noto's letters differ in size from each game font's (Californian's are smaller, Rodin's larger),
    so added letters would look too big or too small beside the game's own. Accented letters are
    decomposed first, so the accent scales with its letter."""
    import unicodedata
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    noto = _letter_heights(font, "Н", "х")  # Cyrillic En and small ha: the subsets have no Latin H, x
    if not noto:
        return
    capital, lowercase = game[0] / noto[0], game[1] / noto[1]
    factors = {}
    for code, name in font.getBestCmap().items():
        factors.setdefault(name, lowercase if unicodedata.category(chr(code)) == "Ll" else capital)
    glyphs = font.getGlyphSet()
    scaled = {}
    for name in font.getGlyphOrder():
        factor = factors.get(name, capital)
        recording = DecomposingRecordingPen(glyphs)
        glyphs[name].draw(recording)
        pen = TTGlyphPen(None)
        recording.replay(TransformPen(pen, (factor, 0, 0, factor, 0, 0)))
        scaled[name] = (pen.glyph(), factor)
    glyf, hmtx = font["glyf"], font["hmtx"]
    for name, (glyph, factor) in scaled.items():
        glyf[name] = glyph
        glyph.recalcBounds(glyf)
        hmtx[name] = (round(hmtx[name][0] * factor), getattr(glyph, "xMin", 0))


def _cut(data: bytes, codepoints: set[int], units_per_em: int, heights: tuple[float, float] | None = None):
    """The Noto font reduced to codepoints and scaled to the game font's units per em (and letter heights)."""
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
    if heights:
        _match_heights(font, heights)
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
    # Chinese characters (add) keep their size: they fill the same square as the game's Japanese ones.
    pieces = [io.BytesIO(_bytes(font)), _cut(replace, replaced, units, _letter_heights(font, "H", "x"))]
    if add is not None:
        missing = set(_open(add).getBestCmap()) - have - replaced
        if missing:
            pieces.append(_cut(add, missing, units))
    # The merger warns about the game fonts' old Mac cmap subtables, which it drops; the game does not use them.
    quiet = logging.getLogger("fontTools.merge")
    level = quiet.level
    quiet.setLevel(logging.ERROR)
    try:
        merged = Merger().merge(pieces)
    finally:
        quiet.setLevel(level)
    # The merger takes the tallest ascent and deepest descent of all fonts; keep the game's, so text
    # (English included) sits and spaces exactly as before.
    for table, fields in (("hhea", ("ascent", "descent", "lineGap")),
                          ("OS/2", ("sTypoAscender", "sTypoDescender", "sTypoLineGap", "usWinAscent", "usWinDescent"))):
        if table in font and table in merged:
            for field in fields:
                setattr(merged[table], field, getattr(font[table], field))
    name = merged["name"]
    version = name.getDebugName(5) or ""
    name.setName(f"{version}; {MARK}" if version else MARK, 5, 3, 1, 0x409)
    return _bytes(merged)


# The game's Unity files holding these fonts: on Android one file per font, on iOS all in one.
ANDROID_FONT_FILES = (
    "assets/bin/Data/6f937efa0660c47f59d5215d276b1cbb",  # FOT-RodinPro-DB
    "assets/bin/Data/7089ac60979c94824ac549baab08cfa7",  # A-OTF-TalkingStd-Regular
    "assets/bin/Data/36ba8c21aaa354fd383f16a4f04ff719",  # MPFBCalifornianText-Roman
)
IOS_FONT_FILE = "Data/resources.assets"
FONT_CLASS = 128
CHUNK = 1 << 20
SFNT_TAGS = (b"OTTO", b"\0\1\0\0", b"true")


class UnityFileError(RuntimeError):
    pass


class _Object(NamedTuple):
    path_id: int
    start: int  # from the data offset
    size: int
    class_id: int
    entry: int  # where its object table entry is in the file


def _parse(handle):
    """The metadata (everything before the objects) and the objects of a serialized file, format 21."""
    header = handle.read(20)
    if len(header) < 20:
        raise UnityFileError("Not a Unity serialized file")
    _, _, version, data_offset = struct.unpack(">IIII", header[:16])
    if version != 21:
        raise UnityFileError(f"Unsupported Unity serialized file format {version}")
    if header[16] != 0:
        raise UnityFileError("Unsupported big-endian Unity serialized file")
    meta = header + _read_exactly(handle, data_offset - 20)
    try:
        p = meta.index(0, 20) + 1 + 4  # Unity version, target platform
        type_tree = meta[p] != 0
        p += 1
        classes = []
        (count,) = struct.unpack_from("<i", meta, p); p += 4
        for _ in range(count):
            (class_id,) = struct.unpack_from("<i", meta, p); p += 4 + 1 + 2
            if class_id == 114:
                p += 16
            p += 16
            if type_tree:
                nodes, strings = struct.unpack_from("<ii", meta, p); p += 8 + nodes * 32 + strings
                (deps,) = struct.unpack_from("<i", meta, p); p += 4 + deps * 4
            classes.append(class_id)
        (count,) = struct.unpack_from("<i", meta, p); p += 4
        objects = []
        for _ in range(count):
            p = (p + 3) & ~3
            path_id, start, size, index = struct.unpack_from("<qIIi", meta, p)
            objects.append(_Object(path_id, start, size, classes[index], p + 8))
            p += 20
    except (struct.error, ValueError, IndexError) as error:
        raise UnityFileError(f"Damaged Unity serialized file ({error})") from None
    return bytearray(meta), objects, data_offset


def _layout(handle):
    """(path id, start, size, class id) of each object, and the data offset."""
    with handle:
        _, objects, data_offset = _parse(handle)
    return [(o.path_id, o.start, o.size, o.class_id) for o in objects], data_offset


def _read_exactly(handle, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = handle.read(min(CHUNK, size - len(data)))
        if not chunk:
            raise UnityFileError("Unity serialized file ends early")
        data += chunk
    return bytes(data)


def _font_span(body: bytes) -> tuple[str, int, int] | None:
    """m_Name, and where m_FontData's font starts and how long it is (None: a Font without data)."""
    (length,) = struct.unpack_from("<i", body, 0)
    name = body[4:4 + length].decode("utf-8", "replace")
    i = (4 + length + 3) & ~3
    while i + 8 <= len(body):
        (size,) = struct.unpack_from("<i", body, i)
        start = i + 4
        if size >= 12 and start + size <= len(body) and body[start:start + 4] in SFNT_TAGS:
            (tables,) = struct.unpack_from(">H", body, start + 4)
            directory = body[start + 12:start + 12 + tables * 16]
            if tables and len(directory) == tables * 16 and all(
                    offset + length <= size for offset, length in
                    (struct.unpack_from(">II", directory, k * 16 + 8) for k in range(tables))):
                return name, start, size
        i += 4
    return name, -1, 0


def _font_objects(handle, objects, data_offset):
    """name → (object, body) of every Font object with data."""
    found = {}
    for o in objects:
        if o.class_id != FONT_CLASS:
            continue
        handle.seek(data_offset + o.start)
        body = _read_exactly(handle, o.size)
        name, start, size = _font_span(body)
        if size:
            found[name] = (o, body, start, size)
    return found


def read_fonts(path: Path) -> dict[str, bytes]:
    """m_Name → font file of every Font object in a Unity serialized file."""
    with open(path, "rb") as handle:
        _, objects, data_offset = _parse(handle)
        return {name: body[start:start + size]
                for name, (_, body, start, size) in _font_objects(handle, objects, data_offset).items()}


def replace_fonts(src: Path, dst: Path, fonts: dict[str, bytes]) -> None:
    """Writes dst: src with these Fonts' data replaced; every other object is copied unchanged."""
    with open(src, "rb") as source:
        meta, objects, data_offset = _parse(source)
        found = _font_objects(source, objects, data_offset)
        unknown = sorted(set(fonts) - set(found))
        if unknown:
            raise UnityFileError(f"No font {', '.join(unknown)} in {Path(src).name}")
        bodies = {}
        for name, data in fonts.items():
            o, body, start, size = found[name]
            rest = (start + size + 3) & ~3
            piece = struct.pack("<i", len(data)) + data
            piece += b"\0" * ((-len(piece)) % 4)
            bodies[o.path_id] = body[:start - 4] + piece + body[rest:]
        with open(dst, "wb") as out:
            out.write(meta)
            position = 0
            for o in sorted(objects, key=lambda o: o.start):
                padding = (-position) % 8
                out.write(b"\0" * padding)
                position += padding
                if o.path_id in bodies:
                    body = bodies[o.path_id]
                    out.write(body)
                    size = len(body)
                else:
                    source.seek(data_offset + o.start)
                    left = size = o.size
                    while left:
                        chunk = source.read(min(CHUNK, left))
                        if not chunk:
                            raise UnityFileError("Unity serialized file ends early")
                        out.write(chunk)
                        left -= len(chunk)
                struct.pack_into("<II", meta, o.entry, position, size)
                position += size
            struct.pack_into(">I", meta, 4, data_offset + position)
            out.seek(0)
            out.write(meta)


def patch_game_fonts(paths: list[Path], log=print) -> None:
    """Adds the letters to the GAME_FONTS found in these Unity files, in place."""
    for path in paths:
        if not Path(path).is_file():
            raise RuntimeError(f"The game's font file {Path(path).name} is missing; this game version is not supported")
    plans = []
    for path in paths:
        fonts = read_fonts(path)
        plans.append((path, {g: fonts[g.name] for g in GAME_FONTS if g.name in fonts}))
    found = {g.name for _, wanted in plans for g in wanted}
    for g in GAME_FONTS:
        if g.name not in found:
            raise RuntimeError(f"The game's font {g.name} was not found; this game version is not supported")
    for path, wanted in plans:
        changed = {}
        for g, data in wanted.items():
            merged = merge_font(data, noto(g.replace), noto(g.add) if g.add else None)
            if merged != data:
                changed[g.name] = merged
                log(f"Fonts: added letters to {g.name}")
            else:
                log(f"Fonts: {g.name} already has the letters")
        if changed:
            temporary = Path(str(path) + ".fonts")
            try:
                replace_fonts(path, temporary, changed)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)


def coverage(apk: Path) -> dict:
    """The characters the game can show once the letters are added: every game font's characters together."""
    import tempfile
    import zipfile

    plans = {g.name: g for g in GAME_FONTS}
    shown, names = set(), []
    with zipfile.ZipFile(apk) as game, tempfile.TemporaryDirectory() as work:
        for name in sorted(game.namelist()):
            if not re.fullmatch(r"assets/bin/Data/[0-9a-f]{32}", name):
                continue
            path = Path(work) / "file"
            with game.open(name) as source, open(path, "wb") as out:
                shutil.copyfileobj(source, out, CHUNK)
            try:
                fonts = read_fonts(path)
            except (UnityFileError, struct.error, ValueError):
                continue  # not a serialized file of this format: no fonts there
            for font_name, data in fonts.items():
                g = plans.get(font_name)
                if g:
                    data = merge_font(data, noto(g.replace), noto(g.add) if g.add else None)
                shown |= set(_open(data).getBestCmap())
                names.append(font_name)
    missing = set(plans) - set(names)
    if missing:
        raise RuntimeError(f"The game's fonts {', '.join(sorted(missing))} were not found in {Path(apk).name}")
    ranges = []
    for c in sorted(shown):
        if ranges and ranges[-1][1] == c - 1:
            ranges[-1][1] = c
        else:
            ranges.append([c, c])
    return {"apk": Path(apk).name, "fonts": sorted(names), "ranges": ranges}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("coverage", help="write the characters the game can show (fonts/coverage.json), "
                                                   "which scripts/check_translations.py checks translations against")
    command.add_argument("--apk", type=Path, required=True, help="the game APK")
    command.add_argument("--out", type=Path, default=ROOT / "fonts/coverage.json")
    args = parser.parse_args(argv)
    result = coverage(args.apk)
    lines = ",\n  ".join(json.dumps(r) for r in result["ranges"])
    args.out.write_text(f'{{"apk": {json.dumps(result["apk"])},\n "fonts": {json.dumps(result["fonts"])},\n'
                        f' "ranges": [\n  {lines}\n ]}}\n')
    print(f"{args.out}: {sum(b - a + 1 for a, b in result['ranges'])} characters in {len(result['fonts'])} fonts")


if __name__ == "__main__":
    main()
