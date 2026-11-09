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
        # Under assets/lunar/: the game APK keeps only assets/lunar/ and assets/chaquopy/ from Bunker's own APK
        # (assemble_apk.py, build_info.py); an asset elsewhere is lost and every text shows its key.
        self.assertIn('open("lunar/bunker_en.json")', source("Texts.java"))
        self.assertRegex(GRADLE, r"into\s+bunkerTextAssets\.map\s*\{\s*it\.dir\('lunar'\)\s*\}|generated/bunkerText/assets/lunar")
        import build_info  # an update keeps the entries it counts as Bunker's
        self.assertTrue(build_info.is_bunker_entry("assets/lunar/bunker_en.json", {"bunkerLibs": [], "gameDex": 1}))


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


class LanguageChange(unittest.TestCase):
    """A language chosen in Pod Programs reaches every word: Texts notices the pack changed on any lookup
    (a stat at most once a second) and counts the change, so each screen and the notification can tell."""

    def test_any_lookup_notices_a_new_pack(self):
        text = source("Texts.java")
        self.assertRegex(text, r"static synchronized int generation\(Context c\)")
        self.assertNotIn("static synchronized boolean refresh(", text)  # told only its first caller
        self.assertRegex(text, r"SystemClock\.elapsedRealtime\(\)\s*-\s*checked\s*>=?\s*1000")

    def test_the_launcher_rebuilds_for_a_new_language(self):
        main = source("MainActivity.java")
        self.assertRegex(main, r"if\(Texts\.generation\(this\)!=shownGeneration\)\{recreate\(\);return;\}")
        self.assertIn("shownGeneration=Texts.generation(this);", main)

    def test_the_notification_follows_a_new_language(self):
        service = source("ServerService.java")
        # renamed channel and words, the next time the notification is built and whenever the launcher asks
        self.assertIn("int now=Texts.generation(this);if(now!=labelled){labelled=now;channel();}", service)
        self.assertRegex(service, r"if\(\(running\|\|tools\)&&Texts\.generation\(this\)!=labelled\)"
                                  r"getSystemService\(NotificationManager\.class\)\.notify\(1,notification\(\)\);")


class Sizes(unittest.TestCase):
    """One way to write a size, everywhere the launcher shows one (the save, imports, updates)."""

    @unittest.skipUnless(__import__("shutil").which("javac"), "needs a JDK")
    def test_sizes_are_1000_based_with_one_decimal_under_100(self):
        import json
        import subprocess
        import tempfile
        english = json.loads((ROOT / "translations/bunker/en.json").read_text())
        puts = "".join(f"en.put({json.dumps(k)}, {json.dumps(v)});" for k, v in english.items() if k.startswith("launcher.size."))
        main = ("package org.veritr1x.bunker;\npublic class Main { public static void main(String[] a) {\n"
                "java.util.Map<String, String> en = new java.util.HashMap<>();" + puts + "\n"
                "BunkerText.Plurals p = new BunkerText.Plurals() { public String category(long n) { return \"other\"; }\n"
                "  public java.util.Set<String> categories() { return java.util.Collections.singleton(\"other\"); } };\n"
                "BunkerText t = new BunkerText(en, null, p, n -> n == Math.rint(n) ? String.valueOf((long) n) : String.valueOf(n));\n"
                "for (long b : new long[]{0, 512, 1400, 999_000, 1_400_000, 99_940_000, 350_000_000, 8_200_000_000L, 120_000_000_000L})"
                " System.out.println(t.size(b));\n} }\n")
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "Main.java").write_text(main, encoding="utf-8")
            subprocess.run(["javac", "-encoding", "UTF-8", "-d", tmp, str(JAVA / "BunkerText.java"), str(Path(tmp, "Main.java"))],
                           check=True, capture_output=True)
            out = subprocess.run(["java", "-cp", tmp, "org.veritr1x.bunker.Main"], check=True,
                                 capture_output=True).stdout.decode().split("\n")[:-1]
        self.assertEqual(out, ["1 KB", "1 KB", "1.4 KB", "999 KB", "1.4 MB", "99.9 MB", "350 MB", "8.2 GB", "120 GB"])

    def test_one_size_helper(self):
        import json
        english = json.loads((ROOT / "translations/bunker/en.json").read_text())
        self.assertEqual(sorted(k for k in english if "size_" in k or k.startswith("launcher.size.")),
                         ["launcher.size.gb", "launcher.size.kb", "launcher.size.mb"])
        for name in ("MainActivity.java", "FilesStore.java", "Updater.java"):
            text = source(name)
            self.assertNotRegex(text, r"(private|static) String size\(", name)
            self.assertIn("Texts.size(", text, name)


