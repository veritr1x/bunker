import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import notice_pack


def pack(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    path = Path(tempfile.mkdtemp()) / "notices.zip"
    path.write_bytes(buf.getvalue())
    return path


class NoticePackTest(unittest.TestCase):
    def test_entries_go_under_assets_notices(self):
        path = pack({"notices.json": json.dumps({"version": 1, "notices": []}), "img/ab_1.webp": b"RIFF"})
        self.assertEqual(sorted(n for n, _, _ in notice_pack.entries(path)),
                         ["assets/notices/img/ab_1.webp", "assets/notices/notices.json"])

    def test_images_are_stored_and_the_index_compressed(self):
        path = pack({"notices.json": "{}", "img/a.webp": b"RIFF"})
        kinds = {n: c for n, _, c in notice_pack.entries(path)}
        self.assertEqual(kinds["assets/notices/img/a.webp"], zipfile.ZIP_STORED)
        self.assertEqual(kinds["assets/notices/notices.json"], zipfile.ZIP_DEFLATED)

    def test_sha256(self):
        import hashlib
        path = pack({"notices.json": "{}"})
        self.assertEqual(notice_pack.sha256(path), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_describe_records_the_pack(self):
        import build_info
        companion = zipfile.ZipFile(io.BytesIO(b"PK\x05\x06" + b"\0" * 18))
        self.assertNotIn("notices", build_info.describe(companion, 1, 0))
        self.assertEqual(build_info.describe(companion, 1, 0, notices="abc")["notices"], "abc")

    def test_rejects_other_files(self):
        for bad in ({"img/a.webp": b"x"}, {"notices.json": "{}", "../evil.so": b"x"},
                    {"notices.json": "{}", "lib/arm64-v8a/x.so": b"x"}, {"notices.json": "{}", "img/a.png": b"x"}):
            with self.subTest(bad=list(bad)), self.assertRaises(ValueError):
                list(notice_pack.entries(pack(bad)))


if __name__ == "__main__":
    unittest.main()
