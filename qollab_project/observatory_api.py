"""JSON bridge between the Observatory's browser UI (main.js) and the Python engine.

Every public function returns a JSON STRING of a plain dict, strict JSON (NaN and
infinity become null). Nothing here raises to the caller: run_json answers
{"status": "failed", "error": ...} with whatever the job evidence knows, and the
other functions answer {"error": ...}.

    profile_json(backend, new_run=False)   backend profile, packing mode, versions
    predict_json(settings_json)            the Demon's forecast (exact model, no job)
    run_json(backend, settings_json)       ONE job: counts, readings, forecast, explanation
    explain_json(result_json, persona)     the factual sentence + one persona's line
    curves_json()                          precomputed theory / noise / coverage curves

Called from main.js as `await api.fn.callPromising(...)` and parsed with
`JSON.parse(String(ret))`. print() inside these functions would not reach the page,
so everything the page needs is in the return value.

Simulators compute what quantum theory predicts, and how a noise model degrades it;
they do not test nature. The readings are a designed model of agency, not a
measurement of free will, and the texts returned here say so.

This effort is supported by Qollab & IonQ
"""

import json
import os

import numpy as np

import observatory
import qk_data
import qk_noise
import qk_runtime

__all__ = [
    "profile_json", "predict_json", "run_json", "explain_json", "curves_json",
    "ATTRIBUTION", "MODEL_VERSION", "DATA_FILES",
]

ATTRIBUTION = observatory.ATTRIBUTION
MODEL_VERSION = observatory.MODEL_VERSION

# Data files, by literal relative path: Qollab ships a data file to the browser only
# when a string literal in the code names it, so _data_text opens each one literally.
DATA_FILES = {
    "theory": "data/fwo_theory.json",
    "noise": "data/fwo_noise.json",
    "coverage": "data/fwo_coverage.json",
}
_SERIES = ("capacity", "p_low", "p_high", "connection_bits", "openness_bits", "p_self_1")
_DIGITS = 6
_FALLBACK_W = 101           # theory fallback grid
_FALLBACK_SCALES = 41       # noise fallback grid: 0..80x the IonQ-like rates
_FALLBACK_REPEATS = 200     # coverage fallback: seeded runs per w


# ---------------------------------------------------------------- plumbing

def _dumps(obj):
    """Strict JSON text: numpy cast, NaN/inf -> null; never emits NaN/Infinity."""
    return json.dumps(qk_data.json_safe(obj), allow_nan=False, separators=(",", ":"))


def _error_text(exc):
    if isinstance(exc, BaseException):
        return ("%s: %s" % (type(exc).__name__, exc))[:600]
    return str(exc)[:600]


def _reject_constant(name):
    raise ValueError("non-standard JSON constant %s" % name)


def _missing(value):
    return value is None or type(value).__name__ in ("JsNull", "JsUndefined")


def _parse_obj(text, what):
    """JSON text (or an already-parsed dict) -> dict; missing/empty -> {}."""
    if _missing(text) or text == "":
        return {}
    if isinstance(text, dict):
        return dict(text)
    try:
        obj = json.loads(str(text), parse_constant=_reject_constant)
    except ValueError as exc:
        raise ValueError("%s is not valid JSON (%s)" % (what, exc))
    if not isinstance(obj, dict):
        raise ValueError("%s must be a JSON object" % what)
    return obj


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _here():
    f = globals().get("__file__")
    return os.path.dirname(os.path.abspath(f)) if f else os.getcwd()


def _data_text(key):
    """Text of one shipped data file (cwd = project folder on Qollab; next to this
    module under CPython). Each path is a literal so Qollab's scanner ships the file."""
    try:
        if key == "theory":
            fh = open("data/fwo_theory.json", encoding="utf-8")
        elif key == "noise":
            fh = open("data/fwo_noise.json", encoding="utf-8")
        elif key == "coverage":
            fh = open("data/fwo_coverage.json", encoding="utf-8")
        else:
            raise KeyError(key)
    except OSError:
        fh = open(os.path.join(_here(), DATA_FILES[key]), encoding="utf-8")
    with fh:
        return fh.read()


