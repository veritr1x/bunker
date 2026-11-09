package org.veritr1x.bunker;

import java.util.ArrayList;
import java.util.List;

/**
 * Words set now and shown later: the server's status detail is set in its process and shown by the launcher,
 * maybe after the language changed. So it keeps a reference to a catalogue text (key, count, values) and
 * in() puts it in words when shown, as the Archive's words.py does. A message that is not a reference (an
 * error from Lunar Tear or Python) is shown as it is. Plain Java, a String: it crosses a Bundle unchanged.
 */
final class Said {
    private Said() { }

    private static final char START = '\u001f', END = '\u001e', SEP = '\u001d';

    /** A reference to key with these values (name, value…). */
    static String text(String key, Object... pairs) { return make(key, "", pairs); }

    /** A reference to key counted n times. */
    static String count(String key, long n, Object... pairs) { return make(key, Long.toString(n), pairs); }

    private static String make(String key, String n, Object... pairs) {
        StringBuilder out = new StringBuilder().append(START).append(clean(key)).append(SEP).append(n);
        for (Object part : pairs) out.append(SEP).append(clean(String.valueOf(part)));
        return out.append(END).toString();
    }

    private static String clean(String s) { return s.replace(String.valueOf(START), "").replace(String.valueOf(END), "").replace(String.valueOf(SEP), ""); }

    /** said with each reference put in words by these texts; anything else as it is. */
    static String in(BunkerText words, String said) {
        if (said == null) return "";
        StringBuilder out = new StringBuilder();
        int i = 0;
        while (i < said.length()) {
            int start = said.indexOf(START, i);
            if (start < 0) { out.append(said, i, said.length()); break; }
            out.append(said, i, start);
            int end = said.indexOf(END, start);
            if (end < 0) { out.append(clean(said.substring(start))); break; }  // cut short: its text, no markers
            out.append(words(words, said.substring(start + 1, end)));
            i = end + 1;
        }
        return out.toString();
    }

    /** error as it should be logged: logs stay English, so a message holding references becomes those words
     *  (english: texts without a translation), on a copy keeping the class name, cause and stack trace.
     *  Any other error is returned as it is. */
    static Throwable forLog(Throwable error, BunkerText english) {
        String message = error.getMessage();
        if (message == null || message.indexOf(START) < 0) return error;
        RuntimeException copy = new RuntimeException(error.getClass().getName() + ": " + in(english, message), error.getCause());
        copy.setStackTrace(error.getStackTrace());
        return copy;
    }

    private static String words(BunkerText words, String reference) {
        List<String> parts = new ArrayList<>();
        int from = 0;
        for (int at; (at = reference.indexOf(SEP, from)) >= 0; from = at + 1) parts.add(reference.substring(from, at));
        parts.add(reference.substring(from));
        if (parts.size() < 2) return "";
        Object[] pairs = parts.subList(2, parts.size()).toArray();
        String key = parts.get(0), n = parts.get(1);
        if (n.isEmpty()) return words.t(key, pairs);
        try { return words.count(key, Long.parseLong(n), pairs); } catch (NumberFormatException e) { return ""; }
    }
}
