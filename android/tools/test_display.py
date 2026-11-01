#!/usr/bin/env python3
"""Pod Programs → Display, and the instructions display_patch.c rewrites.

The settings tests need fastapi (the Android Python requirements) and the
prepared Tools sources (scripts/prepare.py). The binary test runs when
BUNKER_GAME_LIB points at the original 3.7.1 ARM64 libil2cpp.so.
"""
from pathlib import Path
import os, re, struct, subprocess, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))


class Settings(unittest.TestCase):
    def setUp(self):
        import android_display
        self.display = android_display
        self.dir = tempfile.TemporaryDirectory()
        self.conf = Path(self.dir.name) / "display.conf"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_keeps_the_game_defaults(self):
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "default", "screen": "full", "textures": "full", "idle": "on", "heat": "on"})

    def test_saved_choices_are_read_back(self):
        self.display.write_settings("60", "native", "full", self.conf)
        self.assertEqual(self.conf.read_text(), "fps=60\nresolution=native\nscreen=full\ntextures=full\nidle=on\nheat=on\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "60", "resolution": "native", "screen": "full", "textures": "full", "idle": "on", "heat": "on"})
        self.display.write_settings("max", "1440", "safe", self.conf)
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "max", "resolution": "1440", "screen": "safe", "textures": "full", "idle": "on", "heat": "on"})

    def test_lower_resolutions_and_texture_sizes_are_saved(self):
        self.display.write_settings("30", "540", "full", self.conf, textures="quarter")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "540", "screen": "full", "textures": "quarter", "idle": "on", "heat": "on"})
        self.display.write_settings("60", "640", "safe", self.conf, textures="half")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "60", "resolution": "640", "screen": "safe", "textures": "half", "idle": "on", "heat": "on"})
        with self.assertRaises(ValueError):
            self.display.write_settings("30", "default", "full", self.conf, textures="tiny")

    def test_settings_saved_before_the_screen_choice_use_the_full_screen(self):
        self.conf.write_text("fps=60\nresolution=native\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "60", "resolution": "native", "screen": "full", "textures": "full", "idle": "on", "heat": "on"})

    def test_unknown_values_are_refused_and_ignored(self):
        with self.assertRaises(ValueError):
            self.display.write_settings("240", "native", "safe", self.conf)
        with self.assertRaises(ValueError):
            self.display.write_settings("60", "native", "wide", self.conf)
        self.conf.write_text("fps=240\nresolution=8k\nscreen=wide\nnoise\n")
        self.assertEqual(self.display.read_settings(self.conf), {"fps": "30", "resolution": "default", "screen": "full", "textures": "full", "idle": "on", "heat": "on"})

    def test_idle_and_heat_slow_downs_can_be_turned_off(self):
        self.display.write_settings("120", "native", "full", self.conf, idle="off", heat="off")
        self.assertEqual(self.conf.read_text(), "fps=120\nresolution=native\nscreen=full\ntextures=full\nidle=off\nheat=off\n")
        self.assertEqual(self.display.read_settings(self.conf)["idle"], "off")
        self.assertEqual(self.display.read_settings(self.conf)["heat"], "off")
        with self.assertRaises(ValueError):
            self.display.write_settings("120", "native", "full", self.conf, idle="sometimes")


class Encodings(unittest.TestCase):
    def test_highest_preset_immediates(self):
        """orr x11, x11, #(size << 32) for each size display_patch.c can choose."""
        source = (root / "android/app/src/main/cpp/display_patch.c").read_text()
        body = re.search(r"static uint32_t orr_x11_size\(int size\) \{(.*?)\n\}", source, re.S).group(1)
        chosen = {name: int(word, 16) for name, word in re.findall(r"case (\w+): return 0x([0-9a-f]+)u;", body)}
        sizes = {"H540": 3, "H640": 4, "FullHD": 6, "WQHD": 7}
        self.assertEqual(set(chosen), set(sizes))
        for name, word in chosen.items():
            self.assertEqual(word, orr_x11(sizes[name] << 32), name)


def orr_x11(value):
    """The A64 instruction orr x11, x11, #value, for a value that is one run of set bits."""
    ones = bin(value).count("1")
    low = (value & -value).bit_length() - 1
    assert value == ((1 << ones) - 1) << low
    return 0xb2400000 | ((64 - low) % 64) << 16 | (ones - 1) << 10 | 11 << 5 | 11


def patch_sites():
    """(rva, original word) for every site in display_patch.c."""
    source = (root / "android/app/src/main/cpp/display_patch.c").read_text()
    return [(int(rva, 16), int(word, 16)) for rva, word in re.findall(r"\(Site\)\{(0x[0-9A-F]+), (0x[0-9a-f]+)u", source)]


def hook_sites():
    """(rva, four original words) for each hook in display_patch.c."""
    source = (root / "android/app/src/main/cpp/display_patch.c").read_text()
    words = {name: [int(w, 16) for w in re.findall(r"0x([0-9a-f]{8})u", body)]
             for name, body in re.findall(r"static const uint32_t (\w+)\[4\] = \{([^}]*)\}", source)}
    return [(int(rva, 16), words[name]) for rva, name in re.findall(r"\{(0x[0-9A-F]+), (k\w+)\}", source)]


class RenderPace(unittest.TestCase):
    """render_pace.c's choice of how often to draw, built for this computer."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        harness = Path(cls.dir.name) / "harness.c"
        # Reads "fps current delta touching battle thermal idle heat" lines; prints each frame's interval.
        harness.write_text(r"""
#include <stdio.h>
#include "render_pace.h"
int main(void) {
    RenderPace pace = {0};
    int fps, current, touching, battle, thermal, idle, heat; float delta;
    while (scanf("%d %d %f %d %d %d %d %d", &fps, &current, &delta, &touching, &battle, &thermal, &idle, &heat) == 8)
        printf("%d\n", render_pace_decide(&pace, fps, current, delta, touching, battle, thermal, idle, heat)), fflush(stdout);
    return 0;
}
""")
        cls.binary = Path(cls.dir.name) / "harness"
        cpp = root / "android/app/src/main/cpp"
        subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", "-I", str(cpp), "-o", str(cls.binary),
                        str(harness), str(cpp / "render_pace.c")], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def run_frames(self, frames, fps=120, idle=1, heat=1):
        """frames: (current, delta, touching, battle, thermal) per frame; current None follows the last answer."""
        out, last, lines = [], 1, []
        # Each frame's current interval is the one decided the frame before, unless the game sets its own.
        proc = subprocess.Popen([str(self.binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        for current, delta, touching, battle, thermal in frames:
            proc.stdin.write(f"{fps} {last if current is None else current} {delta} {touching} {battle} {thermal} {idle} {heat}\n")
            proc.stdin.flush()
            last = int(proc.stdout.readline())
            out.append(last)
        proc.stdin.close()
        proc.wait()
        return out

    def still(self, seconds, fps=120, **kw):
        return [(None, 1 / fps, 0, 0, 0)] * int(seconds * fps)

    def test_draws_every_frame_while_touched(self):
        self.assertEqual(set(self.run_frames([(None, 1 / 120, 1, 0, 0)] * 600)), {1})

    def test_slows_to_30_a_second_after_two_idle_seconds(self):
        out = self.run_frames(self.still(3))
        self.assertEqual(out[int(1.9 * 120)], 1)
        self.assertEqual(out[-1], 4)  # 120 / 4 = 30 drawn a second

    def test_a_touch_draws_every_frame_again_at_once(self):
        out = self.run_frames(self.still(3) + [(None, 1 / 120, 1, 0, 0)] + self.still(1))
        self.assertEqual(out[360], 1)
        self.assertEqual(out[-1], 1)

    def test_battles_keep_the_chosen_rate(self):
        self.assertEqual(set(self.run_frames([(None, 1 / 120, 0, 1, 0)] * 600)), {1})

    def test_at_60_fps_idle_draws_every_other_frame(self):
        self.assertEqual(self.run_frames(self.still(3, fps=60), fps=60)[-1], 2)

    def test_idle_off_keeps_every_frame(self):
        self.assertEqual(set(self.run_frames(self.still(3), idle=0)), {1})

    def test_power_saving_keeps_the_games_own_slower_rate(self):
        # The game asks for 10 a second (every 12th frame at 120); a touch doesn't speed it up.
        out = self.run_frames([(12, 1 / 120, 1, 0, 0)] + [(None, 1 / 120, 1, 0, 0)] * 10)
        self.assertEqual(set(out), {12})

    def test_a_preset_from_before_the_patch_is_drawn_every_frame(self):
        # The game's own 30 a second at 120 (every 4th) from before the table was changed.
        self.assertEqual(self.run_frames([(4, 1 / 120, 1, 0, 0)])[0], 1)

    def test_serious_heat_draws_60_a_second_and_critical_30(self):
        self.assertEqual(self.run_frames([(None, 1 / 120, 1, 0, 2)])[0], 2)
        self.assertEqual(self.run_frames([(None, 1 / 120, 1, 1, 3)])[0], 4)

    def test_heat_off_keeps_the_chosen_rate(self):
        self.assertEqual(self.run_frames([(None, 1 / 120, 1, 0, 3)], heat=0)[0], 1)

    def test_heat_does_not_slow_a_rate_already_low_enough(self):
        self.assertEqual(self.run_frames([(None, 1 / 60, 1, 0, 2)], fps=60)[0], 1)


class FlyingMom(unittest.TestCase):
    """flying_mom.c's step clock and internal-call decoding, built for this computer."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        harness = Path(cls.dir.name) / "harness.c"
        harness.write_text(r"""
#include <stdio.h>
#include <stdlib.h>
#include "flying_mom.h"
// clock FRAMES DELTA TOUCHES...: one line per frame, "step time" or "-".
int main(int argc, char **argv) {
    if (argv[1][0] == 's') {
        uint32_t code[16]; int n = 0;
        for (int i = 3; i < argc; i++) code[n++] = (uint32_t)strtoul(argv[i], 0, 16);
        printf("%lx\n", (unsigned long)flying_mom_icall_slot(code, strtoul(argv[2], 0, 16)));
        return 0;
    }
    FlyingMomClock clock = {0};
    int frames = atoi(argv[2]);
    for (int f = 0; f < frames; f++) {
        float delta = (float)atof(argv[3]);
        int touch = 0;
        for (int i = 4; i < argc; i++) if (atoi(argv[i]) == f) touch = 1;
        if (flying_mom_clock_tick(&clock, delta, delta, touch)) printf("step %.6f\n", clock.step_time);
        else printf("-\n");
    }
    return 0;
}
""")
        cls.binary = Path(cls.dir.name) / "harness"
        cpp = root / "android/app/src/main/cpp"
        subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", "-I", str(cpp), "-o", str(cls.binary), str(harness),
                        str(cpp / "flying_mom.c")], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def frames(self, count, delta, touches=()):
        out = subprocess.run([str(self.binary), "clock", str(count), str(delta), *map(str, touches)],
                             check=True, capture_output=True, text=True).stdout.split("\n")[:count]
        return [None if line == "-" else float(line.split()[1]) for line in out]

    def test_at_30_fps_or_slower_every_frame_is_a_step(self):
        for delta in (1 / 30, 1 / 20):
            steps = self.frames(10, delta)
            self.assertTrue(all(s is not None for s in steps))
            self.assertAlmostEqual(steps[5], delta, places=5)

    def test_at_60_fps_every_other_frame_is_a_step_of_two_frames(self):
        steps = self.frames(12, 1 / 60)
        self.assertEqual([s is not None for s in steps], [True, False] * 6)
        self.assertAlmostEqual(steps[2], 2 / 60, places=5)

    def test_at_120_fps_every_fourth_frame_is_a_step(self):
        steps = self.frames(16, 1 / 120)
        self.assertEqual([s is not None for s in steps], [True, False, False, False] * 4)
        self.assertAlmostEqual(steps[4], 4 / 120, places=5)

    def test_a_display_a_little_over_60_hz_still_steps_every_other_frame(self):
        # 60.000004 Hz (the emulator's display): each frame is a hair under 1/60 s.
        steps = self.frames(600, 1 / 60.000004)
        self.assertEqual(sum(s is not None for s in steps), 300)
        self.assertEqual([s is not None for s in steps[-6:]], [True, False] * 3)

    def test_a_touch_on_an_in_between_frame_runs_a_step_then_keeps_30_a_second(self):
        steps = self.frames(60, 1 / 60, touches=[3, 21, 40])
        self.assertIsNotNone(steps[3])      # the tap's own frame, so its "began" isn't missed
        self.assertAlmostEqual(steps[3], 1 / 60, places=5)
        self.assertEqual(sum(s is not None for s in steps), 30)

    def test_the_time_of_every_step_adds_up_to_the_time_played(self):
        steps = self.frames(240, 1 / 120, touches=[5, 6, 50, 51, 52, 130])
        # All but the frames after the last step, which the next step covers.
        self.assertLessEqual(abs(sum(s for s in steps if s is not None) - 240 / 120), 1 / 30 + 1e-6)

    def slot(self, address, words):
        out = subprocess.run([str(self.binary), "slot", hex(address), *(hex(w) for w in words)],
                             check=True, capture_output=True, text=True).stdout
        return int(out, 16)

    def test_the_cached_pointer_of_time_get_delta_time_is_found(self):
        # 3.7.1 ARM64 Time.get_deltaTime at 0x4d7ecf4: "adrp x19, 0x79a0000; ldr x0, [x19, #0xc78]".
        words = [0xf81e0ff3, 0xa9017bfd, 0x910043fd, 0xd0016113, 0xf9463e60, 0xb50000a0]
        self.assertEqual(self.slot(0x4d7ecf4, words), 0x79a0c78)

    def test_code_that_is_not_an_internal_call_wrapper_gives_nothing(self):
        # Flying Mama's OnUpdateFreeFall: the adrp is followed by ldrb, not a pointer load.
        words = [0xfc1c0fea, 0x6d0123e9, 0xa9024ff4, 0xa9037bfd, 0x9100c3fd, 0xf0028354, 0x396d7288, 0xaa0003f3]
        self.assertEqual(self.slot(0x291d5c4, words), 0)