def _load(key):
    return qk_data.parse_dataset(_data_text(key))


def _r(x):
    return None if x is None else round(float(x), _DIGITS)


def _provenance(ds, path):
    return {"file": path, "generator": ds.get("generator"), "git_commit": ds.get("git_commit"),
            "created_utc": ds.get("created_utc"), "machine": ds.get("machine"),
            "versions": ds.get("versions"), "params": ds.get("params")}


# ---------------------------------------------------------------- profile

def profile_json(backend, new_run=False):
    """Backend profile + preferred packing mode + versions.

    new_run=True marks the start of a new Qollab run: main.js passes it exactly once,
    at page load, so a reused interpreter starts the run with a fresh one-job guard.
    Nothing else should pass it."""
    try:
        if _as_bool(new_run):
            qk_runtime.begin_run()
        if _missing(backend):
            raise ValueError("no backend was passed in")
        profile = qk_runtime.backend_profile(backend)
        return _dumps({
            "profile": profile,
            "mode": qk_runtime.preferred_mode(profile, "auto"),
            "one_job": bool(profile.get("one_job")),
            "simulator": profile.get("family") != "ionq_qpu",
            "jobs_submitted": qk_runtime.jobs_submitted(),
            "versions": observatory.versions(),
            "sim_note": observatory.SIM_NOTE,
            "model_version": MODEL_VERSION,
        })
    except Exception as exc:
        return _dumps({"error": _error_text(exc), "model_version": MODEL_VERSION})


# ---------------------------------------------------------------- forecast

def _predict(settings):
    s = observatory.validate_settings(settings)
    out = {
        "settings": s,
        "ideal": observatory.prediction(s),
        "baselines": observatory.baselines(),
        "model_version": MODEL_VERSION,
    }
    try:
        out["noisy_ionq_like"] = observatory.noisy_prediction(s)
    except Exception as exc:          # optional: the forecast must not fail with it
        out["noisy_ionq_like"] = None
        out["noisy_ionq_like_error"] = _error_text(exc)
    return out


def predict_json(settings_json="{}"):
    """The Demon's forecast for the settings: exact readings and probe distributions,
    an IonQ-like noisy forecast, and the two classical baselines. No job."""
    try:
        return _dumps(_predict(_parse_obj(settings_json, "settings")))
    except Exception as exc:
        return _dumps({"status": "failed", "error": _error_text(exc),
                       "model_version": MODEL_VERSION})


# ---------------------------------------------------------------- one job

def _failed(exc, settings=None, profile=None, mode=None, shots=None):
    out = {"status": "failed", "error": _error_text(exc), "model_version": MODEL_VERSION}
    if settings is not None:
        out["settings"] = settings
    try:
        out["source"] = observatory.source_info(profile or {}, mode, shots or 0)
    except Exception:
        out["source"] = {"job_id": qk_runtime.LAST_RUN.get("job_id"),
                         "job_returned": bool(qk_runtime.LAST_RUN.get("job_returned", False))}
    out["jobs_submitted"] = qk_runtime.jobs_submitted()
    return out


def run_json(backend, settings_json="{}"):
    """ONE job on `backend` for the settings, then the contract's result dict.

    The one-job guard in qk_runtime (reset by profile_json(backend, true) once per page
    load) refuses a second submission on a one-job backend before anything reaches the
    provider. Any exception becomes {"status": "failed", ...}; nothing raises."""
    settings = profile = mode = shots = None
    try:
        settings = observatory.validate_settings(_parse_obj(settings_json, "settings"))
        shots = settings["shots_per_probe"]
        if _missing(backend):
            raise ValueError("no backend was passed in")
        profile = qk_runtime.backend_profile(backend)
        mode = qk_runtime.preferred_mode(profile, settings["mode"])
        result = observatory.run(backend, settings, profile=profile)
        result["jobs_submitted"] = qk_runtime.jobs_submitted()
        return _dumps(result)
    except Exception as exc:
        try:
            return _dumps(_failed(exc, settings, profile, mode, shots))
        except Exception:               # evidence not JSON-safe: still never raise
            return _dumps({"status": "failed", "error": _error_text(exc),
                           "model_version": MODEL_VERSION})


