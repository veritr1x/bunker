package org.veritr1x.bunker;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Bunker's own words, as bunker_text.py gives them to Pod Programs and the Archive: the English catalogue
 * (translations/bunker/en.json) with a pack's translations over it. A loaded pack is untrusted, so a
 * translation is used only when its placeholders are exactly the English's (same names, no format spec);
 * otherwise the English is shown. Plain Java: Texts.java feeds it on the device, the tests on any JVM
 * (android/tools/test_bunker_text_java.py runs bunker_text_cases.json, the same cases as Python).
 */
final class BunkerText {
    /** The language's plural rule: the category of a whole number, and every category it uses for whole numbers. */
    interface Plurals {
        String category(long n);
        Set<String> categories();
    }

    /** A number written the language's way ("1,200", "1.200", "1 200"). */
    interface Numbers {
        String write(double n);
    }

    private static final String[] CATEGORIES = {"zero", "one", "two", "few", "many", "other"};
    private static final String SLOT = "\u0000";

    private final Map<String, String> english, translation;
    private final Plurals plurals;
    private final Numbers numbers;

    BunkerText(Map<String, String> english, Map<String, String> translation, Plurals plurals, Numbers numbers) {
        this.english = english;
        Map<String, String> kept = new HashMap<>();
        if (translation != null)
            for (Map.Entry<String, String> e : translation.entrySet())
                if (e.getKey() != null && e.getValue() != null && !e.getValue().isEmpty()) kept.put(e.getKey(), e.getValue());
        this.translation = kept;
        this.plurals = plurals;
        this.numbers = numbers;
    }

    /** key's text with these values (name, value, name, value…); the key itself when the catalogue lacks it. */
    String t(String key, Object... pairs) { return tOr(key, key, pairs); }

    /** As t, with what to show when the catalogue lacks key (a name from the game data, say). */
    String tOr(String key, String fallback, Object... pairs) {
        String base = english.get(key);
        if (base == null) return fallback;
        Map<String, Object> params = params(pairs);
        String translated = translation.get(key);
        if (translated != null && sameFields(fields(translated), fields(base))) {
            try { return format(translated, params); } catch (IllegalArgumentException ignored) { }
        }
        try { return format(base, params); } catch (IllegalArgumentException ignored) { return base; }
    }

    /** key counted n times, in the plural form the language uses for n; {n} is n written the language's way.
     *  A translation missing a form its language needs gives the English for every count. */
    String count(String key, long n, Object... pairs) {
        Map<String, Object> params = params(pairs);
        if (!params.containsKey("n")) params.put("n", numbers.write(n));
        Map<String, String> forms = translatedForms(key);
        if (forms != null) {
            String form = forms.get(plurals.category(Math.abs(n)));
            if (form != null) {
                try { return format(form, params); } catch (IllegalArgumentException ignored) { }
            }
        }
        String base = english.get(key + (n == 1 ? ".one" : ".other"));
        if (base == null) return key + ".other";
        try { return format(base, params); } catch (IllegalArgumentException ignored) { return base; }
    }

    /** A sentence around a control or link: its text before and after {slot}. A translation without the slot
     *  exactly once gives the English. */
    String[] around(String key, String slot, Object... pairs) {
        Object[] withSlot = new Object[pairs.length + 2];
        System.arraycopy(pairs, 0, withSlot, 0, pairs.length);
        withSlot[pairs.length] = slot;
        withSlot[pairs.length + 1] = SLOT;
        String text = t(key, withSlot);
        if (occurrences(text, SLOT) != 1) {
            String base = english.containsKey(key) ? english.get(key) : key;
            try { text = format(base, params(withSlot)); } catch (IllegalArgumentException e) { text = base; }
        }
        int at = text.indexOf(SLOT);
        return at < 0 ? new String[]{text, ""} : new String[]{text.substring(0, at), text.substring(at + SLOT.length())};
    }

    String number(double n) { return numbers.write(n); }

    private Map<String, String> translatedForms(String key) {
        String other = english.get(key + ".other");
        if (other == null || translation.isEmpty()) return null;
        List<String[]> allowedList = fields(other);
        if (allowedList == null) return null;
        Set<List<String>> allowed = asSet(allowedList);
        Map<String, String> forms = new HashMap<>();
        for (String category : plurals.categories()) {
            String text = translation.get(key + "." + category);
            List<String[]> found = text == null ? null : fields(text);
            if (found == null || !allowed.containsAll(asSet(found))) return null;
            forms.put(category, text);
        }
        for (String category : CATEGORIES) {  // extra forms are kept too, as in Python
            String text = translation.get(key + "." + category);
            if (forms.containsKey(category) || text == null) continue;
            List<String[]> found = fields(text);
            if (found != null && allowed.containsAll(asSet(found))) forms.put(category, text);
        }
        return forms;
    }

