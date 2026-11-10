"""build.py picks a JDK the Android build works with (17 to 21): newer ones break it (AGP's jlink step fails)."""
import unittest
from pathlib import Path

from build import SUPPORTED_JDKS, choose_jdk, java_major


class JavaVersion(unittest.TestCase):
    def test_reads_the_major_version(self):
        self.assertEqual(java_major('openjdk version "26.0.1" 2026-04-21\nOpenJDK Runtime Environment Homebrew'), 26)
        self.assertEqual(java_major('openjdk version "21.0.5" 2024-10-15 LTS'), 21)
        self.assertEqual(java_major('java version "17" 2021-09-14 LTS'), 17)
        self.assertEqual(java_major('java version "1.8.0_392"'), 8)

    def test_unreadable(self):
        self.assertIsNone(java_major(""))
        self.assertIsNone(java_major("command not found"))


class ChooseJdk(unittest.TestCase):
    def test_a_supported_java_is_kept(self):
        for major in SUPPORTED_JDKS:
            self.assertIsNone(choose_jdk(major, [(Path("/jdk21"), 21)]))

    def test_a_newer_java_is_replaced_by_21(self):
        self.assertEqual(choose_jdk(26, [(Path("/jdk17"), 17), (Path("/jdk26"), 26), (Path("/jdk21"), 21)]), Path("/jdk21"))

    def test_17_when_there_is_no_21(self):
        self.assertEqual(choose_jdk(26, [(Path("/jdk26"), 26), (Path("/jdk17"), 17)]), Path("/jdk17"))

    def test_no_java_at_all(self):
        self.assertEqual(choose_jdk(None, [(Path("/jdk21"), 21)]), Path("/jdk21"))

    def test_nothing_suitable(self):
        with self.assertRaises(LookupError):
            choose_jdk(26, [(Path("/jdk25"), 25), (Path("/jdk11"), 11)])


if __name__ == "__main__":
    unittest.main()
