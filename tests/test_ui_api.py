"""P3: the JSON bridge (reference/chsh/ui_api.py) and static checks on the JS UI shell."""
import json
import math
import os
import re
import shutil
import subprocess
import time
from html.parser import HTMLParser

import pytest
from qiskit.providers.basic_provider import BasicSimulator

import chsh
import qk_noise
import qk_runtime
import ui_api

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "reference/chsh")
SQRT8 = 2 * math.sqrt(2)
ATTRIBUTION = "This effort is supported by Qollab & IonQ"


def _no_constants(name):
    raise ValueError("non-strict JSON constant %s" % name)


def strict(text):
    """json.loads that rejects NaN/Infinity, and checks the result is a dict."""
    assert isinstance(text, str)
    obj = json.loads(text, parse_constant=_no_constants)
    assert isinstance(obj, dict)
    return obj


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class CountingBackend:
    """BasicSimulator wrapper that counts backend.run calls; everything else delegates."""

    def __init__(self, inner=None):
        self._inner = inner or BasicSimulator()
        self.jobs = 0

    def __getattr__(self, item):
        return getattr(self._inner, item)

    def run(self, *a, **k):
        self.jobs += 1
        return self._inner.run(*a, **k)


class OneJobBackend(CountingBackend):
    """Profiles as an IonQ simulator (one job per run) but runs locally."""
    __module__ = "qiskit_ionq.ionq_backend"
    name = "ionq_simulator"
    num_qubits = 29


class FailingBackend(CountingBackend):
    def run(self, *a, **k):
        self.jobs += 1
        raise RuntimeError("provider down")


@pytest.fixture(autouse=True)
def fresh_session():
    ui_api._UI["jobs"] = 0
    qk_runtime.begin_run()
    yield
    ui_api._UI["jobs"] = 0


def _seeded(seed=11):
    be = BasicSimulator()
    be.set_options(seed_simulator=seed)
    return be


# ------------------------------------------------------------------ strict JSON everywhere

def test_every_function_returns_strict_json():
    be = CountingBackend(_seeded())
    run = strict(ui_api.run_chsh_json(be, 500, "auto", True))
    outs = [
        ui_api.profile_json(be),
        ui_api.noise_dial_json("{}"),
        ui_api.noise_dial_json(json.dumps({"preset": "ionq_forte_like_spam", "scale": 3})),
        ui_api.curve_json(),
        ui_api.card_text_json(json.dumps(run["card"])),
        # error paths are strict JSON too
        ui_api.profile_json(None),
        ui_api.noise_dial_json("{\"p2\": NaN}"),
        ui_api.card_text_json("not json"),
        ui_api.run_chsh_json(None, 100),
    ]
    for text in outs:
        strict(text)
        assert not re.search(r"[:\[,]\s*-?(NaN|Infinity)\b", text)


def test_public_names():
    for name in ("profile_json", "noise_dial_json", "run_chsh_json", "curve_json", "card_text_json"):
        assert callable(getattr(ui_api, name)) and name in ui_api.__all__
    assert ui_api.ATTRIBUTION == ATTRIBUTION


# ------------------------------------------------------------------ profile

def test_profile_basic_and_one_job():
    p = strict(ui_api.profile_json(BasicSimulator()))
    assert p["family"] == "basic" and p["one_job"] is False and p["remote"] is False
    assert p["preferred_mode"] in ("tile", "list") and p["run_allowed"] is True
    assert "not a test of nature" in p["sim_note"]
    q = strict(ui_api.profile_json(OneJobBackend()))
    assert q["family"] == "ionq_sim" and q["one_job"] is True and q["preferred_mode"] == "tile"
    assert "one job per run" in q["job_policy"]


# ------------------------------------------------------------------ noise dial

