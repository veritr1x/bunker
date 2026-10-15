import subprocess
import tempfile
import unittest
from pathlib import Path

import version as v


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        (self.root / "VERSION").write_text("1.2.3\n")

    def commit(self):
        git(self.root, "init", "-q")
        git(self.root, "add", "VERSION")
        git(self.root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
        return subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "--short=7", "HEAD"], text=True).strip()

    def test_no_git_is_dev(self):
        self.assertEqual(v.version(self.root), "1.2.3+dev")

    def test_untagged_commit(self):
        commit = self.commit()
        self.assertEqual(v.version(self.root), f"1.2.3+dev.{commit}")

    def test_matching_tag_is_release(self):
        self.commit()
        git(self.root, "tag", "v1.2.3")
        self.assertEqual(v.version(self.root), "1.2.3")

    def test_other_tag_is_dev(self):
        self.commit()
        git(self.root, "tag", "v9.9.9")
        self.assertTrue(v.version(self.root).startswith("1.2.3+dev."))

    def test_rejects_malformed_version(self):
        (self.root / "VERSION").write_text("1.2\n")
        with self.assertRaises(ValueError):
            v.version(self.root)

    def test_newer(self):
        self.assertTrue(v.newer("1.0.1", "1.0.0"))
        self.assertTrue(v.newer("1.0.1", "1.0.0+dev.abc1234"))
        self.assertFalse(v.newer("1.0.0", "1.0.0+dev.abc1234"))
        self.assertFalse(v.newer("1.0.0", "1.0.0"))
        self.assertFalse(v.newer("0.9.9", "1.0.0"))
        self.assertTrue(v.newer("1.10.0", "1.9.9"))


if __name__ == "__main__":
    unittest.main()