class Messages(unittest.TestCase):
    def test_the_archive_error_is_the_message_in_words(self):
        archive = source("ArchiveActivity.java")
        self.assertNotIn("==null?error.toString():error.getMessage())", archive)
        self.assertIn('"error",Texts.said(ArchiveActivity.this,ServerService.message(error))', archive)

    def test_the_progress_bar_says_its_percent_in_words(self):
        look = source("Look.java")
        self.assertNotIn('" percent"', look)
        self.assertIn('Texts.t(look.context,"launcher.progress.percent","n",Texts.number(look.context,permille/10))', look)


class States(unittest.TestCase):
    """The server's state is an id the launcher compares; its words come from the catalogue when shown."""
    SERVICE = source("ServerService.java")

    def ids(self):
        return set(re.findall(r'\bstate\s*=\s*"([^"]*)"', self.SERVICE)) | \
            set(re.findall(r'\?"([a-z_]+)"', re.search(r"state=START\.equals.*", self.SERVICE).group(0)))

    def test_states_are_ids(self):
        self.assertTrue(self.ids())
        self.assertEqual({i for i in self.ids() if not re.fullmatch(r"[a-z_]+", i)}, set())

    def test_no_words_are_compared(self):
        for name in ("MainActivity.java", "ToolsActivity.java", "ServerService.java"):
            text = source(name)
            self.assertEqual(re.findall(r'"[^"]*[A-Z ][^"]*"\.equals\(\s*(?:serverState|state)\s*\)', text), [], name)
            self.assertEqual(re.findall(r'(?:serverState|state)\s*=\s*"[^"]*[A-Z ][^"]*"', text), [], name)

    def test_every_state_has_words(self):
        import json
        english = json.loads((ROOT / "translations/bunker/en.json").read_text())
        self.assertEqual({i for i in self.ids() if f"launcher.state.{i}" not in english}, set())


SAID_MAIN = r'''package org.veritr1x.bunker;
public class Main { public static void main(String[] a) {
  java.util.Map<String, String> en = new java.util.HashMap<>();
  en.put("x.ready", "Ready to play"); en.put("x.left.one", "{n} file left in {place}"); en.put("x.left.other", "{n} files left in {place}");
  java.util.Map<String, String> de = new java.util.HashMap<>(); de.put("x.ready", "Bereit");
  BunkerText.Plurals p = new BunkerText.Plurals() { public String category(long n) { return n == 1 ? "one" : "other"; }
    public java.util.Set<String> categories() { return new java.util.HashSet<>(java.util.Arrays.asList("one", "other")); } };
  BunkerText english = new BunkerText(en, null, p, n -> String.valueOf((long) n)), german = new BunkerText(en, de, p, n -> String.valueOf((long) n));
  String ready = Said.text("x.ready"), left = Said.count("x.left", 3, "place", "Köln\u001e\u001f"), raw = "Port 7777 refused";
  System.out.println(Said.in(english, ready)); System.out.println(Said.in(german, ready));
  System.out.println(Said.in(english, left)); System.out.println(Said.in(english, raw));
  System.out.println(Said.in(english, "") + "|" + Said.in(english, null) + "|" + Said.in(english, "\u001fbroken"));
} }
'''