def test_noise_dial_endpoints():
    d0 = strict(ui_api.noise_dial_json(json.dumps({"preset": "custom", "p2": 0.0})))
    assert d0["S"] == pytest.approx(SQRT8, abs=1e-9)
    assert d0["exceeds"] is True and d0["classical_bound"] == 2.0
    assert d0["quantum_ideal"] == pytest.approx(SQRT8, abs=1e-12)
    for t in d0["terms"]:
        assert sum(t["dist"].values()) == pytest.approx(1.0, abs=1e-12)
        assert set(t["dist"]) == {"00", "01", "10", "11"}
    star = 1 - 1 / math.sqrt(2)
    d1 = strict(ui_api.noise_dial_json(json.dumps({"p2": star})))
    assert d1["S"] == pytest.approx(2.0, abs=1e-9)
    assert d1["exceeds"] is False and d1["shots_per_setting_3sigma"] is None
    assert "at or below the classical bound" in d1["reading"]


@pytest.mark.parametrize("params", [
    {"p2": 0.1},
    {"p1": 0.01, "p2": 0.05, "r01": 0.02, "r10": 0.04},
    {"p2": 0.02, "scale": 3.5},
])
def test_noise_dial_matches_chsh_exact(params):
    d = strict(ui_api.noise_dial_json(json.dumps(params)))
    spec = qk_noise.NoiseSpec(p1=params.get("p1", 0.0), p2=params.get("p2", 0.0),
                              readout=(params.get("r01", 0.0), params.get("r10", 0.0)),
                              scale=params.get("scale", 1.0))
    ref = chsh.exact(spec)
    assert d["S"] == pytest.approx(ref["S"], abs=1e-12)
    for label, e in ref["E"].items():
        assert d["E"][label] == pytest.approx(e, abs=1e-12)
    assert d["noise"]["effective"]["p2"] == pytest.approx(spec.effective()[1])


def test_noise_dial_reading_and_shots():
    d = strict(ui_api.noise_dial_json(json.dumps({"p2": 0.1, "r01": 0.02, "r10": 0.02})))
    assert d["exceeds"] is True and d["shots_per_setting_3sigma"] > 1
    assert d["reading"].startswith("Under this noise model quantum theory predicts S = %.3f" % d["S"])
    assert "%d" % d["shots_per_setting_3sigma"] in d["reading"].replace(",", "")


@pytest.mark.parametrize("preset,spam", [("ionq_forte_like", False), ("ionq_forte_like_spam", True)])
def test_noise_dial_presets(preset, spam):
    for scale in (0.0, 1.0, 40.0):
        d = strict(ui_api.noise_dial_json(json.dumps({"preset": preset, "scale": scale,
                                                      "p2": 0.9})))   # p2 ignored by presets
        ref = chsh.exact(qk_noise.ionq_forte_like(spam=spam, scale=scale))
        assert d["preset"] == preset
        assert d["S"] == pytest.approx(ref["S"], abs=1e-12)
        assert d["preset_note"] == qk_noise.IONQ_PRESET_NOTE
        assert d["noise"]["readout"] == ([0.005, 0.005] if spam else [0.0, 0.0])
    assert strict(ui_api.noise_dial_json(json.dumps({"preset": preset, "scale": 0})))["S"] == \
        pytest.approx(SQRT8, abs=1e-9)


@pytest.mark.parametrize("bad", [
    {"preset": "nope"}, {"p2": -0.1}, {"p2": "abc"}, {"scale": -1}, {"r01": 2.0}, {"p2": True},
])
def test_noise_dial_bad_params_return_error(bad):
    d = strict(ui_api.noise_dial_json(json.dumps(bad)))
    assert set(d) == {"error"} and d["error"]


@pytest.mark.parametrize("text", ["[1, 2]", "{bad json", "{\"p2\": Infinity}"])
def test_noise_dial_bad_json_returns_error(text):
    assert "error" in strict(ui_api.noise_dial_json(text))


