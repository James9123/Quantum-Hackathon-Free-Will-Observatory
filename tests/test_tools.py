"""tools/scrub_check.py (public-repo tripwire) and tools/pack_for_qollab.py (upload packer).

Every pattern in this file is SYNTHETIC ("forbiddenword", "XYZ"). The real pattern list
is private and never enters the repository.
"""
import os
import re
import shutil
import subprocess
import threading
import zipfile
from pathlib import Path

import pytest

import pack_for_qollab as pack
import scrub_check

ROOT = Path(__file__).resolve().parent.parent
ATTR = "This effort is supported by Qollab & IonQ"
# line 2 -> P2 (case-insensitive), line 4 -> P4 (case-sensitive, word-bounded)
SYNTHETIC = "# synthetic test patterns\nforbiddenword\n\ncs:\\bXYZ\\b\n"
BENIGN = "# matches nothing in the project\ncs:\\bQQ_NEVER_PRESENT_7F3A\\b\n"


@pytest.fixture
def patterns(tmp_path, monkeypatch):
    p = tmp_path / "private" / "patterns.txt"
    p.parent.mkdir()
    p.write_text(SYNTHETIC)
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    return p


@pytest.fixture
def no_patterns(tmp_path, monkeypatch):
    monkeypatch.delenv(scrub_check.ENV_VAR, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "emptyhome"))


def scrub(capsys, *args):
    rc = scrub_check.main([str(a) for a in args])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


# ============================================================ scrub_check

def test_scrub_fails_closed_without_patterns_file(tmp_path, no_patterns, capsys):
    (tmp_path / "clean.txt").write_text("nothing to see\n")
    assert scrub_check.default_patterns_path() == (
        tmp_path / "emptyhome" / ".config" / "qollab-hackathon" / "scrub-patterns.txt")
    rc, out, err = scrub(capsys, tmp_path / "clean.txt")
    assert rc == 2
    assert "FAIL CLOSED" in err and "not found" in err
    assert "clean" not in out


def test_scrub_env_var_is_exclusive(tmp_path, monkeypatch, capsys):
    """A set variable pointing nowhere fails; it never falls back to the default file."""
    home = tmp_path / "home"
    default = home / ".config" / "qollab-hackathon" / "scrub-patterns.txt"
    default.parent.mkdir(parents=True)
    default.write_text(SYNTHETIC)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(scrub_check.ENV_VAR, str(tmp_path / "missing.txt"))
    (tmp_path / "proj").mkdir()
    rc, _, err = scrub(capsys, tmp_path / "proj")
    assert rc == 2 and "not found" in err
    monkeypatch.delenv(scrub_check.ENV_VAR)
    rc, out, _ = scrub(capsys, tmp_path / "proj")
    assert rc == 0 and "clean" in out


@pytest.mark.parametrize("content", ["", "\n\n", "# only a comment\n   \n# another\n"])
def test_scrub_fails_closed_on_empty_pattern_file(tmp_path, monkeypatch, capsys, content):
    p = tmp_path / "patterns.txt"
    p.write_text(content)
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    (tmp_path / "proj").mkdir()
    rc, _, err = scrub(capsys, tmp_path / "proj")
    assert rc == 2 and "no patterns" in err


@pytest.mark.parametrize("bad, why", [("unbalanced(", "invalid regex"),
                                      ("cs:", "empty pattern"),
                                      ("a*", "matches the empty string"),
                                      ("x|", "matches the empty string"),
                                      ("secretname  # why", "inline comment")])
def test_scrub_rejects_bad_patterns_without_echoing_them(tmp_path, monkeypatch, capsys, bad, why):
    p = tmp_path / "patterns.txt"
    p.write_text("forbiddenword\n# comment\n%s\n" % bad)
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    (tmp_path / "proj").mkdir()
    rc, out, err = scrub(capsys, tmp_path / "proj")
    assert rc == 2
    assert "line 3" in err and why in err
    assert "forbiddenword" not in out + err
    if len(bad) > 3:
        assert bad not in out + err


