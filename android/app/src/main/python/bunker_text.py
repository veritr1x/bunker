"""Bunker's own text: Pod Programs' and the Archive's words, in the chosen language with English fallback.

The English catalogue is translations/bunker/en.json (scripts/prepare.py copies it beside this file as
bunker_en.json); a language pack's "bunker" object translates it, key by key. t("pods.language.title")
gives the chosen language's text; a missing, empty or broken translation (a placeholder it lacks or adds,
a stray brace) gives the English instead. t_count picks the ".one" or ".other" form of a key by a count.
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path
from string import Formatter

_HERE = Path(__file__).resolve().parent
# From the repository (tests, tools): translations/, which a prepared copy would lag behind. On the device:
# the copy beside this file (scripts/prepare.py).
_CATALOGUES = tuple(p / "translations/bunker/en.json" for p in _HERE.parents[4:5]) + (_HERE / "bunker_en.json",)

_english: dict[str, str] | None = None
_extra: dict[str, str] = {}
_translation: dict[str, str] = {}
_language = "en"
_loaded: tuple | None = None


def english() -> dict[str, str]:
    """The English catalogue."""
    global _english
    if _english is None:
        for path in _CATALOGUES:
            if path.is_file():
                _english = json.loads(path.read_text(encoding="utf-8"))
                break
        else:
            _english = {}
    return _english


def use(texts: dict | None, language: str | None = None) -> None:
    """Translate with these texts, in this language (its plural forms), from now on (None: English only).
    Non-text values are ignored."""
    global _translation, _language, _loaded
    _translation = {key: value for key, value in (texts or {}).items()
                    if isinstance(key, str) and isinstance(value, str) and value}
    _language = language if texts and isinstance(language, str) and language else "en"
    _loaded = None


def plural_category(language_tag: str, n: int) -> str:
    """The plural category ("one", "few", "other"…) of the whole number n in a language."""
    import bunker_plurals
    return bunker_plurals.category(language_tag, n)


def language() -> str:
    """The language the texts are in (a BCP 47 tag), "en" without a translation."""
    return _language


@contextlib.contextmanager
def extra(texts: dict[str, str]):
    """More English texts for a while (tests)."""
    _extra.update(texts)
    try:
        yield
    finally:
        for key in texts:
            _extra.pop(key, None)


def _fields(text: str) -> list | None:
    """The placeholders in text, each with its format spec and conversion (a loaded pack is untrusted:
    "{n:99999999}" would build a huge string), or None when it is not a valid format string."""
    try:
        return sorted((name, spec or "", conversion or "") for _, name, spec, conversion in Formatter().parse(text)
                      if name is not None)
    except ValueError:
        return None


def t(key: str, **params) -> str:
    """The chosen language's text for key, else English; the key itself when the catalogue lacks it."""
    base = _extra.get(key) or english().get(key)
    if base is None:
        return key
    translated = _translation.get(key)
    if translated is not None and _fields(translated) == _fields(base):
        try:
            return translated.format(**params)
        except (KeyError, IndexError, ValueError):
            pass
    try:
        return base.format(**params)
    except (KeyError, IndexError, ValueError):
        return base


def _english_text(key: str) -> str | None:
    return _extra.get(key) or english().get(key)


def _translated_forms(key: str) -> dict[str, str] | None:
    """The translation's plural forms of key, when they cover every form its language uses and each takes only
    placeholders the English has (a form may leave out {n}: "one file"); otherwise None (the English is used)."""
    import bunker_plurals
    other = _english_text(f"{key}.other")
    if other is None or not _translation:
        return None
    allowed = _fields(other)
    forms = {}
    for category in bunker_plurals.categories(_language):
        text = _translation.get(f"{key}.{category}")
        fields = _fields(text) if text is not None else None
        if fields is None or allowed is None or not set(fields) <= set(allowed):
            return None
        forms[category] = text
    for category in bunker_plurals.CATEGORIES:  # extra forms a script may fall back on ("other")
        text = _translation.get(f"{key}.{category}")
        if category not in forms and text is not None and (fields := _fields(text)) is not None \
                and set(fields) <= set(allowed):
            forms[category] = text
    return forms


def t_count(key: str, n: int, **params) -> str:
    """key in the plural form the language uses for n (".one", ".few", ".other"…); {n} is the count. A translation
    missing a form its language needs gives the English text (".one" for 1, ".other" otherwise)."""
    import bunker_plurals
    forms = _translated_forms(key)
    if forms is not None:
        try:
            return forms[bunker_plurals.category(_language, n)].format(n=n, **params)
        except (KeyError, IndexError, ValueError):
            pass
    base = _english_text(f"{key}.one" if n == 1 else f"{key}.other")
    if base is None:
        return f"{key}.other"
    try:
        return base.format(n=n, **params)
    except (KeyError, IndexError, ValueError):
        return base


def plural_forms(key: str) -> dict[str, str]:
    """A counted text's forms for a page script, which picks one with Intl.PluralRules(language()): the
    translation's when complete, else English's one/other. Placeholders are left for the script to fill."""
    forms = _translated_forms(key)
    if forms is not None:
        return forms
    return {category: text for category in ("one", "other")
            if (text := _english_text(f"{key}.{category}")) is not None}


_SLOT = "\x00"   # stands where the slot goes while the text is formatted


def t_around(key: str, slot: str, **params) -> tuple[str, str]:
    """A sentence around a control or a link ("Allow up to {select} pieces to be added."): its text before and
    after {slot}, for a page to put its markup between (each piece escaped as text). A translation that lacks
    the slot, or has it more than once, gives the English, as t() does for any broken translation."""
    text = t(key, **params, **{slot: _SLOT})
    if text.count(_SLOT) != 1:
        base = _extra.get(key) or english().get(key) or key
        try:
            text = base.format(**params, **{slot: _SLOT})
        except (KeyError, IndexError, ValueError):
            text = base
    before, _, after = text.partition(_SLOT)
    return before, after


def install(target) -> None:
    """Gives templates t, t_count and t_around (a Jinja2Templates, or a jinja2 Environment)."""
    env = getattr(target, "env", target)
    env.globals.update(t=t, t_count=t_count, t_around=t_around, plural_forms=plural_forms, text_language=language)


def install_everywhere() -> None:
    """Every Jinja2Templates made from now on gets t and t_count: Bunker's route modules and lunar-base's
    each make their own (android_runtime.create_app calls this before importing them)."""
    from fastapi.templating import Jinja2Templates
    if getattr(Jinja2Templates, "_bunker_text", False):
        return
    original = Jinja2Templates.__init__

    def __init__(self, *args, **kwargs):
        original(self, *args, **kwargs)
        install(self)
    Jinja2Templates.__init__ = __init__
    Jinja2Templates._bunker_text = True


def reload(active: Path | None = None) -> None:
    """Use the "bunker" texts of the pack the server applies (its translation/active.json); English when
    there is none or it cannot be read. Cheap when the file has not changed."""
    global _loaded
    if active is None:
        import bunker_language
        from web import config
        active = bunker_language.for_config(config).active_path
    try:
        stat = active.stat()
        stamp = (str(active), stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = (str(active), None, None)
    if stamp == _loaded:
        return
    texts, language_tag = None, None
    if stamp[1] is not None:
        try:
            pack = json.loads(active.read_text(encoding="utf-8"))
            if isinstance(pack, dict) and isinstance(pack.get("bunker"), dict):
                texts, language_tag = pack["bunker"], pack.get("language")
        except (OSError, UnicodeDecodeError, ValueError):
            texts = None
    use(texts, language_tag)
    _loaded = stamp