def test_noise_dial_is_fast():
    payload = json.dumps({"p2": 0.12, "r01": 0.01, "r10": 0.01})
    ui_api.noise_dial_json(payload)                      # warm up (builds the circuits once)
    best = min(_timed(ui_api.noise_dial_json, payload) for _ in range(5))
    assert best < 0.100, "noise_dial_json took %.1f ms" % (1000 * best)


def _timed(fn, *args):
    t0 = time.perf_counter()
    fn(*args)
    return time.perf_counter() - t0


# ------------------------------------------------------------------ one job

def test_run_is_exactly_one_backend_run_and_returns_a_card():
    be = CountingBackend(_seeded(5))
    r = strict(ui_api.run_chsh_json(be, 2000, "auto", True))
    assert "error" not in r, r.get("error")
    assert be.jobs == 1 and r["job_submitted"] is True
    card = r["card"]
    assert card["schema"] == "claim-card/1" and card["witness"] == "CHSH"
    assert card["verdict"] == "exceeds classical bound"
    assert abs(card["raw"]["value"] - SQRT8) < 4 * card["raw"]["se"]
    assert card["shots"] == 2000 and card["simulator"] is True
    assert r["canary"]["orientation_ok"] is True
    assert [t["label"] for t in r["terms"]] == [t["label"] for t in chsh.SPEC["terms"]]
    assert all(t["n"] == 2000 for t in r["terms"])
    assert r["layout"]["n_circuits"] >= 1 and r["layout"]["canary"] is True
    assert r["mitigation_note"].startswith("not applied")      # ideal simulator: no flips
    assert r["profile"]["jobs_this_session"] == 1


@pytest.mark.parametrize("mode", ["tile", "list"])
def test_run_modes_and_mitigation_flag(mode):
    be = CountingBackend(_seeded(9))
    r = strict(ui_api.run_chsh_json(be, 300, mode, False))
    assert be.jobs == 1 and r["mode"] == mode and r["layout"]["mode"] == mode
    assert r["mitigation_note"] == "not requested" and r["card"]["mitigated"] is None


def test_run_accepts_js_style_values():
    be = CountingBackend(_seeded(3))
    r = strict(ui_api.run_chsh_json(be, 400.0, "AUTO", "false"))   # JS number, odd case, string bool
    assert be.jobs == 1 and r["card"]["shots"] == 400 and r["mitigation_note"] == "not requested"


def test_one_job_backend_refuses_a_second_run():
    be = OneJobBackend(_seeded(4))
    first = strict(ui_api.run_chsh_json(be, 200, "auto", True))
    assert "error" not in first and be.jobs == 1 and first["mode"] == "tile"
    assert strict(ui_api.profile_json(be))["run_allowed"] is False
    second = strict(ui_api.run_chsh_json(be, 200, "auto", True))
    assert "one job per run" in second["error"] and second["job_submitted"] is False
    assert be.jobs == 1


def test_new_run_flag_resets_the_one_job_count():
    """main.js calls profile_json(backend, true) once per page load. If Qollab reused the
    interpreter for a new run, the previous run's job must not block this run's one job."""
    be = OneJobBackend(_seeded(6))
    assert "error" not in strict(ui_api.run_chsh_json(be, 200, "auto", True))
    assert strict(ui_api.profile_json(be))["run_allowed"] is False         # same run: still used
    assert "one job per run" in strict(ui_api.run_chsh_json(be, 200))["error"]
    p = strict(ui_api.profile_json(be, True))                               # a new run starts
    assert p["run_allowed"] is True and p["jobs_this_session"] == 0
    assert "error" not in strict(ui_api.run_chsh_json(be, 200, "auto", True))
    assert be.jobs == 2
    assert strict(ui_api.profile_json(be, "false"))["run_allowed"] is False  # only true resets


class JsNull:
    """Stands in for pyodide.ffi.jsnull (what a JS null becomes in Python)."""


def test_js_null_backend_is_treated_as_missing():
    assert "no backend" in strict(ui_api.profile_json(JsNull()))["error"]
    r = strict(ui_api.run_chsh_json(JsNull(), 100))
    assert "no backend" in r["error"] and r["job_submitted"] is False


