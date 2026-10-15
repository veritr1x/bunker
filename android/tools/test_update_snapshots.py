#!/usr/bin/env python3
"""Pod Programs lists the server's "Before update" snapshots and never prunes them."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))


class UpdateSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        work = Path(self.t.name)
        import android_runtime
        (work / "saves").mkdir()
        android_runtime.configure(work / "saves", work / "server", work / "tools", None)
        from web import config
        from web.services import backup_service
        self.config, self.backups = config, backup_service

    def write(self, name):
        self.backups.ensure_dirs()
        (self.config.BACKUP_DIR / name).write_bytes(b"x")

    def test_update_reason_is_known(self):
        self.assertIn("update", self.backups.VALID_REASONS)
        self.assertEqual(self.backups.reason_label("update"), "Before update")

    def test_ordinary_pruning_keeps_update_snapshots(self):
        self.write("backup_2026-10-15T10-00-00-000000_update.db")
        for i in range(self.config.BACKUP_RETENTION + 2):
            self.write(f"backup_2026-10-16T10-00-{i:02d}-000000_manual.db")
        self.backups.prune_to_last_n(self.config.BACKUP_RETENTION)
        names = [b.filename for b in self.backups.list_backups()]
        self.assertIn("backup_2026-10-15T10-00-00-000000_update.db", names)
        self.assertEqual(sum(1 for n in names if n.endswith("_manual.db")), self.config.BACKUP_RETENTION)


if __name__ == "__main__":
    unittest.main()
