import io
import os
from pathlib import Path
import shutil
import struct
import tempfile
import time
import unittest
from unittest import mock
import zipfile

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


def _align(data: bytearray, n: int):
    data += b"\0" * ((-len(data)) % n)


def unity_file(objects: list[tuple[int, int, bytes]], version: int = 21, big_endian: bool = False) -> bytes:
    """A serialized file (format 21, no type tree) holding objects (path id, class id, body)."""
    classes = sorted({cls for _, cls, _ in objects})
    meta = bytearray(b"2019.4.9f1\0" + struct.pack("<i", 13) + b"\0")
    meta += struct.pack("<i", len(classes))
    for cls in classes:
        meta += struct.pack("<ibh", cls, 0, -1) + (b"\0" * 16 if cls == 114 else b"") + b"\0" * 16
    meta += struct.pack("<i", len(objects))
    entries, body, start = [], bytearray(), 0
    for path_id, cls, data in objects:
        _align(body, 8)
        entries.append((path_id, len(body), len(data), classes.index(cls)))
        body += data
    for path_id, offset, size, index in entries:
        while (20 + len(meta)) % 4:
            meta += b"\0"
        meta += struct.pack("<qIIi", path_id, offset, size, index)
    meta += struct.pack("<iii", 0, 0, 0) + b"\0"
    data_offset = 20 + len(meta)
    data_offset += (-data_offset) % 16
    header = struct.pack(">IIII", len(meta), data_offset + len(body), version, data_offset) + bytes([int(big_endian), 0, 0, 0])
    out = bytearray(header + meta)
    _align(out, 16)
    return bytes(out + body)


def font_object(name: str, font: bytes, tail: bytes = b"\x01\x02\x03\x04") -> bytes:
    """A Font object's body: m_Name, some fields, m_FontData, more fields."""
    encoded = name.encode()
    body = bytearray(struct.pack("<i", len(encoded)) + encoded)
    _align(body, 4)
    body += struct.pack("<fii", 1.5, 0, 7)
    body += struct.pack("<i", len(font)) + font
    _align(body, 4)
    return bytes(body + tail)


def layout(path):
    """(path id, start, size, class id) of each object, and the data offset."""
    return game_fonts._layout(open(path, "rb"))


