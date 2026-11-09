// A copy of bunker_plurals.py's rules for whole numbers (see LTPlurals.h).
#include "LTPlurals.h"
#include <ctype.h>
#include <string.h>

typedef const char *(*Rule)(long long n);

static const char *only_other(long long n) { (void)n; return "other"; }
static const char *one_for_1(long long n) { return n == 1 ? "one" : "other"; }
static const char *one_for_0_1(long long n) { return n == 0 || n == 1 ? "one" : "other"; }
static const char *east_slavic(long long n) {  // ru, uk, be
    if (n % 10 == 1 && n % 100 != 11) return "one";
    if (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return "few";
    return "many";
}
static const char *south_slavic(long long n) {  // hr, sr, bs
    if (n % 10 == 1 && n % 100 != 11) return "one";
    if (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return "few";
    return "other";
}
static const char *polish(long long n) {
    if (n == 1) return "one";
    if (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return "few";
    return "many";
}
static const char *czech(long long n) { return n == 1 ? "one" : n >= 2 && n <= 4 ? "few" : "other"; }  // cs, sk
static const char *lithuanian(long long n) {
    if (n % 10 == 1 && !(n % 100 >= 11 && n % 100 <= 19)) return "one";
    if (n % 10 >= 2 && n % 10 <= 9 && !(n % 100 >= 11 && n % 100 <= 19)) return "few";
    return "other";
}
static const char *latvian(long long n) {
    if (n % 10 == 0 || (n % 100 >= 11 && n % 100 <= 19)) return "zero";
    if (n % 10 == 1 && n % 100 != 11) return "one";
    return "other";
}
static const char *romanian(long long n) {
    if (n == 1) return "one";
    if (n == 0 || (n % 100 >= 2 && n % 100 <= 19)) return "few";
    return "other";
}
static const char *slovenian(long long n) {
    switch (n % 100) { case 1: return "one"; case 2: return "two"; case 3: case 4: return "few"; default: return "other"; }
}
static const char *arabic(long long n) {
    if (n == 0) return "zero";
    if (n == 1) return "one";
    if (n == 2) return "two";
    if (n % 100 >= 3 && n % 100 <= 10) return "few";
    if (n % 100 >= 11 && n % 100 <= 99) return "many";
    return "other";
}
static const char *hebrew(long long n) { return n == 1 ? "one" : n == 2 ? "two" : "other"; }
static const char *irish(long long n) {
    if (n == 1) return "one";
    if (n == 2) return "two";
    if (n >= 3 && n <= 6) return "few";
    return n >= 7 && n <= 10 ? "many" : "other";
}
static const char *welsh(long long n) {
    switch (n) { case 0: return "zero"; case 1: return "one"; case 2: return "two"; case 3: return "few"; case 6: return "many"; default: return "other"; }
}
static const char *icelandic(long long n) { return n % 10 == 1 && n % 100 != 11 ? "one" : "other"; }  // is, mk

static const struct { const char *language; Rule rule; } RULES[] = {
    {"ja", only_other}, {"ko", only_other}, {"zh", only_other}, {"yue", only_other}, {"vi", only_other}, {"th", only_other},
    {"id", only_other}, {"ms", only_other}, {"km", only_other}, {"lo", only_other}, {"my", only_other}, {"jv", only_other},
    {"su", only_other}, {"bo", only_other}, {"dz", only_other},
    {"fr", one_for_0_1}, {"pt", one_for_0_1}, {"hy", one_for_0_1}, {"ff", one_for_0_1}, {"kab", one_for_0_1}, {"hi", one_for_0_1},
    {"bn", one_for_0_1}, {"gu", one_for_0_1}, {"kn", one_for_0_1}, {"mr", one_for_0_1}, {"zu", one_for_0_1}, {"am", one_for_0_1},
    {"fa", one_for_0_1}, {"as", one_for_0_1},
    {"ru", east_slavic}, {"uk", east_slavic}, {"be", east_slavic},
    {"hr", south_slavic}, {"sr", south_slavic}, {"bs", south_slavic},
    {"pl", polish}, {"cs", czech}, {"sk", czech}, {"lt", lithuanian}, {"lv", latvian}, {"ro", romanian}, {"mo", romanian},
    {"sl", slovenian}, {"ar", arabic}, {"he", hebrew}, {"iw", hebrew}, {"ga", irish}, {"cy", welsh}, {"is", icelandic},
    {"mk", icelandic},
};
// Regions whose rule differs from their language's.
static const struct { const char *region; Rule rule; } REGIONS[] = {{"pt-pt", one_for_1}};

static Rule rule_for(const char *tag) {
    char lower[64];
    size_t length = 0;
    for (const char *c = (tag && *tag) ? tag : "en"; *c && length < sizeof lower - 1; c++)
        lower[length++] = *c == '_' ? '-' : (char)tolower((unsigned char)*c);
    lower[length] = 0;
    // The longest region first ("pt-pt-x" → "pt-pt"), then the language alone.
    for (size_t depth = length; depth > 0; depth--) {
        if (depth < length && lower[depth] != '-') continue;
        for (size_t i = 0; i < sizeof REGIONS / sizeof *REGIONS; i++)
            if (strlen(REGIONS[i].region) == depth && strncmp(REGIONS[i].region, lower, depth) == 0) return REGIONS[i].rule;
    }
    size_t base = strcspn(lower, "-");
    for (size_t i = 0; i < sizeof RULES / sizeof *RULES; i++)
        if (strlen(RULES[i].language) == base && strncmp(RULES[i].language, lower, base) == 0) return RULES[i].rule;
    return one_for_1;
}

const char *lt_plural_category(const char *tag, long long n) { return rule_for(tag)(n < 0 ? -n : n); }

int lt_plural_categories(const char *tag, const char *out[6]) {
    static const char *ORDER[] = {"zero", "one", "two", "few", "many", "other"};
    Rule rule = rule_for(tag);
    int used[6] = {0}, count = 0;
    for (long long n = 0; n < 1200; n++) {
        const char *category = rule(n);
        for (int i = 0; i < 6; i++) if (strcmp(category, ORDER[i]) == 0) used[i] = 1;
    }
    for (int i = 0; i < 6; i++) if (used[i]) out[count++] = ORDER[i];
    return count;
}
