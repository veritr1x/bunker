#!/usr/bin/env python3
"""An update is built by the release's own updater, from its Python bundle, so a fix to the
updater reaches the update that brings it (ios_runtime.build_ipa_update)."""
from pathlib import Path
import ctypes, hashlib, sys, tempfile, unittest, zipfile
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "ios/python"))
sys.path.insert(0, str(root / "android/app/src/main/python"))

# The release's updater: it imports a game fix as it builds, as the real one does (unity_sites).
RELEASE_UPDATER = '''
def build_ipa(app_dir, framework_zip, python_zip, sha_framework, sha_python, output_ipa, reporter, notices_zip=None, sha_notices=None):
    import text_buffer
    return "release:" + text_buffer.MARK
'''


def bundle(path, updater=RELEASE_UPDATER, fixes=True):
    with zipfile.ZipFile(path, "w") as z:
        if updater is not None:
            z.writestr("python/app/bunker_ios_update.py", updater)
        if fixes:
            for name in ("guerrilla_unlock", "remain_days", "scroll_snap"):
                z.writestr(f"python/app/{name}.py", "SITES = []\n")
            z.writestr("python/app/text_buffer.py", "SITES = []\nMARK = 'release fixes'\n")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReleaseUpdater(unittest.TestCase):
    def setUp(self):
        # ios_runtime looks up the launcher's functions in its own process as it loads.
        with mock.patch.object(ctypes, "CDLL", lambda name: mock.MagicMock()):
            import ios_runtime
        self.runtime = ios_runtime
        self.reports = []
        p = mock.patch.object(ios_runtime, "_report", self.reports.append)
        p.start()
        self.addCleanup(p.stop)
        import bunker_ios_update, text_buffer
        self.installed = (bunker_ios_update, text_buffer)
        p = mock.patch.object(bunker_ios_update, "build_ipa", lambda *args: "installed")
        p.start()
        self.addCleanup(p.stop)
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def build(self, zip_path, sha):
        return self.runtime.build_ipa_update("app", "framework.zip", str(zip_path), "f", sha, "out.ipa")

    def assert_installed_modules_back(self):
        self.assertIs(sys.modules["bunker_ios_update"], self.installed[0])
        self.assertIs(sys.modules["text_buffer"], self.installed[1])
        self.assertFalse(any(path.startswith(self.dir.name) for path in sys.path))

    def test_the_release_updater_builds_with_the_release_fixes(self):
        path = Path(self.dir.name) / "python.zip"
        self.assertEqual(self.build(path, bundle(path)), "release:release fixes")
        self.assertEqual(self.reports[-1], "Building with the new version's updater…")
        self.assert_installed_modules_back()

    def test_a_bundle_that_is_not_the_release_runs_nothing_from_it(self):
        path = Path(self.dir.name) / "python.zip"
        bundle(path)
        self.assertEqual(self.build(path, "0" * 64), "installed")
        self.assertEqual(self.reports[-1], "Building with this app's updater…")
        self.assert_installed_modules_back()

    def test_a_release_without_its_updater_uses_the_installed_one(self):
        path = Path(self.dir.name) / "python.zip"
        self.assertEqual(self.build(path, bundle(path, updater=None)), "installed")
        self.assert_installed_modules_back()

    def test_an_updater_that_does_not_load_falls_back(self):
        path = Path(self.dir.name) / "python.zip"
        self.assertEqual(self.build(path, bundle(path, updater="raise ImportError('broken')\n")), "installed")
        self.assert_installed_modules_back()


if __name__ == "__main__":
    unittest.main()
