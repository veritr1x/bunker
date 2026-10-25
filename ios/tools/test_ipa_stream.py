"""The streaming IPA writer the browser build uses, on small generated archives."""
from pathlib import Path
import os
import plistlib
import tempfile
import unittest
import zipfile

import ipa_stream

APP = "Payload/Game.app/"


class Sink:
    """Accepts writes only: the browser hands the IPA to the page as it is written."""

    def __init__(self):
        self.parts = []

    def write(self, data):
        self.parts.append(bytes(data))
        return len(data)

    def bytes(self):
        return b"".join(self.parts)


def entry(archive, name, data, mode=0o100644, method=zipfile.ZIP_DEFLATED):
    info = zipfile.ZipInfo(name, (2024, 4, 4, 9, 43, 0))
    info.external_attr = mode << 16
    info.compress_type = method
    archive.writestr(info, data)


class StreamTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "game.ipa"
        info = plistlib.dumps({"CFBundleExecutable": "Game", "CFBundleIdentifier": "game"})
        with zipfile.ZipFile(self.source, "w") as z:
            z.writestr(zipfile.ZipInfo(APP), b"")  # a folder entry
            entry(z, APP + "Info.plist", info)
            entry(z, APP + "Game", b"\xcf\xfa\xed\xfe executable", 0o100755)
            entry(z, APP + "Data/level.bin", os.urandom(5000), method=zipfile.ZIP_STORED)
            entry(z, APP + "Data/globalgamemanagers", b"settings")
            entry(z, APP + "Frameworks/UnityFramework.framework/UnityFramework", b"unity" * 1000)
            entry(z, APP + "Frameworks/Other.framework/_CodeSignature/CodeResources", b"kept")
            entry(z, APP + "SC_Info/Game.sinf", b"store encryption")
            entry(z, APP + "_CodeSignature/CodeResources", b"publisher signature")
            entry(z, APP + "embedded.mobileprovision", b"publisher profile")

    def test_extracts_only_the_files_the_patches_change(self):
        dest = self.root / "edit"
        ipa_stream.extract_for_patching(self.source, dest)
        found = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())
        self.assertEqual(found, sorted(APP + n for n in (
            "Info.plist", "Game", "Data/globalgamemanagers", "Frameworks/UnityFramework.framework/UnityFramework")))
        self.assertEqual((dest / APP / "Game").stat().st_mode & 0o777, 0o755)

    def test_writes_edited_files_new_files_and_copies_the_rest(self):
        edit = self.root / "edit"
        ipa_stream.extract_for_patching(self.source, edit)
        (edit / APP / "Data/globalgamemanagers").write_bytes(b"settings, analytics off")
        added = edit / APP / "Frameworks/LunarTear.framework/LunarTear"
        added.parent.mkdir(parents=True)
        added.write_bytes(b"launcher" * 3000)
        added.chmod(0o755)
        (edit / APP / "notices.zip").write_bytes(b"notices")
        sink = Sink()
        ipa_stream.write_ipa(self.source, edit, sink)
        output = self.root / "out.ipa"
        output.write_bytes(sink.bytes())
        with zipfile.ZipFile(self.source) as before, zipfile.ZipFile(output) as after:
            self.assertIsNone(after.testzip())
            names = set(after.namelist())
            self.assertEqual(names, {
                APP + n for n in ("Info.plist", "Game", "Data/level.bin", "Data/globalgamemanagers",
                                  "Frameworks/UnityFramework.framework/UnityFramework",
                                  "Frameworks/Other.framework/_CodeSignature/CodeResources",
                                  "Frameworks/LunarTear.framework/LunarTear", "notices.zip")})
            self.assertEqual(after.read(APP + "Data/globalgamemanagers"), b"settings, analytics off")
            self.assertEqual(after.read(APP + "Frameworks/LunarTear.framework/LunarTear"), b"launcher" * 3000)
            for unchanged in ("Data/level.bin", "Frameworks/Other.framework/_CodeSignature/CodeResources", "Game"):
                self.assertEqual(after.read(APP + unchanged), before.read(APP + unchanged))
            # Unchanged entries keep their compression; the executable keeps its mode.
            self.assertEqual(after.getinfo(APP + "Data/level.bin").compress_type, zipfile.ZIP_STORED)
            self.assertEqual(after.getinfo(APP + "Game").external_attr >> 16, 0o100755)
            self.assertEqual(after.getinfo(APP + "Frameworks/LunarTear.framework/LunarTear").external_attr >> 16, 0o100755)

    def test_an_ipa_without_one_app_is_refused(self):
        with zipfile.ZipFile(self.source, "w") as z:
            entry(z, "Payload/A.app/Info.plist", b"")
            entry(z, "Payload/B.app/Info.plist", b"")
        with self.assertRaises(RuntimeError):
            ipa_stream.extract_for_patching(self.source, self.root / "edit")


if __name__ == "__main__":
    unittest.main()