class UnityFiles(unittest.TestCase):
    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.font = cff_font({"A": 600})
        self.other = b"behaviour" * 3
        self.texture = b"texture!" * 5
        self.src = self.dir / "src"
        self.src.write_bytes(unity_file([(1, 114, self.other), (3, 128, font_object("X", self.font)), (7, 28, self.texture)]))

    def test_read_fonts(self):
        self.assertEqual(game_fonts.read_fonts(self.src), {"X": self.font})

    def test_replace_font_keeps_other_objects(self):
        new = cff_font({"A": 600, "B": 700, "C": 800})
        dst = self.dir / "dst"
        game_fonts.replace_fonts(self.src, dst, {"X": new})
        self.assertEqual(game_fonts.read_fonts(dst), {"X": new})
        data = dst.read_bytes()
        objects, data_offset = layout(dst)
        bodies = {path_id: data[data_offset + start:data_offset + start + size] for path_id, start, size, _ in objects}
        self.assertEqual(bodies[1], self.other)
        self.assertEqual(bodies[7], self.texture)
        self.assertTrue(bodies[3].endswith(b"\x01\x02\x03\x04"))
        self.assertTrue(all(start % 8 == 0 for _, start, _, _ in objects))
        self.assertEqual(struct.unpack(">I", data[4:8])[0], len(data))

    def test_replace_streams_other_objects(self):
        big = bytes(range(256)) * (4 << 12)  # 4 MB
        self.src.write_bytes(unity_file([(1, 49, big), (3, 128, font_object("X", self.font))]))
        real_open = open

        class Limited:
            def __init__(self, handle):
                self.handle = handle

            def read(self, n=-1):
                if n < 0 or n > 1 << 20:
                    raise AssertionError(f"read({n}) holds too much at once")
                return self.handle.read(n)

            def __getattr__(self, name):
                return getattr(self.handle, name)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.handle.close()

        def limited_open(path, mode="r", *args, **kwargs):
            return Limited(real_open(path, mode, *args, **kwargs))

        dst = self.dir / "dst"
        with mock.patch.object(game_fonts, "open", limited_open, create=True):
            game_fonts.replace_fonts(self.src, dst, {"X": cff_font({"A": 600, "B": 700})})
        objects, data_offset = layout(dst)
        start, size = next((s, n) for p, s, n, _ in objects if p == 1)
        self.assertEqual(dst.read_bytes()[data_offset + start:data_offset + start + size], big)

    def test_unsupported_format(self):
        for version, big in ((22, False), (21, True)):
            self.src.write_bytes(unity_file([(3, 128, font_object("X", self.font))], version=version, big_endian=big))
            with self.assertRaises(game_fonts.UnityFileError):
                game_fonts.read_fonts(self.src)

    def test_unknown_font_name(self):
        with self.assertRaises(game_fonts.UnityFileError):
            game_fonts.replace_fonts(self.src, self.dir / "dst", {"Y": self.font})

    def test_missing_font_is_an_error(self):
        before = self.src.read_bytes()
        with self.assertRaises(RuntimeError) as caught:
            game_fonts.patch_game_fonts([self.src], log=lambda m: None)
        self.assertIn("FOT-RodinPro-DB", str(caught.exception))
        self.assertEqual(self.src.read_bytes(), before)

    def test_patch_game_fonts_in_place(self):
        fonts = [(i + 2, 128, font_object(g.name, cff_font({"A": 600, "Ж": 1000}, name=f"F{i}")))
                 for i, g in enumerate(game_fonts.GAME_FONTS)]
        self.src.write_bytes(unity_file([(1, 114, self.other)] + fonts))
        lines = []
        game_fonts.patch_game_fonts([self.src], log=lines.append)
        found = game_fonts.read_fonts(self.src)
        for g in game_fonts.GAME_FONTS:
            self.assertTrue(has_mark(found[g.name]), g.name)
        self.assertIn("Fonts: added letters to FOT-RodinPro-DB", lines)
        once = self.src.read_bytes()
        game_fonts.patch_game_fonts([self.src], log=lambda m: None)
        self.assertEqual(self.src.read_bytes(), once)


def game_font_files() -> dict[str, bytes]:
    """The three Android font files, each a Unity file with one small CFF font of the right name."""
    return {path: unity_file([(3, 128, font_object(g.name, cff_font({"A": 600, "Ж": 1000}, name=f"F{i}")))])
            for i, (path, g) in enumerate(zip(game_fonts.ANDROID_FONT_FILES, game_fonts.GAME_FONTS))}


