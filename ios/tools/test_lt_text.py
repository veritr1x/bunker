#!/usr/bin/env python3
"""The iOS launcher's words (LTText.m, LTPlurals.c) do what bunker_text.py and BunkerText.java do: the shared
cases (android/tools/bunker_text_cases.json), Python's plural rules for every language, Python's numbers, the
Said references and sizes. Compiled for macOS with clang and Foundation; skipped elsewhere."""
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
import bunker_numbers  # noqa: E402
import bunker_plurals  # noqa: E402

LAUNCHER = ROOT / "ios/launcher"
CASES = json.loads((ROOT / "android/tools/bunker_text_cases.json").read_text(encoding="utf-8"))
MAC = platform.system() == "Darwin" and shutil.which("clang")


def objc(text) -> str:
    return "@" + json.dumps(str(text), ensure_ascii=False)


def dictionary(entries: dict) -> str:
    return "@{" + ", ".join(f"{objc(k)}: {objc(v)}" for k, v in entries.items()) + "}"


def pairs(params: dict) -> str:
    return "@[" + ", ".join(f"{objc(k)}, {objc(v)}" for k, v in params.items()) + "]"


def run(main: str, *sources: Path, c_only=False) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        program = Path(tmp) / ("main.c" if c_only else "main.m")
        program.write_text(main, encoding="utf-8")
        flags = [] if c_only else ["-fobjc-arc", "-framework", "Foundation"]
        subprocess.run(["clang", "-Wall", "-Werror", *flags, "-I", str(LAUNCHER), "-o", str(Path(tmp) / "run"),
                        str(program), *map(str, sources)], check=True, capture_output=True, text=True)
        out = subprocess.run([str(Path(tmp) / "run")], check=True, capture_output=True)
    return out.stdout.decode("utf-8").split("\n")[:-1]


CORE = (LAUNCHER / "LTText.m", LAUNCHER / "LTPlurals.c")


@unittest.skipUnless(MAC, "needs macOS and clang")
class SharedCases(unittest.TestCase):
    def call(self, case: dict) -> str:
        n = case.get("n", 0)
        written = objc(bunker_numbers.write(case["language"], n))
        text = (f"[[LTText alloc] initWithEnglish:{dictionary(CASES['english'])} translation:{dictionary(case['translation'])} "
                f"language:{objc(case['language'])} numbers:^NSString *(double value) {{ return {written}; }}]")
        key, args = objc(case["key"]), pairs(case["params"])
        if case["call"] == "t":
            return f"[{text} t:{key} pairs:{args}]"
        if case["call"] == "t_or":
            return f"[{text} t:{key} fallback:{objc(case['fallback'])} pairs:{args}]"
        if case["call"] == "count":
            return f"[{text} count:{key} n:{n} pairs:{args}]"
        return f"[[{text} around:{key} slot:{objc(case['slot'])} pairs:{args}] componentsJoinedByString:@\"\\t\"]"

    def test_the_shared_cases(self):
        lines = "".join(f"        puts([{self.call(c)} UTF8String]);\n" for c in CASES["cases"])
        main = ("#import <Foundation/Foundation.h>\n#import \"LTText.h\"\n#include <stdio.h>\n"
                "int main(void) {\n    @autoreleasepool {\n" + lines + "    }\n    return 0;\n}\n")
        out = run(main, *CORE)
        for case, got in zip(CASES["cases"], out, strict=True):
            expected = "\t".join(case["expect"]) if isinstance(case["expect"], list) else case["expect"]
            self.assertEqual(got, expected, case["name"])


@unittest.skipUnless(MAC, "needs macOS and clang")
class Plurals(unittest.TestCase):
    LANGUAGES = sorted(set(bunker_plurals.RULES) | set(bunker_plurals.REGIONS) |
                       {"en", "de", "xx", "pt-BR", "PT_pt", "zh-Hans", "sr-Latn", ""})

    def test_every_rule_as_python_has_it(self):
        main = ("#include <stdio.h>\n#include \"LTPlurals.h\"\nint main(void) {\n"
                "    const char *tags[] = {" + ", ".join(json.dumps(t) for t in self.LANGUAGES) + "};\n"
                f"    for (int t = 0; t < {len(self.LANGUAGES)}; t++) {{\n"
                "        for (long long n = 0; n < 1200; n++) printf(\"%s \", lt_plural_category(tags[t], n));\n"
                "        const char *all[6]; int k = lt_plural_categories(tags[t], all);\n"
                "        printf(\"|\"); for (int i = 0; i < k; i++) printf(\" %s\", all[i]); printf(\"\\n\");\n"
                "    }\n    return 0;\n}\n")
        out = run(main, LAUNCHER / "LTPlurals.c", c_only=True)
        for tag, line in zip(self.LANGUAGES, out, strict=True):
            each, _, every = line.partition("|")
            self.assertEqual(each.split(), [bunker_plurals.category(tag, n) for n in range(1200)], tag)
            self.assertEqual(sorted(every.split()), sorted(bunker_plurals.categories(tag)), tag)


