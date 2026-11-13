#!/usr/bin/env python3
"""Arena battle mods: the settings file and the rules the battle hook applies
each frame (battle_mods_settings.c). Needs a host C compiler (cc)."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest

root = Path(__file__).resolve().parents[2]
SOURCE = root / "android/app/src/main/cpp/battle_mods_settings.c"


def run(body, files=None):
    """Compiles body into main() beside battle_mods_settings.c and returns its output; files are
    written first, into the directory the program runs in."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in (files or {}).items():
            (Path(tmp) / name).write_bytes(text.encode())
        main = Path(tmp) / "main.c"
        main.write_text('#include <stdio.h>\n#include "battle_mods_settings.h"\nint main(void) {\n' + body + "\nreturn 0; }\n")
        exe = Path(tmp) / "mods"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", "-I", str(SOURCE.parent), "-o", str(exe), str(main), str(SOURCE)], check=True)
        out = subprocess.run([str(exe)], check=True, capture_output=True, text=True, cwd=tmp).stdout
        saved = {p.name: p.read_text() for p in Path(tmp).iterdir() if p.suffix == ".conf"}
        return out, saved


PRINT = 'printf("%d %d %d %d", r, m.no_death, m.one_hit, m.zero_cooldown);'


@unittest.skipUnless(shutil.which("cc"), "needs a C compiler")
class Settings(unittest.TestCase):
    def parse(self, text):
        out, _ = run('BattleMods m; battle_mods_parse(%s, &m); int r = 0; %s' % (c_string(text), PRINT))
        return [int(x) for x in out.split()][1:]

    def test_parse(self):
        self.assertEqual(self.parse("no_death=on\none_hit=off\r\nzero_cooldown=on\nfoo=on\n"), [1, 0, 1])
        self.assertEqual(self.parse(""), [0, 0, 0])
        self.assertEqual(self.parse("no_death=ON"), [0, 0, 0])  # the value is exact
        self.assertEqual(self.parse("  one_hit = on  \n\n"), [0, 1, 0])

    def test_round_trip(self):
        out, saved = run('BattleMods s = {1, 1, 0}; int w = battle_mods_save("mods.conf", &s);'
                         'BattleMods m; int r = battle_mods_load("mods.conf", &m); printf("%d ", w); ' + PRINT)
        self.assertEqual(out.split(), ["0", "0", "1", "1", "0"])
        self.assertEqual(saved["mods.conf"], "no_death=on\none_hit=on\nzero_cooldown=off\n")

    def test_missing_or_truncated_file(self):
        out, _ = run('BattleMods m = {1, 1, 1}; int r = battle_mods_load("missing.conf", &m); ' + PRINT)
        self.assertEqual(out.split(), ["-1", "0", "0", "0"])
        out, _ = run('BattleMods m = {1, 1, 1}; int r = battle_mods_load("cut.conf", &m); ' + PRINT, {"cut.conf": "no_dea"})
        self.assertEqual(out.split()[1:], ["0", "0", "0"])

    def test_format_too_small(self):
        out, _ = run('BattleMods s = {0, 0, 0}; char b[8]; printf("%d", battle_mods_format(&s, b, sizeof b));')
        self.assertEqual(out, "-1")


@unittest.skipUnless(shutil.which("cc"), "needs a C compiler")
class Rules(unittest.TestCase):
    def values(self, calls):
        out, _ = run(" ".join('printf("%%d ", %s);' % c for c in calls))
        return [int(x) for x in out.split()]

    def test_hp_rules(self):
        self.assertEqual(self.values([
            "battle_mods_player_max(1, 421632)", "battle_mods_player_max(0, 421632)",
            "battle_mods_player_hp(1, 5, 421632)", "battle_mods_player_hp(0, 1000000000, 421632)",
            "battle_mods_player_hp(0, 300000, 421632)",
            "battle_mods_opponent_hp(1, 291364)", "battle_mods_opponent_hp(1, 0)", "battle_mods_opponent_hp(0, 291364)",
        ]), [1000000000, 421632, 1000000000, 421632, 300000, 1, 0, 291364])

    def test_cooltime_rule(self):
        self.assertEqual(self.values([
            "battle_mods_cooltime(1, 0, 690)", "battle_mods_cooltime(1, 0, 0)", "battle_mods_cooltime(0, 12, 690)",
        ]), [690, 0, 12])

    def test_filler(self):
        self.assertEqual(self.values(["battle_mods_is_filler(1234567890)", "battle_mods_is_filler(421632)"]), [1, 0])


def c_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'


if __name__ == "__main__":
    unittest.main()
