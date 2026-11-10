"""How each language writes a number (CLDR, Latin digits): the group and decimal separators, whether a
four-digit number is grouped, and Indian grouping (12,34,567). Page scripts use Intl.NumberFormat with
the same language; test_bunker_text checks the two agree."""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

COMMA, DOT, NBSP, NNBSP, APOSTROPHE = ",", ".", " ", " ", "'"

# group separator, decimal separator, fewest digits grouped (5: "1200" but "12 000"), Indian grouping
_COMMA = (COMMA, DOT, 4, False)
_DOT = (DOT, COMMA, 4, False)
_DOT_5 = (DOT, COMMA, 5, False)
_SPACE = (NBSP, COMMA, 4, False)
_SPACE_5 = (NBSP, COMMA, 5, False)
_INDIAN = (COMMA, DOT, 4, True)
_SWISS = (APOSTROPHE, DOT, 4, False)

GROUPS = {
    **dict.fromkeys(("en", "ja", "zh", "ko", "ar", "he", "ms", "th", "fa", "ur", "kn", "si", "km", "my", "mn",
                     "sw", "zu", "fil", "ga", "cy", "mt", "am"), _COMMA),
    **dict.fromkeys(("hi", "bn", "mr", "ta", "te", "gu", "ml", "pa", "ne"), _INDIAN),
    **dict.fromkeys(("de", "pt", "nl", "tr", "da", "id", "vi", "ro", "el", "hr", "sr", "bs", "mk", "ca", "eu",
                     "gl", "lo", "az", "is", "ps", "lb"), _DOT),
    **dict.fromkeys(("es", "it", "sl"), _DOT_5),
    **dict.fromkeys(("ru", "cs", "sv", "nb", "no", "nn", "fi", "uk", "lt", "sk", "kk", "uz", "af", "ky", "tg"),
                    _SPACE),
    **dict.fromkeys(("pl", "be", "hu", "bg", "et", "lv", "sq", "ka", "hy"), _SPACE_5),
    "fr": (NNBSP, COMMA, 4, False),
}
# Regions that write numbers differently from their language.
REGIONS = {
    **dict.fromkeys(("de-ch", "de-li", "en-ch"), _SWISS),
    "fr-ch": (APOSTROPHE, COMMA, 4, False),
    "it-ch": (APOSTROPHE, DOT, 5, False),
    **dict.fromkeys(("es-mx", "es-419", "es-us"), _COMMA),
    **dict.fromkeys(("de-at", "fr-ca", "en-za"), _SPACE),
    "pt-pt": _SPACE_5,
    "en-in": _INDIAN,
}


def style(language: str) -> tuple[str, str, int, bool]:
    parts = (language or "en").replace("_", "-").lower().split("-")
    for depth in range(len(parts), 1, -1):
        found = REGIONS.get("-".join(parts[:depth]))
        if found:
            return found
    return GROUPS.get(parts[0], _COMMA)


def write(language: str, n) -> str:
    """The number n as language writes it: grouped, up to three decimal places (as Intl.NumberFormat)."""
    group, decimal, smallest, indian = style(language)
    if isinstance(n, bool) or not isinstance(n, (int, float)) or n != n or n in (float("inf"), float("-inf")):
        return str(n)  # not a number (a placeholder, a missing value): shown as it is
    if isinstance(n, float):
        # Intl rounds half away from zero on the number's exact decimal value
        exact = Decimal(n).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    else:
        exact = Decimal(int(n)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    whole, _, fraction = f"{abs(exact):f}".partition(".")
    fraction = fraction.rstrip("0")
    if len(whole) >= smallest:
        groups = [whole[-3:]]
        rest, size = whole[:-3], 2 if indian else 3
        while rest:
            groups.insert(0, rest[-size:])
            rest = rest[:-size]
        whole = group.join(groups)
    written = whole + (decimal + fraction if fraction else "")
    return "-" + written if exact < 0 else written