@unittest.skipUnless(MAC, "needs macOS and clang")
class Numbers(unittest.TestCase):
    SAMPLES = [0, 7, 999, 1200, 12000, 1234567, 97.5, 1234.5678]

    def test_numbers_as_python_writes_them(self):
        languages = sorted(set(bunker_numbers.GROUPS) | set(bunker_numbers.REGIONS))
        main = ("#import <Foundation/Foundation.h>\n#import \"LTText.h\"\n#include <stdio.h>\nint main(void) {\n @autoreleasepool {\n"
                "  NSArray *tags = @[" + ", ".join(objc(t) for t in languages) + "];\n"
                "  double samples[] = {" + ", ".join(str(s) for s in self.SAMPLES) + "};\n"
                "  for (NSString *tag in tags) {\n    NSString *(^write)(double) = [LTText numbersFor:tag];\n"
                f"    for (int i = 0; i < {len(self.SAMPLES)}; i++) printf(\"%s\\t\", [write(samples[i]) UTF8String]);\n"
                "    printf(\"\\n\");\n  }\n }\n return 0;\n}\n")
        out = run(main, *CORE)
        # Apple's CLDR data differs from Node's CLDR 48 (which bunker_numbers follows) in three places, and the
        # device's data wins on the device: Swiss French decimals with "." (1'234.568), and Kannada and Urdu
        # grouped the Indian way (12,34,567).
        def indian(want):
            return [w.replace("1,234,567", "12,34,567") for w in want]
        known = {"fr-ch": lambda want: [w.replace(",", ".") for w in want], "kn": indian, "ur": indian}
        differ = {}
        for tag, line in zip(languages, out, strict=True):
            got, want = line.split("\t")[:-1], [bunker_numbers.write(tag, n) for n in self.SAMPLES]
            want = known.get(tag, lambda w: w)(want)
            if got != want:
                differ[tag] = (got, want)
        self.assertEqual(differ, {})


@unittest.skipUnless(MAC, "needs macOS and clang")
class Said(unittest.TestCase):
    def test_references_sizes_and_english(self):
        main = r'''#import <Foundation/Foundation.h>
#import "LTText.h"
#include <stdio.h>
int main(void) { @autoreleasepool {
  NSDictionary *en = @{@"x.ready": @"Ready to play", @"x.left.one": @"{n} file left in {place}", @"x.left.other": @"{n} files left in {place}",
                       @"launcher.size.kb": @"{n} KB", @"launcher.size.mb": @"{n} MB", @"launcher.size.gb": @"{n} GB"};
  NSString *(^plain)(double) = ^NSString *(double n) { return n == (long long)n ? [NSString stringWithFormat:@"%lld", (long long)n] : [NSString stringWithFormat:@"%g", n]; };
  LTText *english = [[LTText alloc] initWithEnglish:en translation:@{} language:@"en" numbers:plain];
  LTText *german = [[LTText alloc] initWithEnglish:en translation:@{@"x.ready": @"Bereit"} language:@"de" numbers:plain];
  NSString *marks = [NSString stringWithFormat:@"K\u00f6ln%C%C", (unichar)0x1e, (unichar)0x1f];
  NSString *ready = [LTText saidText:@"x.ready" pairs:@[]], *left = [LTText saidCount:@"x.left" n:3 pairs:@[@"place", marks]];
  puts([[english said:ready] UTF8String]); puts([[german said:ready] UTF8String]);
  puts([[english said:left] UTF8String]); puts([[english said:@"Port 7777 refused"] UTF8String]);
  puts([[NSString stringWithFormat:@"%@|%@|%@", [english said:@""], [english said:nil], [english said:[NSString stringWithFormat:@"%Cbroken", (unichar)0x1f]]] UTF8String]);
  puts([[german said:[ready stringByAppendingString:@" · 3"]] UTF8String]);
  for (NSNumber *b in @[@0, @512, @1400, @999000, @1400000, @99940000, @350000000, @8200000000LL, @120000000000LL])
    printf("%s\t", [[english size:b.longLongValue] UTF8String]);
  printf("\n");
} return 0; }
'''
        out = run(main, *CORE)
        self.assertEqual(out[:6], ["Ready to play", "Bereit", "3 files left in Köln", "Port 7777 refused", "||broken", "Bereit · 3"])
        self.assertEqual(out[6].split("\t")[:-1], ["1 KB", "1 KB", "1.4 KB", "999 KB", "1.4 MB", "99.9 MB", "350 MB", "8.2 GB", "120 GB"])

    def test_the_same_references_as_java(self):
        # One encoding everywhere (Said.java): a reference made on one side reads on the other.
        java = (ROOT / "android/app/src/main/java/org/veritr1x/bunker/Said.java").read_text()
        self.assertIn("START = '\\u001f', END = '\\u001e', SEP = '\\u001d'", java)
        source = (LAUNCHER / "LTText.m").read_text()
        for mark in ("0x1f", "0x1e", "0x1d"):
            self.assertIn(mark, source)

    def test_no_uikit_inside(self):
        for name in ("LTText.m", "LTText.h", "LTPlurals.c"):
            self.assertNotIn("UIKit", (LAUNCHER / name).read_text(), name)


if __name__ == "__main__":
    unittest.main()
