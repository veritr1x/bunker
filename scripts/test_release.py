import unittest

import release as r

CHANGELOG = """# Changelog

## 1.10.5 (2026-11-10)

Summary.

## 2026-11-10 (after 1.10.4)

### iPhone and iPad
- A change.

## 1.10.4 (2026-11-09)

Older.
"""


class ReleaseChecks(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(r.parse("1.10.5"), (1, 10, 5))
        self.assertGreater(r.parse("1.10.10"), r.parse("1.10.9"))
        for bad in ("1.10", "v1.10.5", "1.10.5+dev", ""):
            with self.assertRaises(r.ReleaseError):
                r.parse(bad)

    def test_changed_files_keep_the_first_letter(self):
        # A status line starts with a space (" M"); trimmed, the first path lost its first letter.
        self.assertEqual(r.changed_files(" M CHANGELOG.md\n M README.md\nM  VERSION"), {"CHANGELOG.md", "README.md", "VERSION"})

    def test_a_changelog_with_todays_section_passes(self):
        r.check_changelog(CHANGELOG, "1.10.5", today="2026-11-10")

    def test_a_missing_section_is_refused(self):
        with self.assertRaisesRegex(r.ReleaseError, "no section for 1.10.6"):
            r.check_changelog(CHANGELOG, "1.10.6", today="2026-11-10")

    def test_a_section_dated_another_day_is_refused(self):
        with self.assertRaisesRegex(r.ReleaseError, "not today"):
            r.check_changelog(CHANGELOG, "1.10.5", today="2026-11-11")

    def test_an_older_section_is_refused(self):
        with self.assertRaisesRegex(r.ReleaseError, "not the newest"):
            r.check_changelog(CHANGELOG, "1.10.4", today="2026-11-09")


if __name__ == "__main__":
    unittest.main()