    private static Set<List<String>> asSet(List<String[]> fields) {
        Set<List<String>> set = new HashSet<>();
        for (String[] f : fields) set.add(List.of(f));
        return set;
    }

    private static Map<String, Object> params(Object[] pairs) {
        Map<String, Object> params = new LinkedHashMap<>();
        for (int i = 0; i + 1 < pairs.length; i += 2) params.put(String.valueOf(pairs[i]), pairs[i + 1]);
        return params;
    }

    private static int occurrences(String text, String part) {
        int count = 0;
        for (int at = text.indexOf(part); at >= 0; at = text.indexOf(part, at + part.length())) count++;
        return count;
    }

    /** One placeholder: its name, format spec and conversion, as Python's string.Formatter reads them. */
    private static final class Field {
        final String name, spec, conversion;
        final int start, end;  // the whole {…} in the text
        Field(String name, String spec, String conversion, int start, int end) {
            this.name = name; this.spec = spec; this.conversion = conversion; this.start = start; this.end = end;
        }
    }

    /** The text's pieces: literal strings (with doubled braces undone) and fields; IllegalArgumentException
     *  where Python's format would raise ValueError (a single "}", an unclosed "{", a bad conversion). */
    private static List<Object> parse(String text) {
        List<Object> parts = new ArrayList<>();
        StringBuilder literal = new StringBuilder();
        int i = 0, length = text.length();
        while (i < length) {
            char c = text.charAt(i);
            if (c == '}') {
                if (i + 1 < length && text.charAt(i + 1) == '}') { literal.append('}'); i += 2; continue; }
                throw new IllegalArgumentException("Single '}' encountered");
            }
            if (c != '{') { literal.append(c); i++; continue; }
            if (i + 1 < length && text.charAt(i + 1) == '{') { literal.append('{'); i += 2; continue; }
            int depth = 1, j = i + 1;
            while (j < length && depth > 0) {
                char d = text.charAt(j);
                if (d == '{') depth++;
                else if (d == '}') depth--;
                if (depth > 0) j++;
            }
            if (depth > 0) throw new IllegalArgumentException("expected '}' before end of string");
            String inside = text.substring(i + 1, j);
            // The name runs to the first ':' or '!' outside square brackets.
            int k = 0;
            boolean bracket = false;
            for (; k < inside.length(); k++) {
                char d = inside.charAt(k);
                if (d == '[') bracket = true;
                else if (d == ']') bracket = false;
                else if (!bracket && (d == ':' || d == '!')) break;
            }
            String name = inside.substring(0, k), conversion = "", spec = "";
            if (k < inside.length() && inside.charAt(k) == '!') {
                if (k + 1 >= inside.length()) throw new IllegalArgumentException("end of string while looking for conversion specifier");
                conversion = inside.substring(k + 1, k + 2);
                k += 2;
                if (k < inside.length() && inside.charAt(k) != ':') throw new IllegalArgumentException("expected ':' after conversion specifier");
            }
            if (k < inside.length()) spec = inside.substring(k + 1);
            parts.add(literal.toString());
            literal.setLength(0);
            parts.add(new Field(name, spec, conversion, i, j + 1));
            i = j + 1;
        }
        parts.add(literal.toString());
        return parts;
    }

    /** The placeholders in text as (name, spec, conversion), sorted; null when text is not a valid format. */
    static List<String[]> fields(String text) {
        List<String[]> found = new ArrayList<>();
        try {
            for (Object part : parse(text))
                if (part instanceof Field) { Field f = (Field) part; found.add(new String[]{f.name, f.spec, f.conversion}); }
        } catch (IllegalArgumentException e) {
            return null;
        }
        found.sort((a, b) -> {
            for (int i = 0; i < 3; i++) { int c = a[i].compareTo(b[i]); if (c != 0) return c; }
            return 0;
        });
        return Collections.unmodifiableList(found);
    }

    private static boolean sameFields(List<String[]> a, List<String[]> b) {
        if (a == null || b == null) return a == b;
        if (a.size() != b.size()) return false;
        for (int i = 0; i < a.size(); i++) if (!java.util.Arrays.equals(a.get(i), b.get(i))) return false;
        return true;
    }

    /** text with each {name} replaced by its value. Bunker's texts have plain names only: a positional field,
     *  a spec, a conversion or a missing value is an IllegalArgumentException (Python: KeyError/IndexError). */
    private static String format(String text, Map<String, Object> params) {
        StringBuilder out = new StringBuilder();
        for (Object part : parse(text)) {
            if (part instanceof String) { out.append((String) part); continue; }
            Field f = (Field) part;
            if (f.name.isEmpty() || !f.spec.isEmpty() || !f.conversion.isEmpty() || !params.containsKey(f.name))
                throw new IllegalArgumentException("cannot fill " + f.name);
            out.append(String.valueOf(params.get(f.name)));
        }
        return out.toString();
    }
}