def test_scrub_detects_planted_hit_with_line_and_pattern_id(tmp_path, patterns, capsys):
    proj = tmp_path / "proj"
    (proj / "docs").mkdir(parents=True)
    (proj / "docs" / "notes.md").write_text("line one\nline two\nsee forbiddenword here\n")
    (proj / "ok.py").write_text("x = 1\n")
    rc, out, _ = scrub(capsys, proj)
    assert rc == 1
    assert "notes.md:3: P2:" in out
    assert "1 HIT(S)" in out
    # masked by default: the private string and the pattern text are never echoed
    assert "forbiddenword" not in out and "fo*" in out
    assert "\\bXYZ\\b" not in out
    rc, out, _ = scrub(capsys, proj, "--show-match")
    assert rc == 1 and "see forbiddenword here" in out


def test_scrub_case_rules(tmp_path, patterns, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_text(
        "FORBIDDENWORD shouting\n"      # 1: P2 (case-insensitive)
        "xyz lower\n"                   # 2: no hit (P4 is case-sensitive)
        "XYZW longer word\n"            # 3: no hit (word boundary)
        "the XYZ word\n"                # 4: P4
        "ForbiddenWord and XYZ\n")      # 5: P2 and P4
    rc, out, _ = scrub(capsys, proj)
    assert rc == 1
    hits = sorted(re.search(r"a\.txt:(\d+): (P\d+):", line).groups()
                  for line in out.splitlines() if ": P" in line)
    assert hits == [("1", "P2"), ("4", "P4"), ("5", "P2"), ("5", "P4")]


def test_scrub_skips_tool_and_vcs_dirs(tmp_path, patterns, capsys):
    proj = tmp_path / "proj"
    for d in (".git", ".venv", "__pycache__", ".pytest_cache", "node_modules",
              "pkg/__pycache__", "pkg/node_modules/x"):
        (proj / d).mkdir(parents=True, exist_ok=True)
        (proj / d / "planted.txt").write_text("forbiddenword XYZ\n")
    (proj / "pkg" / "clean.py").write_text("print('fine')\n")
    rc, out, _ = scrub(capsys, proj, "--list-files")
    assert rc == 0, out
    scanned = [line for line in out.splitlines() if line.startswith("scanned: ")]
    assert len(scanned) == 1 and scanned[0].endswith("clean.py")
    assert "planted" not in out


def test_scrub_skips_binaries_but_scans_names_and_link_targets(tmp_path, patterns, capsys):
    proj = tmp_path / "proj"
    (proj / "sub").mkdir(parents=True)
    (proj / "blob.bin").write_bytes(b"\x89PNG\x00\x01 forbiddenword XYZ \x00")
    (proj / "sub" / "forbiddenword-notes.txt").write_text("harmless\n")
    os.symlink("/nowhere/XYZ/target", proj / "link")
    rc, out, _ = scrub(capsys, proj, "--list-files")
    assert rc == 1
    assert "skipped (binary)" in out and "blob.bin" in out
    assert "blob.bin:" not in out                  # no content hit from the binary
    assert "fo***********-notes.txt (name): P2: sub/fo***" in out
    assert "link -> (link target):1: P4: /nowhere/X**/target" in out
    assert out.count(": P") == 2
    hits = [line for line in out.splitlines() if ": P" in line]
    assert not any("forbiddenword" in h or "XYZ" in h for h in hits)   # masked everywhere
    rc, out, _ = scrub(capsys, proj, "--show-match")
    assert "forbiddenword-notes.txt (name): P2: sub/forbiddenword-notes.txt" in out


def test_scrub_refuses_patterns_file_inside_scanned_tree(tmp_path, monkeypatch, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    p = proj / "scrub-patterns.txt"
    p.write_text(SYNTHETIC)
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    rc, _, err = scrub(capsys, proj)
    assert rc == 2 and "inside the scanned path" in err


def test_scrub_missing_path_is_a_usage_error(tmp_path, patterns, capsys):
    rc, _, err = scrub(capsys, tmp_path / "does-not-exist")
    assert rc == 2 and "no such path" in err


def test_format_hit_masks_every_match_on_the_line():
    pats = [scrub_check.Pattern(1, re.compile("secretthing", re.IGNORECASE), False),
            scrub_check.Pattern(2, re.compile("XYZ"), True)]
    hits = scrub_check.scan_text("a secretthing and XYZ\nnext\n", pats, "f.txt")
    assert [(h.line, h.pattern_id) for h in hits] == [(1, 1), (1, 2)]
    for h in hits:
        text = scrub_check.format_hit(h)
        assert "secretthing" not in text and "XYZ" not in text
        assert "se*" in text and "X**" in text
    assert "secretthing and XYZ" in scrub_check.format_hit(hits[0], show_match=True)


def _git(env, *args):
    return subprocess.run(["git"] + list(args), env=env, check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_scrub_git_log_scans_messages_and_identities(tmp_path, patterns, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Clean Person", GIT_AUTHOR_EMAIL="nobody",
               GIT_COMMITTER_NAME="Clean Person", GIT_COMMITTER_EMAIL="nobody")
    _git(env, "init", "-q", str(repo))
    (repo / "a.txt").write_text("clean\n")
    _git(env, "-C", str(repo), "add", "a.txt")
    _git(env, "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "first")
    rc, out, _ = scrub(capsys, repo, "--git-log", "--repo", repo)
    assert rc == 0, out
    assert "git history included" in out

    (repo / "a.txt").write_text("still clean\n")
    _git(env, "-C", str(repo), "add", "a.txt")
    env2 = dict(env, GIT_AUTHOR_NAME="Forbiddenword Tester")
    _git(env2, "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-q",
         "-m", "second\n\nmentions XYZ in the body")
    rc, out, _ = scrub(capsys, repo)                 # files only: still clean
    assert rc == 0
    rc, out, _ = scrub(capsys, repo, "--git-log", "--repo", repo)
    assert rc == 1
    assert ":author-name:1: P2:" in out
    assert ":message:3: P4:" in out
    assert "committer-name" not in out


def test_scrub_git_log_outside_a_repo_fails_closed(tmp_path, patterns, capsys):
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    plain = tmp_path / "plain"
    plain.mkdir()
    rc, _, err = scrub(capsys, plain, "--git-log", "--repo", plain)
    assert rc == 2 and "FAIL CLOSED" in err


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_scrub_git_log_scans_old_file_versions_and_paths(tmp_path, patterns, capsys):
    """A string removed from the working tree, a file renamed away from a private name,
    and a side branch are all still in the history that would be published."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Clean Person", GIT_AUTHOR_EMAIL="nobody",
               GIT_COMMITTER_NAME="Clean Person", GIT_COMMITTER_EMAIL="nobody")

    def git(*args):
        _git(env, "-C", str(repo), "-c", "commit.gpgsign=false", *args)

    git("init", "-q")
    (repo / "a.txt").write_text("one\nan old forbiddenword line\n")
    (repo / "XYZ-notes.md").write_text("fine\n")
    (repo / "blob.bin").write_bytes(b"\x00\x01 forbiddenword")      # binary: skipped
    git("add", "-A")
    git("commit", "-q", "-m", "first")
    (repo / "a.txt").write_text("one\nclean now\n")
    git("mv", "XYZ-notes.md", "notes.md")
    git("add", "-A")
    git("commit", "-q", "-m", "second")
    git("checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("XYZ\n")
    git("add", "-A")
    git("commit", "-q", "-m", "third")
    git("checkout", "-q", "-")
    assert not (repo / "side.txt").exists()
    rc, out, _ = scrub(capsys, repo)                   # the working tree is clean
    assert rc == 0, out
    rc, out, _ = scrub(capsys, repo, "--git-log", "--repo", repo)
    assert rc == 1, out
    hits = [line for line in out.splitlines() if ": P" in line]
    assert any(h.startswith("git-blob:") and ":a.txt:2: P2:" in h for h in hits), out
    assert any(h.startswith("git-blob:") and ":side.txt:1: P4:" in h for h in hits), out
    assert "git-path:X**-notes.md (name): P4:" in out
    assert not any("blob.bin" in h for h in hits)
    assert "forbiddenword" not in out and "XYZ" not in out          # masked everywhere


def test_scrub_pattern_file_with_bom_and_crlf(tmp_path, monkeypatch, capsys):
    """A byte-order mark must not glue itself to the first pattern (a silent miss)."""
    p = tmp_path / "patterns.txt"
    p.write_bytes(b"\xef\xbb\xbfforbiddenword\r\n# comment\r\ncs:\\bXYZ\\b\r\n")
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_text("forbiddenword\nXYZ\n")
    rc, out, _ = scrub(capsys, proj)
    assert rc == 1
    assert "a.txt:1: P1:" in out and "a.txt:2: P3:" in out


def test_scrub_anchors_match_at_every_line(tmp_path, monkeypatch, capsys):
    p = tmp_path / "patterns.txt"
    p.write_text("^forbiddenword\ncs:XYZ$\n")
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_bytes(b"first line\r\nforbiddenword at the start\r\nends in XYZ\r\n")
    rc, out, _ = scrub(capsys, proj)
    assert rc == 1, out
    assert "a.txt:2: P1:" in out and "a.txt:3: P2:" in out


def test_scrub_masks_every_occurrence_and_clipped_matches(tmp_path, monkeypatch, capsys):
    p = tmp_path / "patterns.txt"
    p.write_text("forbiddenword\nzz9\n")
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_text("x forbiddenword y forbiddenword and then zz9 " + "w" * 40 + "\n")
    rc, out, _ = scrub(capsys, proj)
    assert rc == 1
    assert out.count(": P") == 2                      # one report per (line, pattern) ...
    assert "forbidden" not in out and "zz9" not in out          # ... every occurrence masked
    # The P2 excerpt window starts inside the first match: that tail is masked in full.
    assert "wo*" not in out and "...****" in out


def test_scrub_large_file_is_scanned_not_skipped(tmp_path, patterns, monkeypatch, capsys):
    monkeypatch.setattr(scrub_check, "MAX_FILE_BYTES", 1000)
    monkeypatch.setattr(scrub_check, "BLOCK_BYTES", 300)
    proj = tmp_path / "proj"
    proj.mkdir()
    lines = ["line %03d %s\n" % (i, "." * 40) for i in range(200)]
    lines[150] = "line 150 has forbiddenword in it\n"
    lines[199] = "last line XYZ\n"
    (proj / "big.txt").write_text("".join(lines))
    assert (proj / "big.txt").stat().st_size > 5 * 1000
    rc, out, _ = scrub(capsys, proj)
    assert rc == 1, out
    assert "big.txt:151: P2:" in out and "big.txt:200: P4:" in out
    assert "too large" not in out


def test_scrub_reads_utf16_text_instead_of_skipping_it(tmp_path, patterns, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "notes.txt").write_bytes("a\nwith forbiddenword\n".encode("utf-16"))
    rc, out, _ = scrub(capsys, proj)
    assert rc == 1 and "notes.txt:2: P2:" in out


def test_scrub_follows_a_symlink_named_on_the_command_line(tmp_path, patterns, capsys):
    real = tmp_path / "real"
    real.mkdir()
    (real / "a.txt").write_text("forbiddenword\n")
    link = tmp_path / "link"
    os.symlink(real, link)
    rc, out, _ = scrub(capsys, link)
    assert rc == 1 and "a.txt:1: P2:" in out


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no FIFOs here")
def test_scrub_skips_special_files_without_blocking(tmp_path, patterns, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    fifo = proj / "pipe"
    os.mkfifo(fifo)
    (proj / "ok.txt").write_text("fine\n")

    def unblock():   # if a regression opens the FIFO for reading, fail instead of hanging
        try:
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass

    timer = threading.Timer(3.0, unblock)
    timer.daemon = True
    timer.start()
    try:
        rc, out, _ = scrub(capsys, proj, "--list-files")
    finally:
        timer.cancel()
    assert rc == 0 and "skipped (not a regular file)" in out


def test_scrub_list_files_masks_private_names(tmp_path, patterns, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "forbiddenword.txt").write_text("fine\n")
    rc, out, _ = scrub(capsys, proj, "--list-files")
    assert rc == 1
    assert "scanned: " in out and "forbiddenword" not in out


# ============================================================ pack_for_qollab

SIG = 'def main(shots: int = 100, label: str = "a", flag: bool = True, scale: float = 0.5):'
MAIN_OK = '''"""Minimal test project.

%s
"""

import helper

TABLE = "data/table.json"


%s
    with open(TABLE) as fh:
        print(helper.describe(fh.read()), shots, label, flag, scale)
''' % (ATTR, SIG)
HELPER = 'def describe(text):\n    return "table: %d chars" % len(text)\n'
INDEX_OK = ('<main id="app">\n  <h1>Test</h1>\n  <button id="go" type="button">Run</button>\n'
            '  <p id="out" aria-live="polite"></p>\n</main>\n')
MAIN_JS_OK = ('import * as api from "ui_api";\nimport { hello } from "./ui/widget.js";\n'
              'console.log(hello(), "%s");\nawait new Promise(() => {});\n' % ATTR)


def make_project(root, js=False):
    (root / "data").mkdir(parents=True)
    (root / "main.py").write_text(MAIN_OK)
    (root / "helper.py").write_text(HELPER)
    (root / "data" / "table.json").write_text('{"x": 1}\n')
    if js:
        (root / "ui").mkdir()
        (root / "index.html").write_text(INDEX_OK)
        (root / "main.js").write_text(MAIN_JS_OK)
        (root / "main.css").write_text("body { font-family: sans-serif; }\n")
        (root / "ui" / "widget.js").write_text("export function hello() { return 1; }\n")
        (root / "ui_api.py").write_text('def ping():\n    return "pong"\n')
    return root


def run_pack(capsys, src, out, entry="python", *extra):
    rc = pack.main(["--entry", entry, "--src", str(src), "--out", str(out)] + list(extra))
    return rc, capsys.readouterr()


def zip_names(path):
    with zipfile.ZipFile(path) as zf:
        return sorted(zf.namelist())


def test_pack_python_clean_build(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj", js=True)
    out = tmp_path / "build" / "upload-python"
    rc, cap = run_pack(capsys, src, out, "python")
    assert rc == 0, cap.out
    assert "RESULT: OK" in cap.out and "FAIL" not in cap.out
    assert zip_names(tmp_path / "build" / "upload-python.zip") == [
        "upload-python/data/table.json", "upload-python/helper.py",
        "upload-python/main.py", "upload-python/ui_api.py"]
    for left_out in ("index.html", "main.js", "main.css", "ui/widget.js"):
        assert not (out / left_out).exists()
        assert left_out in cap.out                      # listed as excluded
    assert SIG in cap.out


def test_pack_js_clean_build(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj", js=True)
    out = tmp_path / "build" / "ui-build"
    rc, cap = run_pack(capsys, src, out, "js", "--name", "my-project")
    assert rc == 0, cap.out
    names = zip_names(tmp_path / "build" / "ui-build.zip")
    assert {n.split("/")[0] for n in names} == {"my-project"}
    assert {n.split("/", 1)[1] for n in names} == {
        "data/table.json", "helper.py", "index.html", "main.css", "main.js", "main.py",
        "ui/widget.js", "ui_api.py"}


def test_pack_leaves_junk_out_and_zip_is_reproducible(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "helper.cpython-314.pyc").write_bytes(b"\x00junk")
    (src / ".DS_Store").write_bytes(b"\x00\x00")
    (src / "data" / ".DS_Store").write_bytes(b"\x00\x00")
    (src / "stale.pyc").write_bytes(b"\x00")
    out = tmp_path / "o" / "up"
    rc, cap = run_pack(capsys, src, out)
    assert rc == 0, cap.out
    first = (tmp_path / "o" / "up.zip").read_bytes()
    assert zip_names(tmp_path / "o" / "up.zip") == [
        "up/data/table.json", "up/helper.py", "up/main.py"]
    rc, cap = run_pack(capsys, src, out, "python", "--force")
    assert rc == 0
    assert (tmp_path / "o" / "up.zip").read_bytes() == first


def test_check_upload_flags_junk_that_reaches_the_folder(tmp_path, patterns):
    folder = make_project(tmp_path / "up")
    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    (folder / ".DS_Store").write_bytes(b"\x00")
    checks, _ = pack.check_upload(folder, "python")
    junk = next(c for c in checks if c.name.startswith("no __pycache__"))
    assert not junk.ok
    assert any("__pycache__/" in p for p in junk.problems)
    assert any(".DS_Store" in p for p in junk.problems)


def _replace_sig(new):
    def mutate(src):
        p = src / "main.py"
        p.write_text(p.read_text().replace(SIG, new))
    return mutate


def _append_main(text):
    def mutate(src):
        p = src / "main.py"
        p.write_text(p.read_text() + text)
    return mutate


def _write(rel, content):
    def mutate(src):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            (src / rel).write_bytes(content)
        else:
            (src / rel).write_text(content)
    return mutate


def _many_files(src):
    for i in range(98):
        (src / ("m%03d.py" % i)).write_text("X = %d\n" % i)


PY_FAILURES = {
    "oversize file": (_write("data/table.json", "x" * (pack.MAX_FILE_BYTES + 1)),
                      "data/table.json is 2,097,153 bytes"),
    "unreferenced data file": (_write("data/orphan.json", "{}\n"),
                               "data/orphan.json is not named by a plain string literal"),
    "data path only in an f-string": (
        lambda src: (src / "main.py").write_text((src / "main.py").read_text().replace(
            'TABLE = "data/table.json"', 'TABLE = f"data/table.json"')),
        "data/table.json is not named"),
    "signature over two lines": (_replace_sig('def main(shots: int = 100,\n'
                                              '         label: str = "a"):'),
                                 "whole signature of main() must be on one line"),
    "missing annotation": (_replace_sig("def main(shots=100):"),
                           "parameter 'shots' must be annotated with a bare int"),
    "string annotation": (_replace_sig('def main(shots: "int" = 100):'),
                          "must be annotated with a bare int"),
    "generic annotation": (_replace_sig("def main(shots: list[int] = 1):"),
                           "(got list[int])"),
    "negative default": (_replace_sig("def main(shots: int = -1):"), "negative default"),
    "default of the wrong type": (_replace_sig("def main(shots: int = 1.5):"),
                                  "default must be an int literal"),
    "non-literal default": (_replace_sig("def main(shots: int = len('ab')):"),
                            "default is not a literal"),
    "no default": (_replace_sig("def main(shots: int):"), "needs a literal default"),
    "keyword-only parameter": (_replace_sig("def main(*, shots: int = 1):"),
                               "keyword-only parameters"),
    "async main": (_replace_sig("async def main(shots: int = 1):"),
                   "need exactly one 'def main(' at column 0, found 0"),
    "two mains": (_append_main("\n\ndef main(x: int = 1):\n    pass\n"),
                  "need exactly one 'def main(' at column 0, found 2"),
    "__main__ guard": (_append_main('\n\nif __name__ == "__main__":\n    print("hi")\n'),
                       'remove the `if __name__ == "__main__"` block'),
    "module-level main() call": (_append_main("\n\nmain()\n"),
                                 "module-level call to main()"),
    "main() call in a guard": (_append_main('\n\nif "__main__" == __name__:\n    main()\n'),
                               "module-level call to main()"),
    "missing attribution": (_write("main.py", MAIN_OK.replace(ATTR, "Supported by friends")),
                            'no uploaded file contains "%s"' % ATTR),
    "too many files": (_many_files, "101 files (limit 100)"),
    "requirements option": (_write("requirements.txt", "numpy\n-r other.txt\n"),
                            "requirements.txt:2: options/flags"),
    "requirements marker": (_write("requirements.txt", "numpy; python_version > '3.8'\n"),
                            "requirements.txt:1: environment markers"),
    "requirements URL": (_write("requirements.txt", "# ok\npkg @ https://x/p.whl\n"),
                         "requirements.txt:2: URLs and direct references"),
    "requirements inline comment": (_write("requirements.txt", "scipy>=1.10  # why\n"),
                                    "requirements.txt:1: not a plain"),
    "syntax error": (_write("helper.py", "def broken(:\n"), "helper.py:1: does not parse"),
    "missing main.py": (lambda src: (src / "main.py").unlink(), "missing top-level main.py"),
    "scrub hit in a file": (_write("notes.txt", "contact forbiddenword\n"),
                            "notes.txt:1: P2:"),
    "scrub hit in a file name": (_write("data/XYZ.json", "{}\n"), "(name): P4:"),
}


@pytest.mark.parametrize("case", sorted(PY_FAILURES))
def test_pack_python_entry_detects_each_failure(tmp_path, patterns, capsys, case):
    mutate, expected = PY_FAILURES[case]
    src = make_project(tmp_path / "proj")
    mutate(src)
    out = tmp_path / "o" / "upload-python"
    stale = tmp_path / "o" / "upload-python.zip"
    stale.parent.mkdir()
    stale.write_bytes(b"stale zip from an earlier run")
    rc, cap = run_pack(capsys, src, out, "python", "--force")    # outside build/: --force
    assert rc == 1, cap.out
    assert expected in cap.out, cap.out
    assert "RESULT: FAILED" in cap.out
    assert not stale.exists() and not out.exists()


def test_pack_valid_requirements_and_main_variants_pass(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj")
    (src / "requirements.txt").write_text(
        "# Qollab bundles qiskit; extras and specifiers only\n\nnumpy>=1.26\n"
        "scipy >= 1.10, < 2\nqiskit[visualization]==2.5.2\n")
    (src / "main.py").write_text(MAIN_OK.replace(
        SIG, 'def main(n: int = 0, x: float = 2, s: str = "", on: bool = False):'))
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up")
    assert rc == 0, cap.out


JS_FAILURES = {
    "inline script": (_write("index.html", INDEX_OK + "<script>alert(1)</script>\n"),
                      "index.html:6: <script> tag"),
    "uppercase script": (_write("index.html", "<div>\n<SCRIPT src=x.js></SCRIPT></div>\n"),
                         "index.html:2: <script> tag"),
    "event-handler attribute": (
        _write("index.html", INDEX_OK.replace('type="button"', 'type="button" onclick="go()"')),
        "index.html:3: onclick= attribute on <button>"),
    "missing index.html": (lambda src: (src / "index.html").unlink(),
                           "missing top-level index.html"),
    "missing main.js": (lambda src: (src / "main.js").unlink(), "missing top-level main.js"),
    "unresolved python import": (_write("main.js", 'import * as api from "no_such_api";\n'),
                                 "'no_such_api' is not an uploaded Python module"),
    "unresolved relative import": (_write("main.js", 'import { a } from "./ui/missing.js";\n'),
                                   "'./ui/missing.js' does not resolve"),
    "external script host": (_write("main.js", 'import x from "https://x/x.js";\n'),
                             "only cdn.jsdelivr.net is allowed"),
}


@pytest.mark.parametrize("case", sorted(JS_FAILURES))
def test_pack_js_entry_detects_each_failure(tmp_path, patterns, capsys, case):
    mutate, expected = JS_FAILURES[case]
    src = make_project(tmp_path / "proj", js=True)
    mutate(src)
    out = tmp_path / "o" / "upload-js"
    rc, cap = run_pack(capsys, src, out, "js")
    assert rc == 1, cap.out
    assert expected in cap.out, cap.out
    assert not (tmp_path / "o" / "upload-js.zip").exists()


def test_pack_fails_when_scrub_patterns_are_missing(tmp_path, no_patterns, capsys):
    src = make_project(tmp_path / "proj")
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up")
    assert rc == 1
    assert "public-repo scrub" in cap.out and "not found" in cap.out
    assert not (tmp_path / "o" / "up.zip").exists()


def test_pack_keep_failed_keeps_the_folder(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj")
    (src / "data" / "orphan.json").write_text("{}\n")
    rc, _ = run_pack(capsys, src, tmp_path / "o" / "up", "python", "--keep-failed")
    assert rc == 1
    assert (tmp_path / "o" / "up" / "data" / "orphan.json").exists()
    assert not (tmp_path / "o" / "up.zip").exists()


def test_pack_refuses_unsafe_output_folders(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj")
    for bad in (src, src / "inside", tmp_path):
        rc, cap = run_pack(capsys, src, bad)
        assert rc == 2, bad
        assert "output folder" in cap.err
    keep = tmp_path / "precious"
    keep.mkdir()
    (keep / "important.txt").write_text("do not delete\n")
    rc, cap = run_pack(capsys, src, keep)
    assert rc == 2 and "--force" in cap.err
    assert (keep / "important.txt").exists()
    rc, cap = run_pack(capsys, src, keep, "python", "--force")
    assert rc == 0 and not (keep / "important.txt").exists()


def test_pack_never_removes_an_unrelated_zip_without_force(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj")
    (src / "data" / "orphan.json").write_text("{}\n")          # this build would fail
    mine = tmp_path / "o" / "up.zip"
    mine.parent.mkdir()
    mine.write_bytes(b"someone's own zip")
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up")
    assert rc == 2 and "--force" in cap.err
    assert mine.read_bytes() == b"someone's own zip"
    (src / "data" / "orphan.json").unlink()
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up")         # a passing build too
    assert rc == 2 and mine.read_bytes() == b"someone's own zip"


def test_pack_refuses_the_current_folder_and_git_repos(tmp_path, patterns, monkeypatch, capsys):
    src = make_project(tmp_path / "proj")
    here = tmp_path / "work" / "here"
    here.mkdir(parents=True)
    (here / "keep.txt").write_text("mine\n")
    monkeypatch.chdir(here)
    for bad in (here, here.parent):
        rc, cap = run_pack(capsys, src, bad, "python", "--force")
        assert rc == 2 and "output folder" in cap.err
    repo = tmp_path / "somerepo"
    (repo / ".git").mkdir(parents=True)
    rc, cap = run_pack(capsys, src, repo, "python", "--force")
    assert rc == 2 and "git repository" in cap.err
    assert (here / "keep.txt").exists() and (repo / ".git").is_dir()


def test_pack_symlinked_data_folder_is_reported_and_fails(tmp_path, patterns, capsys):
    """A symlinked folder is not uploaded; the data path the code names is then missing,
    which would fail on Qollab at run time, so the build fails here instead."""
    src = make_project(tmp_path / "proj")
    real = tmp_path / "elsewhere"
    shutil.move(str(src / "data"), str(real))
    os.symlink(real, src / "data")
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up")
    assert rc == 1, cap.out
    assert "symlinked folder" in cap.out
    assert "data/table.json is named in the code but is not in the upload" in cap.out


def test_pack_data_path_typo_fails(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj")
    p = src / "main.py"
    p.write_text(p.read_text().replace('"data/table.json"', '"data/tabel.json"'))
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up")
    assert rc == 1
    assert "data/tabel.json is named in the code but is not in the upload" in cap.out
    assert "data/table.json is not named by a plain string literal" in cap.out


def test_pack_accepts_html_escaped_attribution(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj", js=True)
    (src / "main.py").write_text(MAIN_OK.replace(ATTR, "no line here"))
    (src / "main.js").write_text(MAIN_JS_OK.replace(ATTR, "no line here"))
    (src / "index.html").write_text(INDEX_OK.replace(
        "</main>", "<p>%s</p>\n</main>" % ATTR.replace("&", "&amp;")))
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up", "js")
    assert rc == 0, cap.out
    assert "attribution line present" in cap.out


def test_pack_summary_masks_private_file_names(tmp_path, patterns, capsys):
    src = make_project(tmp_path / "proj")
    (src / "forbiddenword_notes.txt").write_text("fine\n")
    rc, cap = run_pack(capsys, src, tmp_path / "o" / "up")
    assert rc == 1
    assert "(name): P2:" in cap.out
    assert "forbiddenword" not in cap.out + cap.err
    assert "fo***********_notes.txt" in cap.out           # the file table, masked


def test_pack_real_project_python_entry(tmp_path, monkeypatch, capsys):
    p = tmp_path / "benign.txt"
    p.write_text(BENIGN)
    monkeypatch.setenv(scrub_check.ENV_VAR, str(p))
    out = tmp_path / "build" / "upload-python"
    rc, cap = run_pack(capsys, ROOT / "qollab_project", out, "python")
    assert rc == 0, cap.out
    names = zip_names(tmp_path / "build" / "upload-python.zip")
    rel = {n.split("/", 1)[1] for n in names}
    assert {n.split("/")[0] for n in names} == {"upload-python"}
    assert {"main.py", "chsh.py", "qk_runtime.py", "data/chsh_noise.json",
            "data/chsh_coverage.json", "data/chsh_aer_check.json",
            "data/chsh_ionq_like.json"} <= rel
    assert not rel & {"index.html", "main.js", "main.css"}
    assert not any(r.startswith("ui/") and r.endswith(".js") for r in rel)
    assert not any("__pycache__" in r or r.endswith(".pyc") for r in rel)
    assert len(rel) <= pack.MAX_FILES
    assert "def main(shots: int = 1000" in cap.out
