#!/usr/bin/env python3
"""The Android launcher's words (Texts.java): the English catalogue packed into the APK, the pack Pod Programs
activated, plural rules and numbers from the device's CLDR data; never the phone's own language."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / "android/app/src/main/java/org/veritr1x/bunker"
GRADLE = (ROOT / "android/app/build.gradle").read_text()


def source(name: str) -> str:
    return (JAVA / name).read_text()


class Catalogue(unittest.TestCase):
    def test_the_apk_carries_the_english_catalogue(self):
        self.assertIn("translations/bunker/en.json", GRADLE)
        self.assertRegex(GRADLE, r"rename[^\n]*bunker_en\.json|into[^\n]*\n[^\n]*bunker_en\.json|bunker_en\.json")
        self.assertRegex(GRADLE, r"assets\.srcDir")
        self.assertRegex(GRADLE, r"preBuild\.dependsOn")
        self.assertIn('open("bunker_en.json")', source("Texts.java"))


class Pack(unittest.TestCase):
    def test_reads_the_pack_pod_programs_activated(self):
        # android_archive.active_pack(asset_root) and bunker_language: <server root>/translation/active.json
        text = source("Texts.java")
        self.assertIn("FilesStore.root(", text)
        self.assertIn('"translation/active.json"', text)

    def test_a_pack_is_read_only_when_small(self):
        self.assertRegex(source("Texts.java"), r"MAX_PACK\s*=\s*8\s*\*\s*1024\s*\*\s*1024")

    def test_the_phones_language_is_never_used(self):
        text = source("Texts.java")
        for phone in ("Locale.getDefault", "getConfiguration", "getLocales", "ULocale.getDefault"):
            self.assertNotIn(phone, text)

    def test_rules_come_from_cldr(self):
        text = source("Texts.java")
        self.assertIn("android.icu.text.PluralRules", text)
        # the categories used for whole numbers only, found as bunker_plurals.categories finds them
        self.assertRegex(text, r"for \(long n\s*=\s*0;\s*n\s*<\s*1200;\s*n\+\+\)")
        self.assertIn("android.icu.text.NumberFormat", text)
        self.assertIn("@numbers=latn", text)
        self.assertIn("new BunkerText(", text)

    def test_capitals_follow_the_packs_language(self):
        self.assertRegex(source("Texts.java"), r"toUpperCase\(\s*locale")


if __name__ == "__main__":
    unittest.main()
