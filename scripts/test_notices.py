import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import notices


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.dir = Path(self.t.name)
        self.pack = self.dir / "published.zip"
        self.pack.write_bytes(b"PK notice pack")
        self.lock = self.dir / "notices.lock.json"
        self.lock.write_text(json.dumps({"url": self.pack.as_uri(), "size": self.pack.stat().st_size,
                                         "sha256": hashlib.sha256(self.pack.read_bytes()).hexdigest()}))
        self.out = self.dir / "inputs/bunker-notices.zip"

    def test_downloads_and_checks_the_pinned_pack(self):
        self.assertEqual(notices.fetch(self.lock, self.out), self.out)
        self.assertEqual(self.out.read_bytes(), b"PK notice pack")

    def test_keeps_a_matching_copy(self):
        notices.fetch(self.lock, self.out)
        self.pack.unlink()  # A second fetch must not need the network.
        self.assertEqual(notices.fetch(self.lock, self.out).read_bytes(), b"PK notice pack")

    def test_refuses_a_different_file(self):
        lock = json.loads(self.lock.read_text())
        lock["sha256"] = "0" * 64
        self.lock.write_text(json.dumps(lock))
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            notices.fetch(self.lock, self.out)
        self.assertFalse(self.out.exists())


class SyncedTest(unittest.TestCase):
    """fetch_synced: the pinned pack, kept as fetched, and a copy synced to the summon rules."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        d = self.dir = Path(self.t.name)
        body = ('<h3>Summons Details</h3><div class="information_table"><table><tbody>'
                '<tr><td>10x summon</td><td>3,000 gems</td><td>—</td></tr></tbody></table></div>')
        self.pack = d / "published.zip"
        with zipfile.ZipFile(self.pack, "w") as z:
            z.writestr("notices.json", json.dumps({"version": 1, "gacha": {"186": 1500000186},
                                                   "notices": [{"id": 1500000186, "body": body}]}))
        self.lock = d / "notices.lock.json"
        self.lock.write_text(json.dumps({"url": self.pack.as_uri(), "size": self.pack.stat().st_size,
                                         "sha256": hashlib.sha256(self.pack.read_bytes()).hexdigest()}))
        self.rules = d / "rules.json"
        self.rules.write_text(json.dumps({"rules": {"186": {"steps": [{"cur": "paid", "draws": 10, "price": 3000}]}}, "new": []}))
        self.pinned, self.out = d / "inputs/pinned.zip", d / "inputs/bunker-notices.zip"

    def body(self):
        with zipfile.ZipFile(self.out) as z:
            return json.loads(z.read("notices.json"))["notices"][0]["body"]

    def test_the_build_gets_the_synced_copy(self):
        self.assertEqual(notices.fetch_synced(self.lock, self.pinned, self.out, self.rules), self.out)
        self.assertIn("3,000 paid gems", self.body())
        self.assertEqual(self.pinned.read_bytes(), self.pack.read_bytes())  # kept as published
        # Unchanged pack and rules: nothing is written again, and nothing downloaded.
        self.pack.unlink()
        written = self.out.stat().st_mtime_ns
        notices.fetch_synced(self.lock, self.pinned, self.out, self.rules)
        self.assertEqual(self.out.stat().st_mtime_ns, written)
        # New rules: synced again.
        self.rules.write_text(json.dumps({"rules": {"186": {"steps": [{"cur": "paid", "draws": 10, "price": 1500}]}}, "new": []}))
        notices.fetch_synced(self.lock, self.pinned, self.out, self.rules)
        self.assertIn("1,500 paid gems", self.body())

    def test_a_copy_fetched_before_needs_no_download(self):
        self.out.parent.mkdir(parents=True)
        self.out.write_bytes(self.pack.read_bytes())  # what fetch() used to leave
        self.pack.unlink()
        notices.fetch_synced(self.lock, self.pinned, self.out, self.rules)
        self.assertTrue(self.pinned.is_file())
        self.assertIn("3,000 paid gems", self.body())


if __name__ == "__main__":
    unittest.main()
