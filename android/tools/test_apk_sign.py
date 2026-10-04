#!/usr/bin/env python3
"""apk_sign.py must produce APKs that apksigner accepts.

  test_apk_sign.py [--apk ANY.apk]

Rebuilds the given APK (default: the launcher's debug build) without its
signature, signs it with the public Bunker key and verifies it with apksigner
from the Android SDK. Needs pycryptodome.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apk_sign  # noqa: E402
from assemble_apk import ApkWriter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SDK = Path(os.environ.get("ANDROID_HOME", Path.home() / "Library/Android/sdk"))
APKSIGNER = SDK / "build-tools/36.0.0/apksigner"
SOURCE = ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"


def unsigned_copy(source, target):
    with zipfile.ZipFile(source) as apk, open(source, "rb") as raw, open(target, "wb") as out:
        writer = ApkWriter(out)
        for info in apk.infolist():
            if not re.search(r"^META-INF/.*\.(SF|RSA|DSA|EC|MF)$", info.filename):
                writer.copy(raw, info)
        writer.close()


class SignTest(unittest.TestCase):
    def test_signed_apk_verifies_with_bunker_key(self):
        with tempfile.TemporaryDirectory() as work:
            apk = Path(work) / "test.apk"
            unsigned_copy(SOURCE, apk)
            self.assertNotEqual(self.verify(apk).returncode, 0)
            digest = apk_sign.sign(apk)
            result = self.verify(apk)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("Verified using v2 scheme (APK Signature Scheme v2): true", result.stdout)
            self.assertIn(digest, result.stdout)
            with zipfile.ZipFile(apk) as signed:
                self.assertIsNone(signed.testzip())

    def test_refuses_to_sign_twice(self):
        with tempfile.TemporaryDirectory() as work:
            apk = Path(work) / "test.apk"
            unsigned_copy(SOURCE, apk)
            apk_sign.sign(apk)
            with self.assertRaisesRegex(RuntimeError, "already signed"):
                apk_sign.sign(apk)

    def verify(self, apk):
        return subprocess.run([str(APKSIGNER), "verify", "-v", "--print-certs", str(apk)],
                              capture_output=True, text=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apk", type=Path, default=SOURCE)
    args, rest = parser.parse_known_args()
    SOURCE = args.apk.resolve(strict=True)
    if not APKSIGNER.exists():
        sys.exit(f"Missing {APKSIGNER}")
    unittest.main(argv=[sys.argv[0]] + rest)