def test_local_backend_allows_repeat_runs():
    be = CountingBackend(_seeded(8))
    for _ in range(2):
        assert "error" not in strict(ui_api.run_chsh_json(be, 100, "auto", True))
    assert be.jobs == 2


@pytest.mark.parametrize("shots,mode", [(0, "auto"), (-5, "auto"), (10**6, "auto"), ("x", "auto"),
                                        (100, "sideways")])
def test_run_bad_inputs_return_error_without_a_job(shots, mode):
    be = CountingBackend()
    r = strict(ui_api.run_chsh_json(be, shots, mode, True))
    assert r["error"] and r["job_submitted"] is False and be.jobs == 0


def test_run_backend_failure_returns_error_with_evidence():
    be = FailingBackend()
    r = strict(ui_api.run_chsh_json(be, 100, "auto", True))
    assert "provider down" in r["error"] and be.jobs == 1
    assert r["job_submitted"] is True            # the attempt counts against a one-job budget
    assert r["job"]["n_circuits"] >= 1


def test_run_without_backend_is_an_error():
    r = strict(ui_api.run_chsh_json(None, 100))
    assert "no backend" in r["error"]


# ------------------------------------------------------------------ curves + card text

def _check_curves(c):
    p2 = c["p2_curve"]
    assert len(p2["x"]) == len(p2["S"]) == 71 and p2["x"][0] == 0.0
    assert p2["S"][0] == pytest.approx(SQRT8, abs=1e-6)
    assert p2["lambda_star"] == pytest.approx(1 - 1 / math.sqrt(2), abs=1e-6)
    assert p2["source"] == "precomputed" and p2["provenance"]["machine"] == "48-thread x86 workstation"
    ionq = c["ionq_like"]
    assert len(ionq["x"]) == len(ionq["S"]) and ionq["S_at_scale_1"] > 2.7
    assert 40 < ionq["crossing_scale"] < 70
    assert len(c["coverage"]["rows"]) == 4
    assert 0 < c["aer_check"]["max_abs_diff"] < 1e-12 and c["aer_check"]["n_settings"] == 15
    assert c["classical_bound"] == 2.0


def test_curve_json_from_repo_root():
    _check_curves(strict(ui_api.curve_json()))


def test_curve_json_from_project_dir(monkeypatch):
    monkeypatch.chdir(PROJECT)                  # how Qollab runs it: literal relative paths
    _check_curves(strict(ui_api.curve_json()))


def test_curve_json_falls_back_when_data_missing(monkeypatch):
    def missing(key):
        raise OSError("no such file")
    monkeypatch.setattr(ui_api, "_data_text", missing)
    c = strict(ui_api.curve_json())
    assert c["p2_curve"]["source"].startswith("computed in this session")
    assert c["p2_curve"]["lambda_star"] == pytest.approx(1 - 1 / math.sqrt(2), abs=1e-3)
    assert c["ionq_like"]["source"].startswith("computed in this session")
    assert c["coverage"]["rows"] == [] and c["aer_check"]["n_settings"] == 0


def test_data_files_are_named_by_literal_paths():
    src = _read("reference/chsh/ui_api.py")
    for name in ("chsh_noise", "chsh_ionq_like", "chsh_coverage", "chsh_aer_check"):
        assert re.search(r'open\("data/%s\.json"' % name, src), name
        assert os.path.exists(os.path.join(PROJECT, "data", name + ".json"))


def test_card_text_json():
    be = CountingBackend(_seeded(2))
    card = strict(ui_api.run_chsh_json(be, 300))["card"]
    t = strict(ui_api.card_text_json(json.dumps(card)))
    assert "CLAIM CARD" in t["text"] and "VERDICT:" in t["text"] and "not a test of nature" in t["text"]
    assert all(len(line) <= 100 for line in t["text"].splitlines())
    assert t["markdown"].startswith("## Claim card: chsh")
    assert strict(ui_api.card_text_json(card))["text"] == t["text"]      # dict accepted too
    for bad in ("", "{}", "[1]", "{oops"):
        assert set(strict(ui_api.card_text_json(bad))) == {"error"}


