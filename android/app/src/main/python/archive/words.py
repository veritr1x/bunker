"""Bunker's words inside what the Archive works out ahead of time (the index, the Schedule).

The index and the Schedule are built once and kept; the language can change at any time after. So
they keep a reference to a catalogue text (t below) instead of the words, and said() puts the words,
in the language chosen now, in place of each reference when a page reads them. A reference can sit
inside a longer string (a name, " · ", then a reference) and its values can hold
references of their own."""
from __future__ import annotations

import json
import re

import bunker_text

_START, _END = "\x1f", "\x1e"
_REFERENCE = re.compile(_START + "(.*?)" + _END, re.S)


def t(key: str, **params) -> str:
    """A reference to the catalogue text key with these values, to keep and show later with said()."""
    return _START + json.dumps([key, params], ensure_ascii=False, separators=(",", ":")) + _END


def t_count(key: str, n: int, **params) -> str:
    """t() for key's ".one" form for a count of 1, else its ".other" form; {n} is the count."""
    return t(f"{key}.one" if n == 1 else f"{key}.other", n=n, **params)


def _words(match: re.Match) -> str:
    try:
        key, params = json.loads(match.group(1))
    except ValueError:
        return ""
    return bunker_text.t(key, **{name: said(value) if isinstance(value, str) else value for name, value in params.items()})


def said(text):
    """text with every reference in it put in words; anything else as it is."""
    if isinstance(text, str) and _START in text:
        return _REFERENCE.sub(_words, text)
    return text


def resolve(data):
    """A copy of data (dicts, lists, strings) with every reference put in words."""
    if isinstance(data, dict):
        return {key: resolve(value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [resolve(value) for value in data]
    return said(data)
