#!/usr/bin/env python3
"""LunarTear.framework builds for an iPhone and for the iOS Simulator (simulator_smoke.sh). The simulator SDK has
no MetalFX: there the upscaler is left out (plain stretching, as on a device without MetalFX). Needs Xcode."""
from pathlib import Path
import platform
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILD = (ROOT / "ios/tools/build_framework.sh").read_text()


def sdk(name: str) -> Path | None:
    if platform.system() != "Darwin" or not shutil.which("xcrun"):
        return None
    found = subprocess.run(["xcrun", "--sdk", name, "--show-sdk-path"], capture_output=True, text=True)
    return Path(found.stdout.strip()) if found.returncode == 0 and found.stdout.strip() else None


def compiles(name: str, target: str) -> subprocess.CompletedProcess:
    path = sdk(name)
    return subprocess.run(["xcrun", "--sdk", name, "clang", "-fsyntax-only", "-fobjc-arc", "-isysroot", str(path), "-target", target,
                           "-Werror=implicit-function-declaration", str(ROOT / "ios/launcher/LunarUpscale.m")],
                          capture_output=True, text=True)


class Upscaler(unittest.TestCase):
    @unittest.skipUnless(sdk("iphonesimulator"), "needs Xcode's simulator SDK")
    def test_builds_for_the_simulator(self):
        result = compiles("iphonesimulator", "arm64-apple-ios14.0-simulator")
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(sdk("iphoneos"), "needs Xcode's iPhone SDK")
    def test_builds_for_an_iphone(self):
        result = compiles("iphoneos", "arm64-apple-ios14.0")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_metalfx_is_linked_only_when_the_sdk_has_it(self):
        self.assertNotIn(" -weak_framework MetalFX ", BUILD.replace("$metalfx", ""))
        self.assertIn('[ -d "$sdk/System/Library/Frameworks/MetalFX.framework" ] && metalfx="-weak_framework MetalFX"', BUILD)
        self.assertIn("$metalfx", BUILD)


if __name__ == "__main__":
    unittest.main()
