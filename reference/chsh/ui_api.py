"""JSON bridge between the JavaScript UI (main.js) and the Python toolkit.

Every public function takes plain values or JSON strings and returns a JSON STRING
of a plain dict (strict JSON: NaN/inf become null). Nothing here raises to the
caller: a failure comes back as {"error": "..."} so the page can show it.

    profile_json(backend, new_run=False)        backend profile + preferred packing mode
    noise_dial_json(params_json)                exact CHSH S under a noise setting
    run_chsh_json(backend, shots, mode, mitigate)   ONE job, claim card + diagnostics
    curve_json()                                precomputed noise curves + validation numbers
    card_text_json(card_json)                   plain-text (and Markdown) claim card

Called from main.js as `await api.fn.callPromising(...)` and parsed with
`JSON.parse(String(ret))`. print() inside these functions would not reach the
page, so everything the page needs is in the return value.

Simulators compute what quantum theory predicts, and how a noise model degrades
it; they are not tests of nature. The texts returned here say so.

This effort is supported by Qollab & IonQ
"""

import json
import math
import os
import time

import chsh
import qk_cards
import qk_data
import qk_estimators
import qk_noise
import qk_runtime

__all__ = [
    "profile_json", "noise_dial_json", "run_chsh_json", "curve_json", "card_text_json",
    "PRESETS", "ATTRIBUTION",
]

ATTRIBUTION = "This effort is supported by Qollab & IonQ"
PRESETS = ("custom", "ionq_forte_like", "ionq_forte_like_spam")
MODES = ("auto", "tile", "tiles", "list")
SHOTS_MIN, SHOTS_MAX = 1, 100000
BOUND = float(chsh.SPEC["classical"])
IDEAL = float(chsh.SPEC["quantum"])
_EPS = 1e-12            # S must clear the bound by more than float noise to count as "above"
_DIGITS = 6             # rounding for the compact curve series

# Data files, by literal relative path: Qollab ships a data file to the browser only
# when a string literal in the code names it, so _data_text opens each one literally.
DATA_FILES = {
    "noise": "data/chsh_noise.json",
    "ionq_like": "data/chsh_ionq_like.json",
    "coverage": "data/chsh_coverage.json",
    "aer_check": "data/chsh_aer_check.json",
}

# Outcome keys are Qiskit's: Bob's bit (qubit 1) on the left, Alice's (qubit 0) on the right.
OUTCOME_KEYS = ("00", "01", "10", "11")
SETTING_DEGREES = {k: round(math.degrees(v), 6) for k, v in chsh.ANGLES.items()}

_UI = {"jobs": 0}       # jobs submitted through run_chsh_json in this interpreter
_CIRCUITS = {}          # term label -> unmeasured circuit (built once; the dial reuses them)


# ---------------------------------------------------------------- plumbing

def _dumps(obj):
    """Strict JSON text: numpy cast, NaN/inf -> null; never emits NaN/Infinity."""
    return json.dumps(qk_data.json_safe(obj), allow_nan=False, separators=(",", ":"))


def _error(exc, **extra):
    msg = "%s: %s" % (type(exc).__name__, exc) if isinstance(exc, BaseException) else str(exc)
    out = {"error": msg[:600]}
    out.update(extra)
    return out


def _parse_obj(text, what):
    if _missing(text) or text == "":
        return {}
    if isinstance(text, dict):
        return dict(text)
    obj = json.loads(str(text), parse_constant=_reject_constant)
    if not isinstance(obj, dict):
        raise ValueError("%s must be a JSON object" % what)
    return obj


def _reject_constant(name):
    raise ValueError("non-standard JSON constant %s" % name)


def _finite(value, what, lo=0.0, hi=None):
    if isinstance(value, bool):
        raise ValueError("%s must be a number" % what)
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number, got %r" % (what, value))
    if not math.isfinite(x):
        raise ValueError("%s must be finite" % what)
    if x < lo or (hi is not None and x > hi):
        raise ValueError("%s must be in [%g, %s], got %g" % (what, lo, "inf" if hi is None else "%g" % hi, x))
    return x


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _missing(value):
    """True for None and for Pyodide's stand-ins for JS null/undefined."""
    return value is None or type(value).__name__ in ("JsNull", "JsUndefined")


