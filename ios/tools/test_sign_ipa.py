"""sign_ipa on a tiny IPA; codesign itself is replaced, so no certificate is needed."""
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock
import zipfile

import sign_ipa

APP = "Payload/NieR.app/"


class SignTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.ipa = self.root / "bunker.ipa"
        info = {"CFBundleIdentifier": "com.square-enix.NieRSPww", "CFBundleExecutable": "NieR", "LunarPortOffset": 30000}
        with zipfile.ZipFile(self.ipa, "w") as z:
            for name, data, mode in ((APP + "Info.plist", plistlib.dumps(info), 0o100644),
                                     (APP + "NieR", b"executable", 0o100755),
                                     (APP + "Data/level.bin", b"data", 0o100644)):
                entry = zipfile.ZipInfo(name)
                entry.external_attr = mode << 16
                z.writestr(entry, data)
        self.signed = []
        self.enterContext(mock.patch.object(sign_ipa, "sign", lambda app, identity, profile, work:
                                            self.signed.append((app.name, identity, Path(profile).name))))

    def run_tool(self, *extra):
        sign_ipa.main(["--sign-identity", "Apple Development: Me (TEAM)", "--profile", str(self.root / "team.mobileprovision"),
                       *extra, str(self.ipa)])

    def info(self, path):
        archive = self.enterContext(zipfile.ZipFile(path))
        return plistlib.loads(archive.read(APP + "Info.plist")), archive

    def test_signs_with_a_new_bundle_id_and_keeps_everything_else(self):
        self.run_tool("--bundle-id", "org.example.nier", "--output", str(self.root / "out.ipa"))
        self.assertEqual(self.signed, [("NieR.app", "Apple Development: Me (TEAM)", "team.mobileprovision")])
        info, archive = self.info(self.root / "out.ipa")
        self.assertEqual(info["CFBundleIdentifier"], "org.example.nier")
        self.assertEqual(info["LunarPortOffset"], 30000)  # The builder's settings stay.
        self.assertEqual(archive.getinfo(APP + "NieR").external_attr >> 16 & 0o777, 0o755)
        self.assertEqual(archive.read(APP + "Data/level.bin"), b"data")

    def test_keeps_the_bundle_id_and_names_the_output_after_the_input(self):
        self.run_tool()
        info, _ = self.info(self.root / "bunker-signed.ipa")
        self.assertEqual(info["CFBundleIdentifier"], "com.square-enix.NieRSPww")

    def test_needs_an_identity_and_a_profile(self):
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            sign_ipa.main([str(self.ipa)])


if __name__ == "__main__":
    unittest.main()
