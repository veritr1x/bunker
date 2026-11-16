#!/usr/bin/env python3
"""Pod Programs › Item Editor › Set (android_items.py): an amount becomes the
item's count. The save is backed up before the editing shim's
"set_possession_batch" (bunker_set_items.go); amounts out of range are refused
before either. Every amount row has Set beside Grant. The shim and backups are
stubbed. Needs the Android Python requirements."""
from pathlib import Path
import re, sys, tempfile, unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
from web import config  # noqa: E402


class SetItems(unittest.TestCase):
    def setUp(self):
        import android_items as items
        from web.services import backup_service
        self.items = items
        self.dir = Path(tempfile.mkdtemp())
        self.calls = []

        def shim(payload):
            self.calls.append(("shim", payload))
            return {"ok": True, "applied": len(payload["grants"])}

        def create_backup(reason="manual"):
            self.calls.append(("backup", reason))
            return mock.Mock(filename="backup.db")

        self.patches = [mock.patch.object(config, "GAME_DB_PATH", self.dir / "game.db"),
                        mock.patch.object(items, "_shim", shim),
                        mock.patch.object(backup_service, "create_backup", create_backup)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.items.router)
        return TestClient(app)

    def test_set_backs_up_then_writes_the_amount(self):
        r = self.client().post("/users/1/edit/items/set", json={"possession_type": 6, "possession_id": 108, "count": 0})
        self.assertEqual(r.json(), {"ok": True, "results": [{"possession_type": 6, "possession_id": 108, "amount": 0}]})
        self.assertEqual(self.calls, [
            ("backup", "item-editor"),
            ("shim", {"action": "set_possession_batch", "db_path": str(config.GAME_DB_PATH), "user_id": 1,
                      "grants": [{"possession_type": 6, "possession_id": 108, "count": 0}]})])

    def test_out_of_range_refused_without_backup(self):
        c = self.client()
        for body in ({"possession_type": 6, "possession_id": 1, "count": -1},
                     {"possession_type": 6, "possession_id": 1, "count": 2_147_483_648},
                     {"possession_type": 6, "possession_id": 1, "count": "12"},
                     {"possession_type": 1, "possession_id": 1, "count": 5}):
            r = c.post("/users/1/edit/items/set", json=body)
            self.assertEqual(r.status_code, 400, body)
            self.assertFalse(r.json()["ok"])
        self.assertEqual(self.calls, [])


class Page(unittest.TestCase):
    def test_every_amount_row_has_set_beside_grant(self):
        text = (ROOT / "overlays/python/web/templates/user_items.html").read_text()
        amount_rows = re.findall(r'<input type="number"[^>]*data-amount>\s*<button type="submit">.*?</button>\s*(<button[^>]*>)?', text, re.S)
        self.assertEqual(len(amount_rows), 3)  # each tab's rows, paid gems, free gems
        for after in amount_rows:
            self.assertIn("data-set", after)


if __name__ == "__main__":
    unittest.main()
