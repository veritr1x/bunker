#!/usr/bin/env python3
"""Every Bunker APK, built here or in the web builder, is signed with the one public Bunker key
(web/signing/bunker-key.p12): any build installs over any other and keeps its data, and each can update
itself (Updater.bunkerKey checks for that key)."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/tools"))
sys.path.insert(0, str(root / "scripts"))
import package_game  # noqa: E402


class Signing(unittest.TestCase):
    def test_signs_with_the_public_bunker_key(self):
        args = [str(a) for a in package_game.signing_args(Path("tools"), Path("out.apk"))]
        self.assertEqual(args[:2], [str(Path("tools") / "apksigner"), "sign"])
        self.assertEqual(Path(args[args.index("--ks") + 1]), root / "web/signing/bunker-key.p12")
        self.assertEqual(args[args.index("--ks-key-alias") + 1], "bunker")
        self.assertEqual(args[args.index("--ks-pass") + 1], "pass:bunker")
        self.assertEqual(args[args.index("--key-pass") + 1], "pass:bunker")
        self.assertEqual(args[-1], "out.apk")
        self.assertTrue((root / "web/signing/bunker-key.p12").is_file())

    def test_no_local_key(self):
        source = (root / "android/tools/package_game.py").read_text() + (root / "scripts/build.py").read_text()
        for gone in ("--keystore", "lunar-local", "keytool"):
            self.assertNotIn(gone, source)


if __name__ == "__main__":
    unittest.main()
