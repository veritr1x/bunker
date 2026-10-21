#!/usr/bin/env python3
"""Rebuilding an installed Bunker APK with a newer launcher (assemble_apk.update)."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import assemble_apk
import build_info

ROOT = Path(__file__).resolve().parents[2]
GAME_APK = ROOT / "inputs/game-3.7.1.apk"
COMPANION_APK = ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"
MASTER = "assets/lunar/20240404193219.bin.e"


def manifests():
    if not GAME_APK.is_file() or not COMPANION_APK.is_file():
        raise unittest.SkipTest("needs inputs/game-3.7.1.apk and a built launcher APK")
    with zipfile.ZipFile(GAME_APK) as g, zipfile.ZipFile(COMPANION_APK) as c:
        return g.read("AndroidManifest.xml"), c.read("AndroidManifest.xml")


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.work = Path(self.t.name)
        self.game_manifest, self.companion_manifest = manifests()

    def installed(self, **info_changes):
        info = {"version": "1.0.0", "gamePatch": build_info.GAME_PATCH, "portOffset": 0, "gameDex": 1,
                "bunkerLibs": ["lib/arm64-v8a/liblunar.so", "lib/arm64-v8a/libold.so"]}
        info.update(info_changes)
        path = self.work / "installed.apk"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("AndroidManifest.xml", b"patched manifest, replaced by the update")
            z.writestr("classes.dex", b"game dex")
            z.writestr("lib/arm64-v8a/libil2cpp.so", b"patched game library")
            z.writestr("assets/bin/Data/a", b"game data")
            z.writestr("classes2.dex", b"old launcher dex")
            z.writestr("lib/arm64-v8a/liblunar.so", b"old server")
            z.writestr("lib/arm64-v8a/libold.so", b"dropped library")
            z.writestr("assets/chaquopy/old.zip", b"old python")
            z.writestr(MASTER, b"patched master")
            z.writestr("assets/lunar/original-master.bin.e", b"original master")
            z.writestr("assets/lunar/LUNAR_TEAR_LICENSE.txt", b"license")
            z.writestr("assets/lunar/game-manifest.xml", self.game_manifest)
            z.writestr("assets/lunar/build.json", json.dumps(info))
            z.writestr("META-INF/CERT.RSA", b"old signature")
            z.writestr("assets/notices/notices.json", b"old notices")
            z.writestr("assets/notices/img/old.webp", b"old image")
        return path

    def notice_pack(self):
        path = self.work / "notices.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("notices.json", b"new notices")
            z.writestr("img/new.webp", b"new image")
        return path

    def companion(self):
        path = self.work / "bundle.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("AndroidManifest.xml", self.companion_manifest)
            z.writestr("classes.dex", b"new launcher dex")
            z.writestr("lib/arm64-v8a/liblunar.so", b"new server")
            z.writestr("lib/arm64-v8a/libnew.so", b"new library")
            z.writestr("assets/chaquopy/new.zip", b"new python")
            z.writestr("assets/lunar/bunker-version.txt", b"1.1.0\n")
        return path

    def test_update_replaces_bunker_files_keeps_game(self):
        out = self.work / "out.apk"
        info = assemble_apk.update(self.installed(), self.companion(), out, log=lambda m: None)
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
            for name, data in [("classes.dex", b"game dex"), ("lib/arm64-v8a/libil2cpp.so", b"patched game library"),
                               ("assets/bin/Data/a", b"game data"), (MASTER, b"patched master"),
                               ("assets/lunar/original-master.bin.e", b"original master"),
                               ("assets/lunar/game-manifest.xml", self.game_manifest),
                               ("classes2.dex", b"new launcher dex"), ("lib/arm64-v8a/liblunar.so", b"new server"),
                               ("lib/arm64-v8a/libnew.so", b"new library"), ("assets/chaquopy/new.zip", b"new python")]:
                self.assertEqual(z.read(name), data, name)
            for gone in ["lib/arm64-v8a/libold.so", "assets/chaquopy/old.zip", "META-INF/CERT.RSA"]:
                self.assertNotIn(gone, names)
            manifest = z.read("AndroidManifest.xml")
            self.assertNotEqual(manifest, b"patched manifest, replaced by the update")
            self.assertIn("org.veritr1x.bunker".encode("utf-16-le"), manifest)
            written = json.loads(z.read("assets/lunar/build.json"))
        self.assertEqual(written, info)
        self.assertEqual(info["version"], "1.1.0")
        self.assertEqual(info["gameDex"], 1)
        self.assertEqual(info["bunkerLibs"], ["lib/arm64-v8a/liblunar.so", "lib/arm64-v8a/libnew.so"])

    def test_update_keeps_the_installed_notices(self):
        out = self.work / "out.apk"
        info = assemble_apk.update(self.installed(notices="abc"), self.companion(), out, log=lambda m: None)
        with zipfile.ZipFile(out) as z:
            self.assertEqual(z.read("assets/notices/notices.json"), b"old notices")
            self.assertEqual(z.read("assets/notices/img/old.webp"), b"old image")
        self.assertEqual(info["notices"], "abc")

    def test_update_replaces_the_notices_with_a_new_pack(self):
        import notice_pack
        out = self.work / "out.apk"
        pack = self.notice_pack()
        info = assemble_apk.update(self.installed(notices="abc"), self.companion(), out, log=lambda m: None, notices=pack)
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
            self.assertEqual(z.read("assets/notices/notices.json"), b"new notices")
            self.assertEqual(z.read("assets/notices/img/new.webp"), b"new image")
            self.assertNotIn("assets/notices/img/old.webp", names)
        self.assertEqual(info["notices"], notice_pack.sha256(pack))

    def test_update_keeps_port_offset(self):
        out = self.work / "out.apk"
        info = assemble_apk.update(self.installed(portOffset=7), self.companion(), out, log=lambda m: None)
        self.assertEqual(info["portOffset"], 7)

    def test_old_build_needs_web_builder(self):
        path = self.work / "old.apk"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("AndroidManifest.xml", b"x")
            z.writestr("classes.dex", b"game dex")
        with self.assertRaisesRegex(RuntimeError, "web builder"):
            assemble_apk.update(path, self.companion(), self.work / "out.apk", log=lambda m: None)
        self.assertFalse((self.work / "out.apk").exists())

    def test_game_patch_change_needs_web_builder(self):
        with self.assertRaisesRegex(RuntimeError, "web builder"):
            assemble_apk.update(self.installed(gamePatch=build_info.GAME_PATCH + 1), self.companion(),
                                self.work / "out.apk", log=lambda m: None)


class DeviceBuildTests(unittest.TestCase):
    """bunker_update.build_android, as the launcher runs it (with the tools importable as bunker_tools)."""

    def setUp(self):
        import sys
        import types
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.work = Path(self.t.name)
        package = types.ModuleType("bunker_tools")
        package.__path__ = [str(Path(__file__).resolve().parent)]
        sys.modules["bunker_tools"] = package
        sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
        import bunker_update
        self.bunker_update = bunker_update
        self.case = UpdateTests("test_update_keeps_port_offset")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_damaged_download_is_refused(self):
        bundle = self.case.companion()
        with self.assertRaisesRegex(RuntimeError, "damaged"):
            self.bunker_update.build_android(self.case.installed(), bundle, "0" * 64, self.work / "update",
                                             ROOT / "web/signing/bunker-key.pem", ROOT / "web/signing/bunker-cert.der", print)
        self.assertFalse(any((self.work / "update").glob("*.apk")))

    def test_damaged_notices_are_refused(self):
        import hashlib
        bundle = self.case.companion()
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        with self.assertRaisesRegex(RuntimeError, "damaged"):
            self.bunker_update.build_android(self.case.installed(), bundle, digest, self.work / "update",
                                             ROOT / "web/signing/bunker-key.pem", ROOT / "web/signing/bunker-cert.der", print,
                                             self.case.notice_pack(), "0" * 64)

    def test_builds_and_signs(self):
        import hashlib
        bundle = self.case.companion()
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        apk = Path(self.bunker_update.build_android(self.case.installed(), bundle, digest, self.work / "update",
                                                    ROOT / "web/signing/bunker-key.pem", ROOT / "web/signing/bunker-cert.der",
                                                    lambda m: None))
        self.assertTrue(apk.is_file())
        self.assertIn(b"APK Sig Block 42", apk.read_bytes())


if __name__ == "__main__":
    unittest.main()