def _here():
    f = globals().get("__file__")
    return os.path.dirname(os.path.abspath(f)) if f else os.getcwd()


def _data_text(key):
    """Text of one shipped data file (cwd = project folder on Qollab; next to this
    module under CPython)."""
    try:
        if key == "noise":
            fh = open("data/chsh_noise.json", encoding="utf-8")
        elif key == "ionq_like":
            fh = open("data/chsh_ionq_like.json", encoding="utf-8")
        elif key == "coverage":
            fh = open("data/chsh_coverage.json", encoding="utf-8")
        elif key == "aer_check":
            fh = open("data/chsh_aer_check.json", encoding="utf-8")
        else:
            raise KeyError(key)
    except OSError:
        fh = open(os.path.join(_here(), DATA_FILES[key]), encoding="utf-8")
    with fh:
        return fh.read()


# ---------------------------------------------------------------- profile

def _profile_dict(backend):
    profile = qk_runtime.backend_profile(backend)
    one_job = bool(profile.get("one_job"))
    used = _UI["jobs"]
    if one_job:
        explain = ("This backend accepts one job per run. Run submits that one job; "
                   "to submit another, run the project again.")
    else:
        explain = "Local simulator: no job limit. Each press of Run submits one job."
    out = dict(profile)
    out.update({
        "preferred_mode": qk_runtime.preferred_mode(profile, "auto"),
        "simulator": profile.get("family") != "ionq_qpu",
        "jobs_this_session": used,
        "run_allowed": not (one_job and used >= 1),
        "job_policy": explain,
        "sim_note": qk_cards.SIM_NOTE if profile.get("family") != "ionq_qpu" else None,
    })
    return out


def profile_json(backend, new_run=False):
    """Backend profile (qk_runtime.backend_profile) + preferred packing mode + job policy.

    new_run=True marks the start of a new Qollab run (main.js passes it once, at page
    load): the one-job count starts again from zero, so an interpreter reused across
    runs cannot refuse the new run's one job. Nothing else should pass it."""
    try:
        if _as_bool(new_run):
            _UI["jobs"] = 0
            qk_runtime.begin_run()
        if _missing(backend):
            raise ValueError("no backend was passed in")
        return _dumps(_profile_dict(backend))
    except Exception as exc:
        return _dumps(_error(exc))


# ---------------------------------------------------------------- noise dial

def _circuits():
    if not _CIRCUITS:
        for t in chsh.SPEC["terms"]:
            _CIRCUITS[t["label"]] = chsh.circuit_for(t)
    return _CIRCUITS


def _parity(dist):
    return sum(p * (1.0 if k.count("1") % 2 == 0 else -1.0) for k, p in dist.items())


def _noise_from_params(params):
    preset = str(params.get("preset") or "custom").strip().lower()
    if preset not in PRESETS:
        raise ValueError("preset must be one of %s, got %r" % (", ".join(PRESETS), preset))
    scale = _finite(params.get("scale", 1.0), "scale", 0.0, 1000.0)
    if preset == "custom":
        spec = qk_noise.NoiseSpec(
            p1=_finite(params.get("p1", 0.0), "p1", 0.0, 4.0 / 3.0),
            p2=_finite(params.get("p2", 0.0), "p2", 0.0, 16.0 / 15.0),
            readout=(_finite(params.get("r01", 0.0), "r01", 0.0, 1.0),
                     _finite(params.get("r10", 0.0), "r10", 0.0, 1.0)),
            scale=scale)
    else:
        spec = qk_noise.ionq_forte_like(spam=preset.endswith("_spam"), scale=scale)
    return preset, spec


def _exact_terms(spec):
    terms, S = [], 0.0
    for t in chsh.SPEC["terms"]:
        dist = qk_noise.exact_distribution(_circuits()[t["label"]], [0, 1], spec)
        e = _parity(dist)
        S += t["coef"] * e
        terms.append({"label": t["label"], "vars": list(t["vars"]), "coef": t["coef"], "E": e,
                      "dist": {k: float(dist.get(k, 0.0)) for k in OUTCOME_KEYS}})
    return S, terms


