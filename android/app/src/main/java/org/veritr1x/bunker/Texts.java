package org.veritr1x.bunker;

import android.content.Context;
import android.icu.text.NumberFormat;
import android.icu.text.PluralRules;
import android.icu.util.ULocale;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * The launcher's words: the English catalogue packed into the APK (translations/bunker/en.json, as
 * lunar/bunker_en.json) with the pack Pod Programs activated over it (the server's translation/active.json, the file
 * Pod Programs and the Archive read). One language for Bunker: the phone's own language is never used.
 * Plural rules and numbers are the device's CLDR data for the pack's language, with Latin digits.
 */
final class Texts {
    private Texts() { }

    static final long MAX_PACK = 8 * 1024 * 1024;  // a loaded pack is untrusted: larger ones are ignored
    // A language tag as bunker_language.CODE accepts it ("pt-BR", "zh-Hans").
    private static final Pattern CODE = Pattern.compile("[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,3}");

    private static Map<String, String> english;
    private static BunkerText text;
    private static String language = "en";
    private static Locale locale = Locale.ENGLISH;
    private static String stamp;
    private static Context app;  // for calls without a Context (Python asking the service after it ended)

    static String t(Context c, String key, Object... pairs) { return current(c).t(key, pairs); }
    static String tOr(Context c, String key, String fallback, Object... pairs) { return current(c).tOr(key, fallback, pairs); }
    static String count(Context c, String key, long n, Object... pairs) { return current(c).count(key, n, pairs); }
    static String[] around(Context c, String key, String slot, Object... pairs) { return current(c).around(key, slot, pairs); }
    static String number(Context c, double n) { return current(c).number(n); }
    /** Words set earlier (Said.text) put in words now; any other message as it is. */
    static String said(Context c, String said) { return Said.in(current(c), said); }

    /** text in capitals, the pack's language's way ("İ" in Turkish). */
    static String upper(Context c, String text) {
        current(c);
        synchronized (Texts.class) { return text.toUpperCase(locale); }
    }

    /** The language of the words (a BCP 47 tag), "en" without a pack. */
    static synchronized String language(Context c) { current(c); return language; }

    /** Reads the pack again if it changed since it was last read (a language chosen in Pod Programs).
     *  True when it did: a screen built with the old words should build itself again. */
    static synchronized boolean refresh(Context c) {
        if (text == null) { current(c); return false; }
        if (stampOf(pack(c)).equals(stamp)) return false;
        load(c.getApplicationContext());
        return true;
    }

    /** c may be null: the application context of an earlier call is used; with none yet, keys are shown. */
    private static synchronized BunkerText current(Context c) {
        if (c != null && app == null) app = c.getApplicationContext();
        if (text == null) {
            if (app == null) return new BunkerText(new HashMap<>(), null, ENGLISH_RULE, n -> String.valueOf((long) n));
            load(app);
        }
        return text;
    }

    private static final BunkerText.Plurals ENGLISH_RULE = new BunkerText.Plurals() {
        public String category(long n) { return n == 1 ? "one" : "other"; }
        public Set<String> categories() { return new HashSet<>(java.util.Arrays.asList("one", "other")); }
    };

    private static File pack(Context c) { return new File(FilesStore.root(c.getApplicationContext()), "translation/active.json"); }

    private static String stampOf(File f) { return f.isFile() ? f.length() + ":" + f.lastModified() : "none"; }

    private static void load(Context c) {
        Context app = c.getApplicationContext();
        if (english == null) english = readEnglish(app);
        File file = pack(app);
        stamp = stampOf(file);
        Map<String, String> words = new HashMap<>();
        String tag = "en";
        if (file.isFile() && file.length() <= MAX_PACK) {
            try {
                JSONObject pack = new JSONObject(new String(read(new FileInputStream(file), MAX_PACK), StandardCharsets.UTF_8));
                JSONObject bunker = pack.optJSONObject("bunker");
                if (bunker != null) {
                    for (Iterator<String> keys = bunker.keys(); keys.hasNext(); ) {
                        String key = keys.next();
                        Object value = bunker.opt(key);
                        if (value instanceof String && !((String) value).isEmpty()) words.put(key, (String) value);
                    }
                }
                String said = pack.optString("language", "");
                if (!words.isEmpty() && CODE.matcher(said).matches()) tag = said;
            } catch (Exception | OutOfMemoryError broken) {
                android.util.Log.w("LunarTear", "Language pack unreadable: English", broken);
                words.clear();
            }
        }
        language = tag;
        locale = Locale.forLanguageTag(tag);
        ULocale where = ULocale.forLanguageTag(tag);
        final PluralRules rule = PluralRules.forLocale(where);
        final Set<String> categories = new HashSet<>();
        for (long n = 0; n < 1200; n++) categories.add(rule.select(n));
        final Set<String> fixed = Collections.unmodifiableSet(categories);
        final NumberFormat format = NumberFormat.getInstance(new ULocale(where.toLanguageTag().replace('-', '_') + "@numbers=latn"));
        format.setMaximumFractionDigits(3);
        text = new BunkerText(english, words, new BunkerText.Plurals() {
            public String category(long n) { return rule.select(n); }
            public Set<String> categories() { return fixed; }
        }, n -> { synchronized (format) { return format.format(n); } });
    }

    private static Map<String, String> readEnglish(Context app) {
        Map<String, String> words = new HashMap<>();
        try (InputStream in = app.getAssets().open("lunar/bunker_en.json")) {
            JSONObject all = new JSONObject(new String(read(in, Long.MAX_VALUE), StandardCharsets.UTF_8));
            for (Iterator<String> keys = all.keys(); keys.hasNext(); ) {
                String key = keys.next();
                words.put(key, all.optString(key));
            }
        } catch (Exception broken) {
            android.util.Log.e("LunarTear", "Bunker's catalogue is missing from the APK", broken);
        }
        return words;
    }

    private static byte[] read(InputStream in, long limit) throws IOException {
        try (InputStream source = in) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[65536];
            for (int got; (got = source.read(buffer)) > 0; ) {
                out.write(buffer, 0, got);
                if (out.size() > limit) throw new IOException("too large");
            }
            return out.toByteArray();
        }
    }
}
