#!/usr/bin/env python3
"""The launcher builds the Archive's index before it starts the game, when the
index is missing or out of date; the Archive's page shows that same build.
Needs fastapi and jinja2."""
from pathlib import Path
import json, sqlite3, sys, tempfile, threading, time, unittest
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / "android/app/src/main/python"), str(root / "upstream/lunar-base/tools")]
import android_archive  # noqa: E402
from archive import app, index  # noqa: E402


def game_files(folder: Path) -> tuple[Path, Path]:
    """Imported game files with English text and the master data in use."""
    assets, archive = folder / "server", folder / "archive"
    (assets / "assets/revisions/0/assetbundle/text/en").mkdir(parents=True)
    (assets / "assets/release").mkdir(parents=True)
    (assets / "assets/release/20240404193219.bin.e").write_bytes(b"master")
    return assets, archive


def fake_build(release: threading.Event, calls: list):
    def build(revision, master, db_path, progress=lambda *a: None, scenario=None):
        calls.append(db_path)
        progress(1, 2, "Story text")
        release.wait(5)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO meta VALUES ('signature', ?)", (json.dumps(index.signature(revision, master)),))
        return {}
    return build


class LauncherIndex(unittest.TestCase):
    def setUp(self):
        app._builders.clear()

    def test_nothing_to_build_without_game_text(self):
        with tempfile.TemporaryDirectory() as folder:
            status = json.loads(android_archive.index_status(str(Path(folder) / "server"), str(Path(folder) / "archive")))
            self.assertEqual((status["possible"], status["ready"], status["running"]), (False, False, False))
            self.assertEqual(json.loads(android_archive.build_index(str(Path(folder) / "server"), str(Path(folder) / "archive"),
                                                                    scenario=None))["running"], False)

    def test_builds_once_then_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            assets, archive = game_files(Path(folder))
            release, calls = threading.Event(), []
            with mock.patch.object(index, "build", fake_build(release, calls)):
                first = json.loads(android_archive.build_index(str(assets), str(archive), scenario=None))
                self.assertTrue(first["possible"] and first["running"] and not first["ready"])
                time.sleep(.05)
                second = json.loads(android_archive.build_index(str(assets), str(archive), scenario=None))
                self.assertEqual((second["running"], second["done"], second["total"], second["step"]), (True, 1, 2, "Story text"))
                release.set()
                for _ in range(100):
                    status = json.loads(android_archive.index_status(str(assets), str(archive)))
                    if not status["running"]:
                        break
                    time.sleep(.02)
            self.assertEqual(len(calls), 1)
            self.assertTrue(status["ready"])
            self.assertEqual(status["error"], "")
            # Current: asking again builds nothing.
            with mock.patch.object(index, "build", fake_build(release, calls)):
                self.assertTrue(json.loads(android_archive.build_index(str(assets), str(archive), scenario=None))["ready"])
            self.assertEqual(len(calls), 1)

    def test_a_failed_build_reports_its_error(self):
        with tempfile.TemporaryDirectory() as folder:
            assets, archive = game_files(Path(folder))
            with mock.patch.object(index, "build", side_effect=FileNotFoundError("no text")):
                android_archive.build_index(str(assets), str(archive), scenario=None)
                for _ in range(100):
                    status = json.loads(android_archive.index_status(str(assets), str(archive)))
                    if not status["running"]:
                        break
                    time.sleep(.02)
            self.assertEqual((status["ready"], status["error"]), (False, "no text"))

    def test_the_archive_page_shares_the_launchers_build(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "archive.db"
            first = app.shared_builder(Path(folder) / "rev", Path(folder) / "m", db)
            self.assertIs(app.shared_builder(Path(folder) / "rev", Path(folder) / "m", db), first)
            self.assertIsNot(app.shared_builder(Path(folder) / "rev2", Path(folder) / "m", db), first)


if __name__ == "__main__":
    unittest.main()
