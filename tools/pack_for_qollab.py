"""Build the Qollab upload folder and zip from qollab_project/, refusing anything the
platform would silently break on.

    python tools/pack_for_qollab.py --entry python    # build/upload-python/ + build/upload-python.zip
    python tools/pack_for_qollab.py --entry js        # build/upload-js/     + build/upload-js.zip
    python tools/pack_for_qollab.py --entry python --out build/mine --name my-project

The zip holds ONE top-level folder (--name, default: the --out folder's name).

What goes in: every file under --src (default qollab_project/) except junk
(__pycache__/, *.pyc, *.pyo, dotfiles such as .DS_Store). For --entry python the JS
entry files are left out too (top-level index.html, main.js, main.css and ui/**/*.js),
because on Qollab a top-level index.html + main.js wins over main.py.

Checks, run on the folder exactly as it will be uploaded (every failure is listed):
- entry files: python needs main.py; js needs index.html and main.js
- at most 100 files, each at most 2,097,152 bytes; no __pycache__/.pyc/.DS_Store
- every .py file parses
- every file under data/ is named by a literal string constant in an uploaded .py file
  (AST scan of str constants, compared as normalized relative paths; f-strings, `+` and
  os.path.join do not count, because Qollab's data-file scanner does not see them), and
  every literal that is just a data/ file path names a file that is in the upload
- python entry, main.py: exactly one `def main(` at column 0, the whole signature on
  that line, every parameter annotated with a bare int/float/str/bool and given a literal
  non-negative default of that type (no *args, **kwargs, keyword-only or positional-only
  parameters, no decorators); no `if __name__ == "__main__"` block; no module-level main()
- js entry: index.html has no <script> tags and no on*= attributes; JS imports resolve
  (bare names to uploaded Python modules, ./ and ../ to uploaded files)
- the attribution line, verbatim, appears in at least one uploaded file
- requirements.txt, if present: only `name[extras] specifiers` lines (no -options, no ;
  markers, no URLs or direct references); blank lines and # comment lines are allowed
- tools/scrub_check.py passes on the output folder (fails if its private patterns file
  is missing: see that tool's docstring)

Symbolic links in the source (files or folders) are never uploaded; they are listed as
excluded, and the checks above then see the upload exactly as Qollab will.

On any failure nothing is left behind: the output folder and any stale zip are removed
(unless --keep-failed). An existing output folder or <out>.zip is replaced (or removed)
only when it lies under the repo's build/ directory or --force is given. The source
folder, the repo root, build/ itself, the home folder, the current folder (or any folder
above it) and a folder holding a git repository are never used as the output folder.

Exit codes: 0 built, 1 a check failed, 2 usage error.
This file is a local tool and is NOT part of the upload.
"""

import argparse
import ast
import html
import io
import math
import os
import posixpath
import re
import shutil
import sys
import tokenize
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scrub_check  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "qollab_project"
BUILD_DIR = ROOT / "build"
ATTRIBUTION = "This effort is supported by Qollab & IonQ"
MAX_FILES = 100
MAX_FILE_BYTES = 2_097_152
ENTRIES = ("python", "js")
PY_ENTRY_EXCLUDE_TOP = ("index.html", "main.js", "main.css")
MAIN_TYPES = ("int", "float", "str", "bool")
ZIP_DATE = (1980, 1, 1, 0, 0, 0)

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

_REQ_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
_REQ_SPEC = r"(?:===|==|!=|~=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+"
_REQ_RE = re.compile(r"^%s(?:\[\s*%s(?:\s*,\s*%s)*\s*\])?(?:\s*%s(?:\s*,\s*%s)*)?$"
                     % (_REQ_NAME, _REQ_NAME, _REQ_NAME, _REQ_SPEC, _REQ_SPEC))
# A string literal that is nothing but a relative file path under data/ (normalized).
_DATA_PATH_RE = re.compile(r"^data/[^\s*?<>{}|\"'%]+\.[A-Za-z0-9]+$")
# Bare specifiers that Qollab's JS runtime resolves through its own import map
# (three.js 0.186.1, postprocessing 6.39.5, tween.js, meshline); everything else bare
# must be an uploaded Python module.
QOLLAB_IMPORT_MAP = frozenset(("three", "postprocessing", "@tweenjs/tween.js", "meshline"))
QOLLAB_IMPORT_MAP_PREFIXES = ("three/addons/",)