# ---------------------------------------------------------------- explanation

def explain_json(result_json, persona="self"):
    """{"persona", "factual", "poetic"} for a completed result (the run_json output
    or any dict with settings, metrics and prediction)."""
    try:
        result = _parse_obj(result_json, "result")
        if not result:
            raise ValueError("empty result")
        if _missing(persona) or persona == "":
            persona = "self"
        if not isinstance(persona, str) or persona.strip().lower() not in observatory.PERSONAS:
            raise ValueError("persona must be one of %s, got %r"
                             % (", ".join(observatory.PERSONAS), persona))
        persona = persona.strip().lower()
        if result.get("status") == "failed":
            raise ValueError("the run failed: %s" % result.get("error"))
        if all(k in result for k in ("settings", "metrics", "prediction")):
            expl = observatory.explanation(result["settings"], result["metrics"],
                                           result["prediction"])
        elif isinstance(result.get("explanation"), dict):
            expl = result["explanation"]
        else:
            raise ValueError("result needs settings, metrics and prediction (or explanation)")
        return _dumps({
            "persona": persona,
            "factual": expl["factual"],
            "poetic": expl["poetic"][persona],
            "poetic_all": expl["poetic"],
            "resolved": expl.get("resolved"),
            "note": expl.get("note", observatory.PERSONA_NOTE),
            "model_version": MODEL_VERSION,
        })
    except Exception as exc:
        return _dumps({"error": _error_text(exc), "model_version": MODEL_VERSION})


# ---------------------------------------------------------------- curves

def _rows_to_series(rows, x_name, extra=()):
    """Column-wise series from sweep rows: x from params, metrics from the row."""
    xs = [r["params"][x_name] for r in rows]
    order = sorted(range(len(rows)), key=lambda i: float(xs[i]))
    out = {x_name: [_r(xs[i]) for i in order]}
    for key in _SERIES + tuple(extra):
        if all(key in rows[i] for i in order):
            out[key] = [_r(rows[i][key]) for i in order]
    return out


def _theory_curve():
    try:
        ds = _load("theory")
        rows = [r for r in ds["results"]["rows"] if "capacity" in r and "w" in r.get("params", {})]
        if not rows:
            raise ValueError("no theory rows")
        out = _rows_to_series(rows, "w")
        out.update({"source": "precomputed", "provenance": _provenance(ds, DATA_FILES["theory"]),
                    "fixed": ds["params"].get("fixed", {}),
                    "derived": ds["results"].get("derived", {})})
        return out
    except Exception as exc:
        ws = [i / (_FALLBACK_W - 1) for i in range(_FALLBACK_W)]
        out = {"w": [_r(w) for w in ws]}
        for key in _SERIES:
            out[key] = []
        for w in ws:
            ex = observatory.exact_metrics({"world_coupling": w})
            for key in _SERIES:
                out[key].append(_r(ex[key]))
        out.update({"source": "computed in this session (data file unavailable: %s)"
                              % type(exc).__name__,
                    "provenance": None,
                    "fixed": {"intention_rad": observatory.DEFAULTS["intention_rad"],
                              "perspective_rad": observatory.DEFAULTS["perspective_rad"]},
                    "derived": {}})
    out["capacity_formula"] = "cos(w * pi / 2)"
    return out


