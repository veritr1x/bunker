"""Asset-copy checks using tiny synthetic files, without private game inputs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prepare_assets import prepare_assets


class PrepareAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "dump/assets"
        self.revision = self.source / "revisions/0"
        self.revision.mkdir(parents=True)
        (self.revision / "list.bin").write_bytes(b"catalog")
        (self.revision / "sample.assetbundle").write_bytes(b"resource")
        (self.revision / "info.json").write_text('[{"to-revision":0}]')
        self.output = self.root / "phone/assets"

    def test_copies_revision_zero_without_changing_source(self):
        before = {p.relative_to(self.source): p.read_bytes()
                  for p in self.source.rglob("*") if p.is_file()}
        prepare_assets(self.source.parent, self.output)
        self.assertTrue((self.output / ".nomedia").is_file())
        for name, content in before.items():
            self.assertEqual((self.source / name).read_bytes(), content)
            self.assertEqual((self.output / name).read_bytes(), content)

    def test_preserves_existing_output(self):
        self.output.mkdir(parents=True)
        marker = self.output / "keep"
        marker.write_text("existing")
        with self.assertRaises(FileExistsError):
            prepare_assets(self.source, self.output)
        self.assertEqual(marker.read_text(), "existing")
        self.assertFalse((self.output / "revisions").exists())

    def test_rejects_cross_revision_dump(self):
        (self.revision / "info.json").write_text('[{"to-revision":12}]')
        with self.assertRaisesRegex(ValueError, "another revision"):
            prepare_assets(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_output_inside_source(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            prepare_assets(self.source, self.source / "phone")
        self.assertFalse((self.source / "phone").exists())

    def test_failed_copy_does_not_leave_partial_output(self):
        with patch("prepare_assets.shutil.copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                prepare_assets(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob(".assets-*")), [])


if __name__ == "__main__":
    unittest.main()
