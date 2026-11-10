#!/usr/bin/env python3
"""BunkerText.java (the Android launcher's text) does what bunker_text.py does: the cases in
bunker_text_cases.json, compiled and run with javac. Plural categories and numbers come from the device
(android.icu) in the app; here each case gets them from bunker_plurals and bunker_numbers. Needs a JDK."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
import bunker_numbers  # noqa: E402
import bunker_plurals  # noqa: E402

JAVA = ROOT / "android/app/src/main/java/org/veritr1x/bunker/BunkerText.java"
CASES = json.loads((Path(__file__).parent / "bunker_text_cases.json").read_text(encoding="utf-8"))
SPLIT = "\u0001"  # between the two pieces of around()


def literal(text) -> str:
    return json.dumps(str(text))  # a JSON string is a Java string literal (ASCII, \\uXXXX escapes)


def java_map(entries: dict) -> str:
    puts = "".join(f"m.put({literal(k)}, {literal(v)});" for k, v in entries.items())
    return f"new java.util.HashMap<String, String>() {{{{ java.util.HashMap<String, String> m = this; {puts} }}}}"


def pairs(params: dict) -> str:
    return "".join(f", {literal(k)}, {literal(v)}" for k, v in params.items())


def call(case: dict) -> str:
    language, ns = case["language"], [case.get("n", 0)]
    categories = ", ".join(literal(c) for c in sorted(bunker_plurals.categories(language)))
    plurals = (f"new BunkerText.Plurals() {{ public String category(long n) {{ return {literal(bunker_plurals.category(language, ns[0]))}; }}"
               f" public java.util.Set<String> categories() {{ return new java.util.HashSet<>(java.util.Arrays.asList({categories})); }} }}")
    numbers = f"n -> {literal(bunker_numbers.write(language, ns[0]))}"
    text = f"new BunkerText({java_map(CASES['english'])}, {java_map(case['translation'])}, {plurals}, {numbers})"
    key, args = literal(case["key"]), pairs(case["params"])
    if case["call"] == "t":
        return f"{text}.t({key}{args})"
    if case["call"] == "t_or":
        return f"{text}.tOr({key}, {literal(case['fallback'])}{args})"
    if case["call"] == "count":
        return f"{text}.count({key}, {case['n']}L{args})"
    return f"String.join({literal(SPLIT)}, {text}.around({key}, {literal(case['slot'])}{args}))"


def expected(case: dict) -> str:
    return SPLIT.join(case["expect"]) if isinstance(case["expect"], list) else case["expect"]


@unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "needs a JDK")
class BunkerTextJava(unittest.TestCase):
    def test_the_shared_cases(self):
        lines = "".join(f"        System.out.println({call(c)});\n" for c in CASES["cases"])
        main = ("package org.veritr1x.bunker;\npublic class Main {\n    public static void main(String[] a) {\n"
                + lines + "    }\n}\n")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Main.java").write_text(main, encoding="utf-8")
            subprocess.run(["javac", "-encoding", "UTF-8", "-d", tmp, str(JAVA), str(Path(tmp) / "Main.java")],
                           check=True, capture_output=True)
            out = subprocess.run(["java", "-Dstdout.encoding=UTF-8", "-cp", tmp, "org.veritr1x.bunker.Main"],
                                 check=True, capture_output=True).stdout.decode("utf-8").split("\n")[:-1]
        for case, got in zip(CASES["cases"], out, strict=True):
            self.assertEqual(got, expected(case), case["name"])

    def test_no_android_inside(self):
        # The core runs on any JVM: Texts.java gives it the catalogue, the pack and android.icu.
        source = JAVA.read_text()
        self.assertNotIn("import android", source)
        self.assertNotIn("import org.json", source)


if __name__ == "__main__":
    unittest.main()