def _reading(S, exceeds, shots3):
    if exceeds:
        return ("Under this noise model quantum theory predicts S = %.3f, above the classical "
                "bound of 2 by %.3f; about %s shots per setting would put a run 3 standard "
                "errors above the bound." % (S, S - BOUND, "{:,}".format(shots3)))
    return ("Under this noise model quantum theory predicts S = %.3f, at or below the classical "
            "bound of 2, so no number of shots would show a CHSH violation at this noise level."
            % S)


def noise_dial_json(params_json="{}"):
    """Exact CHSH S (density matrix, no sampling) under a NoiseSpec from
    {"p1", "p2", "r01", "r10", "scale", "preset"}; presets ignore p1/p2/r01/r10."""
    t0 = time.perf_counter()
    try:
        params = _parse_obj(params_json, "params")
        preset, spec = _noise_from_params(params)
        S, terms = _exact_terms(spec)
        E = {t["label"]: t["E"] for t in terms}
        exceeds = S > BOUND + _EPS
        shots3 = None
        if exceeds:
            sd = qk_estimators.witness_sd_per_shot(chsh.SPEC, E)
            shots3 = int(qk_estimators.shots_for_sigma(S - BOUND, sd, k=3))
        out = {
            "preset": preset,
            "noise": spec.to_dict(),
            "S": S,
            "E": E,
            "terms": terms,
            "outcome_key_order": "Bob's bit then Alice's bit (Qiskit order, qubit 0 rightmost)",
            "settings_degrees": SETTING_DEGREES,
            "classical_bound": BOUND,
            "quantum_ideal": IDEAL,
            "exceeds": exceeds,
            "margin": S - BOUND,
            "shots_per_setting_3sigma": shots3,
            "reading": _reading(S, exceeds, shots3),
            "preset_note": None if preset == "custom" else qk_noise.IONQ_PRESET_NOTE,
            "sim_note": qk_cards.SIM_NOTE,
        }
        out["elapsed_ms"] = round(1000 * (time.perf_counter() - t0), 3)
        return _dumps(out)
    except Exception as exc:
        return _dumps(_error(exc))


# ---------------------------------------------------------------- one job

def _job_evidence():
    keep = ("n_circuits", "submitted_as", "shots_requested", "job_returned", "job_id",
            "job_class", "submit_s", "result_s", "wall_s", "result_retry", "failed_circuits")
    return {k: qk_runtime.LAST_RUN[k] for k in keep if k in qk_runtime.LAST_RUN}


def _layout(summ):
    out = {k: summ.get(k) for k in ("mode", "canary", "max_qubits", "n_circuits",
                                     "qubits_per_circuit", "clbits_per_circuit")}
    out["n_blocks"] = len(summ.get("blocks") or [])
    return out


def _mitigation_note(requested, card, canary):
    """Why the card has (or lacks) a mitigated value; mirrors chsh.analyze's rule."""
    if not requested:
        return "not requested"
    if card.get("mitigated"):
        return "applied: %s" % card["mitigated"].get("method", "readout inversion")
    p01 = (canary or {}).get("p_flip_0to1_mean")
    p10 = (canary or {}).get("p_flip_1to0_mean")
    if not isinstance(p01, (int, float)) or not isinstance(p10, (int, float)) \
            or not (math.isfinite(p01) and math.isfinite(p10)):
        return "not applied: the canary gave no readout flip rates"
    if p01 <= 0 and p10 <= 0:
        return "not applied: the canary saw no readout flips, so there was nothing to invert"
    return "not applied: readout error too large to invert reliably (1 - p01 - p10 <= 0.2)"