def _noise_curve():
    try:
        ds = _load("noise")
        rows = [r for r in ds["results"]["rows"] if "capacity" in r]
        if not rows:
            raise ValueError("no noise rows")
        grid = ds["params"].get("grid") or {}
        x_name = next(iter(grid), None) or ("scale" if "scale" in rows[0]["params"] else "w")
        out = _rows_to_series(rows, x_name, extra=("capacity_ideal",))
        out.update({"x_name": x_name, "fixed": ds["params"].get("fixed", {}),
                    "source": "precomputed", "provenance": _provenance(ds, DATA_FILES["noise"])})
    except Exception as exc:
        xs = [80.0 * i / (_FALLBACK_SCALES - 1) for i in range(_FALLBACK_SCALES)]
        out = {"scale": [_r(x) for x in xs]}
        for key in _SERIES:
            out[key] = []
        for x in xs:
            ex = observatory.exact_metrics({}, qk_noise.ionq_forte_like(scale=x))
            for key in _SERIES:
                out[key].append(_r(ex[key]))
        out.update({"x_name": "scale",
                    "fixed": {"p1": qk_noise.IONQ_FORTE1_R1Q, "p2": qk_noise.IONQ_FORTE1_R2Q,
                              "w": observatory.DEFAULTS["world_coupling"],
                              "intention_rad": observatory.DEFAULTS["intention_rad"],
                              "perspective_rad": observatory.DEFAULTS["perspective_rad"]},
                    "source": "computed in this session (data file unavailable: %s)"
                              % type(exc).__name__,
                    "provenance": None})
    out["note"] = qk_noise.IONQ_PRESET_NOTE
    return out


def _coverage_fallback(ws=(0.0, 0.5, 1.0), repeats=_FALLBACK_REPEATS, shots=1024, seed=0):
    rows = []
    rng = np.random.default_rng(seed)
    for w in ws:
        dists = observatory.exact_probe_distributions({"world_coupling": w})
        exact_c = abs(observatory._p_self_1(dists["intent_high"])
                      - observatory._p_self_1(dists["intent_low"]))
        inside = 0
        width = 0.0
        for _ in range(repeats):
            counts = {}
            for name in ("intent_low", "intent_high"):
                p = np.array([dists[name][k] for k in observatory.OUTCOMES])
                draw = rng.multinomial(shots, p / p.sum())
                counts[name] = {k: int(n) for k, n in zip(observatory.OUTCOMES, draw)}
            d = observatory._p_self_1(counts["intent_high"]) - observatory._p_self_1(counts["intent_low"])
            ci, _ = observatory.capacity_interval(d, observatory.hoeffding_e(shots, shots))
            inside += ci[0] <= exact_c <= ci[1]
            width += ci[1] - ci[0]
        rows.append({"w": w, "repeats": repeats, "shots": shots, "capacity_exact": _r(exact_c),
                     "coverage_95": _r(inside / repeats), "mean_width": _r(width / repeats)})
    return rows


def _coverage():
    try:
        ds = _load("coverage")
        rows = []
        for r in ds["results"]["rows"]:
            rows.append({"w": r["params"].get("w"), "repeats": r.get("repeats"),
                         "shots": r.get("shots"), "capacity_exact": r.get("capacity_exact"),
                         "coverage_95": r.get("coverage_95"), "mean_width": r.get("mean_width"),
                         "resolved_fraction": r.get("resolved_fraction")})
        if not rows:
            raise ValueError("no coverage rows")
        return {"rows": rows, "nominal": 0.95, "source": "precomputed",
                "provenance": _provenance(ds, DATA_FILES["coverage"])}
    except Exception as exc:
        return {"rows": _coverage_fallback(), "nominal": 0.95,
                "source": "computed in this session (data file unavailable: %s)"
                          % type(exc).__name__,
                "provenance": None}


def curves_json():
    """Theory curves vs w (capacity, p_low, p_high, connection, openness, P(Self=1)),
    the IonQ-like noise degradation, and the Hoeffding-interval coverage check. Each
    comes from a shipped data file opened by a literal path; when a file is missing the
    curve is computed in the session and labelled as such."""
    try:
        theory = _theory_curve()
        noise = _noise_curve()
        coverage = _coverage()
        return _dumps({
            "theory": theory,
            "noise": noise,
            "coverage": coverage,
            "provenance": {
                "theory": theory.get("provenance"),
                "noise": noise.get("provenance"),
                "coverage": coverage.get("provenance"),
                "sources": {"theory": theory.get("source"), "noise": noise.get("source"),
                            "coverage": coverage.get("source")},
                "hoeffding_e_1024": observatory.hoeffding_e(1024, 1024),
                "model_version": MODEL_VERSION,
            },
            "sim_note": observatory.SIM_NOTE,
            "model_version": MODEL_VERSION,
        })
    except Exception as exc:
        return _dumps({"error": _error_text(exc), "model_version": MODEL_VERSION})
