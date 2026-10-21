"""Rebuilding the installed iOS app into an IPA with a newer Bunker (bunker_ios_update.build_ipa)."""
import hashlib
import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
import bunker_ios_update  # noqa: E402


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())


class BuildIpaTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        work = Path(self.t.name)
        self.app = work / "NieR.app"
        with (write(self.app / "Info.plist", b"") or (self.app / "Info.plist")).open("wb") as f:
            plistlib.dump({"CFBundleIdentifier": "org.example.nier", "BunkerVersion": "1.0.0", "LunarPortOffset": 3}, f)
        write(self.app / "NieR", "game executable")
        write(self.app / "Data/data.unity3d", "game data")
        write(self.app / "_CodeSignature/CodeResources", "old signature")
        write(self.app / "embedded.mobileprovision", "old profile")
        write(self.app / "Frameworks/UnityFramework.framework/UnityFramework", "patched unity")
        write(self.app / "Frameworks/UnityFramework.framework/_CodeSignature/CodeResources", "sig")
        write(self.app / "Frameworks/LunarTear.framework/LunarTear", "old launcher")
        write(self.app / "Frameworks/LunarTear.framework/build.json", '{"version": "1.0.0", "gamePatch": 1}')
        write(self.app / "Frameworks/LunarTear.framework/20240404193219.bin.e", "patched master")
        write(self.app / "Frameworks/LunarTear.framework/original-master.bin.e", "original master")
        write(self.app / "Frameworks/Python.framework/Python", "old python")
        write(self.app / "Frameworks/old.module.framework/old.module", "old module")
        write(self.app / "Frameworks/old.module.framework/old.module.origin", "python/x.fwork")
        write(self.app / "python/app/old.py", "old code")
        write(self.app / "notices.zip", "old notices")
        self.framework_zip = work / "framework.zip"
        with zipfile.ZipFile(self.framework_zip, "w") as z:
            binary = zipfile.ZipInfo("LunarTear.framework/LunarTear")
            binary.external_attr = 0o100755 << 16
            z.writestr(binary, "new launcher")
            z.writestr("LunarTear.framework/build.json", '{"version": "1.1.0", "gamePatch": 1}')
        self.python_zip = work / "python.zip"
        with zipfile.ZipFile(self.python_zip, "w") as z:
            z.writestr("Frameworks/Python.framework/Python", "new python")
            z.writestr("Frameworks/new.module.framework/new.module", "new module")
            z.writestr("Frameworks/new.module.framework/new.module.origin", "python/y.fwork")
            z.writestr("python/app/new.py", "new code")
        self.output = work / "Bunker-1.1.0.ipa"

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def build(self, sha_framework=None, sha_python=None):
        return bunker_ios_update.build_ipa(self.app, self.framework_zip, self.python_zip,
                                           sha_framework or self.sha(self.framework_zip), sha_python or self.sha(self.python_zip),
                                           self.output, lambda m: None)

    def test_keeps_the_installed_notices(self):
        self.build()
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read("Payload/NieR.app/notices.zip"), b"old notices")

    def test_replaces_the_notices_with_a_new_pack(self):
        pack = Path(self.t.name) / "new-notices.zip"
        pack.write_bytes(b"new notices")
        bunker_ios_update.build_ipa(self.app, self.framework_zip, self.python_zip, self.sha(self.framework_zip),
                                    self.sha(self.python_zip), self.output, lambda m: None, pack, self.sha(pack))
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read("Payload/NieR.app/notices.zip"), b"new notices")
            self.assertEqual(z.namelist().count("Payload/NieR.app/notices.zip"), 1)
            self.assertEqual(plistlib.loads(z.read("Payload/NieR.app/Info.plist"))["BunkerNotices"], self.sha(pack))

    def test_damaged_notices_are_refused(self):
        pack = Path(self.t.name) / "new-notices.zip"
        pack.write_bytes(b"new notices")
        with self.assertRaisesRegex(RuntimeError, "damaged"):
            bunker_ios_update.build_ipa(self.app, self.framework_zip, self.python_zip, self.sha(self.framework_zip),
                                        self.sha(self.python_zip), self.output, lambda m: None, pack, "0" * 64)

    def test_ipa_has_new_bunker_and_same_game(self):
        self.assertEqual(self.build(), str(self.output))
        with zipfile.ZipFile(self.output) as z:
            names = set(z.namelist())
            app = "Payload/NieR.app/"
            self.assertEqual(z.read(app + "NieR"), b"game executable")
            self.assertEqual(z.read(app + "Data/data.unity3d"), b"game data")
            self.assertEqual(z.read(app + "Frameworks/UnityFramework.framework/UnityFramework"), b"patched unity")
            self.assertEqual(z.read(app + "Frameworks/LunarTear.framework/LunarTear"), b"new launcher")
            self.assertEqual(z.read(app + "Frameworks/Python.framework/Python"), b"new python")
            self.assertEqual(z.read(app + "Frameworks/new.module.framework/new.module"), b"new module")
            self.assertEqual(z.read(app + "python/app/new.py"), b"new code")
            for gone in ["_CodeSignature/CodeResources", "embedded.mobileprovision", "python/app/old.py",
                         "Frameworks/old.module.framework/old.module", "Frameworks/UnityFramework.framework/_CodeSignature/CodeResources"]:
                self.assertNotIn(app + gone, names)
            self.assertEqual(z.getinfo(app + "Frameworks/LunarTear.framework/LunarTear").external_attr >> 16, 0o100755)
            info = plistlib.loads(z.read(app + "Info.plist"))
        self.assertEqual(info["BunkerVersion"], "1.1.0")
        self.assertEqual(info["CFBundleIdentifier"], "org.example.nier")
        self.assertEqual(info["LunarPortOffset"], 3)

    def test_master_data_stays(self):
        # Release bundles never hold master data; the player's own copy stays in the framework.
        self.build()
        with zipfile.ZipFile(self.output) as z:
            framework = "Payload/NieR.app/Frameworks/LunarTear.framework/"
            self.assertEqual(z.read(framework + "20240404193219.bin.e"), b"patched master")
            self.assertEqual(z.read(framework + "original-master.bin.e"), b"original master")

    def test_leftover_partial_is_removed_on_failure(self):
        with self.assertRaises(RuntimeError):
            self.build(sha_python="0" * 64)
        self.assertFalse(self.output.with_name(self.output.name + ".partial").exists())

    def test_damaged_download_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "damaged"):
            self.build(sha_framework="0" * 64)
        self.assertFalse(self.output.exists())

    def test_game_patch_change_needs_web_builder(self):
        with zipfile.ZipFile(self.framework_zip, "w") as z:
            z.writestr("LunarTear.framework/LunarTear", "new launcher")
            z.writestr("LunarTear.framework/build.json", '{"version": "1.1.0", "gamePatch": 2}')
        with self.assertRaisesRegex(RuntimeError, "web builder"):
            self.build()


if __name__ == "__main__":
    unittest.main()