def run_chsh_json(backend, shots=1000, mode="auto", mitigate=True):
    """ONE job through chsh.run: canary + the four CHSH settings, then a claim card.

    Never calls backend.run twice: qk_runtime's guard covers one call, and this module
    refuses a second job on a one-job backend for the life of the interpreter."""
    submitted = 0
    try:
        if _missing(backend):
            raise ValueError("no backend was passed in")
        shots = int(_finite(shots, "shots", SHOTS_MIN, SHOTS_MAX))
        mode = str(mode or "auto").strip().lower()
        if mode not in MODES:
            raise ValueError("mode must be one of %s, got %r" % (", ".join(MODES), mode))
        mitigate = _as_bool(mitigate)
        qk_runtime.begin_run()
        profile = qk_runtime.backend_profile(backend)
        if profile.get("one_job") and _UI["jobs"] >= 1:
            return _dumps({"error": "one job per run: this backend already received its job "
                                    "in this run; run the project again to submit another",
                           "job_submitted": False, "one_job": True})
        mode_used = qk_runtime.preferred_mode(profile, mode)
        try:
            card, details = chsh.run(backend, shots=shots, mode=mode_used, mitigate=mitigate,
                                     profile=profile)
        finally:
            submitted = qk_runtime.jobs_submitted()
            _UI["jobs"] += submitted
        analysis = details["analysis"]
        mit = analysis.get("mitigated") or {}
        terms = []
        for t in chsh.SPEC["terms"]:
            raw_t = analysis["raw"]["terms"][t["label"]]
            mit_t = (mit.get("terms") or {}).get(t["label"]) or {}
            terms.append({"label": t["label"], "vars": list(t["vars"]), "coef": t["coef"],
                          "E": raw_t["E"], "se": raw_t["se"], "n": raw_t["n"],
                          "E_mitigated": mit_t.get("E"), "se_mitigated": mit_t.get("se")})
        out = {
            "card": card,
            "mitigation_note": _mitigation_note(mitigate, card, analysis.get("canary")),
            "canary": analysis.get("canary"),
            "terms": terms,
            "layout": _layout(details["layout"]),
            "mode": mode_used,
            "mode_requested": mode,
            "profile": _profile_dict(backend),
            "job": _job_evidence(),
            "job_submitted": submitted > 0,
            "jobs_this_session": _UI["jobs"],
        }
        return _dumps(out)
    except Exception as exc:
        try:
            evidence = _job_evidence()
        except Exception:
            evidence = {}
        try:
            return _dumps(_error(exc, job_submitted=submitted > 0, job=evidence,
                                 jobs_this_session=_UI["jobs"]))
        except Exception:           # evidence not JSON-safe: still never raise to JS
            return _dumps(_error(exc, job_submitted=submitted > 0, jobs_this_session=_UI["jobs"]))


# ---------------------------------------------------------------- precomputed curves

def _r(x):
    return None if x is None else round(float(x), _DIGITS)


def _provenance(ds, path):
    return {"file": path, "generator": ds.get("generator"), "git_commit": ds.get("git_commit"),
            "created_utc": ds.get("created_utc"), "machine": ds.get("machine"),
            "versions": ds.get("versions")}


def _load(key):
    return qk_data.parse_dataset(_data_text(key))


def _first_crossing(xs, ys):
    """Linear interpolation of the first x where y falls to the bound."""
    for i in range(1, len(xs)):
        if ys[i - 1] > BOUND >= ys[i]:
            x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
            return x0 + (y0 - BOUND) * (x1 - x0) / (y0 - y1)
    return None


def _p2_curve():
    try:
        ds = _load("noise")
        rows = [r for r in ds["results"]["rows"] if "S" in r]
        d = ds["results"].get("derived", {})
        return {
            "x": [_r(r["params"].get("p2", 0.0)) for r in rows],
            "S": [_r(r["S"]) for r in rows],
            "shots_3sigma": [r.get("shots_3sigma") for r in rows],
            "x_name": "p2",
            "x_label": "two-qubit depolarizing strength p2",
            "lambda_star": d.get("lambda_star_numeric"),
            "lambda_star_theory": d.get("lambda_star_theory", chsh.LAMBDA_STAR),
            "source": "precomputed",
            "provenance": _provenance(ds, DATA_FILES["noise"]),
        }
    except Exception as exc:
        xs = [round(0.01 * i, 2) for i in range(36)]
        ys = [_exact_terms(qk_noise.NoiseSpec(p2=x))[0] for x in xs]
        return {
            "x": xs, "S": [_r(y) for y in ys], "shots_3sigma": None,
            "x_name": "p2", "x_label": "two-qubit depolarizing strength p2",
            "lambda_star": _first_crossing(xs, ys), "lambda_star_theory": chsh.LAMBDA_STAR,
            "source": "computed in this session (data file unavailable: %s)" % type(exc).__name__,
            "provenance": None,
        }


