#!/usr/bin/env python3
"""The Arena season dates the game is given for the season turns
(arena_season.c): the same seasons, in the same order, on the same weekly
resets as the server (overlays/server/internal/pvp/catalog.go, Season and
TestSeasonRotation). Needs a host C compiler (cc)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil, subprocess, tempfile, unittest

root = Path(__file__).resolve().parents[2]
SOURCE = root / "android/app/src/main/cpp/arena_season.c"
DAY, WEEK = 24 * 3600 * 1000, 7 * 24 * 3600 * 1000
FAR = int(datetime(2099, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
GMT8 = timezone(timedelta(hours=-8))


def monday_at(y, m, d):
    """Monday 00:00 GMT-8 of the week holding the UTC date (gametime.WeeklyVersion)."""
    t = datetime(y, m, d, 12, tzinfo=timezone.utc).astimezone(GMT8)
    monday = datetime(t.year, t.month, t.day, tzinfo=GMT8) - timedelta(days=t.weekday())
    return int(monday.timestamp() * 1000)


def season(id, start, end, rank_group, invalid=0):
    return (id, start, end, 2, rank_group, 1, invalid)


@unittest.skipUnless(shutil.which("cc"), "needs a C compiler")
class Turns(unittest.TestCase):
    def turns(self, rows, now):
        """The dates each row gets at now, and how many changed."""
        table = ",".join("{%d,%dLL,%dLL,%d,%d,%d,%d}" % r for r in rows)
        body = f"""
            ArenaSeasonRow rows[] = {{{table}}};
            int64_t start[{len(rows)}], end[{len(rows)}];
            printf("%d", arena_season_turns(rows, {len(rows)}, {now}LL, start, end));
            for (int i = 0; i < {len(rows)}; i++) printf(" %lld %lld", (long long)start[i], (long long)end[i]);
        """
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "main.c"
            main.write_text('#include <stdio.h>\n#include "arena_season.h"\nint main(void) {\n' + body + "\nreturn 0; }\n")
            exe = Path(tmp) / "turns"
            subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", "-I", str(SOURCE.parent), "-o", str(exe), str(main), str(SOURCE)], check=True)
            out = [int(x) for x in subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.split()]
        return out[0], [(out[1 + 2 * i], out[2 + 2 * i]) for i in range(len(rows))]

    def in_force(self, rows, now):
        changed, dates = self.turns(rows, now)
        ids = [r[0] for r, (s, e) in zip(rows, dates) if (s, e) != (r[1], r[2]) and s <= now < e]
        return changed, dates, ids

    def test_same_turns_as_the_server(self):
        s1, s2, s3 = monday_at(2023, 8, 7), monday_at(2023, 9, 4), monday_at(2024, 2, 19)
        rows = [season(1, monday_at(2022, 1, 3), FAR, 2),  # other reward tables: never in turn
                season(2, s1, FAR, 4), season(3, s2, FAR, 4), season(4, s3, FAR, 4),
                season(5, s3, FAR, 4, invalid=1), season(6, FAR, FAR + 30 * DAY, 4)]  # invalid, not started
        # TestSeasonRotation's times and seasons.
        for at, want in [(s3 + DAY, 4), (s3 + 4 * WEEK - 1, 4), (s3 + 4 * WEEK, 2), (s3 + 8 * WEEK + 3 * DAY, 3),
                         (s3 + 12 * WEEK, 4), (s3 + 16 * WEEK, 2)]:
            changed, dates, ids = self.in_force(rows, at)
            self.assertEqual(changed, 3, at)
            self.assertEqual(ids, [want], at)
            for i in (0, 4, 5):  # left as they were
                self.assertEqual(dates[i], rows[i][1:3])
            for start, end in dates[1:4]:
                self.assertEqual(end - start, 4 * WEEK)
                self.assertEqual((start - s3) % WEEK, 0)  # on a weekly reset

    def test_ended_turns_are_in_the_past_and_unplayed_ones_ahead(self):
        s1, s2, s3 = monday_at(2023, 8, 7), monday_at(2023, 9, 4), monday_at(2024, 2, 19)
        rows = [season(2, s1, FAR, 4), season(3, s2, FAR, 4), season(4, s3, FAR, 4)]
        _, dates = self.turns(rows, s3 + 5 * WEEK)  # season 2's turn; 4's has ended, 3's is next
        self.assertEqual(dates[2], (s3, s3 + 4 * WEEK))
        self.assertEqual(dates[0], (s3 + 4 * WEEK, s3 + 8 * WEEK))
        self.assertEqual(dates[1], (s3 + 8 * WEEK, s3 + 12 * WEEK))
        _, dates = self.turns(rows, s3 + 9 * WEEK)  # now 3's: 2's ended, 4's last turn stays past
        self.assertEqual(dates[1], (s3 + 8 * WEEK, s3 + 12 * WEEK))
        self.assertEqual(dates[0], (s3 + 4 * WEEK, s3 + 8 * WEEK))
        self.assertEqual(dates[2], (s3, s3 + 4 * WEEK))

    def test_the_games_own_dates_are_left_alone(self):
        # The Original calendar, at any speed: seasons follow each other.
        a, b = monday_at(2023, 8, 7), monday_at(2023, 8, 28)
        rows = [season(1, a, b, 4), season(2, b, b + 21 * DAY, 4)]
        for at in (a + DAY, b + DAY, b + 22 * DAY, a - WEEK):
            changed, dates = self.turns(rows, at)
            self.assertEqual(changed, 0, at)
            self.assertEqual(dates, [r[1:3] for r in rows])


if __name__ == "__main__":
    unittest.main()