# ------------------------------------------------------------------ static checks: JS shell

JS_FILES = ["reference/chsh/main.js"] + sorted(
    "reference/chsh/ui/" + f for f in os.listdir(os.path.join(PROJECT, "ui")) if f.endswith(".js"))


def _strip_js_comments(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


@pytest.mark.parametrize("path", JS_FILES)
def test_js_has_no_import_meta_or_dynamic_import(path):
    code = _strip_js_comments(_read(path))
    assert "import.meta" not in code
    assert not re.search(r"\bimport\s*\(", code), "dynamic import() in %s" % path
    assert "localStorage" not in code and "sessionStorage" not in code
    assert not re.search(r"\b(alert|confirm|prompt)\s*\(", code)
    urls = re.findall(r"https?://[^\s\"']+", code)
    assert set(urls) <= {"http://www.w3.org/2000/svg"}, urls       # only the SVG namespace
    assert "innerHTML" not in code                 # text goes in as text, never as markup
    assert all(ord(c) < 128 for c in _read(path)), "non-ASCII character in %s" % path


def test_ui_modules_import_nothing():
    for path in JS_FILES[1:]:
        assert not re.search(r"(?m)^\s*import\b", _read(path)), path


def test_main_js_imports_and_ending():
    src = _read("reference/chsh/main.js")
    code = _strip_js_comments(src)
    assert re.search(r'(?m)^import \* as api from "ui_api";$', code)
    assert not re.search(r'import\s+\w+\s+from\s+"ui_api"', code)          # default import is undefined
    specs = re.findall(r'(?m)^import .* from "([^"]+)";$', code)
    assert specs[0] == "ui_api" and all(s.startswith("./") for s in specs[1:])
    lines = [ln for ln in code.splitlines() if ln.strip()]
    first_other = next(i for i, ln in enumerate(lines) if not ln.startswith("import "))
    assert not any(ln.startswith("import ") for ln in lines[first_other:]), "imports must all be at the top"
    assert lines[-1].strip() == "await new Promise(() => {});"
    assert "callPromising" in code and "JSON.parse(String(" in code
    assert re.search(r"\b(\w+)\.name \?\? \1\.backend_name\b", code)      # name may be missing
    assert re.search(r"\bconsole\.(log|error)\(", code)
    assert not re.search(r"\bconsole\.(table|dir|group|time|trace|assert)\b", code)
    assert ATTRIBUTION in src


def test_main_js_parses_as_an_async_function_body():
    """Emulates Qollab: imports become `await require(...)`, the file runs as the body
    of an async function with console/setTimeout/backend injected. Needs node."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    script = r"""
const fs = require("fs");
let s = fs.readFileSync(process.argv[1], "utf8");
s = s.replace(/^import \* as (\w+) from ("[^"]+");$/gm, "const $1 = await require($2);")
     .replace(/^import \{([^}]+)\} from ("[^"]+");$/gm, "const {$1} = await require($2);");
if (/^\s*(import|export)\b/m.test(s)) throw new Error("import/export left after transform");
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction("require", "console", "setTimeout", "backend", s);
console.log("ok");
"""
    out = subprocess.run([node, "-e", script, os.path.join(PROJECT, "main.js")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr


@pytest.mark.parametrize("path", JS_FILES + ["reference/chsh/dev/stub_api.js", "reference/chsh/dev/boot.js"])
def test_js_syntax_with_node(path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    with open(os.path.join(ROOT, path), "rb") as fh:
        out = subprocess.run([node, "--input-type=module", "--check"], stdin=fh,
                             capture_output=True, timeout=60)
    assert out.returncode == 0, out.stderr.decode()


# ------------------------------------------------------------------ static checks: HTML + CSS

class _Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.ids, self.label_for, self.controls = [], set(), set(), []
        self.attrs_seen, self.stack, self.in_label = [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        self.attrs_seen.extend(k for k, _ in attrs)
        if "id" in a:
            assert a["id"] not in self.ids, "duplicate id %s" % a["id"]
            self.ids.add(a["id"])
        if tag == "label":
            self.in_label += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        if tag in ("input", "select", "textarea"):
            self.controls.append((tag, a.get("id"), a.get("type"), self.in_label > 0))

    def handle_endtag(self, tag):
        if tag == "label":
            self.in_label -= 1


def _fragment():
    p = _Fragment()
    p.feed(_read("reference/chsh/index.html"))
    return p


def test_index_html_is_a_safe_body_fragment():
    src = _read("reference/chsh/index.html")
    p = _fragment()
    for tag in ("script", "html", "head", "body", "link", "style", "iframe", "form"):
        assert tag not in p.tags, "<%s> in index.html" % tag
    assert not [a for a in p.attrs_seen if a.lower().startswith("on")], "on* attribute in index.html"
    assert "style" not in p.attrs_seen                       # inline styles may be blocked by CSP
    assert "http://" not in src and "https://" not in src
    assert "qh-app" in p.ids


def test_index_html_has_attribution_verbatim():
    assert ATTRIBUTION in _read("reference/chsh/index.html")


def test_every_control_has_a_label():
    p = _fragment()
    assert p.controls
    for tag, cid, typ, wrapped in p.controls:
        assert wrapped or (cid and cid in p.label_for), "unlabelled %s#%s" % (tag, cid)


def test_ids_used_by_js_exist_in_index_html():
    ids = _fragment().ids
    used = set()
    for path in JS_FILES:
        used |= set(re.findall(r'byId\("([\w-]+)"\)', _read(path)))
        used |= set(re.findall(r'whenMounted\("([\w-]+)"', _read(path)))
    used |= set(re.findall(r'"(qh-[\w-]+-field)"', _read("reference/chsh/ui/experiment.js")))
    assert used and not (used - ids), "missing ids: %s" % sorted(used - ids)


def test_status_and_reading_are_live_regions():
    src = _read("reference/chsh/index.html")
    assert re.search(r'id="qh-status"[^>]*role="status"[^>]*aria-live="polite"', src)
    assert re.search(r'id="qh-dial-reading"[^>]*aria-live="polite"', src)
    # Only those two: <output> is an implicit role="status" live region, so slider
    # values shown in one would be announced twice (aria-valuetext already says them).
    assert "<output" not in src
    assert len(re.findall(r"\baria-live=", src)) == 2
    assert len(re.findall(r'\brole="(status|alert|log)"', src)) == 1
    for path in JS_FILES:
        code = _strip_js_comments(_read(path))
        assert "aria-live" not in code and '"output"' not in code, path


def test_main_js_starts_a_new_run_and_guards_double_clicks():
    code = _strip_js_comments(_read("reference/chsh/main.js"))
    assert 'callPy(api.profile_json, "profile_json", BACKEND, true)' in code
    assert code.count("BACKEND, true") == 1                  # nothing else resets the count
    handler = code[code.index('runBtn.addEventListener("click"'):]
    first_await = handler.index("await ")
    for guard in ("if (running || runBtn.disabled || (oneJob && jobsUsed >= 1)) return;",
                  "running = true;", "jobsUsed += 1;", "if (oneJob) lockRun();"):
        assert -1 < handler.index(guard) < first_await, guard   # all before the first await


def _node_or_skip():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    return node


@pytest.mark.parametrize("key", ["p2_curve", "ionq_like"])
@pytest.mark.parametrize("width", [254, 553, 600, 1000])
def test_chart_ticks_and_labels(key, width):
    """Runs ui/chart.js in node with a fake SVG builder on the real curves: tick labels
    must be evenly spaced (a 0.25 step once printed 2.75 as 2.8), and each reference-line
    label must sit at the end of the plot where the curve is far from that line."""
    node = _node_or_skip()
    curve = strict(ui_api.curve_json())[key]
    script = r"""
const { pathToFileURL } = await import("node:url");
const dom = await import(pathToFileURL(process.argv[1] + "/ui/dom.js").href);
const { renderChart } = await import(pathToFileURL(process.argv[1] + "/ui/chart.js").href);
const c = JSON.parse(process.argv[2]); const width = Number(process.argv[3]);
const node = (tag, attrs, ...kids) => ({ tag, attrs, kids: kids.flat(), appendChild(k) { this.kids.push(k); } });
let root = null;
const lib = { svg: node, fmt: dom.fmt, replace: (el, r) => { root = r; } };
renderChart(lib, { clientWidth: width }, { id: "t", title: "t", desc: "d", xLabel: "x", yLabel: "S",
  xs: c.x, ys: c.S, hLines: [{ y: 2, kind: "bound", short: "S = 2" }, { y: 2 * Math.SQRT2, kind: "ideal", short: "ideal" }],
  marker: null, point: null });
const texts = [];
const walk = (n) => { if (!n || typeof n !== "object") return; if (n.tag === "text") texts.push(n); (n.kids || []).forEach(walk); };
walk(root);
const label = (t) => t.kids.join("");
console.log(JSON.stringify({
  y: texts.filter((t) => t.attrs["text-anchor"] === "end" && !t.attrs.class).map(label),
  x: texts.filter((t) => t.attrs["text-anchor"] === "middle" && !t.attrs.class).map(label),
  lines: texts.filter((t) => t.attrs.class === "qh-c-label").map((t) => [label(t), t.attrs["text-anchor"]]),
}));
"""
    out = subprocess.run([node, "--input-type=module", "-e", script, PROJECT, json.dumps(curve), str(width)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    res = json.loads(out.stdout.strip().splitlines()[-1])
    for axis in ("y", "x"):
        vals = [float(s.replace("−", "-")) for s in res[axis]]
        assert len(vals) >= 2 and len(set(res[axis])) == len(vals), res[axis]
        steps = [b - a for a, b in zip(vals, vals[1:])]
        assert max(steps) - min(steps) < 1e-9, (axis, res[axis])
    sides = dict(res["lines"])
    assert sides == {"S = 2": "start", "ideal": "end"}, sides   # curves start at 2.83 and fall


def test_dial_reading_is_announced_once_the_dial_settles():
    """Runs ui/dial.js in node against a fake DOM and a virtual clock: six slider steps
    250 ms apart (a person tapping an arrow key) must write the aria-live reading once,
    not six times, and the reading must match the final setting."""
    node = _node_or_skip()
    script = r"""
const { pathToFileURL } = await import("node:url");
const base = process.argv[1];
const dom = await import(pathToFileURL(base + "/ui/dom.js").href);
const { createDial } = await import(pathToFileURL(base + "/ui/dial.js").href);
let now = 0; let timers = [];
const setTimeoutFn = (f, ms) => { timers.push({ at: now + ms, f }); };
async function advance(ms) {
  const end = now + ms;
  for (;;) {
    timers.sort((a, b) => a.at - b.at);
    const next = timers[0];
    if (!next || next.at > end) break;
    timers.shift(); now = next.at; next.f();
    for (let i = 0; i < 10; i++) await Promise.resolve();
  }
  now = end;
}
const els = {};
let writes = 0; let readingText = "";
const reading = { get textContent() { return readingText; }, set textContent(v) { writes++; readingText = v; } };
function el(id) {
  if (id === "qh-dial-reading") return reading;
  return els[id] ||= { id, textContent: "", hidden: false, className: "", style: {}, value: "0",
    classList: { toggle() {} }, attrs: {}, listeners: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    addEventListener(t, f) { (this.listeners[t] ||= []).push(f); },
    fire(t) { for (const f of this.listeners[t] || []) f(); } };
}
el("qh-preset").value = "custom";
const lib = Object.assign({}, dom, { byId: el, h: () => ({}), replace: () => {}, table: () => ({}) });
const exp = { gaugeMax: 3, outcomeColumns: [], termName: () => "",
  presets: { custom: { fields: ["qh-p2-field"], curve: "p2" } },
  dialParams: (preset, v) => ({ preset, p2: v.p2 }) };
let calls = 0;
const callDial = async (p) => { calls++; const S = 2.8284 - 2.8284 * p.p2;
  return { S, exceeds: S > 2, reading: "S = " + S.toFixed(3), terms: [], noise: { effective: {} } }; };
const dial = createDial(lib, exp, { callDial, setTimeoutFn });
await dial.refresh();
const out = { afterLoad: writes };
const slider = el("qh-p2");
for (let i = 1; i <= 6; i++) { slider.value = String(0.01 * i); slider.fire("input"); await advance(250); }
out.duringSteps = writes;
await advance(3000);
out.afterSettle = writes; out.text = readingText; out.calls = calls;
console.log(JSON.stringify(out));
"""
    out = subprocess.run([node, "--input-type=module", "-e", script, PROJECT],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res["afterLoad"] == 1                     # first reading is written at once
    assert res["calls"] == 7                         # the number still updates on every step
    assert res["duringSteps"] == 1                   # nothing announced while still moving
    assert res["afterSettle"] == 2                   # one announcement after it settles
    assert res["text"] == "S = %.3f" % (2.8284 - 2.8284 * 0.06)


def test_css_is_scoped_and_respects_reduced_motion():
    css = _read("reference/chsh/main.css")
    assert "@import" not in css and "url(" not in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    selectors = re.findall(r"(?m)^([^@{}\s][^{}]*)\{", body)
    for sel in selectors:
        for part in sel.split(","):
            assert part.strip().startswith("#qh-app"), "unscoped selector %r" % part.strip()


def _contrast(a, b):
    def lum(h):
        r, g, bl = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bl)
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_text_color_contrast_at_least_4_5():
    tok = dict(re.findall(r"--qh-([a-z-]+):\s*(#[0-9a-fA-F]{6})", _read("reference/chsh/main.css")))
    pairs = [("text", "bg"), ("text", "surface"), ("text", "info-bg"), ("muted", "bg"),
             ("muted", "surface"), ("muted", "info-bg"), ("on-accent", "accent"),
             ("on-accent", "accent-hover"), ("pass-fg", "pass-bg"), ("fail-fg", "fail-bg"),
             ("warn-fg", "warn-bg"), ("text", "fail-bg")]
    for fg, bg in pairs:
        assert _contrast(tok[fg], tok[bg]) >= 4.5, (fg, bg)
    for line in ("control", "focus", "chart-curve", "chart-bound", "chart-ideal", "chart-star"):
        assert _contrast(tok[line], tok["bg"]) >= 3.0, line         # non-text UI contrast


# ------------------------------------------------------------------ public-repo hygiene

@pytest.mark.parametrize("path", JS_FILES + [
    "reference/chsh/index.html", "reference/chsh/main.css", "reference/chsh/ui_api.py",
    "reference/chsh/dev/index.html", "reference/chsh/dev/boot.js", "reference/chsh/dev/stub_api.js", "reference/chsh/dev/stub_data.js",
    "reference/chsh/make_ui_stubs.py", "reference/chsh/UI.md"])
def test_no_machine_details_in_ui_files(path):
    src = _read(path)
    for home in ("Users", "home"):                       # no home-directory paths
        assert "/%s/" % home not in src
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", src), "IP-like address in %s" % path
    assert not re.search(r"[\w.+-]+@[A-Za-z][\w-]*\.[A-Za-z]{2,}", src), "email-like text in %s" % path
    assert ("local" + "host") not in src.lower()