class SaidLater(unittest.TestCase):
    """Said.java: words the service sets now and the launcher shows later, in the language of that moment."""

    @unittest.skipUnless(__import__("shutil").which("javac"), "needs a JDK")
    def test_put_in_words_when_shown(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "Main.java").write_text(SAID_MAIN, encoding="utf-8")
            subprocess.run(["javac", "-encoding", "UTF-8", "-d", tmp, str(JAVA / "BunkerText.java"), str(JAVA / "Said.java"),
                            str(Path(tmp, "Main.java"))], check=True, capture_output=True)
            out = subprocess.run(["java", "-Dstdout.encoding=UTF-8", "-cp", tmp, "org.veritr1x.bunker.Main"], check=True,
                                 capture_output=True).stdout.decode().split("\n")[:-1]
        self.assertEqual(out, ["Ready to play", "Bereit", "3 files left in Köln", "Port 7777 refused", "||broken"])

    @unittest.skipUnless(__import__("shutil").which("javac"), "needs a JDK")
    def test_logged_failures_read_in_english(self):
        # An exception carrying a Said reference is logged as English, with its stack trace and cause kept.
        import subprocess
        import tempfile
        main = r'''package org.veritr1x.bunker;
public class Main { public static void main(String[] a) {
  java.util.Map<String, String> en = new java.util.HashMap<>(); en.put("x.gone", "Lunar Tear isn't running: {why}");
  BunkerText.Plurals p = new BunkerText.Plurals() { public String category(long n) { return "other"; }
    public java.util.Set<String> categories() { return java.util.Collections.singleton("other"); } };
  BunkerText english = new BunkerText(en, null, p, n -> String.valueOf((long) n));
  Exception cause = new java.io.IOException("disk");
  IllegalStateException e = new IllegalStateException(Said.text("x.gone", "why", "port 7777"), cause);
  Throwable logged = Said.forLog(e, english);
  System.out.println(logged.getMessage());
  System.out.println(logged.getCause() == cause);
  System.out.println(java.util.Arrays.equals(logged.getStackTrace(), e.getStackTrace()));
  Exception plain = new IllegalStateException("Go said no");
  System.out.println(Said.forLog(plain, english) == plain);
} }
'''
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "Main.java").write_text(main, encoding="utf-8")
            subprocess.run(["javac", "-encoding", "UTF-8", "-d", tmp, str(JAVA / "BunkerText.java"), str(JAVA / "Said.java"),
                            str(Path(tmp, "Main.java"))], check=True, capture_output=True)
            out = subprocess.run(["java", "-cp", tmp, "org.veritr1x.bunker.Main"], check=True,
                                 capture_output=True).stdout.decode().split("\n")[:-1]
        self.assertEqual(out, ["java.lang.IllegalStateException: Lunar Tear isn't running: port 7777", "true", "true", "true"])

    def test_logs_stay_english(self):
        service = source("ServerService.java")
        for what in ("Tools startup failed", "Operation failed", "Closing the game for Pod Programs failed"):
            self.assertIn(f'android.util.Log.e("LunarTear","{what}",Texts.forLog(error));', service)
        self.assertEqual(service.count('"Restarting the server beside the game failed: "+Texts.inEnglish('), 2)
        # resumeForTools' answer is only logged (android_runtime, android_mods): a reference, logged in English
        resume = service[service.index("public static String resumeForTools(boolean title)"):service.index("private static String resumeServer")]
        self.assertNotIn("Texts.said(", resume)
        self.assertNotIn("Texts.t(", resume)
        self.assertIn("public static String inEnglish(String said)", service)
        runtime = (ROOT / "android/app/src/main/python/android_runtime.py").read_text()
        self.assertIn("resume_game = lambda title=True: str(service.inEnglish(service.resumeForTools(bool(title))))", runtime)

    def test_the_launcher_shows_the_detail_in_words(self):
        self.assertIn("Said.in(", source("Texts.java"))
        main = source("MainActivity.java")
        self.assertNotRegex(main, r"message=serverDetail;|\+serverDetail\)")
        self.assertIn("Texts.said(this,serverDetail)", main)
        self.assertIn("Texts.said(ToolsActivity.this,ServerService.detail)", source("ToolsActivity.java"))


if __name__ == "__main__":
    unittest.main()
