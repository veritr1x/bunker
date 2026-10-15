#!/usr/bin/env python3
"""What a Bunker APK records about itself (assets/lunar/build.json)."""
import io
import unittest
import zipfile

import build_info


def zip_of(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        for name, content in entries.items():
            z.writestr(name, content)
    data.seek(0)
    return zipfile.ZipFile(data)


class BuildInfoTests(unittest.TestCase):
    def test_describe(self):
        companion = zip_of({"classes.dex": "d", "lib/arm64-v8a/liblunar.so": "l", "lib/arm64-v8a/libbunkerdisplay.so": "b",
                            "assets/lunar/bunker-version.txt": "1.2.3\n"})
        info = build_info.describe(companion, game_dex=2, port_offset=5)
        self.assertEqual(info["version"], "1.2.3")
        self.assertEqual(info["gameDex"], 2)
        self.assertEqual(info["portOffset"], 5)
        self.assertEqual(info["gamePatch"], build_info.GAME_PATCH)
        self.assertEqual(info["bunkerLibs"], ["lib/arm64-v8a/libbunkerdisplay.so", "lib/arm64-v8a/liblunar.so"])

    def test_describe_without_version_file(self):
        self.assertEqual(build_info.describe(zip_of({"classes.dex": "d"}), 1, 0)["version"], "dev")

    def test_is_bunker_entry(self):
        info = {"gameDex": 2, "bunkerLibs": ["lib/arm64-v8a/liblunar.so"]}
        for name in ["classes3.dex", "classes4.dex", "lib/arm64-v8a/liblunar.so", "assets/chaquopy/a", "assets/lunar/build.json"]:
            self.assertTrue(build_info.is_bunker_entry(name, info), name)
        for name in ["classes.dex", "classes2.dex", "lib/arm64-v8a/libil2cpp.so", "assets/bin/Data/x", "AndroidManifest.xml"]:
            self.assertFalse(build_info.is_bunker_entry(name, info), name)


if __name__ == "__main__":
    unittest.main()
