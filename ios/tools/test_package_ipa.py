"""Packaging checks on tiny generated binaries; no game files are needed."""
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest

from package_ipa import LAUNCHER, dylibs, insert_dylib, patch_info


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


if __name__ == "__main__":
    unittest.main()
