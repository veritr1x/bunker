#!/usr/bin/env python3
"""Choosing which player the game signs in as: Pod Programs → Users → Use this player.

Runs on a fresh save made from the server's own schema; needs fastapi (the
Android Python requirements) in the host Python.
"""
from pathlib import Path
import contextlib, sqlite3, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
import android_players  # noqa: E402


def schema():
    text = (root / "server/migrations/20260416182710_initial_schema.sql").read_text()
    return text.split("-- +goose Down")[0]


class UsePlayer(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.save = Path(self.dir.name) / "game.db"
        with contextlib.closing(sqlite3.connect(self.save)) as db, db:
            db.executescript(schema())
            for user, uuid in ((1, "phone"), (2, "old-phone")):
                db.execute("INSERT INTO users (user_id, uuid, player_id) VALUES (?, ?, ?)", (user, uuid, user))
            db.execute("INSERT INTO sessions VALUES ('s1', 1, 'phone', '2026-10-04T12:00:00Z')")
        self.backups = []

    def tearDown(self):
        self.dir.cleanup()

    def owners(self):
        with contextlib.closing(sqlite3.connect(self.save)) as db:
            users = dict(db.execute("SELECT uuid, user_id FROM users"))
            sessions = dict(db.execute("SELECT uuid, user_id FROM sessions"))
            return users, sessions

    def test_switch_swaps_ids_and_keeps_both_players(self):
        self.assertTrue(android_players.use_player(2, self.save, self.backups.append))
        users, sessions = self.owners()
        self.assertEqual(users, {"phone": 2, "old-phone": 1})
        # The game's existing sign-in now belongs to the chosen player.
        self.assertEqual(sessions, {"phone": 2})
        self.assertEqual(self.backups, ["player-switch"])

    def test_switch_back(self):
        android_players.use_player(2, self.save)
        android_players.use_player(1, self.save)
        self.assertEqual(self.owners()[0], {"phone": 1, "old-phone": 2})

    def test_already_in_use_changes_nothing(self):
        self.assertFalse(android_players.use_player(1, self.save, self.backups.append))
        self.assertEqual(self.backups, [])
        self.assertEqual(self.owners()[0], {"phone": 1, "old-phone": 2})

    def test_needs_a_sign_in_and_a_real_player(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            android_players.use_player(9, self.save)
        with contextlib.closing(sqlite3.connect(self.save)) as db, db:
            db.execute("DELETE FROM sessions")
        with self.assertRaisesRegex(ValueError, "sign in"):
            android_players.use_player(2, self.save)

    def test_newest_sign_in_is_this_device(self):
        with contextlib.closing(sqlite3.connect(self.save)) as db, db:
            db.execute("INSERT INTO sessions VALUES ('s2', 2, 'old-phone', '2026-10-01T12:00:00Z')")
        # The newest sign-in was by 'old-phone', so player 2 is the one in use.
        self.assertFalse(android_players.use_player(2, self.save))

    def test_new_player_frees_the_device_and_keeps_the_old_player(self):
        self.assertEqual(android_players.new_player(self.save, self.backups.append), 1)
        users, sessions = self.owners()
        self.assertNotIn("phone", users)          # the next sign-in starts a new player
        self.assertEqual(sorted(users.values()), [1, 2])  # nobody is deleted
        self.assertEqual(sessions, {"phone": 1})  # the device's ID is still known
        self.assertEqual(self.backups, ["player-switch"])
        self.assertIsNone(android_players.new_player(self.save))  # already free
        # The old player can be chosen again.
        self.assertTrue(android_players.use_player(1, self.save))
        self.assertEqual(self.owners()[0]["phone"], 1)


if __name__ == "__main__":
    unittest.main()
