"""Static checks on the Observatory's JS UI (qollab_project/index.html, main.js, main.css,
ui/*.js), the stub harness (dev/) and the stub generator (tools/make_ui_stubs.py).

Nothing here needs a browser: the checks are the platform rules from
docs/platform-notes.md, the accessibility contract of docs/ui.md, public-repo hygiene,
and the contract between the stub generator and the stub API.
"""
import json
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "qollab_project")
ATTRIBUTION = "This effort is supported by Qollab & IonQ"
MAX_BYTES = 2_097_152

JS_FILES = ["qollab_project/main.js"] + sorted(
    "qollab_project/ui/" + f for f in os.listdir(os.path.join(PROJECT, "ui")) if f.endswith(".js"))
DEV_JS = ["dev/boot.js", "dev/stub_api.js"]
MY_FILES = JS_FILES + DEV_JS + ["qollab_project/index.html", "qollab_project/main.css", "dev/index.html",
                                "tools/make_ui_stubs.py", "docs/ui.md", "tests/test_ui_static.py"]
STUB_DATA = os.path.join(ROOT, "dev", "stub_data.js")


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def _strip_js_comments(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def _no_constants(name):
    raise ValueError("non-strict JSON constant %s" % name)


# ------------------------------------------------------------------ index.html

class _Fragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.ids, self.label_for, self.controls = [], set(), set(), []
        self.attrs_seen, self.in_label, self.attrs_by_tag = [], 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        self.attrs_by_tag.append((tag, a))
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
    p.feed(_read("qollab_project/index.html"))
    return p


def test_index_html_is_a_safe_body_fragment():
    src = _read("qollab_project/index.html")
    p = _fragment()
    for tag in ("script", "html", "head", "body", "link", "style", "iframe", "form", "object", "embed"):
        assert tag not in p.tags, "<%s> in index.html" % tag
    assert not [a for a in p.attrs_seen if a.lower().startswith("on")], "on* attribute in index.html"
    assert "style" not in p.attrs_seen                       # inline styles may be blocked by CSP
    assert "http://" not in src and "https://" not in src
    assert "fwo-app" in p.ids


def test_index_html_has_attribution_verbatim():
    assert ATTRIBUTION in _read("qollab_project/index.html")
    assert ATTRIBUTION in _read("qollab_project/main.js")


def test_every_control_has_a_label():
    p = _fragment()
    assert len(p.controls) >= 7
    for tag, cid, typ, wrapped in p.controls:
        assert wrapped or (cid and cid in p.label_for), "unlabelled %s#%s" % (tag, cid)


def test_persona_tabs_follow_the_aria_pattern():
    p = _fragment()
    tabs = [a for t, a in p.attrs_by_tag if a.get("role") == "tab"]
    panels = [a for t, a in p.attrs_by_tag if a.get("role") == "tabpanel"]
    assert len(tabs) == 3 and len(panels) == 3
    assert [t for t, a in p.attrs_by_tag if a.get("role") == "tablist"] == ["div"]
    assert sum(a.get("aria-selected") == "true" for a in tabs) == 1
    for a in tabs:
        assert a.get("aria-controls") in p.ids and a.get("tabindex") in ("0", "-1")
    for a in panels:
        assert a.get("aria-labelledby") in p.ids


def test_ids_used_by_js_exist_in_index_html():
    ids = _fragment().ids
    used = set()
    for path in JS_FILES:
        used |= set(re.findall(r'byId\("([\w-]+)"\)', _read(path)))
        used |= set(re.findall(r'whenMounted\("([\w-]+)"', _read(path)))
    for key in ("self", "demon", "observer"):
        used |= {"fwo-tab-" + key, "fwo-panel-" + key}
    assert used and not (used - ids), "missing ids: %s" % sorted(used - ids)


def test_live_regions_are_exactly_status_and_persona_line():
    src = _read("qollab_project/index.html")
    assert re.search(r'id="fwo-status"[^>]*role="status"[^>]*aria-live="polite"', src)
    assert re.search(r'id="fwo-poetic"[^>]*aria-live="polite"', src)
    assert "<output" not in src                          # an implicit second live region
    assert len(re.findall(r"\baria-live=", src)) == 2
    assert len(re.findall(r'\brole="(status|alert|log)"', src)) == 1
    for path in JS_FILES:
        code = _strip_js_comments(_read(path))
        assert "aria-live" not in code and '"output"' not in code, path


def test_sliders_cover_the_contract_ranges():
    src = _read("qollab_project/index.html")
    def rng(i):
        m = re.search(r'id="%s"[^>]*' % i, src).group(0)
        return {k: v for k, v in re.findall(r'(min|max|step|value)="([^"]+)"', m)}
    assert rng("fwo-intention") == {"min": "0", "max": "360", "step": "1", "value": "90"}
    assert rng("fwo-coupling") == {"min": "0", "max": "1", "step": "0.01", "value": "0"}
    assert rng("fwo-perspective") == {"min": "0", "max": "180", "step": "1", "value": "0"}
    assert rng("fwo-shots") == {"min": "1", "max": "4096", "step": "1", "value": "1024"}
    code = _strip_js_comments(_read("qollab_project/main.js"))
    assert code.count('setAttribute("aria-valuetext"') == 3


# ------------------------------------------------------------------ JS rules

@pytest.mark.parametrize("path", JS_FILES)
def test_js_obeys_the_platform_rules(path):
    raw = _read(path)
    code = _strip_js_comments(raw)
    assert "import.meta" not in code
    assert not re.search(r"\bimport\s*\(", code), "dynamic import() in %s" % path
    assert "localStorage" not in code and "sessionStorage" not in code and "indexedDB" not in code
    assert not re.search(r"\b(alert|confirm|prompt|open)\s*\(", code)
    assert not re.search(r"\bdocument\.write\b", code)
    assert "innerHTML" not in code                       # text goes in as text, never as markup
    urls = re.findall(r"https?://[^\s\"']+", code)
    assert set(urls) <= {"http://www.w3.org/2000/svg"}, urls
    assert all(ord(c) < 128 for c in raw), "non-ASCII character in %s (use \\u escapes)" % path
    assert not re.search(r"\bconsole\.(table|dir|group|time|trace|assert|count)\b", code)


def test_no_math_random_anywhere_in_the_project_js():
    """Decoration uses the seeded PRNG in ui/scene.js; data never uses randomness."""
    for path in JS_FILES:
        assert "Math.random" not in _strip_js_comments(_read(path)), path
    assert "export function mulberry32" in _read("qollab_project/ui/scene.js")


def test_ui_modules_import_nothing():
    for path in JS_FILES[1:]:
        assert not re.search(r"(?m)^\s*import\b", _read(path)), path


def test_main_js_imports_and_ending():
    src = _read("qollab_project/main.js")
    code = _strip_js_comments(src)
    specs = re.findall(r'(?m)^import .* from "([^"]+)";$', code)
    assert specs[0] == "observatory_api" and specs[1] == "three"
    assert all(s.startswith("./ui/") for s in specs[2:]) and len(specs) >= 5
    assert re.search(r'(?m)^import \* as api from "observatory_api";$', code)
    assert re.search(r'(?m)^import \* as THREE from "three";$', code)
    assert not re.search(r'import\s+\w+\s+from\s+"observatory_api"', code)   # default import is undefined
    lines = [ln for ln in code.splitlines() if ln.strip()]
    first_other = next(i for i, ln in enumerate(lines) if not ln.startswith("import "))
    assert not any(ln.startswith("import ") for ln in lines[first_other:]), "imports must all be at the top"
    assert lines[-1].strip() == "await new Promise(() => {});"
    assert "callPromising" in code and "JSON.parse(String(" in code
    assert 'callPy(api.profile_json, "profile_json", BACKEND, true)' in code
    assert code.count("BACKEND, true") == 1                  # nothing else resets the one-job count
    for fn in ("predict_json", "run_json", "curves_json"):
        assert "api." + fn in code, fn
    assert re.search(r"\b(\w+)\.name \?\? \1\.backend_name\b", code)
    assert "No resolved influence" in _read("qollab_project/ui/text.js")


def test_run_handler_guards_before_its_first_await():
    code = _strip_js_comments(_read("qollab_project/main.js"))
    handler = code[code.index('el.run.addEventListener("click"'):]
    first_await = handler.index("await ")
    head = handler[:first_await]
    assert "if (running || el.run.disabled || (oneJob && jobsUsed >= 1)) return;" in head
    assert "running = true;" in head and "jobsUsed += 1;" in head
    assert "if (oneJob) lockRun();" in head


def test_scene_exposes_text_alternatives_and_mappings():
    code = _read("qollab_project/ui/scene.js")
    assert 'setAttribute("role", "img")' in code and 'setAttribute("aria-label"' in code
    assert "Math.cbrt(p1)" in code and "2 + 10 * p1" in code      # radius ~ cbrt(p), thickness 2 + 10 p px
    assert "0.15 + 0.85 * I" in code                            # bridge opacity follows connection
    assert "requestAnimationFrame" in code and "reduced" in code


def test_css_honours_reduced_motion_and_scopes_everything():
    css = _read("qollab_project/main.css")
    assert "@media (prefers-reduced-motion: reduce)" in css
    # one Google Fonts stylesheet may be imported (team decision, 2026-10-11); nothing else external
    fonts = re.compile(r'(?m)^@import (?:url\()?"https://fonts\.googleapis\.com/css2\?[^"\s]+"\)?;$')
    assert len(fonts.findall(css)) <= 1
    rest = fonts.sub("", css)
    assert "@import" not in rest and "url(" not in rest
    for line in css.splitlines():
        s = line.strip()
        if s.endswith("{") and not s.startswith(("@", "#fwo-app", "}")) and s != "{":
            raise AssertionError("unscoped selector: " + s)


# ------------------------------------------------------------------ contrast

def _css_vars():
    css = _read("qollab_project/main.css")
    return dict(re.findall(r"--(fwo-[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", css))


def _lum(hex_color):
    def chan(c):
        c = int(c, 16) / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * chan(hex_color[1:3]) + 0.7152 * chan(hex_color[3:5]) + 0.0722 * chan(hex_color[5:7])


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


TEXT_PAIRS = [  # (foreground, background): body and UI text, >= 4.5:1
    ("fwo-text", "fwo-bg"), ("fwo-text", "fwo-surface"), ("fwo-text", "fwo-surface-2"), ("fwo-text", "fwo-info-bg"),
    ("fwo-muted", "fwo-bg"), ("fwo-muted", "fwo-surface"), ("fwo-muted", "fwo-surface-2"),
    ("fwo-self", "fwo-bg"), ("fwo-self", "fwo-surface"), ("fwo-self", "fwo-surface-2"),
    ("fwo-world", "fwo-bg"), ("fwo-world", "fwo-surface"), ("fwo-world", "fwo-surface-2"),
    ("fwo-on-accent", "fwo-self-strong"), ("fwo-on-accent", "fwo-self"),
    ("fwo-ok-fg", "fwo-ok-bg"), ("fwo-warn-fg", "fwo-warn-bg"), ("fwo-error-fg", "fwo-error-bg"),
    ("fwo-ghost", "fwo-bg"), ("fwo-muted", "fwo-info-bg"),
]
NON_TEXT_PAIRS = [  # focus ring, control borders, chart strokes: >= 3:1
    ("fwo-focus", "fwo-bg"), ("fwo-focus", "fwo-surface"), ("fwo-control", "fwo-bg"), ("fwo-control", "fwo-surface"),
    ("fwo-self-strong", "fwo-bg"), ("fwo-self-strong", "fwo-surface"), ("fwo-chart-band", "fwo-bg"),
    ("fwo-chart-forecast", "fwo-bg"), ("fwo-ghost", "fwo-surface"), ("fwo-world", "fwo-surface-2"),
]


@pytest.mark.parametrize("fg,bg", TEXT_PAIRS)
def test_text_contrast_at_least_4_5(fg, bg):
    v = _css_vars()
    assert contrast(v[fg], v[bg]) >= 4.5, "%s on %s: %.2f" % (fg, bg, contrast(v[fg], v[bg]))


@pytest.mark.parametrize("fg,bg", NON_TEXT_PAIRS)
def test_non_text_contrast_at_least_3(fg, bg):
    v = _css_vars()
    assert contrast(v[fg], v[bg]) >= 3.0, "%s on %s: %.2f" % (fg, bg, contrast(v[fg], v[bg]))


# ------------------------------------------------------------------ hygiene + size

def _joined(*parts):
    """Build a guarded pattern from fragments so this file never spells the words it bans
    (the repo's own scrub would otherwise flag this test)."""
    return "".join(parts)


FORBIDDEN = [
    _joined("/Us", "ers/"), _joined("/ho", "me/"), r"\b\d{1,3}(?:\.\d{1,3}){3}\b", r"[\w.+-]+@[\w-]+\.[a-z]{2,}",
    _joined(r"\bs", r"sh\b"), _joined(r"\bsu", r"do\b"), _joined(r"\bng", r"inx\b"), _joined(r"\bsys", r"temd\b"),
    _joined(r"\bcloud", "flare"), _joined(r"\bwire", r"guard\b"), _joined(r"\bu", r"fw\b"),
    _joined(r"\bhost", r"name\b"), r"\.local\b", _joined(r"\blocal", r"host\b"), _joined("127", r"\.0\.0\.1"),
]


@pytest.mark.parametrize("rel", MY_FILES + ["dev/stub_data.js"])
def test_no_machine_details_and_under_2mb(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        pytest.skip(rel + " not generated")
    assert os.path.getsize(path) < MAX_BYTES, rel
    text = _read(rel)
    for pat in FORBIDDEN:
        if rel == "tests/test_ui_static.py":
            break                                  # this file holds the patterns themselves
        hits = [m.group(0) for m in re.finditer(pat, text)]
        # the dev harness may name the loopback address in a comment about serving locally
        if rel.startswith(("dev/", "docs/", "tests/")) and pat in (r"\blocalhost\b", r"127\.0\.0\.1"):
            continue
        assert not hits, "%s matches %s: %s" % (rel, pat, hits[:3])
    assert "48-thread x86 workstation" in text or "workstation" not in text.lower() or rel == "dev/stub_data.js"


def test_every_project_file_under_2mb():
    for folder, _, files in os.walk(PROJECT):
        for f in files:
            if f.startswith(".") or f.endswith((".pyc",)):
                continue
            assert os.path.getsize(os.path.join(folder, f)) < MAX_BYTES, f


# ------------------------------------------------------------------ dev harness + stubs

def test_dev_index_import_map_and_wiring():
    src = _read("dev/index.html")
    m = re.search(r'<script type="importmap">\s*(\{.*?\})\s*</script>', src, re.S)
    assert m, "no import map"
    imports = json.loads(m.group(1))["imports"]
    assert imports["observatory_api"] == "./stub_api.js"
    assert imports["three"].startswith("https://cdn.jsdelivr.net/npm/three@0.186.1/")
    assert imports["three/addons/"].startswith("https://cdn.jsdelivr.net/npm/three@0.186.1/")
    assert 'href="../qollab_project/main.css"' in src
    boot = _read("dev/boot.js")
    assert '"../qollab_project/main.js"' in boot and '"../qollab_project/index.html"' in boot


def test_stub_data_is_strict_json_per_entry():
    if not os.path.exists(STUB_DATA):
        pytest.skip("dev/stub_data.js not generated (run tools/make_ui_stubs.py)")
    text = _read("dev/stub_data.js")
    body = text.split("export const STUB = ", 1)[1].rstrip().rstrip(";")
    data = json.loads(body, parse_constant=_no_constants)
    assert set(data) >= {"profiles", "predicts", "runs", "curves", "settings", "model_version"}
    for kind in ("basic", "ionq", "error"):
        assert "profile" in data["profiles"][kind] and "mode" in data["profiles"][kind]
    import make_ui_stubs
    keys = {make_ui_stubs.settings_key(*s) for s in make_ui_stubs.SETTINGS}
    assert set(data["predicts"]) == keys == set(data["runs"]["basic"])
    for key, p in data["predicts"].items():
        json.loads(json.dumps(p), parse_constant=_no_constants)
        assert 0.0 <= p["ideal"]["p_self_1"] <= 1.0 and "probe_distributions" in p["ideal"]
    for key, r in data["runs"]["basic"].items():
        assert r["status"] == "completed" and r["bit_order"] == "SelfWorld"
        assert set(r["counts"]) == {"display", "intent_low", "intent_high", "connection"}
        assert r["source"]["bit_order_check"]["orientation_ok"] is True
        assert set(r["explanation"]["poetic"]) == {"self", "demon", "observer"}
    assert data["runs"]["ionq:refused"]["status"] == "failed"
    assert all(r["status"] == "failed" for r in data["runs"]["error"].values())
    assert data["runs"]["basic"]["90|1|0|1024"]["metrics"]["resolved"] is False
    assert data["runs"]["basic"]["90|0|0|1024"]["metrics"]["resolved"] is True


def test_settings_key_format_matches_the_js_stub():
    import make_ui_stubs
    assert make_ui_stubs.settings_key(90, 0.0, 0, 1024) == "90|0|0|1024"
    assert make_ui_stubs.settings_key(90, 0.5, 45, 1024) == "90|0.5|45|1024"
    assert make_ui_stubs.settings_key(180, 1.0, 0, 512) == "180|1|0|512"


# ------------------------------------------------------------------ node checks

def _node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    return node


@pytest.mark.parametrize("path", JS_FILES + DEV_JS)
def test_js_syntax_with_node(path):
    node = _node()
    with open(os.path.join(ROOT, path), "rb") as fh:
        out = subprocess.run([node, "--input-type=module", "--check"], stdin=fh, capture_output=True, timeout=60)
    assert out.returncode == 0, out.stderr.decode()


def test_main_js_parses_as_an_async_function_body():
    """Emulates Qollab: imports become `await require(...)`, the file runs as the body
    of an async function with console/setTimeout/backend injected."""
    node = _node()
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


def test_stub_closed_form_matches_the_engine():
    """The JS stub synthesizes forecasts for settings without canned data from the
    closed-form distributions; they must agree with observatory.prediction."""
    if not os.path.exists(STUB_DATA):
        pytest.skip("dev/stub_data.js not generated")
    node = _node()
    import observatory
    settings = {"intention_rad": 1.1, "world_coupling": 0.37, "perspective_rad": 0.4, "shots_per_probe": 200}
    script = r"""
const m = await import(process.argv[1]);
const out = JSON.parse(await m.predict_json.callPromising(process.argv[2]));
console.log(JSON.stringify(out.ideal));
"""
    out = subprocess.run([node, "--input-type=module", "-e", script, os.path.join(ROOT, "dev", "stub_api.js"),
                          json.dumps(settings)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    ideal = json.loads(out.stdout.strip().splitlines()[-1])
    ref = observatory.prediction(settings)
    for key in ("p_self_1", "p_low", "p_high", "capacity", "openness_bits", "connection_bits"):
        assert abs(ideal[key] - ref[key]) < 1e-9, key
    for probe, dist in ref["probe_distributions"].items():
        for k, p in dist.items():
            assert abs(ideal["probe_distributions"][probe][k] - p) < 1e-9, (probe, k)


# ------------------------------------------------------------------ contract conformance

def _path(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            assert isinstance(cur, dict) and part in cur, "missing %s (at %r)" % (dotted, part)
            cur = cur[part]
    return cur


RUN_FIELDS_READ_BY_THE_UI = [
    "status", "bit_order", "model_version",
    "settings.intention_rad", "settings.world_coupling", "settings.perspective_rad", "settings.shots_per_probe",
    "settings.gamma_rad",
    "source.provider_family", "source.backend_name", "source.mode", "source.simulator", "source.noisy", "source.remote",
    "source.job_id", "source.job_returned", "source.submitted_as", "source.n_circuits", "source.wall_s",
    "source.shots_requested", "source.shots_seen.display", "source.shots_seen.connection", "source.versions",
    "source.bit_order_check.orientation_ok", "source.bit_order_check.p_flip_0to1_mean",
    "source.bit_order_check.p_flip_1to0_mean", "source.layout.n_circuits", "source.layout.qubits_per_circuit",
    "metrics.p_self_1", "metrics.p_low", "metrics.p_high", "metrics.capacity", "metrics.capacity_ci95.0",
    "metrics.capacity_ci95.1", "metrics.hoeffding_e", "metrics.openness_bits", "metrics.connection_bits",
    "metrics.resolved", "metrics.shots_seen.display",
    "prediction.p_self_1", "prediction.capacity", "prediction.openness_bits", "prediction.connection_bits",
    "explanation.factual", "explanation.poetic.self", "explanation.poetic.demon", "explanation.poetic.observer",
    "explanation.animation.self", "explanation.animation.demon", "explanation.animation.observer",
    "explanation.note",
    "baselines.fixed_output.capacity", "baselines.fixed_output.openness_bits", "baselines.fixed_output.label",
    "baselines.fixed_output.description", "baselines.fair_coin.capacity", "baselines.fair_coin.openness_bits",
    "baselines.fair_coin.label", "baselines.fair_coin.description", "baselines.note",
] + ["counts.%s.%s" % (p, k) for p in ("display", "intent_low", "intent_high", "connection") for k in ("00", "01", "10", "11")]

PREDICT_FIELDS_READ_BY_THE_UI = [
    "settings.intention_rad", "settings.world_coupling", "settings.perspective_rad", "settings.shots_per_probe",
    "ideal.p_self_1", "ideal.p_low", "ideal.p_high", "ideal.capacity", "ideal.openness_bits", "ideal.connection_bits",
    "ideal.formula_p_self_1", "ideal.probe_distributions.display.10", "noisy_ionq_like",
    "baselines.fixed_output.capacity", "baselines.fair_coin.openness_bits", "baselines.note", "model_version",
]

PROFILE_FIELDS_READ_BY_THE_UI = [
    "profile.name", "profile.family", "profile.noisy", "profile.remote", "profile.max_qubits", "profile.one_job",
    "mode", "one_job", "model_version",
]

CURVE_FIELDS_READ_BY_THE_UI = [
    "theory.w", "theory.capacity", "theory.p_low", "theory.p_high", "theory.connection_bits", "theory.openness_bits",
    "theory.source", "theory.provenance",
    "noise.capacity", "noise.x_name", "noise.p_self_1", "noise.connection_bits", "noise.fixed", "noise.note", "noise.source",
    "coverage.rows.0.w", "coverage.rows.0.capacity_exact", "coverage.rows.0.shots", "coverage.rows.0.repeats",
    "coverage.rows.0.coverage_95", "coverage.rows.0.mean_width", "coverage.source",
]


def test_every_field_the_ui_reads_exists_in_the_live_contract():
    """main.js / ui/*.js read these paths from the four observatory_api replies; a rename
    on the Python side must fail here, not silently show n/a on the page."""
    from qiskit.providers.basic_provider import BasicSimulator
    import observatory_api
    import qk_runtime
    be = BasicSimulator()
    be.set_options(seed_simulator=3)
    qk_runtime.begin_run()
    profile = json.loads(observatory_api.profile_json(be, True), parse_constant=_no_constants)
    for dotted in PROFILE_FIELDS_READ_BY_THE_UI:
        _path(profile, dotted)
    settings = json.dumps({"intention_rad": 1.0, "world_coupling": 0.5, "perspective_rad": 0.2, "shots_per_probe": 32})
    pred = json.loads(observatory_api.predict_json(settings), parse_constant=_no_constants)
    for dotted in PREDICT_FIELDS_READ_BY_THE_UI:
        _path(pred, dotted)
    if pred["noisy_ionq_like"] is not None:
        for key in ("p_self_1", "p_low", "p_high", "capacity", "openness_bits", "connection_bits", "note"):
            assert key in pred["noisy_ionq_like"], key
    run = json.loads(observatory_api.run_json(be, settings), parse_constant=_no_constants)
    assert run["status"] == "completed", run.get("error")
    for dotted in RUN_FIELDS_READ_BY_THE_UI:
        _path(run, dotted)
    assert isinstance(run["metrics"]["resolved"], bool)
    assert run["source"]["bit_order_check"]["orientation_ok"] is True
    curves = json.loads(observatory_api.curves_json(), parse_constant=_no_constants)
    assert "error" not in curves, curves.get("error")
    for dotted in CURVE_FIELDS_READ_BY_THE_UI:
        _path(curves, dotted)
    assert curves["noise"]["x_name"] in curves["noise"]           # the x series is stored under x_name
    if curves["theory"]["provenance"]:
        for key in ("generator", "git_commit", "machine", "created_utc"):
            assert key in curves["theory"]["provenance"], key
    # a failed run carries the evidence fields the error view reads
    failed = json.loads(observatory_api.run_json(be, json.dumps({"shots_per_probe": 0})), parse_constant=_no_constants)
    assert failed["status"] == "failed" and "error" in failed and "source" in failed
    for key in ("job_id", "job_returned", "n_circuits", "submitted_as"):
        assert key in failed["source"], key


def test_unresolved_wording_and_the_scene_text_match_the_layout():
    text = _read("qollab_project/ui/text.js")
    readings = _read("qollab_project/ui/readings.js")
    assert 'NO_RESOLVED = "No resolved influence at this shot count."' in text
    assert "txt.NO_RESOLVED" in readings and "NO_RESOLVED" in text.split("capacitySentence", 1)[1]
    # Future 1 is the upper right sphere and Future 0 the lower right one (ui/scene.js P.f1 / P.f0)
    scene = _read("qollab_project/ui/scene.js")
    assert re.search(r"f1: \[2\.25, 1\.02, 0\], f0: \[2\.25, -1\.05, 0\]", scene)
    assert "upper right sphere" in text and "lower right sphere" in text
    assert "left sphere" not in text and "right sphere) holds" not in text.replace("upper right sphere", "").replace("lower right sphere", "")
    # the theory chart draws no noisy line, so the summary must not describe one
    assert "dotted line" not in text
    assert "fwo-c-line--noisy" not in _read("qollab_project/main.js")


def test_scene_releases_the_gpu_when_detached_or_lost():
    scene = _read("qollab_project/ui/scene.js")
    assert "webglcontextlost" in scene and "ev.preventDefault()" in scene
    assert "canvas.isConnected" in scene and "renderer.dispose()" in scene and "forceContextLoss" in scene
    assert "api.dispose = dispose" in scene
    assert "mesh.userData.tubeKey" in scene                     # tube geometry rebuilt only on change
    main = _read("qollab_project/main.js")
    assert "el.motion.disabled = true" in main                 # no WebGL: the Motion control says so
    boot = _read("dev/boot.js")
    assert 'params.get("nowebgl") === "1"' in boot


def test_run_error_evidence_uses_the_submission_markers():
    code = _strip_js_comments(_read("qollab_project/ui/readings.js"))
    body = code[code.index("export function renderRunError"):]
    assert "src.job_returned && !stale" in body
    assert "src.n_circuits || src.submitted_as" in body
    assert '"No job reached the backend."' in body
    main = _strip_js_comments(_read("qollab_project/main.js"))
    assert "renderRunError(dom, el.runError, r, current && current.source ? current.source.job_id : null)" in main
