"""Which plural form a language uses for a whole number: the CLDR categories zero, one, two, few, many, other.

The device has no plural data (no Intl, no Babel), so the rules for whole numbers are written out here for the
languages translators are likely to bring (CLDR 44). Any other language uses English's rule: "one" for 1,
"other" for everything else. Page scripts use the browser's Intl.PluralRules, which follows the same data.
"""
from __future__ import annotations

CATEGORIES = ("zero", "one", "two", "few", "many", "other")


def _only_other(n: int) -> str:
    return "other"


def _one_for_1(n: int) -> str:
    return "one" if n == 1 else "other"


def _one_for_0_1(n: int) -> str:
    return "one" if n in (0, 1) else "other"


def _east_slavic(n: int) -> str:  # ru, uk, be
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


def _south_slavic(n: int) -> str:  # hr, sr, bs
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "other"


def _polish(n: int) -> str:
    if n == 1:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


def _czech(n: int) -> str:  # cs, sk ("many" is for fractions only)
    if n == 1:
        return "one"
    return "few" if 2 <= n <= 4 else "other"


def _lithuanian(n: int) -> str:
    if n % 10 == 1 and not 11 <= n % 100 <= 19:
        return "one"
    if 2 <= n % 10 <= 9 and not 11 <= n % 100 <= 19:
        return "few"
    return "other"


def _latvian(n: int) -> str:
    if n % 10 == 0 or 11 <= n % 100 <= 19:
        return "zero"
    if n % 10 == 1 and n % 100 != 11:
        return "one"
    return "other"


def _romanian(n: int) -> str:
    if n == 1:
        return "one"
    if n == 0 or 2 <= n % 100 <= 19:
        return "few"
    return "other"


def _slovenian(n: int) -> str:
    return {1: "one", 2: "two", 3: "few", 4: "few"}.get(n % 100, "other")


def _arabic(n: int) -> str:
    if n in (0, 1, 2):
        return ("zero", "one", "two")[n]
    if 3 <= n % 100 <= 10:
        return "few"
    if 11 <= n % 100 <= 99:
        return "many"
    return "other"


def _hebrew(n: int) -> str:
    return {1: "one", 2: "two"}.get(n, "other")


def _irish(n: int) -> str:
    if n in (1, 2):
        return ("one", "two")[n - 1]
    if 3 <= n <= 6:
        return "few"
    return "many" if 7 <= n <= 10 else "other"


def _welsh(n: int) -> str:
    return {0: "zero", 1: "one", 2: "two", 3: "few", 6: "many"}.get(n, "other")


def _icelandic(n: int) -> str:  # is, mk
    return "one" if n % 10 == 1 and n % 100 != 11 else "other"


RULES = {
    **dict.fromkeys(("ja", "ko", "zh", "yue", "vi", "th", "id", "ms", "km", "lo", "my", "jv", "su", "bo", "dz"), _only_other),
    **dict.fromkeys(("fr", "pt", "hy", "ff", "kab", "hi", "bn", "gu", "kn", "mr", "zu", "am", "fa", "as"), _one_for_0_1),
    **dict.fromkeys(("ru", "uk", "be"), _east_slavic),
    **dict.fromkeys(("hr", "sr", "bs"), _south_slavic),
    "pl": _polish, "cs": _czech, "sk": _czech, "lt": _lithuanian, "lv": _latvian, "ro": _romanian, "mo": _romanian,
    "sl": _slovenian, "ar": _arabic, "he": _hebrew, "iw": _hebrew, "ga": _irish, "cy": _welsh, "is": _icelandic,
    "mk": _icelandic,
}
# Regions whose rule differs from their language's.
REGIONS = {"pt-pt": _one_for_1}


def rule(language: str):
    tag = (language or "en").replace("_", "-").lower()
    parts = tag.split("-")
    for depth in range(len(parts), 0, -1):
        found = REGIONS.get("-".join(parts[:depth]))
        if found:
            return found
    return RULES.get(parts[0], _one_for_1)


def category(language: str, n: int) -> str:
    """The plural category of the whole number n in language (a BCP 47 tag such as "pt-BR")."""
    return rule(language)(abs(int(n)))


def categories(language: str) -> frozenset[str]:
    """Every category language uses for whole numbers."""
    pick = rule(language)
    return frozenset(pick(n) for n in range(0, 1200))
