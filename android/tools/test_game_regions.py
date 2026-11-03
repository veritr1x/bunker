"""Regional build checks; private APK fixtures are optional and never modified.

Set BUNKER_GLOBAL_APK and BUNKER_JP_APK to exercise both real 3.7.1 clients.
"""
import os
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import assemble_apk
import axml
import game_patch
from axml import Attr, Document, Element

ROOT = Path(__file__).resolve().parents[2]


def manifest(package, launcher=".Game", companion=False):
    app = Element("application")
    activity = Element("activity", [Attr.string("name", launcher, assemble_apk.NAME)])
    activity.children.append(Element("intent-filter", children=[Element("category", [
        Attr.string("name", "android.intent.category.LAUNCHER", assemble_apk.NAME)])]))
    app.children.append(activity)
    if companion:
        app.children.append(Element("provider", [Attr.string("name", "org.veritr1x.bunker.GameProcessProvider", assemble_apk.NAME)]))
    root = Element("manifest", [Attr("package", ns=None, raw=package), Attr.string("versionName", "3.7.1", 0x0101021C)], [
        Element("uses-sdk", [Attr.integer("minSdkVersion", 24, assemble_apk.MIN_SDK)]), app])
    return axml.serialize(Document(root, [("android", axml.ANDROID_NS, 1)]))


def metadata(strings):
    raw = [s.encode() for s in strings]
    table, blob = 24, 24 + len(raw) * 8
    data = bytearray(struct.pack("<6I", 0xFAB11BAF, 24, table, len(raw) * 8, blob, sum(map(len, raw))))
    index = 0
    for value in raw:
        data.extend(struct.pack("<II", len(value), index)); index += len(value)
    return bytes(data) + b"".join(raw)


def literals(data):
    table, size, blob, _ = struct.unpack_from("<4I", data, 8)
    result = []
    for at in range(table, table + size, 8):
        length, index = struct.unpack_from("<II", data, at)
        result.append(data[blob + index:blob + index + length].decode())
    return result


class Regions(unittest.TestCase):
    def test_korean_uses_the_global_profile(self):
        self.assertEqual(game_patch.profile_for_manifest(game_patch.PACKAGE_PREFIX + "ww", "3.7.1"), "global")
        self.assertEqual(game_patch.profile_for_manifest(game_patch.PACKAGE_PREFIX + "jp", "3.7.1"), "jp")
        for package, version in [(game_patch.PACKAGE_PREFIX + "ww", "3.7.0"), (game_patch.PACKAGE_PREFIX + "kr", "3.7.1")]:
            with self.assertRaises(RuntimeError):
                game_patch.profile_for_manifest(package, version)

    def test_manifest_preserves_each_region_on_build_and_update(self):
        companion = manifest("org.veritr1x.bunker", "org.veritr1x.bunker.MainActivity", companion=True)
        for profile in game_patch.PROFILES.values():
            package = profile["package"]
            for launcher in (".Game", "Game", "com.unity3d.player.UnityPlayerActivity"):
                with self.subTest(package=package, launcher=launcher):
                    original = manifest(package, launcher)
                    for _ in range(2):  # update() patches the preserved original manifest too.
                        result, activity = assemble_apk.patch_manifest(original, companion, 30000)
                        doc = axml.parse(result).root
                        self.assertEqual(doc.get("package", ns=None).raw, package)
                        expected = launcher if "." in launcher and not launcher.startswith(".") else package + "." + launcher.lstrip(".")
                        self.assertEqual(activity, expected)
                        provider = doc.find_all("application")[0].find_all("provider")[0]
                        self.assertEqual(provider.get("authorities").raw, package + ".lunar_loopback")

    def test_endpoints_are_whole_literals_and_jp_credentials_are_removed(self):
        for region, profile in game_patch.PROFILES.items():
            suffix = "app.nierreincarnation." + profile["domain"]
            web = "https://" + ("unused:example@" if region == "jp" else "") + "web." + suffix
            original = metadata(["unrelated", "api." + suffix, web,
                "https://web." + suffix + "/assets/release/{0}/database.bin",
                "https://resources-api." + suffix + "/"])
            result = game_patch.patch_metadata(original, region, 30000)
            self.assertEqual(len(result), len(original))
            self.assertEqual(literals(result), ["unrelated", "127.0.0.1", "http://127.0.0.1:38080",
                "http://127.0.0.1:38080/assets/release/{0}/database.bin", "http://127.0.0.1:38080/"])
            self.assertNotIn(b"unused:example@", result)

    def test_missing_endpoints_and_malformed_data_are_refused(self):
        for raw in [b"", metadata(["https://web.app.nierreincarnation.com"]), struct.pack("<6I", 0xFAB11BAF, 24, 24, 8, 32, 5)]:
            with self.assertRaises(RuntimeError):
                game_patch.patch_metadata(raw, "global")
        with self.assertRaises(RuntimeError):
            game_patch.patch_files(b"unknown library", b"unknown metadata")
        with self.assertRaises(RuntimeError):
            game_patch.elf_offset(bytes(64), 0, 4)


