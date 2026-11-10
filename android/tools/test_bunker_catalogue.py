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
# The launchers' Java: Texts.t(context, "key", "name", value…), Texts.count(context, "key", n, "name", value…),
# Texts.tOr(context, "key", shown_instead, …), Texts.around(context, "key", "slot", …), Said.text/count("key", …).
JAVA_SOURCES = sorted((ROOT / "android/app/src/main/java/org/veritr1x/bunker").glob("*.java"))
JAVA_CALL = re.compile(r"\b(?:Texts\.(t|tOr|count|around)\(\s*[^,()\"]+,|Said\.(text|count)\()\s*\"([a-z0-9_.-]+)\"(?!\s*\+)")


def java_arguments(text: str, at: int) -> list[str]:
    """The arguments after a call's key, from just after the key's closing quote to the call's ")"."""
    args, depth, quote, start = [], 0, None, at
    for i in range(at, len(text)):
        ch = text[i]
        if quote:
            if ch == "\\":
                continue
            if ch == quote and text[i - 1] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                args.append(text[start:i])
                break
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(text[start:i])
            start = i + 1
    return [a.strip() for a in args[1:]]  # args[0] is what lies between the key and its first comma: nothing


def java_strings(text: str):
    """(line, literal, offset) for each string literal in Java source, comments skipped, escapes kept as written."""
    i, line, n = 0, 1, len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                return
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            line += text.count("\n", i, end)
            i = end + 2
            continue
        elif ch == "'":
            # a char literal: 'a', '\\'', '\\\\', '\\u0041'; the closing quote comes after the escape
            j = i + 3 if text[i + 1] == "\\" else i + 2
            i = text.find("'", j) + 1
            continue
        elif ch == '"':
            j = i + 1
            while text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            yield line, text[i + 1:j], i
            i = j + 1
            continue
        i += 1


# Java literals that are not words: ids, keys, file names, MIME types, intent actions, preference names.
JAVA_CODE = re.compile(r"[a-z0-9_-]+|[^\s]*[/._:=@#<>\\%][^\s]*|[a-z]+[A-Z][A-Za-z0-9]*|[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+"
                       r"|[A-Z]+-[0-9]+")
LOGGED = re.compile(r"(Log\.[dewiv]|NativeBridge\.log|Log\.wtf)\(")