_JS_IMPORT_RE = re.compile(
    r"""(?:\bimport\s+[^'";]*?\bfrom\s*|\bimport\s*|\bexport\s+[^'";]*?\bfrom\s*)(["'])([^"']+)\1""")


class UsageError(Exception):
    pass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    problems: list = field(default_factory=list)
    # scrub only: private text found in uploaded file names -> its masked form, so the
    # summary never prints it (file table, excluded list, other checks' problems)
    masked_names: dict = field(default_factory=dict)


@dataclass
class Result:
    entry: str
    src: Path
    out: Path
    zip_path: Path
    top: str
    files: list = field(default_factory=list)        # (relpath, bytes), as uploaded
    excluded: list = field(default_factory=list)     # (relpath, reason)
    checks: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self):
        return all(c.ok for c in self.checks)


# ------------------------------------------------------------------ selection

def _junk_reason(rel):
    parts = rel.split("/")
    if "__pycache__" in parts:
        return "junk (__pycache__)"
    if any(p.startswith(".") for p in parts):
        return "junk (dotfile)"
    if rel.endswith((".pyc", ".pyo")):
        return "junk (compiled Python)"
    return None


def select_files(src, entry):
    """(included relpaths, [(relpath, reason)] excluded) for an upload of `src`."""
    included, excluded = [], []
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames.sort()
        for name in dirnames:       # os.walk does not descend into these: say so
            if (Path(dirpath) / name).is_symlink():
                rel = (Path(dirpath) / name).relative_to(src).as_posix()
                excluded.append((rel + "/", "symlinked folder (not uploaded, nor its files)"))
        for name in sorted(filenames):
            rel = (Path(dirpath) / name).relative_to(src).as_posix()
            why = _junk_reason(rel)
            if why is None and entry == "python":
                if rel in PY_ENTRY_EXCLUDE_TOP or (rel.startswith("ui/") and rel.endswith(".js")):
                    why = "JS-entry file (left out of a python-entry upload)"
            if why is None and (Path(dirpath) / name).is_symlink():
                why = "symlink (not uploaded)"
            if why:
                excluded.append((rel, why))
            else:
                included.append(rel)
    return included, excluded


# ------------------------------------------------------------------ helpers

def _read(folder, rel):
    return (folder / rel).read_text(encoding="utf-8", errors="replace")


def _all_files(folder):
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames.sort()
        for name in sorted(filenames):
            out.append((Path(dirpath) / name).relative_to(folder).as_posix())
    return out


def _norm_rel(s):
    s = s.replace("\\", "/").strip()
    if not s or s.startswith("/"):
        return None
    n = posixpath.normpath(s)
    return None if n.startswith("..") else n


_FORMATTED = tuple(t for t in (ast.JoinedStr, getattr(ast, "TemplateStr", None)) if t)


def literal_strings(tree):
    """Plain str constants in a module, skipping f-string (and t-string) pieces:
    Qollab's data-file scanner only sees plain literals."""
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, _FORMATTED):
            for sub in ast.walk(node):
                if sub is not node:
                    skip.add(id(sub))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


def _fmt_bytes(n):
    return "{:,}".format(n)


# ------------------------------------------------------------------ main.py rules

