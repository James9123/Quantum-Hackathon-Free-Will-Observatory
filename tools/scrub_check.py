"""Public-repo hygiene tripwire: scan files (and optionally git history) for private strings.

The pattern list is PRIVATE and is deliberately NOT in this repository: the patterns
themselves name the things they guard against. They are loaded from

    $QOLLAB_SCRUB_PATTERNS                          (when set and non-empty), else
    ~/.config/qollab-hackathon/scrub-patterns.txt

Pattern file format: one Python regular expression per line (UTF-8, a BOM is fine).
Matching is case-insensitive unless the line starts with "cs:" (then case-sensitive,
prefix removed), and ^ / $ anchor at line boundaries. Blank lines and lines starting
with "#" are ignored; surrounding whitespace is stripped (write [ ] or \\s for a space
at either end). There are no inline comments: a pattern with whitespace followed by "#"
is rejected (write \\# for a literal #). A pattern's ID is its line number in the file,
so reports never repeat the pattern itself.

Fails closed: a missing, unreadable or empty pattern file, an invalid regex, a regex
that matches the empty string, or a pattern file lying inside a scanned path is a
configuration error (exit 2), never a clean pass.

    python tools/scrub_check.py [PATH ...] [--git-log] [--list-files] [--show-match]

PATH defaults to the repository root. Directories are scanned recursively, skipping
.git, .venv, __pycache__, .pytest_cache and node_modules. Text files are scanned line
by line (UTF-8, else Latin-1; UTF-16/32 when they start with a byte-order mark; files
over 50 MiB in blocks of whole lines), and every file's path below the scan root is
scanned too (a file or folder name can leak as much as file contents); such hits are
reported as `path (name)`. Binary files (a NUL byte in the first 8 KiB, no BOM) are
skipped and counted. Symbolic links inside a scanned folder are not followed; their
target string is scanned instead. A PATH given on the command line is followed.

--git-log also scans the git history that would be published with the repository:
every commit reachable from any ref (git log --all): the message, the author and
committer names and emails; ref names and annotated-tag messages; every file path that
any of those commits recorded; and the contents of every file version (blob) they
reference, so a string removed from the working tree but still in an old commit is
reported as `git-blob:<id>:<path>:line`.

Reports look like `path:line: P<id>: excerpt`. The matched text is masked (first
characters only) in both the excerpt and the path unless --show-match is given, so a
report can be shared without repeating the private string. --list-files masks the same
way. --show-match turns masking off (never paste that output anywhere).

Exit codes: 0 clean, 1 at least one hit, 2 configuration/usage error (or a file that
could not be read, since it could not be checked).
"""

