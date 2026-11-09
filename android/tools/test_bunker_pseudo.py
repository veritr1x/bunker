"""Nothing on Bunker's own pages stays English when another language is chosen.

Every Pod Programs and Archive template is rendered in a pseudo language (each catalogue text wrapped in ⟦…⟧).
What the page shows (its text, its title/placeholder/aria-label/alt attributes; not scripts or styles) may then
hold letters only inside ⟦…⟧, apart from the NieR flavour lines (bunker_text_allow.json). Data a page would show
is missing here (undefined values render empty), so this sees each page's own text; the catalogue lint
(test_bunker_catalogue.py) reads every branch of the source."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
import bunker_text  # noqa: E402

POD = ROOT / "overlays/python/web/templates"
ARCHIVE = ROOT / "android/app/src/main/python/archive/templates"
ALLOW = json.loads((Path(__file__).with_name("bunker_text_allow.json")).read_text(encoding="utf-8"))
CONVERTED = json.loads((Path(__file__).with_name("bunker_text_converted.json")).read_text(encoding="utf-8"))
BRACKETED = re.compile(r"⟦[^⟦⟧]*⟧")


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "title"):
            self.skip += 1
        for name, value in attrs:
            if name in ("title", "placeholder", "aria-label", "alt") and value:
                self.text.append(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "title"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def english_left(html: str) -> list[str]:
    parser = _Visible()
    parser.feed(html)
    shown = BRACKETED.sub(" ", "\n".join(parser.text))
    for line in ALLOW["flavour"]:
        shown = shown.replace(line, " ")
    words = re.findall(r"\S+", shown)
    # Literal words that stay as they are (the info icon's "i", the RESTORE a player types to confirm).
    return [w for w in words if any(unicodedata.category(ch).startswith("L") for ch in w) and w not in ALLOW["literal"]]


class _Anything:
    """Stands in for page data: renders empty, iterates as nothing, calls and attributes give more of itself."""
    def __getattr__(self, name): return self
    def __call__(self, *a, **k): return self
    def __getitem__(self, key): return self
    def __iter__(self): return iter(())
    def __len__(self): return 0
    def __bool__(self): return False
    def __str__(self): return ""
    def __html__(self): return ""
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __index__(self): return 0
    def __round__(self, n=0): return 0
    def __lt__(self, other): return False
    __gt__ = __le__ = __ge__ = __lt__
    def __eq__(self, other): return False
    def __hash__(self): return 0
    def __add__(self, other): return self
    __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = __mod__ = __add__


def environment(folder: Path):
    import jinja2

    class Missing(jinja2.ChainableUndefined):
        # Page data and the apps' helpers (asset(), img(), …): callable, formattable, empty.
        def __call__(self, *args, **kwargs): return self
        def __format__(self, spec): return ""
        def __iter__(self): return iter(())
        def __int__(self): return 0
        def __float__(self): return 0.0
        def __round__(self, n=0): return 0
        def __lt__(self, other): return False
        __gt__ = __le__ = __ge__ = __lt__

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(folder)), autoescape=True, undefined=Missing)
    for name in ("rich", "prose", "plain", "quoted", "tojson", "lower", "round", "int"):
        env.filters.setdefault(name, lambda value, *a, **k: "")
    env.filters["tojson"] = lambda value, *a, **k: "null"
    bunker_text.install(env)
    return env


class PseudoLanguage(unittest.TestCase):
    def setUp(self):
        self.addCleanup(bunker_text.use, None)
        bunker_text.use({key: "⟦" + value + "⟧" for key, value in bunker_text.english().items()})

    def test_everything_converted(self):
        templates = {p.relative_to(ROOT).as_posix() for folder in (POD, ARCHIVE) for p in folder.glob("*.html")}
        self.assertEqual(sorted(templates - set(CONVERTED["templates"])), [])

    def test_pseudo_language_pages(self):
        left = {}
        for folder in (POD, ARCHIVE):
            env = environment(folder)
            for path in sorted(folder.glob("*.html")):
                if path.name.startswith("_"):
                    continue
                try:
                    html = env.get_template(path.name).render(request=_Anything(), active="", theme="")
                except Exception as exc:  # a page that cannot render without its data: the lint covers it
                    left[f"{folder.parent.name}/{path.name}"] = [f"(not rendered: {type(exc).__name__}: {exc})"]
                    continue
                words = english_left(html)
                if words:
                    left[f"{folder.parent.name}/{path.name}"] = sorted(set(words))[:12]
        failed = {k: v for k, v in left.items() if not v[0].startswith("(not rendered")}
        self.assertEqual(failed, {})
        rendered = sum(1 for folder in (POD, ARCHIVE) for p in folder.glob("*.html") if not p.name.startswith("_"))
        self.assertLessEqual(len(left), rendered // 4, f"too many pages could not render: {left}")

    def test_the_check_sees_english(self):
        self.assertEqual(english_left('<p>⟦Hello⟧ there</p><b title="Tip">⟦x⟧</b><script>var a = "No";</script>'),
                         ["there", "Tip"])
        self.assertEqual(english_left("<footer>End of transmission // Glory to mankind</footer><p>⟦a b⟧ 12 ×3</p>"), [])


if __name__ == "__main__":
    unittest.main()