def _signature_on_one_line(text, def_line):
    """True when `def main(` ... `)` [-> ann] `:` all sit on line `def_line`."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return False
    i = next((k for k, t in enumerate(toks) if t.type == tokenize.NAME and t.string == "def"
              and t.start == (def_line, 0)), None)
    if i is None:
        return False
    depth = 0
    for t in toks[i:]:
        if t.type == tokenize.OP and t.string in "([{":
            depth += 1
        elif t.type == tokenize.OP and t.string in ")]}":
            depth -= 1
        if t.start[0] != def_line or t.end[0] != def_line:
            return False
        if depth == 0 and t.type == tokenize.OP and t.string == ":":
            return True
    return False


def _default_ok(ann, node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return False, "negative default"
    if not isinstance(node, ast.Constant):
        return False, "default is not a literal"
    v = node.value
    if ann == "bool":
        return (isinstance(v, bool), "default must be True or False")
    if ann == "str":
        return (isinstance(v, str), "default must be a str literal")
    if ann == "int":
        if not isinstance(v, int) or isinstance(v, bool):
            return False, "default must be an int literal"
        return (v >= 0, "negative default")
    if ann == "float":
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return False, "default must be a number literal"
        if not math.isfinite(v):
            return False, "default must be finite"
        return (v >= 0, "negative default")
    return False, "unsupported annotation"


class _ModuleLevelCalls(ast.NodeVisitor):
    """Calls to main() that run at import time (module level, class bodies,
    decorators and default values), not those inside function bodies."""

    def __init__(self):
        self.lines = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "main":
            self.lines.append(node.lineno)
        self.generic_visit(node)

    def _function(self, node):
        for d in node.decorator_list:
            self.visit(d)
        for d in node.args.defaults + [k for k in node.args.kw_defaults if k is not None]:
            self.visit(d)

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_Lambda(self, node):
        for d in node.args.defaults + [k for k in node.args.kw_defaults if k is not None]:
            self.visit(d)


def _is_main_guard(node):
    if not isinstance(node, ast.Compare):
        return False
    sides = [node.left] + list(node.comparators)
    names = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    mains = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return names and mains


def check_main_py(text):
    """Problems with main.py against Qollab's main() rules (empty list = OK), and the
    signature text for the summary."""
    problems = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return ["main.py does not parse (line %s: %s)" % (exc.lineno, exc.msg)], ""
    lines = text.splitlines()
    def_lines = [i for i, line in enumerate(lines, 1) if line.startswith("def main(")]
    tops = [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "main"]
    sig = ""
    if len(def_lines) != 1:
        problems.append("need exactly one 'def main(' at column 0, found %d" % len(def_lines))
    if len(tops) != 1 or not isinstance(tops[0], ast.FunctionDef):
        problems.append("need exactly one module-level 'def main(' (not async), found %d"
                        % len(tops))
    if len(def_lines) == 1 and len(tops) == 1 and isinstance(tops[0], ast.FunctionDef):
        fn, line = tops[0], def_lines[0]
        sig = lines[line - 1].strip()
        if fn.lineno != line:
            problems.append("the column-0 'def main(' (line %d) is not the module-level main()"
                            % line)
        if fn.decorator_list:
            problems.append("main() must not be decorated")
        if not _signature_on_one_line(text, line):
            problems.append("main.py:%d: the whole signature of main() must be on one line "
                            "(through the closing ':')" % line)
        a = fn.args
        if a.posonlyargs:
            problems.append("main(): positional-only parameters ('/') are not supported")
        if a.vararg:
            problems.append("main(): *%s is not allowed" % a.vararg.arg)
        if a.kwonlyargs:
            problems.append("main(): keyword-only parameters (%s) are not allowed; the runner "
                            "passes positional literals" % ", ".join(k.arg for k in a.kwonlyargs))
        if a.kwarg:
            problems.append("main(): **%s is not allowed" % a.kwarg.arg)
        params = a.posonlyargs + a.args
        defaults = [None] * (len(params) - len(a.defaults)) + list(a.defaults)
        for p, d in zip(params, defaults):
            ann = p.annotation
            ann_name = ann.id if isinstance(ann, ast.Name) and ann.id in MAIN_TYPES else None
            if ann_name is None:
                problems.append("main(): parameter '%s' must be annotated with a bare int, "
                                "float, str or bool (got %s)"
                                % (p.arg, ast.unparse(ann) if ann is not None else "none"))
            if d is None:
                problems.append("main(): parameter '%s' needs a literal default" % p.arg)
            elif ann_name is not None:
                ok, why = _default_ok(ann_name, d)
                if not ok:
                    problems.append("main(): parameter '%s: %s = %s': %s (need a literal, "
                                    "non-negative default of that type)"
                                    % (p.arg, ann_name, ast.unparse(d), why))
    guards = sorted({n.lineno for n in ast.walk(tree) if _is_main_guard(n)})
    for g in guards:
        problems.append("main.py:%d: remove the `if __name__ == \"__main__\"` block (the "
                        "runner appends its own main(...) call; main would run twice)" % g)
    calls = _ModuleLevelCalls()
    for stmt in tree.body:
        calls.visit(stmt)
    for c in sorted(set(calls.lines)):
        problems.append("main.py:%d: module-level call to main() (the runner already calls "
                        "it; main would run twice)" % c)
    return problems, sig


# ------------------------------------------------------------------ JS rules

class _HtmlScan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems = []

    def handle_starttag(self, tag, attrs):
        line = self.getpos()[0]
        if tag == "script":
            self.problems.append("index.html:%d: <script> tag (inline scripts never run on "
                                 "Qollab; put code in main.js)" % line)
        for name, _ in attrs:
            if name.startswith("on"):
                self.problems.append("index.html:%d: %s= attribute on <%s> (event-handler "
                                     "attributes never run; add listeners in main.js)"
                                     % (line, name, tag))

    handle_startendtag = handle_starttag


def check_index_html(text):
    scan = _HtmlScan()
    try:
        scan.feed(text)
        scan.close()
    except Exception as exc:  # HTMLParser is lenient; be safe anyway
        scan.problems.append("index.html could not be parsed (%s)" % type(exc).__name__)
    seen = {p.split(":")[1] for p in scan.problems if "<script>" in p}
    for m in re.finditer(r"<\s*script\b", text, re.IGNORECASE):
        line = str(text.count("\n", 0, m.start()) + 1)
        if line not in seen:
            scan.problems.append("index.html:%s: <script> tag (inline scripts never run on "
                                 "Qollab; put code in main.js)" % line)
    return scan.problems


def _strip_js_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"(?m)(^|[^:\\])//.*$", r"\1", text)


def check_js_imports(folder, files):
    """Problems with import specifiers in uploaded .js files."""
    problems, warnings = [], []
    present = set(files)
    for rel in [f for f in files if f.endswith(".js")]:
        text = _strip_js_comments(_read(folder, rel))
        if "import.meta" in text:
            warnings.append("%s uses import.meta (Qollab runs main.js as CommonJS)" % rel)
        if re.search(r"(?<![\w.$])import\s*\(", text):
            warnings.append("%s uses dynamic import() (not supported by Qollab's loader)" % rel)
        for m in _JS_IMPORT_RE.finditer(text):
            spec = m.group(2)
            line = text.count("\n", 0, m.start()) + 1
            if spec.startswith(("http://", "https://")):
                if "cdn.jsdelivr.net" not in spec:
                    problems.append("%s:%d: external import %r (only cdn.jsdelivr.net is "
                                    "allowed)" % (rel, line, spec))
                continue
            if spec.startswith(("./", "../")):
                target = _norm_rel(posixpath.join(posixpath.dirname(rel), spec))
                if target is None or not ({target, target + ".js"} & present):
                    problems.append("%s:%d: import %r does not resolve to an uploaded file"
                                    % (rel, line, spec))
                continue
            if spec in QOLLAB_IMPORT_MAP or any(spec.startswith(pfx) for pfx in QOLLAB_IMPORT_MAP_PREFIXES):
                continue
            mod = spec.replace(".", "/")
            if not ({mod + ".py", mod + "/__init__.py"} & present):
                problems.append("%s:%d: import %r is not an uploaded Python module (JS files "
                                "need ./ or ../ paths)" % (rel, line, spec))
    return problems, warnings


# ------------------------------------------------------------------ requirements

def check_requirements(text):
    problems = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            problems.append("requirements.txt:%d: options/flags (lines starting with -) are not "
                            "allowed" % i)
        elif ";" in line:
            problems.append("requirements.txt:%d: environment markers (;) are not allowed" % i)
        elif "://" in line or "@" in line:
            problems.append("requirements.txt:%d: URLs and direct references are not allowed" % i)
        elif not _REQ_RE.match(line):
            problems.append("requirements.txt:%d: not a plain 'name[extras] specifiers' line "
                            "(inline comments and continuations are not allowed either)" % i)
    return problems


# ------------------------------------------------------------------ checks

def check_upload(folder, entry, top=None):
    """Run every check on an upload folder. Returns (checks, warnings)."""
    folder = Path(folder)
    files = _all_files(folder)
    sizes = {f: (folder / f).stat().st_size for f in files}
    checks, warnings = [], []

    need = ["main.py"] if entry == "python" else ["index.html", "main.js"]
    missing = [n for n in need if n not in sizes]
    checks.append(Check("entry files present (%s)" % entry, not missing, ", ".join(need),
                        ["missing top-level %s" % n for n in missing]))
    if entry == "python" and "index.html" in sizes and "main.js" in sizes:
        checks[-1].ok = False
        checks[-1].problems.append("index.html + main.js present: Qollab would run the JS entry")

    checks.append(Check("file count <= %d" % MAX_FILES, len(files) <= MAX_FILES, str(len(files)),
                        [] if len(files) <= MAX_FILES else
                        ["%d files (limit %d)" % (len(files), MAX_FILES)]))

    big = [f for f in files if sizes[f] > MAX_FILE_BYTES]
    largest = max(files, key=lambda f: sizes[f]) if files else None
    checks.append(Check("each file <= %s bytes" % _fmt_bytes(MAX_FILE_BYTES), not big,
                        "largest %s (%s)" % (largest, _fmt_bytes(sizes[largest])) if largest else "",
                        ["%s is %s bytes" % (f, _fmt_bytes(sizes[f])) for f in big]))

    junk = []
    for dirpath, dirnames, filenames in os.walk(folder):
        rel_dir = Path(dirpath).relative_to(folder).as_posix()
        junk += [posixpath.normpath(posixpath.join(rel_dir, d)) + "/" for d in dirnames
                 if d == "__pycache__"]
        junk += [posixpath.normpath(posixpath.join(rel_dir, f)) for f in filenames
                 if f.endswith((".pyc", ".pyo")) or f == ".DS_Store"]
    checks.append(Check("no __pycache__/.pyc/.DS_Store", not junk, "",
                        ["junk in upload: %s" % j for j in sorted(junk)]))

    py = [f for f in files if f.endswith(".py")]
    trees, parse_problems = {}, []
    for f in py:
        src = _read(folder, f)
        try:
            trees[f] = ast.parse(src, filename=f)
        except SyntaxError as exc:
            parse_problems.append("%s:%s: does not parse (%s)" % (f, exc.lineno, exc.msg))
            continue
        try:
            ast.parse(src, filename=f, feature_version=(3, 12))
        except SyntaxError:
            warnings.append("%s uses syntax newer than Python 3.12 (Qollab's Pyodide may be "
                            "older than the local interpreter)" % f)
    checks.append(Check("python files parse", not parse_problems, "%d file(s)" % len(py),
                        parse_problems))

    literals = set()
    for tree in trees.values():
        for s in literal_strings(tree):
            if len(s) <= 400 and "\n" not in s:
                n = _norm_rel(s)
                if n:
                    literals.add(n)
    data = [f for f in files if f.startswith("data/")]
    unnamed = [f for f in data if f not in literals]
    checks.append(Check("data files named by a literal", not unnamed,
                        "%d of %d" % (len(data) - len(unnamed), len(data)),
                        ["%s is not named by a plain string literal in any uploaded .py file "
                         "(Qollab will not load it)" % f for f in unnamed]))
    # The converse: a data path the code names but the upload lacks (a typo, a file left
    # out, a symlink that was not uploaded) fails on Qollab at run time.
    named = sorted(n for n in literals if _DATA_PATH_RE.match(n))
    absent = [n for n in named if n not in sizes]
    checks.append(Check("data paths named in code are uploaded", not absent,
                        "%d named" % len(named),
                        ["%s is named in the code but is not in the upload" % n
                         for n in absent]))
    other = [f for f in files if not f.startswith("data/") and not f.endswith((".py", ".js",
             ".css", ".html")) and f not in literals and f != "requirements.txt"]
    if other:
        warnings.append("not named by a literal in any .py file (fine unless Python opens "
                        "them): %s" % ", ".join(other))

    if entry == "python":
        if "main.py" in sizes:
            problems, sig = check_main_py(_read(folder, "main.py"))
            checks.append(Check("main() rules (signature, no __main__ guard, no main() call)",
                                not problems, sig, problems))
    else:
        html_problems = check_index_html(_read(folder, "index.html")) if "index.html" in sizes \
            else []
        checks.append(Check("index.html: no <script>, no on*= attributes", not html_problems,
                            "", html_problems))
        js_problems, js_warn = check_js_imports(folder, files)
        warnings += js_warn
        checks.append(Check("JS imports resolve", not js_problems,
                            "%d .js file(s)" % sum(f.endswith(".js") for f in files),
                            js_problems))

    carriers = []
    for f in files:
        try:
            text = (folder / f).read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        if f.endswith((".html", ".htm")):
            text = html.unescape(text)          # "Qollab &amp; IonQ" renders verbatim
        if ATTRIBUTION in text:
            carriers.append(f)
    checks.append(Check("attribution line present", bool(carriers),
                        ", ".join(carriers[:3]) + (" ..." if len(carriers) > 3 else ""),
                        [] if carriers else ['no uploaded file contains "%s"' % ATTRIBUTION]))
    shown = ("main.py",) if entry == "python" else ("index.html", "main.js")
    if carriers and not set(shown) & set(carriers):
        warnings.append("the attribution line is not in %s, so a viewer may never see it"
                        % " or ".join(shown))

    if "requirements.txt" in sizes:
        rp = check_requirements(_read(folder, "requirements.txt"))
        checks.append(Check("requirements.txt rules", not rp, "present", rp))
    else:
        checks.append(Check("requirements.txt rules", True, "(none)"))

    scrub, scrub_warnings = scrub_folder(folder, top)
    checks.append(scrub)
    warnings += scrub_warnings
    return checks, warnings


def scrub_folder(folder, top=None):
    """(Check, warnings) for tools/scrub_check.py run on the upload folder."""
    try:
        patterns = scrub_check.load_patterns(scrub_check.resolve_patterns_path())
    except scrub_check.PatternError as exc:
        return Check("public-repo scrub", False, "", [str(exc).splitlines()[0]]), []
    report = scrub_check.scan_paths([folder], patterns)
    if top:
        report.hits.extend(scrub_check.scan_text(top, patterns, "zip top-level folder",
                                                 first_line=0))
    shown = scrub_check.listed_path_masker(report)
    problems = [scrub_check.format_hit(h) for h in report.hits]
    problems += ["unreadable, so not checked: %s (%s)" % (shown(s), why)
                 for s, why in report.unreadable]
    warnings = ["not scanned by the scrub (%s): %s" % (why, shown(s))
                for s, why in report.skipped]
    masked = {}
    for name in _all_files(folder) + ([top] if top else []):
        for h in scrub_check.scan_text(name, patterns, "", first_line=0):
            for s, e in h.spans:
                masked[name[s:e]] = scrub_check._mask_spans(name[s:e], [(0, e - s)])
    return Check("public-repo scrub", not problems,
                 "%d file(s), %d pattern(s)" % (len(report.scanned), len(patterns)),
                 problems, masked), warnings


# ------------------------------------------------------------------ build

def _inside(child, parent):
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def _safe_out(src, out, zip_path, force):
    out_r, src_r = out.resolve(), src.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), ROOT.resolve(), BUILD_DIR.resolve(),
                 src_r}
    if out_r in forbidden or _inside(src_r, out_r) or _inside(Path.cwd(), out_r):
        raise UsageError("refusing to use %s as the output folder" % scrub_check.display_path(out))
    if _inside(out_r, src_r):
        raise UsageError("the output folder must not be inside the source folder")
    if out_r.exists() and not out_r.is_dir():
        raise UsageError("%s exists and is not a folder" % scrub_check.display_path(out))
    under_build = _inside(out_r, BUILD_DIR)
    if out_r.is_dir() and any(out_r.iterdir()):
        if (out_r / ".git").exists():
            raise UsageError("refusing to replace %s: it holds a git repository"
                             % scrub_check.display_path(out))
        if not (force or under_build):
            raise UsageError("%s exists and is not empty; pass --force to replace it"
                             % scrub_check.display_path(out))
    # The zip is replaced on success and removed on failure: never someone else's file.
    if zip_path.exists() or zip_path.is_symlink():
        if not zip_path.is_file() or zip_path.is_symlink():
            raise UsageError("%s exists and is not a regular file"
                             % scrub_check.display_path(zip_path))
        if not (force or under_build):
            raise UsageError("%s already exists; pass --force to replace it"
                             % scrub_check.display_path(zip_path))


def write_zip(folder, zip_path, top, files):
    tmp = zip_path.with_name(zip_path.name + ".partial")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in sorted(files):
                info = zipfile.ZipInfo("%s/%s" % (top, rel), date_time=ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, (folder / rel).read_bytes())
        os.replace(tmp, zip_path)
    finally:
        if tmp.exists():
            tmp.unlink()


def build(entry="python", src=None, out=None, name=None, force=False, keep_failed=False):
    """Copy, check and zip. Returns a Result; raises UsageError for bad arguments."""
    if entry not in ENTRIES:
        raise UsageError("--entry must be one of %s" % ", ".join(ENTRIES))
    src = Path(src) if src else DEFAULT_SRC
    if not src.is_dir():
        raise UsageError("source folder not found: %s" % scrub_check.display_path(src))
    out = Path(out) if out else BUILD_DIR / ("upload-%s" % entry)
    out = Path(str(out).rstrip("/\\") or str(out))
    zip_path = out.with_name(out.name + ".zip")
    top = name or out.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", top):
        raise UsageError("--name must be a simple folder name (letters, digits, . _ -)")
    _safe_out(src, out, zip_path, force)

    included, excluded = select_files(src, entry)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for rel in included:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / rel, dst)
    res = Result(entry, src, out, zip_path, top, excluded=excluded)
    res.files = [(f, (out / f).stat().st_size) for f in _all_files(out)]
    res.checks, res.warnings = check_upload(out, entry, top)
    if res.ok:
        write_zip(out, zip_path, top, [f for f, _ in res.files])
    else:
        if zip_path.is_file():
            zip_path.unlink()
        if not keep_failed:
            shutil.rmtree(out)
    return res


def summary_text(res):
    shown = scrub_check.display_path
    total = sum(n for _, n in res.files)
    lines = ["pack_for_qollab: entry=%s  source=%s  files=%d  bytes=%s"
             % (res.entry, shown(res.src), len(res.files), _fmt_bytes(total))]
    if res.excluded:
        lines.append("excluded from the upload:")
        lines += ["  %-44s %s" % (f, why) for f, why in res.excluded]
    lines.append("")
    lines.append("  %-44s %10s" % ("FILE", "BYTES"))
    lines += ["  %-44s %10s" % (f, _fmt_bytes(n)) for f, n in res.files]
    lines.append("")
    lines.append("  %-60s %-6s %s" % ("CHECK", "RESULT", "DETAIL"))
    for c in res.checks:
        lines.append("  %-60s %-6s %s" % (c.name, "PASS" if c.ok else "FAIL", c.detail))
        if not c.ok:
            lines += ["      - %s" % p for p in c.problems]
    for w in res.warnings:
        lines.append("  warning: %s" % w)
    lines.append("")
    if res.ok:
        lines.append("RESULT: OK -> %s/ and %s (one top-level folder: %s/)"
                     % (shown(res.out), shown(res.zip_path), res.top))
        lines.append("Upload the zip (or the folder) to Qollab; see SUBMIT.md.")
    else:
        bad = sum(not c.ok for c in res.checks)
        lines.append("RESULT: FAILED (%d check(s)); no zip written. Fix the items above and "
                     "re-run." % bad)
    text = "\n".join(lines)
    masked = {}
    for c in res.checks:
        masked.update(c.masked_names)
    for private in sorted(masked, key=len, reverse=True):   # never print a scrub hit
        text = text.replace(private, masked[private])
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pack_for_qollab.py",
                                 description="Build and check the Qollab upload folder + zip.")
    ap.add_argument("--entry", choices=ENTRIES, default="python")
    ap.add_argument("--src", default=None, help="project folder (default: qollab_project/)")
    ap.add_argument("--out", default=None,
                    help="output folder (default: build/upload-<entry>); the zip is <out>.zip")
    ap.add_argument("--name", default=None, help="top-level folder name inside the zip")
    ap.add_argument("--force", action="store_true",
                    help="replace a non-empty --out folder outside build/")
    ap.add_argument("--keep-failed", action="store_true",
                    help="keep the output folder for inspection when a check fails")
    a = ap.parse_args(argv)
    try:
        res = build(a.entry, a.src, a.out, a.name, a.force, a.keep_failed)
    except UsageError as exc:
        print("pack_for_qollab: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    print(summary_text(res))
    return EXIT_OK if res.ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
