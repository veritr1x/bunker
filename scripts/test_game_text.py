import os
import tempfile
import unittest
from pathlib import Path

from game_text import BundleError, Text, area_of, bundle_rank, read_language

ROOT = Path(__file__).resolve().parents[1]
DUMP = Path(os.environ.get("BUNKER_DUMP", ROOT / "client/android-dump/revisions/0"))


class FakeTree:
    """An assetbundle folder of empty bundle files, read by a fake reader from a dict of texts."""

    def __init__(self, texts: dict[str, str]):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.texts = texts
        for rel in texts:
            path = self.root / (rel + ".assetbundle")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def read(self, path: Path, assetbundle_root: Path) -> list[tuple[str, str]]:
        rel = path.relative_to(assetbundle_root).with_suffix("").as_posix()
        return [("asset", self.texts[rel])]


class AreaTest(unittest.TestCase):
    def test_area_of(self):
        self.assertEqual(area_of("ui"), "ui")
        self.assertEqual(area_of("skill/skill_0090150"), "skill")
        self.assertEqual(area_of("gacha_title/gacha_title_0100150"), "shop")
        self.assertEqual(area_of("main/0001/scene"), "story_main")
        self.assertEqual(area_of("navigation_cut_in"), "ui")

    def test_bundle_rank(self):
        self.assertEqual(bundle_rank("ability/ability_0090150"), 90150)
        self.assertEqual(bundle_rank("ability"), -1)


class ReadLanguageTest(unittest.TestCase):
    def read(self, texts, lang="en"):
        tree = FakeTree(texts)
        self.addCleanup(tree.dir.cleanup)
        return read_language(tree.root, lang, read=tree.read)

    def test_highest_numbered_bundle_wins(self):
        texts = self.read({
            "text/en/ability": "k:old",
            "text/en/ability/ability_0070250": "k:new",
            "text/en/ability/ability_0010000": "k:older",
        })
        self.assertEqual(texts["k"], Text("new", "ability/ability_0070250"))

    def test_value_keeps_colons_and_comments_are_skipped(self):
        texts = self.read({"text/en/ui": "// note\nk:a:b\n"})
        self.assertEqual(texts["k"].value, "a:b")
        self.assertEqual(set(texts), {"k"})

    def test_unreadable_bundle_names_it(self):
        tree = FakeTree({"text/en/gift": "k:v"})
        self.addCleanup(tree.dir.cleanup)

        def bad(path, root):
            raise ValueError("corrupt")

        with self.assertRaisesRegex(BundleError, "text/en/gift"):
            read_language(tree.root, "en", read=bad)

    def test_only_the_requested_language(self):
        texts = self.read({"text/en/ui": "a:A", "text/ja/ui": "a:エー\nb:ビー"})
        self.assertEqual(texts, {"a": Text("A", "ui")})


@unittest.skipUnless(DUMP.is_dir(), "Requires the game dump (set BUNKER_DUMP to its revisions/0 folder).")
class RealDumpTest(unittest.TestCase):
    def test_real_dump(self):
        en = read_language(DUMP / "assetbundle", "en")
        self.assertEqual(len(en), 143565)
        self.assertEqual(en["gift.comment.3"].value, "Sent by administration.")
        self.assertEqual(en["ability.description.long.1002056"].bundle, "ability/ability_0070250")


if __name__ == "__main__":
    unittest.main()