import argparse
import bisect
import itertools
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_VAR = "QOLLAB_SCRUB_PATTERNS"
DEFAULT_RELATIVE = Path(".config") / "qollab-hackathon" / "scrub-patterns.txt"
SKIP_DIRS = frozenset({".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"})
BINARY_SNIFF = 8192
MAX_FILE_BYTES = 50 * 1024 * 1024      # larger text files are scanned in blocks, not skipped
BLOCK_BYTES = 8 * 1024 * 1024
# Byte-order marks, longest first (the UTF-32-LE mark starts with the UTF-16-LE one).
_BOMS = ((b"\xff\xfe\x00\x00", "utf-32"), (b"\x00\x00\xfe\xff", "utf-32"),
         (b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"))
CONTEXT = 30          # characters of context on each side of a match in an excerpt
MAX_EXCERPT = 100

EXIT_CLEAN, EXIT_HITS, EXIT_CONFIG = 0, 1, 2

__all__ = [
    "PatternError", "Pattern", "Hit", "Report", "default_patterns_path",
    "resolve_patterns_path", "load_patterns", "scan_text", "scan_paths", "scan_git_log",
    "format_hit", "display_path", "listed_path_masker", "main",
]


class PatternError(Exception):
    """The pattern file is missing, empty or invalid (fail closed: exit 2)."""


@dataclass(frozen=True)
class Pattern:
    id: int                   # line number in the pattern file
    regex: "re.Pattern"
    case_sensitive: bool


@dataclass
class Hit:
    location: str             # display path, "git:<hash>:<field>", ...
    line: int                 # 1-based line within the location; 0 = the name itself
    pattern_id: int
    line_text: str
    span: tuple               # (start, end) of this match within line_text
    spans: tuple = ()         # every match span on this line (all masked in the excerpt)
    location_spans: tuple = ()  # private text inside `location` itself (masked too)


@dataclass
class Report:
    hits: list = field(default_factory=list)
    scanned: list = field(default_factory=list)       # display paths of scanned files
    skipped: list = field(default_factory=list)       # (display path, reason)
    unreadable: list = field(default_factory=list)    # (display path, reason)


# ------------------------------------------------------------------ patterns

def display_path(p):
    """A path for messages: relative to the cwd when below it, else with $HOME as ~."""
    p = Path(p)
    try:
        rel = os.path.relpath(p)
        if not rel.startswith(".."):
            return rel
    except ValueError:
        pass
    s = str(p)
    home = str(Path.home())
    if home and home != "/" and (s == home or s.startswith(home + os.sep)):
        return "~" + s[len(home):]
    return s


def default_patterns_path():
    return Path.home() / DEFAULT_RELATIVE


def resolve_patterns_path(explicit=None):
    """--patterns, else $QOLLAB_SCRUB_PATTERNS, else the default under ~/.config.
    A set variable is used exclusively: it never falls back to the default."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return Path(env).expanduser()
    return default_patterns_path()


def load_patterns(path=None):
    """Compile the pattern file. Raises PatternError (never returns an empty list)."""
    path = resolve_patterns_path() if path is None else Path(path)
    shown = display_path(path)
    if not path.is_file():
        raise PatternError(
            "scrub patterns file not found: %s\n  The pattern list is private and is not "
            "in the repo. Create it (one regex per line) or set %s to its path."
            % (shown, ENV_VAR))
    try:
        # utf-8-sig: a byte-order mark must not glue itself to the first pattern
        # (which would then never match: a silent fail-open).
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise PatternError("cannot read scrub patterns file %s: %s"
                           % (shown, type(exc).__name__)) from None
    patterns, problems = [], []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cs = line.startswith("cs:")
        body = line[3:].strip() if cs else line
        if not body:
            problems.append("line %d: empty pattern" % lineno)
            continue
        if re.search(r"\s#", body):
            # "name  # why" would silently look for the comment text as well
            problems.append("line %d: looks like an inline comment (whitespace then #); put "
                            "comments on their own line, or write \\# for a literal #" % lineno)
            continue
        try:
            # MULTILINE: text is matched a whole file at a time, and "^..." must mean
            # "at the start of any line", not "at the start of the file".
            rx = re.compile(body, re.MULTILINE | (0 if cs else re.IGNORECASE))
        except re.error as exc:       # str(exc) names the position, not the pattern
            problems.append("line %d: invalid regex (%s)" % (lineno, exc))
            continue
        if rx.search("") is not None:
            problems.append("line %d: pattern matches the empty string" % lineno)
            continue
        patterns.append(Pattern(lineno, rx, cs))
    if problems:
        raise PatternError("scrub patterns file %s is invalid:\n  %s"
                           % (shown, "\n  ".join(problems)))
    if not patterns:
        raise PatternError("scrub patterns file %s has no patterns (only blank lines or "
                           "comments); refusing to report a clean scan" % shown)
    return patterns


# ------------------------------------------------------------------ matching

def scan_text(text, patterns, location, first_line=1):
    """Every (line, pattern) hit in `text`. Line numbers start at `first_line`."""
    if not text:
        return []
    text = text.replace("\r\n", "\n")       # so "$" anchors before a Windows line end too
    starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_end(li):
        return starts[li + 1] - 1 if li + 1 < len(starts) else len(text)

    found = []                     # (line index, pattern id, start col, end col)
    seen = set()
    by_line = {}                   # line index -> spans of EVERY match touching that line
    for pat in patterns:
        for m in pat.regex.finditer(text):
            if m.end() == m.start():
                continue
            start = m.start()
            while start < m.end() - 1 and text[start] == "\n":   # report the line where
                start += 1                                       # the visible text begins
            first = li = bisect.bisect_right(starts, start) - 1
            while li < len(starts) and starts[li] < m.end():
                a = max(start, starts[li]) - starts[li]
                b = min(m.end(), line_end(li)) - starts[li]
                if b > a:
                    by_line.setdefault(li, []).append((a, b))
                li += 1
            if (first, pat.id) in seen:      # one report per (line, pattern) ...
                continue                     # ... but every match is masked (by_line)
            seen.add((first, pat.id))
            a = start - starts[first]
            found.append((first, pat.id, a, max(a, min(m.end(), line_end(first)) - starts[first])))
    hits = []
    for li, pid, a, b in sorted(found):
        hits.append(Hit(location, li + first_line, pid, text[starts[li]:line_end(li)],
                        (a, b), tuple(sorted(by_line.get(li, ())))))
    return hits


def _mask(s):
    n = len(s)
    keep = 2 if n >= 6 else (1 if n >= 3 else 0)
    return s[:keep] + "*" * max(1, min(n - keep, 12))


def _mask_spans(text, spans, show_match=False, clipped_start=False):
    """`text` with every span masked. Overlapping spans are merged first, so only the
    first characters of a whole match ever show; with clipped_start, a span starting at
    0 is the tail of a match cut off by the excerpt window and is masked completely."""
    if show_match or not spans:
        return text
    merged = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        elif e > s:
            merged.append([s, e])
    out, pos = [], 0
    for s, e in merged:
        out.append(text[pos:s])
        out.append("*" * max(1, min(e - s, 12)) if clipped_start and s == 0
                   else _mask(text[s:e]))
        pos = e
    out.append(text[pos:])
    return "".join(out)


def listed_path_masker(report, show_match=False):
    """A function mapping a path in `report` (scanned, skipped or unreadable) to the
    form safe to print: private text found in the path itself is masked."""
    masked = {}
    if not show_match:
        for h in report.hits:
            if h.location_spans and h.location not in masked:
                masked[h.location] = _mask_spans(h.location, h.location_spans)
    return lambda s: masked.get(s, s)


def format_hit(hit, show_match=False):
    """`location:line: P<id>: excerpt` (`location (name): ...` for a hit in a path).
    Matched text is masked, in the excerpt and in the location, unless show_match."""
    text, (a, b) = hit.line_text, hit.span
    lo, hi = max(0, a - CONTEXT), min(len(text), b + CONTEXT)
    spans = [(max(s, lo) - lo, min(e, hi) - lo) for s, e in (hit.spans or (hit.span,))
             if e > lo and s < hi]
    clipped = any(s < lo < e for s, e in (hit.spans or (hit.span,)))
    excerpt = " ".join(_mask_spans(text[lo:hi], spans, show_match, clipped).split())
    if len(excerpt) > MAX_EXCERPT:
        excerpt = excerpt[:MAX_EXCERPT - 3] + "..."
    excerpt = ("..." if lo > 0 else "") + excerpt + ("..." if hi < len(text) else "")
    location = _mask_spans(hit.location, hit.location_spans, show_match)
    where = "%s:%d" % (location, hit.line) if hit.line else "%s (name)" % location
    return "%s: P%d: %s" % (where, hit.pattern_id, excerpt)


# ------------------------------------------------------------------ files

def _decode_plain(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")         # never fails: every byte is a character


def _decode(data):
    """The text of a file's bytes, or None when it is binary. A UTF-16/32 file has NUL
    bytes, so its byte-order mark is checked before the NUL sniff."""
    for bom, enc in _BOMS:
        if data.startswith(bom):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                break
    if b"\0" in data[:BINARY_SNIFF]:
        return None
    return _decode_plain(data)


def _scan_contents(path, patterns, shown):
    """(hits, None) after scanning a text file's contents; (None, reason) when it was not
    scanned. A reason starting with "unreadable" fails the run (it could not be checked)."""
    try:
        st = path.stat()
    except OSError as exc:
        return None, "unreadable: %s" % type(exc).__name__
    if not stat.S_ISREG(st.st_mode):        # a FIFO would block a read forever
        return None, "not a regular file"
    try:
        if st.st_size <= MAX_FILE_BYTES:
            text = _decode(path.read_bytes())
            if text is None:
                return None, "binary"
            return scan_text(text, patterns, shown), None
        # Large file: never skip it (that would be a silent pass); scan blocks of whole
        # lines so memory stays bounded and line numbers stay right.
        hits = []
        with open(path, "rb") as fh:
            head = fh.read(BINARY_SNIFF)
            if any(head.startswith(bom) for bom, enc in _BOMS if enc != "utf-8-sig"):
                return None, "unreadable: UTF-16/32 text over %d bytes" % MAX_FILE_BYTES
            if b"\0" in head:
                return None, "binary"
            fh.seek(0)
            lineno, block, size = 1, [], 0
            for raw in itertools.chain(fh, [b""]):
                block.append(raw)
                size += len(raw)
                if size >= BLOCK_BYTES or not raw:
                    text = _decode_plain(b"".join(block))
                    if lineno == 1:
                        text = text.lstrip("﻿")
                    hits.extend(scan_text(text, patterns, shown, first_line=lineno))
                    lineno += text.count("\n")
                    block, size = [], 0
        return hits, None
    except OSError as exc:
        return None, "unreadable: %s" % type(exc).__name__


def _scan_file(path, rel, patterns, report):
    shown = display_path(path)
    hits = scan_text(rel, patterns, shown, first_line=0)
    loc_spans = ()
    if hits:   # the path itself holds private text: mask it wherever this file is named
        if shown.endswith(rel):
            off = len(shown) - len(rel)
            loc_spans = tuple((s + off, e + off) for s, e in hits[0].spans)
        else:
            loc_spans = ((0, len(shown)),)
    try:
        if path.is_symlink():
            try:
                target = os.readlink(path)
            except OSError as exc:
                report.unreadable.append((shown, "symlink: %s" % type(exc).__name__))
                return
            hits.extend(scan_text(target, patterns, shown + " -> (link target)"))
            report.skipped.append((shown, "symlink (target string scanned, not followed)"))
            return
        content_hits, why = _scan_contents(path, patterns, shown)
        if content_hits is None:
            (report.unreadable if why.startswith("unreadable") else report.skipped).append(
                (shown, why))
            return
        report.scanned.append(shown)
        hits.extend(content_hits)
    finally:
        for h in hits:
            h.location_spans = loc_spans
        report.hits.extend(hits)


def _inside(child, parent):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def scan_paths(paths, patterns):
    """Scan files and directory trees. Raises FileNotFoundError for a missing path."""
    report = Report()
    for given in paths:
        base = Path(given)
        if not base.exists() and not base.is_symlink():
            raise FileNotFoundError(str(given))
        if base.is_symlink() and base.exists():
            # Named on the command line: scan what it points to. (Not following it would
            # scan nothing and report a clean pass.)
            base = base.resolve()
        if base.is_file() or base.is_symlink() or not base.is_dir():
            _scan_file(base, base.name, patterns, report)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            d = Path(dirpath)
            keep = []
            for name in sorted(dirnames):
                sub = d / name
                if name in SKIP_DIRS:
                    continue
                if sub.is_symlink():
                    _scan_file(sub, sub.relative_to(base).as_posix(), patterns, report)
                    continue
                keep.append(name)
            dirnames[:] = keep
            # Each file's whole path below `base` is scanned, which covers directory
            # names too (empty directories are never committed or zipped).
            for name in sorted(filenames):
                p = d / name
                _scan_file(p, p.relative_to(base).as_posix(), patterns, report)
    return report


# ------------------------------------------------------------------ git

def _git_bytes(repo, args, stdin=None):
    try:
        out = subprocess.run(["git", "-C", str(repo)] + list(args), input=stdin,
                             capture_output=True, timeout=300)
    except FileNotFoundError:
        raise PatternError("--git-log: git is not installed") from None
    except subprocess.TimeoutExpired:
        raise PatternError("--git-log: git timed out") from None
    if out.returncode != 0:
        msg = out.stderr.decode("utf-8", "replace").strip().splitlines()
        raise PatternError("--git-log: git %s failed in %s: %s"
                           % (args[0], display_path(repo), msg[-1] if msg else "error"))
    return out.stdout


def _git(repo, *args):
    return _git_bytes(repo, args).decode("utf-8", "replace")


def _named(prefix, name, patterns, suffix=""):
    """(location, spans) for `prefix + name + suffix`, with any private text in `name`
    marked for masking, and the hits found in `name` itself (line 0)."""
    location = prefix + name + suffix
    name_hits = scan_text(name, patterns, location, first_line=0)
    spans = tuple((s + len(prefix), e + len(prefix))
                  for s, e in (name_hits[0].spans if name_hits else ()))
    for h in name_hits:
        h.location_spans = spans
    return location, spans, name_hits


def _scan_history_files(repo, patterns):
    """Hits in every file path recorded by a reachable commit, and in the contents of
    every reachable file version (blob). Binary blobs are skipped, as in a file scan."""
    hits = []
    names = _git_bytes(repo, ["log", "--all", "-m", "--no-renames", "--name-only",
                              "--format=", "-z"])
    paths = sorted({p.strip(b"\n").decode("utf-8", "replace")
                    for p in names.split(b"\0") if p.strip(b"\n")})
    for path in paths:
        hits.extend(_named("git-path:", path, patterns)[2])
    first_path = {}
    for line in _git(repo, "rev-list", "--all", "--objects").splitlines():
        sha, _, path = line.partition(" ")
        if sha:
            first_path.setdefault(sha, path)
    if not first_path:
        return hits
    check = _git_bytes(repo, ["cat-file", "--batch-check=%(objectname) %(objecttype)"],
                       stdin="\n".join(first_path).encode() + b"\n").decode()
    blobs = [ln.split()[0] for ln in check.splitlines() if ln.endswith(" blob")]
    if not blobs:
        return hits
    data = _git_bytes(repo, ["cat-file", "--batch"], stdin="\n".join(blobs).encode() + b"\n")
    pos = 0
    while pos < len(data):
        nl = data.find(b"\n", pos)
        if nl < 0:
            break
        header = data[pos:nl].decode("utf-8", "replace").split()
        if len(header) != 3 or not header[2].isdigit():     # e.g. "<id> missing"
            raise PatternError("--git-log: unexpected git cat-file output; history not "
                               "fully scanned")
        sha, size = header[0], int(header[2])
        body = data[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
        text = _decode(body)
        if text is None:
            continue
        location, spans, _ = _named("git-blob:%s:" % sha[:10], first_path.get(sha, ""),
                                    patterns)
        for h in scan_text(text, patterns, location):
            h.location_spans = spans
            hits.append(h)
    return hits


def scan_git_log(repo, patterns):
    """Hits in commit metadata/messages (all refs), ref names, annotated tags, every
    file path the history records, and every file version it holds.
    Raises PatternError when git is unavailable or `repo` is not a repository."""
    repo = Path(repo)
    _git(repo, "rev-parse", "--git-dir")
    hits = []
    has_commits = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q",
                                  "HEAD"], capture_output=True).returncode == 0
    refs_text = _git(repo, "for-each-ref", "--format=%(refname)%1f%(objecttype)%1f"
                     "%(taggername)%1f%(taggeremail)%1f%(contents)%1e")
    if has_commits or refs_text.strip():
        hits.extend(_scan_history_files(repo, patterns))
        log = _git(repo, "log", "--all", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e")
        for rec in log.split("\x1e"):
            rec = rec.strip("\n")
            if not rec:
                continue
            parts = rec.split("\x1f")
            if len(parts) < 6:
                continue
            sha = parts[0][:10]
            for label, value in zip(("author-name", "author-email", "committer-name",
                                     "committer-email"), parts[1:5]):
                hits.extend(scan_text(value, patterns, "git:%s:%s" % (sha, label)))
            hits.extend(scan_text("\x1f".join(parts[5:]), patterns, "git:%s:message" % sha))
    for rec in refs_text.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split("\x1f")
        ref = parts[0]
        hits.extend(scan_text(ref, patterns, "git-ref", first_line=0))
        if len(parts) >= 5 and parts[1] == "tag":
            for label, value in (("tagger-name", parts[2]), ("tagger-email", parts[3]),
                                 ("message", "\x1f".join(parts[4:]))):
                location, spans, _ = _named("git-tag:", ref, patterns, ":" + label)
                for h in scan_text(value, patterns, location):
                    h.location_spans = spans
                    hits.append(h)
    return hits


# ------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="scrub_check.py",
        description="Public-repo hygiene tripwire (patterns are private; see module doc).")
    ap.add_argument("paths", nargs="*", help="files or directories (default: the repo root)")
    ap.add_argument("--git-log", action="store_true",
                    help="also scan the git history: commit messages, author/committer names "
                         "and emails, refs and tags, every recorded path and file version")
    ap.add_argument("--repo", default=None,
                    help="repository for --git-log (default: the repo root)")
    ap.add_argument("--list-files", action="store_true", help="print what was scanned/skipped")
    ap.add_argument("--show-match", action="store_true",
                    help="print matched text unmasked (do not paste such output anywhere)")
    ap.add_argument("--patterns", default=None,
                    help="pattern file (default: $%s, else ~/%s)" % (ENV_VAR, DEFAULT_RELATIVE))
    ap.add_argument("--max-report", type=int, default=200, help="print at most N hits")
    a = ap.parse_args(argv)

    try:
        pattern_file = resolve_patterns_path(a.patterns)
        patterns = load_patterns(pattern_file)
    except PatternError as exc:
        print("scrub_check: FAIL CLOSED: %s" % exc, file=sys.stderr)
        return EXIT_CONFIG

    paths = [Path(p) for p in (a.paths or [ROOT])]
    pf = pattern_file.resolve()
    for p in paths:
        if _inside(pf, p.resolve()):
            print("scrub_check: FAIL CLOSED: the patterns file lies inside the scanned path %s; "
                  "keep it outside the repository" % display_path(p), file=sys.stderr)
            return EXIT_CONFIG
    try:
        report = scan_paths(paths, patterns)
    except FileNotFoundError as exc:
        print("scrub_check: no such path: %s" % display_path(Path(str(exc))), file=sys.stderr)
        return EXIT_CONFIG
    if a.git_log:
        try:
            report.hits.extend(scan_git_log(Path(a.repo) if a.repo else ROOT, patterns))
        except PatternError as exc:
            print("scrub_check: FAIL CLOSED: %s" % exc, file=sys.stderr)
            return EXIT_CONFIG

    if a.list_files:
        shown = listed_path_masker(report, a.show_match)
        for s in report.scanned:
            print("scanned: %s" % shown(s))
        for s, why in report.skipped:
            print("skipped (%s): %s" % (why, shown(s)))
    shown = listed_path_masker(report, a.show_match)
    for s, why in report.unreadable:
        print("UNREADABLE (%s): %s" % (why, shown(s)), file=sys.stderr)
    for h in report.hits[:max(0, a.max_report)]:
        print(format_hit(h, a.show_match))
    if len(report.hits) > a.max_report:
        print("... and %d more hit(s)" % (len(report.hits) - a.max_report))
    n_bin = sum(1 for _, why in report.skipped if why == "binary")
    summary = ("scrub_check: %d pattern(s); scanned %d text file(s), skipped %d (%d binary)%s"
               % (len(patterns), len(report.scanned), len(report.skipped), n_bin,
                  "; git history included" if a.git_log else ""))
    if report.hits:
        print("%s; %d HIT(S): fix these before sharing" % (summary, len(report.hits)))
        return EXIT_HITS
    if report.unreadable:
        print("%s; %d file(s) UNREADABLE, so the scan is incomplete"
              % (summary, len(report.unreadable)), file=sys.stderr)
        return EXIT_CONFIG
    print("%s; clean" % summary)
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
