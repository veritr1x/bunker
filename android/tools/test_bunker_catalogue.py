"""Bunker's own text stays in its catalogue (translations/bunker/en.json, bunker_text.py).

Every key a page or module uses exists, every key in the catalogue is used, each call passes the placeholders
its English names, and the pages and modules already moved to the catalogue (CONVERTED, CONVERTED_PY) show no
English of their own. The NieR flavour lines (bunker_text_allow.json) stay English everywhere."""
from __future__ import annotations

import ast
import json
import re
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from string import Formatter
import unittest

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "android/app/src/main/python"
POD = ROOT / "overlays/python/web/templates"
ARCHIVE = PY / "archive/templates"
ENGLISH = json.loads((ROOT / "translations/bunker/en.json").read_text(encoding="utf-8"))
ALLOW = json.loads((Path(__file__).with_name("bunker_text_allow.json")).read_text(encoding="utf-8"))
ALLOWED = set(ALLOW["flavour"]) | set(ALLOW["literal"])

# Pages and modules whose words all come from the catalogue (bunker_text_converted.json).
_CONVERTED = json.loads((Path(__file__).with_name("bunker_text_converted.json")).read_text(encoding="utf-8"))
CONVERTED: list[Path] = [ROOT / p for p in _CONVERTED["templates"]]
CONVERTED_PY: list[Path] = [ROOT / p for p in _CONVERTED["python"]]

# Where t() calls live.
SOURCES = [*POD.glob("*.html"), *ARCHIVE.glob("*.html"), *PY.glob("android_*.py"),
           *(p for p in PY.glob("bunker_*.py") if p.name != "bunker_text.py"),
           *(PY / "archive").glob("*.py"), *(PY / "deckbuilder").glob("*.py"), ROOT / "ios/python/ios_runtime.py",
           *(ROOT / "patches").glob("lunar-base-*texts*.patch")]
CALL = re.compile(r"\bt(_count|_around)?\(\s*[\"']([a-z0-9_.-]+)[\"']((?:[^()]|\([^()]*\))*)\)")


def calls():
    """(file, key, plural, keyword names) for every t()/t_count()/t_around() call with a literal key (t_around's
    slot, its second argument, counts as a name)."""
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for match in CALL.finditer(text):
            plural, key, rest = match.group(1) == "_count", match.group(2), match.group(3)
            names = set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*=(?!=)", rest))
            if match.group(1) == "_around":
                names |= set(re.findall(r"^\s*,\s*[\"']([a-z_][a-z0-9_]*)[\"']", rest))
            if plural:
                names.add("n")
            yield path, key, plural, names


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name}


def has_letter(text: str) -> bool:
    return any(unicodedata.category(ch).startswith("L") for ch in text)


# A query or one of its clauses, whichever helper runs it: not text anyone reads.
SQL = re.compile(r"^\s*(select|insert|update|delete|with|from|where|order by|group by)\b|\b\w+\s*(=|<|>|<=|>=|!=|in|like)\s*\?|\?\s*,\s*\?", re.I)
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)
STRING = re.compile(r"\"([^\"\\]*)\"|'([^'\\]*)'")


class _Text(HTMLParser):
    ATTRIBUTES = ("title", "placeholder", "aria-label", "alt")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        attrs = dict(attrs)
        for name in self.ATTRIBUTES:
            if attrs.get(name):
                self.found.append(attrs[name])
        if tag == "input" and attrs.get("type") in ("submit", "button") and attrs.get("value"):
            self.found.append(attrs["value"])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.found.append(data.strip())


def template_english(path: Path) -> list[str]:
    """English a template shows of its own: in its HTML, and as a string inside {{ }} / {% %}."""
    source = path.read_text(encoding="utf-8")
    found = []
    for block in JINJA.findall(source):
        if block.startswith("{#"):
            continue
        inside = CALL.sub(lambda m: m.group(0).replace(m.group(2), ""), block)  # a key is not text
        for a, b in STRING.findall(inside):
            text = a or b
            # Words people read: a space between letters, or a capital first (not a key, path, class or value).
            if has_letter(text) and (" " in text.strip() or text[:1].isupper()) and not text.endswith(".html"):
                found.append(text)
    parser = _Text()
    parser.feed(JINJA.sub(" ", source))
    found += [text for text in parser.found if has_letter(text)]
    return [text for text in found if text not in ALLOWED]


