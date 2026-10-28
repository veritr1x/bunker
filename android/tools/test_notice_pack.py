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

    def test_carries_the_web_app(self):
        """The official web app (web/...) for the Anecdotes' panel mission page."""
        path = pack({"notices.json": "{}", "web/default_page.html": "<!doctype html>", "web/main/main.bundle.js": "var a;",
                     "web/npm/vue2-perfect-scrollbar@1.5.0/dist/vue2-perfect-scrollbar.css": "",
                     "web/images/en/operations/panel_mission/8/page1/card/" + "ab" * 32: b"\xff\xd8\xff",
                     "web/audio/se_ui_common_ok.wav": b"RIFF", "web/images/common/icon/gem_icon.png": b"\x89PNG"})
        kinds = {n: c for n, _, c in notice_pack.entries(path)}
        self.assertEqual(kinds["assets/notices/web/main/main.bundle.js"], zipfile.ZIP_DEFLATED)
        for stored in ("web/images/en/operations/panel_mission/8/page1/card/" + "ab" * 32, "web/audio/se_ui_common_ok.wav",
                       "web/images/common/icon/gem_icon.png"):
            self.assertEqual(kinds["assets/notices/" + stored], zipfile.ZIP_STORED, stored)
        for bad in ("web/../lib/x.so", "web/a b.js", "webx/a.js"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                list(notice_pack.entries(pack({"notices.json": "{}", bad: b"x"})))

    def test_rejects_other_files(self):
        for bad in ({"img/a.webp": b"x"}, {"notices.json": "{}", "../evil.so": b"x"},
                    {"notices.json": "{}", "lib/arm64-v8a/x.so": b"x"}, {"notices.json": "{}", "img/a.png": b"x"}):
            with self.subTest(bad=list(bad)), self.assertRaises(ValueError):
                list(notice_pack.entries(pack(bad)))


if __name__ == "__main__":
    unittest.main()
