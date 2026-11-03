import ast
import unittest
import json
from pathlib import Path
import tempfile
import zipfile

import build_site


def added_paths(source):
    """Folders a file puts on sys.path as Path(__file__).resolve().parents[N] / "name"."""
    folders = []
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and isinstance(node.right, ast.Constant) \
                and isinstance(node.left, ast.Subscript) and isinstance(node.left.value, ast.Attribute) \
                and node.left.value.attr == "parents" and isinstance(node.left.slice, ast.Constant):
            folders.append(source.resolve().parents[node.left.slice.value] / node.right.value)
    return [f for f in folders if f.is_dir()]


class SiteFilesTest(unittest.TestCase):
    def test_notice_parts_preserve_the_archive_and_fit_the_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("notices/notices.json", b"[]" * 100)
            for limit in (64, source.stat().st_size):
                out = Path(tmp) / str(limit)
                build_site.notice_bundle(source, out, part_size=limit)
                manifest = json.loads((out / "notices.json").read_text())
                chunks = [(out / name).read_bytes() for name in manifest["parts"]]
                self.assertTrue(all(len(chunk) <= limit for chunk in chunks))
                self.assertEqual(b"".join(chunks), source.read_bytes())
                self.assertEqual(manifest["size"], source.stat().st_size)
                if limit == source.stat().st_size:
                    self.assertEqual(manifest["parts"], ["notices.zip"])

    def test_split_notices_cannot_publish_master_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("private/master.bin.e", b"private")
            with self.assertRaisesRegex(SystemExit, "master data"):
                build_site.notice_bundle(source, Path(tmp) / "out", part_size=16)

    def test_every_local_import_is_published(self):
        published = {path for path in build_site.PYTHON if path.endswith(".py")}
        missing = []
        for path in sorted(published):
            folders = [(build_site.ROOT / path).parent] + added_paths(build_site.ROOT / path)
            for node in ast.walk(ast.parse((build_site.ROOT / path).read_text())):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    module = next((f / (name.split(".")[0] + ".py") for f in folders if (f / (name.split(".")[0] + ".py")).exists()), None)
                    if module:
                        relative = module.relative_to(build_site.ROOT).as_posix()
                        if relative not in published:
                            missing.append(f"{path} imports {relative}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
