import hashlib
import json
from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