def _ionq_curve():
    try:
        ds = _load("ionq_like")
        rows = ds["results"]["rows"]
        xs = [float(r["params"]["scale"]) for r in rows]
        ys = [float(r["S"]) for r in rows]
        fixed = ds["params"].get("fixed", {})
        source, prov = "precomputed", _provenance(ds, DATA_FILES["ionq_like"])
    except Exception as exc:
        xs = [float(2 * i) for i in range(41)]
        ys = [_exact_terms(qk_noise.ionq_forte_like(scale=x))[0] for x in xs]
        fixed = {"p1": qk_noise.IONQ_FORTE1_R1Q, "p2": qk_noise.IONQ_FORTE1_R2Q}
        source = "computed in this session (data file unavailable: %s)" % type(exc).__name__
        prov = None
    at1 = next((y for x, y in zip(xs, ys) if x == 1.0), None)
    first_le = next((x for x, y in zip(xs, ys) if y <= BOUND), None)
    return {
        "x": [_r(x) for x in xs], "S": [_r(y) for y in ys],
        "x_name": "scale",
        "x_label": "IonQ-like preset scale (multiple of the published rates)",
        "fixed": fixed, "S_at_scale_1": at1,
        "first_scale_at_or_below_bound": first_le,
        "crossing_scale": _first_crossing(xs, ys),
        "note": qk_noise.IONQ_PRESET_NOTE,
        "source": source, "provenance": prov,
    }


def _coverage():
    try:
        ds = _load("coverage")
        rows = [{"p2": r["params"]["p2"], "S_exact": r["S_exact"], "shots": r["shots"],
                 "repeats": r["repeats"], "coverage_1sigma": r["coverage_1sigma"],
                 "coverage_2sigma": r["coverage_2sigma"]} for r in ds["results"]["rows"]]
        return {"rows": rows, "expected_1sigma": 0.6827, "expected_2sigma": 0.9545,
                "provenance": _provenance(ds, DATA_FILES["coverage"])}
    except Exception as exc:
        return {"rows": [], "unavailable": type(exc).__name__}


def _aer_check():
    try:
        ds = _load("aer_check")
        rows = ds["results"]["rows"]
        return {"n_settings": len(rows),
                "max_abs_diff": max(abs(r["S_aer"] - r["S_exact"]) for r in rows),
                "fixed": ds["params"].get("fixed", {}),
                "provenance": _provenance(ds, DATA_FILES["aer_check"])}
    except Exception as exc:
        return {"n_settings": 0, "unavailable": type(exc).__name__}


def curve_json():
    """Compact precomputed series (S vs p2; IonQ-like S vs scale), lambda*, provenance,
    and the validation numbers (error-bar coverage, qiskit-aer cross-check)."""
    try:
        return _dumps({
            "p2_curve": _p2_curve(),
            "ionq_like": _ionq_curve(),
            "coverage": _coverage(),
            "aer_check": _aer_check(),
            "classical_bound": BOUND,
            "quantum_ideal": IDEAL,
            "lambda_star_theory": chsh.LAMBDA_STAR,
        })
    except Exception as exc:
        return _dumps(_error(exc))


# ---------------------------------------------------------------- card text

def card_text_json(card_json):
    """qk_cards.card_text (ASCII console view) and card_markdown for a card dict/JSON."""
    try:
        card = _parse_obj(card_json, "card")
        if not card:
            raise ValueError("empty card")
        return _dumps({"text": qk_cards.card_text(card), "markdown": qk_cards.card_markdown(card)})
    except Exception as exc:
        return _dumps(_error(exc))