class _Strings(ast.NodeVisitor):
    """String constants a module shows: returned, passed, stored or put in a dict (not docstrings, logging,
    patterns, dict keys or lookups)."""
    QUIET = {"debug", "info", "warning", "error", "exception", "critical", "print", "compile", "match", "search",
             "fullmatch", "sub", "split", "findall", "execute", "executemany", "get", "getattr", "setdefault",
             "startswith", "endswith", "replace", "join", "format", "strftime", "strptime", "Path", "open",
             "joinpath", "with_name", "with_suffix", "glob", "rglob", "encode", "decode", "partition", "rpartition",
             "t", "t_count", "t_around", "router", "post", "get_template", "TemplateResponse", "redirect_to", "jclass"}

    def __init__(self):
        self.found = []

    def visit_Call(self, node):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in self.QUIET:
            return
        self.generic_visit(node)

    def visit_Expr(self, node):  # docstrings and bare strings
        if isinstance(node.value, ast.Constant):
            return
        self.generic_visit(node)

    def visit_Subscript(self, node):
        self.visit(node.value)

    def visit_Dict(self, node):
        for value in node.values:
            self.visit(value)

    def visit_Compare(self, node):
        return

    def visit_Constant(self, node):
        if isinstance(node.value, str) and has_letter(node.value) and " " in node.value.strip() \
                and node.value not in ALLOWED and not SQL.search(node.value):
            self.found.append((node.lineno, node.value))

    def visit_JoinedStr(self, node):
        text = "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
        if has_letter(text) and " " in text.strip() and not SQL.search(text):
            self.found.append((node.lineno, text))


def python_english(path: Path) -> list[tuple[int, str]]:
    visitor = _Strings()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
    return visitor.found


class Catalogue(unittest.TestCase):
    def test_used_keys_exist(self):
        missing = []
        for path, key, plural, _ in calls():
            wanted = [f"{key}.one", f"{key}.other"] if plural else [key]
            missing += [f"{path.relative_to(ROOT)}: {k}" for k in wanted if k not in ENGLISH]
        self.assertEqual(missing, [])

    def test_no_unused_keys(self):
        used = set()
        for _, key, plural, _ in calls():
            used |= {f"{key}.one", f"{key}.other"} if plural else {key}
        unused = [key for key in ENGLISH if key not in used and not key.startswith(tuple(ALLOW["dynamic"]))]
        self.assertEqual(unused, [])

    def test_params_match(self):
        wrong = []
        for path, key, plural, names in calls():
            for k in ([f"{key}.one", f"{key}.other"] if plural else [key]):
                if k in ENGLISH and not fields(ENGLISH[k]) <= names:
                    wrong.append(f"{path.relative_to(ROOT)}: {k} needs {sorted(fields(ENGLISH[k]))}, gets {sorted(names)}")
        self.assertEqual(wrong, [])

    def test_every_bunker_template_set_has_t(self):
        # Each route module makes its templates as it is imported, before create_app's hook can apply.
        for path in sorted([*PY.glob("android_*.py"), PY / "archive/app.py"]):
            source = path.read_text(encoding="utf-8")
            if "Jinja2Templates(" in source:
                self.assertIn("bunker_text.install(templates)", source, path.name)

    def test_catalogue_is_sorted_plain_text(self):
        self.assertEqual(list(ENGLISH), sorted(ENGLISH))
        for key, value in ENGLISH.items():
            self.assertRegex(key, r"^(common|pods|archive)\.[a-z0-9_.-]+$")
            self.assertIsInstance(value, str)
            self.assertNotRegex(value, r"<[A-Za-z/]", key)  # no HTML in the catalogue

    def test_no_literal_text_in_templates(self):
        left = {str(path.relative_to(ROOT)): template_english(path) for path in CONVERTED}
        self.assertEqual({k: v for k, v in left.items() if v}, {})

    def test_no_literal_messages_in_python(self):
        left = {str(path.relative_to(ROOT)): python_english(path) for path in CONVERTED_PY}
        self.assertEqual({k: v for k, v in left.items() if v}, {})

    def test_the_lint_sees_english(self):
        # The checks above are only as good as these two finders.
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "p.html"
            page.write_text('<h1>Title</h1><input placeholder="Search here">{{ info("Some help.") }}'
                            '{{ t("pods.x") }}{% if key == "comfort" %}<b>{{ name }}</b>{% endif %}<script>var a = "No";</script>'
                            '<footer>End of transmission // Glory to mankind</footer>')
            self.assertEqual(sorted(template_english(page)), ["Search here", "Some help.", "Title"])
            module = Path(folder) / "m.py"
            module.write_text('"""Docs here."""\nimport logging\nlog = logging.getLogger("x")\n'
                              'def f(x):\n    log.warning("Not this one")\n    if x == "a b":\n        return t("pods.y")\n'
                              '    return redirect(error="Choose a language first.")\nMESSAGE = f"Saved {x} now"\n'
                              'q("select costume_id from user_costumes where user_id=?")\nrows(1, "description_gift_text_id = ?")\n'
                              'q(f"select id from {table} where user_id=?")\n')
            self.assertEqual([text for _, text in python_english(module)], ["Choose a language first.", "Saved  now"])


if __name__ == "__main__":
    unittest.main()
