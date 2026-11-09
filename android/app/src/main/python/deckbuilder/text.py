"""Deck Builder's words, made when they are shown.

Results, reasons and labels are worked out once and kept (a session holds them for many requests), while the
player can change Pod Programs' language at any time. So what a deck says is kept as a Later: a recipe that
calls bunker_text.t when the text is shown (str()), in the language chosen at that moment. A Later compares,
measures and searches as its text does, so it can stand where a str stood; JSON gets str(later).
"""
from __future__ import annotations


class Later:
    """Text made when shown: str(later) runs make() (which calls bunker_text.t) each time."""
    __slots__ = ("_make",)

    def __init__(self, make):
        self._make = make

    def __str__(self):
        return self._make()

    def __repr__(self):
        return repr(str(self))

    def __eq__(self, other):
        return str(self) == (str(other) if isinstance(other, Later) else other)

    def __hash__(self):
        return hash(str(self))

    def __contains__(self, part):
        return part in str(self)

    def __len__(self):
        return len(str(self))

    def __format__(self, spec):
        return format(str(self), spec)


def shown(value):
    """value as text for the page: a Later made now, anything else as it is."""
    return str(value) if isinstance(value, Later) else value