@unittest.skipUnless(os.environ.get("BUNKER_GLOBAL_APK") and os.environ.get("BUNKER_JP_APK"), "set BUNKER_GLOBAL_APK and BUNKER_JP_APK")
class OriginalApks(unittest.TestCase):
    def apks(self):
        return [(region, Path(os.environ[key])) for region, key in [("global", "BUNKER_GLOBAL_APK"), ("jp", "BUNKER_JP_APK")]]

    def test_real_binaries_default_and_offset_ports(self):
        for region, path in self.apks():
            with zipfile.ZipFile(path) as apk:
                lib, meta = apk.read(game_patch.LIB), apk.read(game_patch.METADATA)
            for port_offset in [0, 30000, 57455]:
                with self.subTest(region=region, port_offset=port_offset):
                    result, metadata_out = game_patch.patch_files(lib, meta, port_offset, expected=region)
                    self.assertEqual(len(result), len(lib))
                    rvas = game_patch.PROFILES[region]["rvas"]
                    reachability = game_patch.elf_offset(result, rvas[13], 8)
                    self.assertEqual(result[reachability:reachability + 8], bytes.fromhex("40008052c0035fd6"))
                    port = game_patch.elf_offset(result, rvas[10], 8)
                    self.assertEqual(struct.unpack_from("<II", result, port), (0x52800000 | (8003 + port_offset) << 5, 0xD65F03C0))
                    # The public getter is a four-byte B to the original getter.
                    # Preserve it, including when callers use either entry point.
                    self.assertEqual(result[port - 4:port], lib[port - 4:port])
                    host = game_patch.elf_offset(result, rvas[14], 4)
                    self.assertEqual(lib[host:host + 4], bytes.fromhex("80010036"))
                    self.assertEqual(result[host:host + 4], bytes.fromhex("1f2003d5"))
                    self.assertIn(f"http://127.0.0.1:{8080 + port_offset}", literals(metadata_out))
            with self.assertRaisesRegex(RuntimeError, "different regions"):
                game_patch.patch_files(lib, meta, expected="jp" if region == "global" else "global")
            with self.assertRaises(RuntimeError):
                game_patch.patch_library(lib[:-1], region)
            with self.assertRaises(ValueError):
                game_patch.patch_library(lib, region, 57456)

    def test_cli_uses_original_manifest_when_apktool_omits_version(self):
        import sys
        for region, apk in self.apks():
            with self.subTest(region=region), tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(apk) as original:
                decoded = Path(tmp)
                for name in (game_patch.LIB, game_patch.METADATA):
                    target = decoded / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(original.read(name))
                (decoded / "AndroidManifest.xml").write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="'
                    + game_patch.PROFILES[region]["package"] + '"><application /></manifest>')
                with patch.object(sys, "argv", ["game_patch", "--decoded-dir", str(decoded), "--game-apk", str(apk), "--port-offset", "30000"]):
                    game_patch.main()
                expected_lib, expected_metadata = game_patch.patch_files(original.read(game_patch.LIB), original.read(game_patch.METADATA), 30000)
                self.assertEqual((decoded / game_patch.LIB).read_bytes(), expected_lib)
                self.assertEqual((decoded / game_patch.METADATA).read_bytes(), expected_metadata)

    def test_runtime_patch_guards_match_both_original_binaries(self):
        cpp = ROOT / "android/app/src/main/cpp"
        header = (cpp / "game_region.h").read_text()
        mapping = {int(a, 16): int(b, 16) for a, b in re.findall(r"case (0x[0-9A-F]+): return (0x[0-9A-F]+);", header)}
        body = header.split("static inline uint32_t game_original", 1)[1].split("static inline uint32_t game_patched", 1)[0]
        originals = {int(a, 16): int(b, 16) for a, b in re.findall(r"case (0x[0-9A-F]+): return (0x[0-9a-f]+)u;", body)}
        for region, path in self.apks():
            with zipfile.ZipFile(path) as apk:
                lib = apk.read(game_patch.LIB)
            for name in ["text_buffer.c", "remain_days.c", "display_patch.c", "camera_edge.c"]:
                source = (cpp / name).read_text()
                for a, word in re.findall(r"\{(0x[0-9A-F]+), (0x[0-9a-f]+)u", source):
                    rva, expected = int(a, 16), int(word, 16)
                    if region == "jp":
                        expected = originals.get(rva, expected)
                        rva = mapping[rva]
                    offset = game_patch.elf_offset(lib, rva, 4)
                    self.assertEqual(struct.unpack_from("<I", lib, offset)[0], expected, (region, name, a))
                words = {n: bytes.fromhex("".join(int(w,16).to_bytes(4,"little").hex() for w in re.findall(r"0x([0-9a-f]+)u", v)))
                    for n, v in re.findall(r"static const uint32_t (\w+)\[4\] = \{([^}]*)\}", source)}
                for a, n in re.findall(r"\{(0x[0-9A-F]+), (k\w+)\}", source):
                    rva = int(a, 16)
                    if region == "jp": rva = mapping[rva]
                    offset = game_patch.elf_offset(lib, rva, 16)
                    self.assertEqual(lib[offset:offset + 16], words[n], (region, n))

    def test_web_build_sign_and_update_keep_region(self):
        import sys
        sys.path.insert(0, str(ROOT / "web"))
        import webbuild
        import apk_sign
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            master = tmp / "master.bin.e"; master.write_bytes(b"original master")
            companion = tmp / "companion.apk"
            notices = tmp / "notices.zip"
            with zipfile.ZipFile(notices, "w") as pack:
                pack.writestr("notices.json", "[]")
            with zipfile.ZipFile(companion, "w") as apk:
                apk.writestr("AndroidManifest.xml", manifest("org.veritr1x.bunker", "org.veritr1x.bunker.MainActivity", companion=True))
                apk.writestr("classes.dex", b"launcher dex")
                apk.writestr("assets/lunar/bunker-version.txt", b"dev")
                apk.writestr("assets/lunar/game-patch.txt", str(assemble_apk.build_info.GAME_PATCH))
            for region, path in self.apks():
                out, updated = tmp / (region + ".apk"), tmp / (region + "-updated.apk")
                with patch.object(assemble_apk, "patch_master", return_value=b"patched master"):
                    webbuild.build_android(path, master, companion, out, log=lambda _:None, port_offset=30000, notices=notices)
                self.assertIn(apk_sign.MAGIC, out.read_bytes())
                assemble_apk.update(out, companion, updated, log=lambda _:None)
                with zipfile.ZipFile(out) as built, zipfile.ZipFile(updated) as new:
                    self.assertIsNone(built.testzip())
                    for apk in (built, new):
                        root = axml.parse(apk.read("AndroidManifest.xml")).root
                        self.assertEqual(root.get("package", ns=None).raw, game_patch.PROFILES[region]["package"])
                        app = root.find_all("application")[0]
                        self.assertNotEqual(app.get("label").raw, "Bunker")  # the game keeps its own name and icon
                        self.assertIn("assets/notices/notices.json", apk.namelist())
                    import privacy
                    with zipfile.ZipFile(path) as original:
                        expected_lib = privacy.patch_library(game_patch.patch_library(original.read(game_patch.LIB), region, 30000), profile=region)
                    self.assertEqual(built.read(game_patch.LIB), expected_lib)
                    self.assertEqual(new.read(game_patch.LIB), built.read(game_patch.LIB))
                    self.assertEqual(new.read(game_patch.METADATA), built.read(game_patch.METADATA))


if __name__ == "__main__":
    unittest.main()