class AndroidBuild(unittest.TestCase):
    def setUp(self):
        import assemble_apk
        self.assemble_apk = assemble_apk
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_apk_font_entries(self):
        apk = self.dir / "game.apk"
        with zipfile.ZipFile(apk, "w") as z:
            for name, data in game_font_files().items():
                z.writestr(name, data)
        before = apk.read_bytes()
        with zipfile.ZipFile(apk) as game:
            patched = self.assemble_apk.patch_font_entries(game, self.dir / "work", log=lambda m: None)
        self.assertEqual(sorted(patched), sorted(game_fonts.ANDROID_FONT_FILES))
        for name, path in patched.items():
            (font,) = game_fonts.read_fonts(path).values()
            self.assertTrue(has_mark(font), name)
        self.assertEqual(apk.read_bytes(), before)

    def test_assemble_adds_fonts_and_licence(self):
        a = self.assemble_apk
        apk, companion, out = self.dir / "game.apk", self.dir / "companion.apk", self.dir / "out.apk"
        with zipfile.ZipFile(apk, "w") as z:
            for name in ("AndroidManifest.xml", a.LIB, a.METADATA, a.SETTINGS, "resources.arsc", "classes.dex"):
                z.writestr(name, b"x")
            for name, data in game_font_files().items():
                z.writestr(name, data)
        with zipfile.ZipFile(companion, "w") as z:
            z.writestr("classes.dex", b"dex")
            z.writestr("AndroidManifest.xml", b"m")
        work = self.dir / "patched"
        work.mkdir()
        (work / "lib").write_bytes(b"lib"); (work / "meta").write_bytes(b"meta")
        with mock.patch.object(a, "patch_game_files", lambda *args: (work / "lib", work / "meta")), \
                mock.patch.object(a, "patch_manifest", lambda *args: (b"manifest", "Main")), \
                mock.patch.object(a, "patch_master", lambda data: data), \
                mock.patch.object(a, "patch_unity_connect", lambda data: data), \
                mock.patch.object(a.build_info, "check_companion", lambda c: None), \
                mock.patch.object(a.build_info, "describe", lambda *args: {}):
            master = self.dir / "master.bin.e"
            master.write_bytes(b"master")
            a.assemble(apk, master, companion, out, log=lambda m: None)
        with zipfile.ZipFile(out) as z:
            for name in game_fonts.ANDROID_FONT_FILES:
                path = self.dir / "check"
                path.write_bytes(z.read(name))
                (font,) = game_fonts.read_fonts(path).values()
                self.assertTrue(has_mark(font), name)
            self.assertEqual(z.read("assets/lunar/NOTO_OFL.txt"), (game_fonts.NOTO / "OFL.txt").read_bytes())


INPUTS = Path(os.environ.get("BUNKER_INPUTS", Path(__file__).resolve().parents[2] / "inputs"))


@unittest.skipUnless((INPUTS / "game-3.7.1.apk").is_file() and (INPUTS / "game-3.7.1.ipa").is_file(),
                     "needs the game files (set BUNKER_INPUTS to the folder holding game-3.7.1.apk and .ipa)")
class RealGameFiles(unittest.TestCase):
    def test_real_game_files(self):
        work = Path(self.enterContext(tempfile.TemporaryDirectory()))
        with zipfile.ZipFile(INPUTS / "game-3.7.1.apk") as apk:
            android = []
            for name in game_fonts.ANDROID_FONT_FILES:
                (work / Path(name).name).write_bytes(apk.read(name))
                android.append(work / Path(name).name)
        with zipfile.ZipFile(INPUTS / "game-3.7.1.ipa") as ipa:
            ios = work / "resources.assets"
            with ipa.open("Payload/NieR.app/" + game_fonts.IOS_FONT_FILE) as source, open(ios, "wb") as out:
                shutil.copyfileobj(source, out, 1 << 20)
        original = work / "resources.original"
        shutil.copyfile(ios, original)
        before = game_fonts.read_fonts(original)
        for files in (android, [ios]):
            started = time.time()
            game_fonts.patch_game_fonts(files, log=print)
            print("merged in", round(time.time() - started, 1), "s:", [f.name for f in files])
            fonts = {}
            for f in files:
                fonts.update(game_fonts.read_fonts(f))
            for g in game_fonts.GAME_FONTS:
                self.assertTrue(has_mark(fonts[g.name]), g.name)
        after = game_fonts.read_fonts(ios)
        self.assertEqual(len(after), len(before))
        for name, data in before.items():
            if name not in {g.name for g in game_fonts.GAME_FONTS}:
                self.assertEqual(after[name], data, name)
        old, old_offset = layout(original)
        new, new_offset = layout(ios)
        self.assertEqual([o[0] for o in old], [o[0] for o in new])
        fonts = {pid for pid, _, _, cls in old if cls == 128}
        with open(original, "rb") as a, open(ios, "rb") as b:
            for (pid, start, size, _), (_, start2, size2, _) in zip(old, new):
                if pid in fonts:
                    continue
                self.assertEqual(size, size2, pid)
                a.seek(old_offset + start); b.seek(new_offset + start2)
                self.assertEqual(a.read(size), b.read(size2), pid)


if __name__ == "__main__":
    unittest.main()
