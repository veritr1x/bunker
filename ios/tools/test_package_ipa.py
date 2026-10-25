"""Packaging checks on tiny generated binaries; no game files are needed."""
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest

from package_ipa import LAUNCHER, dylibs, insert_dylib, patch_info
from text_buffer import SITES, patch_text_buffer


def build_executable(directory, *flags):
    source = Path(directory) / "main.c"
    source.write_text("int main(void) { return 0; }\n")
    output = Path(directory) / "Game"
    sdk = subprocess.check_output(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"], text=True).strip()
    subprocess.run(["xcrun", "--sdk", "iphoneos", "clang", "-isysroot", sdk, "-arch", "arm64",
                    "-miphoneos-version-min=14.0", *flags, str(source), "-o", str(output)], check=True)
    return output


class InsertDylibTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_adds_launcher_once_and_keeps_existing_libraries(self):
        executable = build_executable(self.temp.name, "-Wl,-headerpad,0x1000")
        before = dylibs(executable.read_bytes())
        self.assertTrue(insert_dylib(executable))
        after = dylibs(executable.read_bytes())
        self.assertEqual(after, before + [LAUNCHER])
        self.assertFalse(insert_dylib(executable))
        self.assertEqual(dylibs(executable.read_bytes()), after)
        listing = subprocess.check_output(["otool", "-L", str(executable)], text=True)
        self.assertIn(LAUNCHER, listing)

    def test_refuses_executable_without_header_space(self):
        executable = build_executable(self.temp.name, "-Wl,-headerpad,0")
        data = bytearray(executable.read_bytes())
        # Fill any remaining padding so no command can fit.
        size = int.from_bytes(data[20:24], "little")
        data[32 + size:32 + size + 4096] = b"\xff" * min(4096, len(data) - 32 - size)
        executable.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError, "No free load-command space"):
            insert_dylib(executable)


class InfoTests(unittest.TestCase):
    def test_enables_file_sharing_and_raises_minimum_os(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp)
            with (app / "Info.plist").open("wb") as handle:
                plistlib.dump({"MinimumOSVersion": "11.0", "CFBundleIdentifier": "game", "CFBundleExecutable": "Game", "CFBundleDisplayName": "NieR"}, handle)
            info = patch_info(app, "org.example.nier")
            self.assertEqual(info["MinimumOSVersion"], "14.0")
            self.assertTrue(info["UIFileSharingEnabled"])
            self.assertTrue(info["LSSupportsOpeningDocumentsInPlace"])
            self.assertEqual(info["CFBundleIdentifier"], "org.example.nier")
            with (app / "Info.plist").open("rb") as handle:
                self.assertEqual(plistlib.load(handle)["CFBundleDisplayName"], "NieR")

    def test_turns_analytics_off(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp)
            with (app / "Info.plist").open("wb") as handle:
                plistlib.dump({"CFBundleExecutable": "Game", "FacebookAutoLogAppEventsEnabled": True,
                               "GADApplicationIdentifier": "ca-app-pub-1~2"}, handle)
            info = patch_info(app)
            self.assertTrue(info["FIREBASE_ANALYTICS_COLLECTION_DEACTIVATED"])
            for key in ("FirebaseCrashlyticsCollectionEnabled", "FirebaseMessagingAutoInitEnabled", "FacebookAutoInitEnabled",
                        "FacebookAutoLogAppEventsEnabled", "FacebookAdvertiserIDCollectionEnabled"):
                self.assertIs(info[key], False, key)
            self.assertEqual(info["GADApplicationIdentifier"], "ca-app-pub-1~2")  # AdMob stops the game without it


class TextBufferTests(unittest.TestCase):
    SITES = ((0x10, 0x531F7941, 0x0B0B0141), (0x20, 0x531F7901, 0x0B090101))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "UnityFramework"

    def write(self, words):
        data = bytearray(0x30)
        for offset, word in words:
            data[offset:offset + 4] = word.to_bytes(4, "little")
        self.path.write_bytes(data)

    def word(self, offset):
        return int.from_bytes(self.path.read_bytes()[offset:offset + 4], "little")

    def test_patches_each_site_once(self):
        self.write([(o, w) for o, w, _ in self.SITES])
        self.assertEqual(patch_text_buffer(self.path, self.SITES), 2)
        self.assertEqual([self.word(o) for o, _, _ in self.SITES], [p for _, _, p in self.SITES])
        self.assertEqual(patch_text_buffer(self.path, self.SITES), 0)

    def test_unknown_binary_is_left_alone(self):
        self.write([(0x10, 0x531F7941), (0x20, 0xD503201F)])
        before = self.path.read_bytes()
        with self.assertRaises(RuntimeError):
            patch_text_buffer(self.path, self.SITES)
        self.assertEqual(self.path.read_bytes(), before)

    def test_sites_are_lsl_to_add(self):
        self.assertEqual(len(SITES), 58)
        for offset, original, patched in SITES:
            self.assertEqual(original & 0xFFFFFC1F, 0x531F7801)  # lsl w1, wN, #1
            self.assertEqual(patched & 0xFFE0FC1F, 0x0B000001)   # add w1, wN, wM
            self.assertEqual(original >> 5 & 31, patched >> 5 & 31)

class BunkerVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Path(self.temp.name) / "Game.app"
        (self.app / "Frameworks/LunarTear.framework").mkdir(parents=True)
        with (self.app / "Info.plist").open("wb") as f:
            plistlib.dump({"CFBundleIdentifier": "a.b", "CFBundleExecutable": "Game", "MinimumOSVersion": "14.0"}, f)

    def test_records_the_framework_version(self):
        (self.app / "Frameworks/LunarTear.framework/build.json").write_text('{"version": "1.2.3"}')
        self.assertEqual(patch_info(self.app)["BunkerVersion"], "1.2.3")
        with (self.app / "Info.plist").open("rb") as f:
            self.assertEqual(plistlib.load(f)["BunkerVersion"], "1.2.3")

    def test_framework_without_version_is_dev(self):
        self.assertEqual(patch_info(self.app)["BunkerVersion"], "dev")


if __name__ == "__main__":
    unittest.main()


class ScrollSnapTests(unittest.TestCase):
    def test_site_is_the_threshold_load(self):
        import scroll_snap
        (offset, original, patched), = scroll_snap.SITES
        self.assertEqual(original & 0xFFFFFFE0, 0xBD401900)  # ldr sN, [x8, #0x18]
        self.assertEqual(patched & 0xFFFFFFE0, 0x1E2E1000)   # fmov sN, #1.0
        self.assertEqual(original & 31, patched & 31)


class RemainDaysTests(unittest.TestCase):
    def test_each_caller_caps_the_days_then_jumps_to_its_call(self):
        import remain_days
        self.assertEqual(len(remain_days.SITES), 8)
        for start in (0, 4):
            sites = remain_days.SITES[start:start + 4]
            self.assertEqual([p for _, _, p in sites[:3]], [0x52807CE8, 0x6B08001F, 0x1A88D000])
            offset, original, patched = sites[3]
            self.assertEqual(original & 0xFFF8001F, 0x36480008)  # tbz w8, #9, ...
            self.assertEqual(offset + (patched & 0x3FFFFFF) * 4, offset + (original >> 5 & 0x3FFF) * 4 + 4)  # the call after the init check
            self.assertEqual([o - offset for o, _, _ in sites], [-12, -8, -4, 0])
