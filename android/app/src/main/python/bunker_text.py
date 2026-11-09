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


def use(texts: dict | None) -> None:
    """Translate with these texts from now on (None: English only). Non-text values are ignored."""
    global _translation, _loaded
    _translation = {key: value for key, value in (texts or {}).items()
                    if isinstance(key, str) and isinstance(value, str) and value}
    _loaded = None


@contextlib.contextmanager
def extra(texts: dict[str, str]):
    """More English texts for a while (tests)."""
    _extra.update(texts)
    try:
        yield
    finally:
        for key in texts:
            _extra.pop(key, None)


def _fields(text: str) -> set[str] | None:
    """The placeholder names in text, or None when it is not a valid format string."""
    try:
        return {name for _, name, _, _ in Formatter().parse(text) if name is not None}
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


def t_count(key: str, n: int, **params) -> str:
    """key's ".one" form for a count of 1, its ".other" form otherwise; {n} is the count."""
    return t(f"{key}.one" if n == 1 else f"{key}.other", n=n, **params)


def install(target) -> None:
    """Gives templates t and t_count (a Jinja2Templates, or a jinja2 Environment)."""
    env = getattr(target, "env", target)
    env.globals.update(t=t, t_count=t_count)


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
    texts = None
    if stamp[1] is not None:
        try:
            pack = json.loads(active.read_text(encoding="utf-8"))
            if isinstance(pack, dict) and isinstance(pack.get("bunker"), dict):
                texts = pack["bunker"]
        except (OSError, UnicodeDecodeError, ValueError):
            texts = None
    use(texts)
    _loaded = stamp
