// Which plural form a language uses for a whole number (CLDR categories): a C copy of
// android/app/src/main/python/bunker_plurals.py, for the iOS launcher (iOS has no public plural rules).
// ios/tools/test_lt_text.py checks it against Python for every language and every n in 0..1199.
#pragma once

/** "zero", "one", "two", "few", "many" or "other": the category of the whole number n in tag ("pt-BR"). */
const char *lt_plural_category(const char *tag, long long n);

/** Every category tag uses for whole numbers, in the order zero one two few many other; returns how many. */
int lt_plural_categories(const char *tag, const char *out[6]);
