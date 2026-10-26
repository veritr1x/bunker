"""The Android builder streams the large game files instead of holding them whole."""
from pathlib import Path
import io
import os
import struct
import tempfile
import unittest
import unittest.mock
import zipfile

import assemble_apk
import package_game

RVA = 0x4910D4C


def reachability_library(path, prologue="f30f1ef8fd7b01a9"):
    """A small ELF whose executable segment maps the reachability getter's RVA."""
    data = bytearray(64 + 56 + 64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 183)
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    start = 64 + 56
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, start, RVA, 0, 64, 64, 4)
    data[start:start + 16] = bytes.fromhex(prologue + "fd430091738401b0")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return start


class StreamTests(unittest.TestCase):
    def test_reachability_is_patched_where_the_library_lies(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            library = game / "lib/arm64-v8a/libil2cpp.so"
            at = reachability_library(library)
            before = library.read_bytes()
            with unittest.mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read the whole library")):
                package_game.patch_local_reachability(game)
            after = library.read_bytes()
            self.assertEqual(after[at:at + 8], bytes.fromhex("40008052c0035fd6"))
            self.assertEqual(after[:at] + after[at + 8:], before[:at] + before[at + 8:])
            package_game.patch_local_reachability(game)  # Already patched is fine.

    def test_reachability_refuses_an_unknown_library(self):
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp)
            library = game / "lib/arm64-v8a/libil2cpp.so"
            reachability_library(library, prologue="1f2003d51f2003d5")
            before = library.read_bytes()
            with self.assertRaises(RuntimeError):
                package_game.patch_local_reachability(game)
            self.assertEqual(library.read_bytes(), before)

    def test_files_are_written_like_bytes(self):
        data = os.urandom(3000) + b"\0" * 70000
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "big.bin"
            path.write_bytes(data)
            for compress in (True, False):
                with self.subTest(compress=compress):
                    from_bytes, from_file = io.BytesIO(), io.BytesIO()
                    for out, add in ((from_bytes, lambda w: w.add("lib/arm64-v8a/libx.so", data, compress)),
                                     (from_file, lambda w: w.add_file("lib/arm64-v8a/libx.so", path, compress))):
                        writer = assemble_apk.ApkWriter(out)
                        writer.add("a.txt", b"first")
                        add(writer)
                        writer.close()
                    self.assertEqual(from_file.getvalue(), from_bytes.getvalue())
                    with zipfile.ZipFile(from_file) as z:
                        self.assertEqual(z.read("lib/arm64-v8a/libx.so"), data)


if __name__ == "__main__":
    unittest.main()