@unittest.skipUnless(os.environ.get("BUNKER_GAME_LIB"), "set BUNKER_GAME_LIB to the original 3.7.1 libil2cpp.so")
class GameBinary(unittest.TestCase):
    def test_every_site_holds_the_expected_instruction(self):
        data = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        sites = patch_sites()
        self.assertEqual(len(sites), 6)
        for rva, original in sites:
            # The library's first segment maps at address 0 with file offset 0.
            self.assertEqual(struct.unpack_from("<I", data, rva)[0], original, hex(rva))

    def test_every_hook_finds_its_original_instructions(self):
        data = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        hooks = hook_sites()
        self.assertEqual(len(hooks), 4)
        for rva, original in hooks:
            self.assertEqual(list(struct.unpack_from("<4I", data, rva)), original, hex(rva))

    def test_event_zone_methods_are_where_the_patch_calls_them(self):
        data = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        prologue = [0xf81d0ff5, 0xa9014ff4, 0xa9027bfd, 0x910083fd]
        # EventTriggerOnStayCollision.OnStateBegin and OnStay.
        for rva in (0x2984210, 0x2984420):
            self.assertEqual(list(struct.unpack_from("<4I", data, rva)), prologue, hex(rva))
        # StateConductor.OnStateUpdate, the empty virtual the patch replaces: "ret".
        self.assertEqual(struct.unpack_from("<I", data, 0x3A05C64)[0], 0xd65f03c0)


if __name__ == "__main__":
    unittest.main()
