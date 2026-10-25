import gc
import sys
import unittest
import weakref
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app/src/main/python"))

from archive.memo import memo  # noqa: E402


class Counter:
    def __init__(self):
        self.calls = 0

    @memo
    def value(self, key="x"):
        self.calls += 1
        return [key, self.calls]


class MemoTest(unittest.TestCase):
    def test_remembers_per_instance_and_arguments(self):
        a, b = Counter(), Counter()
        self.assertIs(a.value(), a.value())
        self.assertEqual(a.value("y"), ["y", 2])
        self.assertEqual(a.calls, 2)
        self.assertEqual(b.value(), ["x", 1])

    def test_results_go_with_the_instance(self):
        c = Counter()
        result = c.value()
        gone = weakref.ref(c)
        del c
        gc.collect()
        self.assertIsNone(gone())
        self.assertEqual(result, ["x", 1])


if __name__ == "__main__":
    unittest.main()
