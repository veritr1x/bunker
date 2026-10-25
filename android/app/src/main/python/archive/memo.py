"""Results remembered on the object that computed them."""
from __future__ import annotations

import functools


def memo(method):
    """Remembers a method's results on its instance, so they go when the instance does.

    functools.cache on a method keeps every instance, and all it returned, for as long
    as Python runs, which on iOS is as long as the game."""
    name = "_memo_" + method.__name__

    @functools.wraps(method)
    def remembered(self, *args):
        results = self.__dict__.setdefault(name, {})
        if args not in results:
            results[args] = method(self, *args)
        return results[args]

    return remembered
