"""build.py runs Gradle with any JDK 17 or newer (Java itself is compiled with a JDK 21 toolchain, android/app/build.gradle);
an older or missing java is replaced by an installed JDK 21 (or 17), or the build stops saying what to install."""
import unittest
from pathlib import Path

from build import choose_jdk, java_major


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
    def test_17_and_newer_are_kept(self):
        for major in (17, 21, 25, 26, 30):
            self.assertIsNone(choose_jdk(major, [(Path("/jdk21"), 21)]))

    def test_an_older_java_is_replaced_by_21(self):
        self.assertEqual(choose_jdk(11, [(Path("/jdk17"), 17), (Path("/jdk8"), 8), (Path("/jdk21"), 21)]), Path("/jdk21"))

    def test_otherwise_the_newest_installed(self):
        self.assertEqual(choose_jdk(8, [(Path("/jdk17"), 17), (Path("/jdk26"), 26)]), Path("/jdk26"))

    def test_no_java_at_all(self):
        self.assertEqual(choose_jdk(None, [(Path("/jdk21"), 21)]), Path("/jdk21"))

    def test_nothing_suitable(self):
        with self.assertRaises(LookupError):
            choose_jdk(11, [(Path("/jdk11"), 11), (Path("/jdk8"), 8)])


if __name__ == "__main__":
    unittest.main()