def java_english(path: Path) -> list[tuple[int, str]]:
    """Words people read in a launcher Java file: literals with letters that are not code-like, outside log
    calls, the flavour, and the Java allowlist."""
    text = path.read_text(encoding="utf-8")
    allowed = ALLOWED | set(ALLOW.get("java", []))
    # What log calls say stays English: the literals between a Log…( and its closing parenthesis.
    logged = []
    for match in LOGGED.finditer(text):
        depth, i = 0, match.end()
        quote = None
        while i < len(text):
            ch = text[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            i += 1
        logged.append((match.end(), i))
    found = []
    for line, literal, at in java_strings(text):
        words = re.sub(r"\\[ntr]", " ", literal)  # an escape is not a letter ("\\n> " holds no words)
        if not has_letter(words) or literal in allowed or any(start <= at < end for start, end in logged):
            continue
        # A piece of a sentence (" percent") or a word ending one ("Exported.", "Error:") is words, whatever it holds.
        sentence = literal != literal.strip() or re.fullmatch(r"[A-Z][a-z]+[.:!]", words)
        if not sentence and not re.search(r"\s", words.strip()) and JAVA_CODE.fullmatch(words.strip()):
            continue
        found.append((line, literal))
    return found


def java_calls():
    for path in JAVA_SOURCES:
        text = path.read_text(encoding="utf-8")
        for match in JAVA_CALL.finditer(text):
            kind, key = match.group(1) or match.group(2), match.group(3)
            args = java_arguments(text, match.end())
            names = set()
            if kind in ("count", "tOr"):
                args = args[1:]
            if kind == "around" and args:
                names.add(args[0].strip('"'))
                args = args[1:]
            names |= {a.strip('"') for a in args[0::2] if re.fullmatch(r'"[a-z_][a-z0-9_]*"', a)}
            if kind == "count":
                names.add("n")
            yield path, key, kind == "count", names


# The iOS launcher's Objective-C: T(@"key", @"name", value…), TCount(@"key", n, …), LTTFallback(@"key", shown, @[…]),
# Said(@"key", …), SaidCount(@"key", n, …) (LTTexts.h).
OBJC_SOURCES = sorted(p for p in (ROOT / "ios/launcher").iterdir() if p.suffix in (".m", ".h", ".c"))
OBJC_CALL = re.compile(r"\b(T|TCount|Said|SaidCount|LTTFallback)\(\s*@\"([a-z0-9_.-]+)\"(?!\s*\+|\s*\])")
OBJC_LOGGED = re.compile(r"\b(NSLog|LunarLog|LTDisplayLog|LTAppLog|GameLog)\(")
# Files whose words only reach the exported log ([App] and [Display] lines), never the screen.
OBJC_LOG_ONLY = {"LunarWindow.m"}
# Literals that are code, not words (the Python a launcher runs): between these two comments.
OBJC_CODE = re.compile(r"// bunker-text: code\b.*?// bunker-text: end", re.S)


def blank_comments(text: str) -> str:
    """text with its // and /* */ comments turned to spaces (offsets kept), string literals untouched."""
    out, i, n = list(text), 0, len(text)
    while i < n:
        if text[i] == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif text.startswith("//", i) or text.startswith("/*", i):
            end = text.find("\n", i) if text[i + 1] == "/" else text.find("*/", i) + 2
            end = n if end < (1 if text[i + 1] == "/" else 2) else end
            for j in range(i, end):
                if out[j] != "\n":
                    out[j] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def objc_calls():
    for path in OBJC_SOURCES:
        text = blank_comments(path.read_text(encoding="utf-8"))
        for match in OBJC_CALL.finditer(text):
            kind, key = match.group(1), match.group(2)
            args = [a[1:] if a.startswith('@"') else a for a in java_arguments(text, match.end())]
            if kind in ("TCount", "SaidCount", "LTTFallback"):
                args = args[1:]
            if kind == "LTTFallback":  # its values are an array: @[@"name", value…]
                inside = args[0].strip()[2:-1] if args and args[0].strip().startswith("@[") else ""
                args = [a.strip()[1:] if a.strip().startswith('@"') else a.strip() for a in inside.split(",")]
            names = {a.strip('"') for a in args[0::2] if re.fullmatch(r'"[a-z_][a-z0-9_]*"', a)}
            plural = kind in ("TCount", "SaidCount")
            if plural:
                names.add("n")
            yield path, key, plural, names


def objc_english(path: Path) -> list[tuple[int, str]]:
    """Words people read in an iOS launcher file, as java_english: every literal (@"…", a C string, each piece of
    a joined literal) outside log calls, outside the code blocks marked for the lint, not flavour and not in the
    objc allowlist."""
    text = path.read_text(encoding="utf-8")
    allowed = ALLOWED | set(ALLOW.get("objc", []))
    skipped = [(m.start(), m.end()) for m in OBJC_CODE.finditer(text)]
    for match in OBJC_LOGGED.finditer(text):
        end, depth = match.end(), 1
        while end < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            end += 1
        skipped.append((match.end(), end))
    found = []
    for line, literal, at in java_strings(text):
        if any(start <= at < end for start, end in skipped):
            continue
        if text[at - 1:at] != "@" and not re.search(r"[A-Za-z]{2,}\s+[A-Za-z]", literal):
            continue  # a C string of one word is a name (a symbol, a class, a variable); a sentence is words
        words = re.sub(r"\\[ntr]", " ", literal)
        if not has_letter(words) or literal in allowed:
            continue
        sentence = literal != literal.strip() or re.fullmatch(r"[A-Z][a-z]+[.:!…]", words)
        if not sentence and not re.search(r"\s", words.strip()) and JAVA_CODE.fullmatch(words.strip()):
            continue
        found.append((line, literal))
    return found


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
    yield from java_calls()
    yield from objc_calls()
    yield from go_calls()


# The text the Go server puts into the game (summon details, notices, panel pages): internal/bunkertext.
GO_SOURCES = sorted(p for p in (ROOT / "overlays/server/internal/service").glob("*.go") if not p.name.endswith("_test.go"))
GO_KEY = re.compile(r"(\b(?:T|TOr|Count)\(\s*|\bsay\(\s*(?:words,\s*)?)?\"(ingame\.[a-z0-9_.]+)\"")


def go_calls():
    """Every ingame.* key the server's Go code names. A key passed straight to T/Count/say has the names of
    the map after it (to the end of the statement, or the next key); a key held in a variable or a table
    first is trusted to get its placeholders."""
    for path in GO_SOURCES:
        text = path.read_text(encoding="utf-8")
        for match in GO_KEY.finditer(text):
            called, key = match.group(1), match.group(2)
            rest = text[match.end():].split(")\n")[0].split("\"ingame.")[0]
            plural = key not in ENGLISH and f"{key}.other" in ENGLISH
            if called:
                names = set(re.findall(r"\"([a-z_][a-z0-9_]*)\":", rest))
            else:
                names = fields(ENGLISH.get(key, "")) | fields(ENGLISH.get(f"{key}.other", ""))
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
            self.assertRegex(key, r"^(common|pods|archive|launcher|ingame)\.[a-z0-9_.-]+$")
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

    def test_no_english_in_the_launcher(self):
        left = {path.name: java_english(path) for path in JAVA_SOURCES}
        self.assertEqual({k: v for k, v in left.items() if v}, {})

    def test_the_lint_sees_english_in_java(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            java = Path(folder) / "A.java"
            java.write_text('class A { // "Not this"\n /* "Nor this" */ void f() { char q = \'"\';\n'
                            '  set("READY"); set("Choose the files"); set("Deploy"); set("game.db"); set("lunar_server");\n'
                            '  set("application/zip"); set("launcher.state."+s); Log.e("LunarTear", "Failed to start");\n'
                            '  set("LUNAR TEAR // 127.0.0.1"); set("a \\"quoted\\" word");\n'
                            '  set(n+" percent"); set("Exported."); set("Error:"); set("v1.2");\n'
                            '  char b = \'\\\\\'; set("After a backslash");\n'
                            '  try{f();}catch(Exception e){Log.w("Bunker","Saving failed",e);Toast.makeText(this,"Could not save it",0);} } }\n')
            self.assertEqual([text for _, text in java_english(java)],
                             ["READY", "Choose the files", "Deploy", 'a \\"quoted\\" word', " percent", "Exported.", "Error:",
                              "After a backslash", "Could not save it"])

    def test_no_english_in_the_ios_launcher(self):
        left = {path.name: objc_english(path) for path in OBJC_SOURCES if path.name not in OBJC_LOG_ONLY}
        self.assertEqual({k: v for k, v in left.items() if v}, {})

    def test_log_only_files_show_nothing(self):
        # Their words go to the exported log, in English; a file that starts showing text leaves the list.
        for name in OBJC_LOG_ONLY:
            text = (ROOT / "ios/launcher" / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b(T|TUpper|TSaid|TCount|Said)\(|UILabel|UIAlertController|setTitle:", text), name)

    def test_the_lint_sees_english_in_objc(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "A.m"
            source.write_text('// "Not this"\nstatic void f(void) { NSLog(@"Started %@", x); title = @"Choose the files";\n'
                              '  chip = @"READY"; key = @"bunker_en"; path = @"translation/active.json"; c = "C string";\n'
                              '  // bunker-text: code\n  code = @"    import ios_runtime\\n";\n  // bunker-text: end\n'
                              '  a = @" percent"; b = @"Done."; caption = @"LUNAR TEAR // 127.0.0.1"; label = T(@"common.close");\n'
                              '  joined = @"Pick one " "of the folders"; c_text = "Could not save it"; tag = "en_US_POSIX"; }\n')
            self.assertEqual([text for _, text in objc_english(source)],
                             ["Choose the files", "READY", " percent", "Done.", "Pick one ", "of the folders", "Could not save it"])
            self.assertNotIn("launcher.x", {key for _, key, _, _ in objc_calls()})  # an example in a comment is no call

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
