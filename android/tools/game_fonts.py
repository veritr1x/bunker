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
    # The merger warns about the game fonts' old Mac cmap subtables, which it drops; the game does not use them.
    quiet = logging.getLogger("fontTools.merge")
    level = quiet.level
    quiet.setLevel(logging.ERROR)
    try:
        merged = Merger().merge(pieces)
    finally:
        quiet.setLevel(level)
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
