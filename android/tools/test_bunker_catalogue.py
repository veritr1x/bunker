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
CALL = re.compile(r"\b(t_count|t_around|plural_forms|t)\(\s*[\"']([a-z0-9_.-]+)[\"']((?:[^()]|\([^()]*\))*)\)")
FORMS = re.compile(r"\bplural_forms\(\s*[\"']([a-z0-9_.-]+)[\"']\s*\)")


def calls():
    """(file, key, plural, keyword names) for every t()/t_count()/t_around()/plural_forms() call with a literal
    key (t_around's slot, its second argument, counts as a name; plural_forms leaves every placeholder to the
    page's script)."""
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for match in CALL.finditer(text):
            plural, key, rest = match.group(1) in ("t_count", "plural_forms"), match.group(2), match.group(3)
            names = set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*=(?!=)", rest))
            if match.group(1) == "plural_forms":
                names |= {name for form in ("one", "other") for name in fields(ENGLISH.get(f"{key}.{form}", ""))}
            if match.group(1) == "t_around":
                names |= set(re.findall(r"^\s*,\s*[\"']([a-z_][a-z0-9_]*)[\"']", rest))
            if plural:
                names.add("n")
            yield path, key, plural, names
        # plural_forms("key") hands a page script every form with its placeholders, which the script fills.
        for match in FORMS.finditer(text):
            key = match.group(1)
            yield path, key, True, fields(ENGLISH.get(f"{key}.other", "")) | {"n"}


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
             "t", "t_count", "t_around", "plural_forms", "router", "post", "get_template", "TemplateResponse", "redirect_to", "jclass"}

    def __init__(self):
        self.found = []

    # Arguments that name what a page shows: a single word there is English too ("Saved", "Owned").
    LABELS = {"message", "error", "label", "title", "detail", "text", "note", "status", "caption", "heading"}

    def visit_Call(self, node):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in self.QUIET or name == "FastAPI":
            return
        for keyword in node.keywords:
            value = keyword.value
            if keyword.arg in self.LABELS and isinstance(value, ast.Constant) and isinstance(value.value, str) \
                    and has_letter(value.value) and " " not in value.value.strip() and value.value not in ALLOWED:
                self.found.append((value.lineno, value.value))
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


SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.S)
# A comment: "//" starting a line or after code (not inside "http://"), or /* … */.
JS_COMMENT = re.compile(r"(^|[\s;{}(,])//[^\n]*|/\*.*?\*/", re.S)
JS_STRING = re.compile(r"\"((?:[^\"\\\n]|\\.)*)\"|'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`")


def script_english(path: Path) -> list[str]:
    """English in a template's page scripts: string literals that read as words people see (two words or more,
    with a capital or sentence punctuation or three words), not selectors, CSS, keys or code."""
    found = []
    for block in SCRIPT.findall(path.read_text(encoding="utf-8")):
        block = JINJA.sub("\"\"", block)
        block = JS_COMMENT.sub(lambda m: m.group(1) or "", block)
        for match in JS_STRING.finditer(block):
            text = next(g for g in match.groups() if g is not None)
            text = re.sub(r"\$\{[^}]*\}", " ", text)  # a template literal's ${…} is code
            # Words people read: whitespace-separated, letters only (an id, class or key has - _ or .).
            words = [w for w in re.split(r"\s+", re.sub(r"[,.!?…]+(\s|$)", " ", text)) if len(w) >= 2 and w.isalpha()]
            if len(words) < 2 or re.search(r"[:;#\[\](){}=<>/\\|]", text) or text in ALLOWED:
                continue
            if any(w[0].isupper() for w in words) or re.search(r"[.!?]\s*$", text.strip()) or len(words) >= 3:
                found.append(text.strip())
    return found


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

    def test_placeholders_are_plain_names(self):
        # Python, Java and Objective-C fill {name} alike; a spec ({n:,}), a conversion ({x!r}), a position ({})
        # or an attribute ({a.b}) would only work in Python.
        odd = {}
        for key, text in ENGLISH.items():
            for _, name, spec, conversion in Formatter().parse(text):
                if name is not None and (spec or conversion or not re.fullmatch(r"[a-z_][a-z0-9_]*", name)):
                    odd[key] = text
        self.assertEqual(odd, {})

    def test_numbers_are_written_in_the_pages_language(self):
        # Templates: number(n). Python: bunker_text.number. Scripts: Intl.NumberFormat with the page's language.
        english = re.compile(r"\{[a-z_0-9.\[\]'\"]*:,|\"\{:,\}\"|toLocaleString\(\)|toFixed\(")
        found = {str(path.relative_to(ROOT)): english.findall(path.read_text(encoding="utf-8"))
                 for path in CONVERTED + CONVERTED_PY}
        self.assertEqual({k: v for k, v in found.items() if v}, {})

    def test_no_english_in_page_scripts(self):
        left = {str(path.relative_to(ROOT)): script_english(path) for path in CONVERTED}
        self.assertEqual({k: v for k, v in left.items() if v}, {})

    def test_upstream_routes_add_no_new_english(self):
        # lunar-base's routes keep a few English messages players only see after a malformed request
        # (bunker_text_allow.json "upstream"). A lunar-base update that adds English shows up here.
        routes = PY / "web/routes"
        if not routes.is_dir():
            self.skipTest("run scripts/prepare.py first")
        found = {text for path in routes.glob("*.py") for _, text in python_english(path)}
        self.assertEqual(sorted(found - set(ALLOW["upstream"])), [])

    def test_the_lint_sees_english_in_scripts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "p.html"
            page.write_text('<script>\n// the game\'s portrait\nconst a = "Network error", b = "button.on", c = "Escape";\n'
                            'const d = `${x} items left now`, e = "display:flex;gap:4px", f = "script, style";\n'
                            'const h = "tl-art small", i = "limit_break_count", j = "en-US";\n'
                            'fetch("http://x/y"); alert("Saved."); const g = {{ t("pods.x")|tojson }};</script>')
            self.assertEqual(script_english(page), ["Network error", "items left now"])
            module = Path(folder) / "m.py"
            module.write_text('def f():\n    return redirect(message="Saved", error="bad request")\napp = FastAPI(title="Archive")\n')
            self.assertEqual([text for _, text in python_english(module)], ["Saved", "bad request"])

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
