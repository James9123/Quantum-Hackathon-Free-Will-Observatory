"""The JSON bridge (qollab_project/observatory_api.py), main.py's Qollab form, the
Qollab-style exec emulation, the offline qiskit-ionq serialization of the packed job, and
(opt-in, FWO_SLOW=1) the FakeFez noisy list path.

Every bridge function must return strict JSON text and never raise; run_json must submit
exactly one job, refuse a second one on a one-job backend before anything is submitted,
and keep the job evidence when a provider fails.
"""
import ast
import base64
import gzip
import json
import math
import os
import re

import pytest
from qiskit.providers.basic_provider import BasicSimulator

import observatory as obs
import observatory_api as api
import qk_packer
import qk_runtime
import run_smoke_local

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "qollab_project")
PI = math.pi
ATTRIBUTION = "This effort is supported by Qollab & IonQ"
NO_RESOLVED = "No resolved influence at this shot count"
SOURCE_KEYS = {"provider_family", "backend_name", "mode", "simulator", "noisy", "remote", "job_id",
               "job_returned", "submitted_as", "wall_s", "shots_requested", "shots_seen", "versions",
               "bit_order_check", "layout", "n_circuits", "sim_note"}
METRIC_KEYS = {"p_self_1", "p_low", "p_high", "delta_signed", "capacity", "capacity_ci95",
               "hoeffding_e", "openness_bits", "connection_bits", "resolved", "shots_seen"}
IDEAL_KEYS = {"p_self_1", "p_low", "p_high", "capacity", "openness_bits", "connection_bits",
              "formula_p_self_1", "probe_distributions"}


def _reject(name):
    raise ValueError("non-strict JSON constant %s" % name)


def strict(text):
    """json.loads that rejects NaN/Infinity; the result must be a dict."""
    assert isinstance(text, str)
    assert not re.search(r"[:\[,]\s*-?(NaN|Infinity)\b", text)
    obj = json.loads(text, parse_constant=_reject)
    assert isinstance(obj, dict)
    return obj


def _seeded(seed=11):
    be = BasicSimulator()
    be.set_options(seed_simulator=seed)
    return be


class CountingBackend:
    """BasicSimulator wrapper that counts backend.run calls; everything else delegates."""

    def __init__(self, inner=None):
        self._inner = inner or _seeded()
        self.jobs = 0

    def __getattr__(self, item):
        return getattr(self._inner, item)

    def run(self, *a, **k):
        self.jobs += 1
        return self._inner.run(*a, **k)


class OneJobBackend(CountingBackend):
    """Profiles as the IonQ simulator (one job per run, no transpile) but runs locally."""
    __module__ = "qiskit_ionq.ionq_backend"
    name = "ionq_simulator"
    num_qubits = 29


class IbmLikeBackend(CountingBackend):
    """Profiles as an IBM noise model (local, noisy: list mode) but runs locally."""
    __module__ = "qiskit_ibm_runtime.fake_provider.backends.fez.fake_fez"
    name = "fake_fez"
    num_qubits = 156


class FailingBackend(CountingBackend):
    def run(self, *a, **k):
        self.jobs += 1
        raise RuntimeError("provider down")


class FailingResultBackend:
    """Submits fine, then job.result() raises (both the poll and the single retry)."""
    __module__ = "qiskit_ionq.ionq_backend"
    name = "ionq_simulator"
    num_qubits = 29

    def __init__(self):
        self.jobs = 0

    def run(self, run_input, shots=1024, **kw):
        self.jobs += 1

        class _Job:
            def job_id(self_):
                return "job-123"

            def result(self_):
                raise RuntimeError("IonQ: simulation failed")
        return _Job()


class _ScaledResult:
    def __init__(self, inner, factor):
        self._inner, self._factor = inner, factor

    def _scale(self, counts):
        return {k: int(round(v * self._factor)) for k, v in counts.items()}

    def get_counts(self, i=None):
        c = self._inner.get_counts() if i is None else self._inner.get_counts(i)
        return [self._scale(x) for x in c] if isinstance(c, list) else self._scale(c)


class _ScaledJob:
    def __init__(self, inner, factor):
        self._inner, self._factor = inner, factor

    def job_id(self):
        return "scaled-" + str(self._inner.job_id())

    def result(self):
        return _ScaledResult(self._inner.result(), self._factor)


class RoundingBackend(CountingBackend):
    """Emulates IonQ's noisy simulator, whose histogram is round(prob * shots) per key:
    the totals it returns differ from the requested shots."""

    def run(self, *a, **k):
        self.jobs += 1
        return _ScaledJob(self._inner.run(*a, **k), 0.997)


@pytest.fixture(autouse=True)
def fresh_run():
    qk_runtime.begin_run()
    yield
    qk_runtime.begin_run()


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ names and strict JSON

def test_public_names_and_attribution():
    for name in ("profile_json", "predict_json", "run_json", "explain_json", "curves_json"):
        assert callable(getattr(api, name)) and name in api.__all__
    assert api.ATTRIBUTION == ATTRIBUTION and api.MODEL_VERSION == obs.MODEL_VERSION
    assert set(api.DATA_FILES) == {"theory", "noise", "coverage"}
    assert all(p.startswith("data/") and p.endswith(".json") for p in api.DATA_FILES.values())
    # Qollab ships a data file only when a literal names it: each path must be a literal
    src = _read("qollab_project/observatory_api.py")
    for path in api.DATA_FILES.values():
        assert ('"%s"' % path) in src, path


def test_every_function_returns_strict_json_including_error_paths():
    be = CountingBackend(_seeded())
    run = api.run_json(be, json.dumps({"shots_per_probe": 100}))
    outs = [
        api.profile_json(be), api.profile_json(None), api.profile_json(be, "false"),
        api.predict_json(), api.predict_json("{}"), api.predict_json("{bad"),
        api.predict_json('{"intention_rad": NaN}'), api.predict_json("[1, 2]"),
        api.predict_json(json.dumps({"shots_per_probe": 0})),
        run, api.run_json(None, "{}"), api.run_json(be, "{nope"), api.run_json(be, '{"persona": "god"}'),
        api.explain_json(run, "demon"), api.explain_json("not json"), api.explain_json("{}"),
        api.explain_json(run, "nobody"), api.curves_json(),
    ]
    for text in outs:
        assert "model_version" in strict(text)
    assert be.jobs == 1


# ------------------------------------------------------------------ profile_json

def test_profile_json_contract_for_the_three_backend_families():
    p = strict(api.profile_json(_seeded()))
    assert set(p) >= {"profile", "mode", "one_job", "versions", "model_version"}
    assert p["profile"]["family"] == "basic" and p["profile"]["max_qubits"] == 24
    assert p["mode"] == "tile" and p["one_job"] is False and p["simulator"] is True
    assert p["jobs_submitted"] == 0 and p["versions"]["model_version"] == obs.MODEL_VERSION
    assert "does not test nature" in p["sim_note"]
    q = strict(api.profile_json(OneJobBackend()))
    assert q["profile"]["family"] == "ionq_sim" and q["one_job"] is True and q["mode"] == "tile"
    assert q["profile"]["transpile"] is False and q["profile"]["remote"] is True
    i = strict(api.profile_json(IbmLikeBackend()))
    assert i["profile"]["family"] == "ibm_noise" and i["mode"] == "list" and i["one_job"] is False
    assert i["profile"]["noisy"] is True and i["profile"]["max_qubits"] == 24
    e = strict(api.profile_json(None))
    assert "error" in e and "no backend" in e["error"]


def test_profile_json_new_run_resets_the_one_job_guard_only_when_true():
    be = OneJobBackend(_seeded(4))
    assert strict(api.profile_json(be, True))["jobs_submitted"] == 0
    assert strict(api.run_json(be, "{\"shots_per_probe\": 50}"))["status"] == "completed"
    assert strict(api.profile_json(be))["jobs_submitted"] == 1              # plain profile: no reset
    assert strict(api.profile_json(be, "false"))["jobs_submitted"] == 1
    assert strict(api.profile_json(be, 0))["jobs_submitted"] == 1
    assert strict(api.profile_json(be, "true"))["jobs_submitted"] == 0      # JS-style true resets
    assert be.jobs == 1


# ------------------------------------------------------------------ predict_json

def test_predict_json_defaults_are_act_one():
    d = strict(api.predict_json("{}"))
    assert d["model_version"] == obs.MODEL_VERSION
    s = d["settings"]
    assert s["intention_rad"] == pytest.approx(PI / 2) and s["world_coupling"] == 0.0
    assert s["perspective_rad"] == 0.0 and s["shots_per_probe"] == 1024 and s["gamma_rad"] == 0.0
    assert s["persona"] == "self" and s["mode"] == "auto" and s["canary"] is True
    ideal = d["ideal"]
    assert IDEAL_KEYS <= set(ideal)
    assert ideal["p_self_1"] == pytest.approx(0.5, abs=1e-12) and ideal["p_low"] == pytest.approx(0.0, abs=1e-12)
    assert ideal["p_high"] == pytest.approx(1.0, abs=1e-12) and ideal["capacity"] == pytest.approx(1.0, abs=1e-12)
    assert ideal["openness_bits"] == pytest.approx(1.0, abs=1e-12)
    assert ideal["connection_bits"] == pytest.approx(0.0, abs=1e-12)
    assert ideal["formula_p_self_1"] == obs.FORMULA
    for name in obs.PROBES:
        dist = ideal["probe_distributions"][name]
        assert set(dist) == {"00", "01", "10", "11"} and sum(dist.values()) == pytest.approx(1.0, abs=1e-12)
    assert ideal["probe_distributions"]["intent_high"]["10"] == pytest.approx(1.0, abs=1e-12)
    noisy = d["noisy_ionq_like"]
    assert noisy is not None and 0.9 < noisy["capacity"] < 1.0 and "note" in noisy and "noise" in noisy
    assert d["baselines"]["fixed_output"] == dict(d["baselines"]["fixed_output"], capacity=0.0, openness_bits=0.0)
    assert d["baselines"]["fair_coin"]["capacity"] == 0.0 and d["baselines"]["fair_coin"]["openness_bits"] == 1.0


def test_predict_json_half_and_full_coupling_and_perspective():
    h = strict(api.predict_json(json.dumps({"world_coupling": 0.5})))["ideal"]
    assert h["p_low"] == pytest.approx(0.1464, abs=5e-5) and h["p_high"] == pytest.approx(0.8536, abs=5e-5)
    assert h["capacity"] == pytest.approx(math.cos(PI / 4), abs=1e-12)
    f = strict(api.predict_json(json.dumps({"world_coupling": 1, "intention_rad": 2.0})))["ideal"]
    assert f["p_self_1"] == pytest.approx(0.5, abs=1e-12) and f["capacity"] == pytest.approx(0.0, abs=1e-12)
    assert f["connection_bits"] == pytest.approx(1.0, abs=1e-12)
    a = strict(api.predict_json(json.dumps({"world_coupling": 0.5, "intention_rad": 1.0, "perspective_rad": 0.0})))
    b = strict(api.predict_json(json.dumps({"world_coupling": 0.5, "intention_rad": 1.0, "perspective_rad": 0.7})))
    assert a["ideal"]["capacity"] == pytest.approx(b["ideal"]["capacity"], abs=1e-12)
    assert abs(a["ideal"]["p_self_1"] - b["ideal"]["p_self_1"]) > 0.05
    assert b["settings"]["perspective_rad"] == 0.7
    # a dict (not text) and JS-style values are accepted as well
    assert strict(api.predict_json({"world_coupling": "0.5", "shots_per_probe": 512.0}))["settings"]["shots_per_probe"] == 512


@pytest.mark.parametrize("bad", [
    {"shots_per_probe": 0}, {"shots_per_probe": 5000}, {"persona": "god"}, {"world_coupling": 2},
    {"world_coupling": -0.1}, {"perspective_rad": 4}, {"intention_rad": -1}, {"mode": "batch"},
    {"canary": "maybe"},
])
def test_predict_json_invalid_settings_fail_cleanly(bad):
    d = strict(api.predict_json(json.dumps(bad)))
    assert d["status"] == "failed" and d["error"] and "ideal" not in d
    assert list(bad)[0] in d["error"]


@pytest.mark.parametrize("text", ["{bad", "[1, 2]", '{"intention_rad": NaN}', '{"world_coupling": Infinity}', "42"])
def test_predict_json_bad_json_fails_cleanly(text):
    d = strict(api.predict_json(text))
    assert d["status"] == "failed" and "error" in d


# ------------------------------------------------------------------ run_json

def test_run_json_is_exactly_one_job_and_honours_the_contract():
    be = CountingBackend(_seeded(5))
    r = strict(api.run_json(be, json.dumps({"world_coupling": 0.5, "persona": "observer"})))
    assert be.jobs == 1 and r["jobs_submitted"] == 1
    assert r["status"] == "completed" and r["bit_order"] == "SelfWorld" and r["model_version"] == obs.MODEL_VERSION
    assert r["settings"]["persona"] == "observer" and r["settings"]["gamma_rad"] == pytest.approx(PI / 4)
    src = r["source"]
    assert SOURCE_KEYS <= set(src)
    assert src["provider_family"] == "basic" and src["mode"] == "tile" and src["simulator"] is True
    assert src["noisy"] is False and src["remote"] is False and src["job_returned"] is True
    assert src["submitted_as"] == "circuit" and src["n_circuits"] == 1 and src["shots_requested"] == 1024
    assert src["job_id"] is None or isinstance(src["job_id"], str)
    assert isinstance(src["wall_s"], (int, float)) and src["wall_s"] >= 0
    assert src["shots_seen"] == {name: 1024 for name in obs.PROBES}
    assert src["bit_order_check"]["orientation_ok"] is True
    assert src["bit_order_check"]["p_flip_0to1_mean"] == 0.0 and src["bit_order_check"]["p_flip_1to0_mean"] == 0.0
    assert src["layout"]["n_circuits"] == 1 and src["layout"]["canary"] is True
    assert src["versions"]["qiskit"] and src["sim_note"] == obs.SIM_NOTE
    for name in obs.PROBES:
        c = r["counts"][name]
        assert set(c) == {"00", "01", "10", "11"} and all(isinstance(v, int) for v in c.values())
        assert sum(c.values()) == 1024
    m = r["metrics"]
    assert METRIC_KEYS <= set(m)
    c = r["counts"]
    p_low = (c["intent_low"]["10"] + c["intent_low"]["11"]) / 1024
    p_high = (c["intent_high"]["10"] + c["intent_high"]["11"]) / 1024
    assert m["p_low"] == pytest.approx(p_low) and m["p_high"] == pytest.approx(p_high)
    assert m["capacity"] == pytest.approx(abs(p_high - p_low)) and m["delta_signed"] == pytest.approx(p_high - p_low)
    assert m["hoeffding_e"] == pytest.approx(obs.hoeffding_e(1024, 1024))
    lo, hi = m["capacity_ci95"]
    assert 0.0 <= lo <= m["capacity"] <= hi <= 1.0 and m["resolved"] is True
    assert lo <= math.cos(PI / 4) <= hi
    assert IDEAL_KEYS <= set(r["prediction"]) and r["prediction"]["capacity"] == pytest.approx(math.cos(PI / 4))
    ex = r["explanation"]
    assert set(ex["poetic"]) == {"self", "demon", "observer"}
    assert "capacity %.3f" % m["capacity"] in ex["factual"]
    assert r["baselines"]["kind"] == "theoretical classical references"


@pytest.mark.parametrize("mode,submitted_as,n_circuits", [("tile", "circuit", 1), ("list", "list", 7), ("auto", "circuit", 1)])
def test_run_json_modes(mode, submitted_as, n_circuits):
    be = CountingBackend(_seeded(9))
    r = strict(api.run_json(be, json.dumps({"mode": mode, "shots_per_probe": 256})))
    assert be.jobs == 1 and r["status"] == "completed"
    assert r["source"]["submitted_as"] == submitted_as and r["source"]["n_circuits"] == n_circuits
    assert r["source"]["mode"] == ("tile" if mode == "auto" else mode)
    assert all(n == 256 for n in r["metrics"]["shots_seen"].values())


def test_run_json_ibm_like_backend_auto_selects_list():
    be = IbmLikeBackend(_seeded(12))
    r = strict(api.run_json(be, json.dumps({"shots_per_probe": 128})))
    assert be.jobs == 1 and r["status"] == "completed", r.get("error")
    assert r["source"]["mode"] == "list" and r["source"]["n_circuits"] == 7
    assert r["source"]["provider_family"] == "ibm_noise"


def test_run_json_second_job_on_a_one_job_backend_is_refused_before_submitting():
    be = OneJobBackend(_seeded(4))
    assert strict(api.profile_json(be, True))["one_job"] is True             # page load: new run
    first = strict(api.run_json(be, json.dumps({"shots_per_probe": 64})))
    assert first["status"] == "completed" and be.jobs == 1 and first["jobs_submitted"] == 1
    assert first["source"]["mode"] == "tile" and first["source"]["transpile"]["transpiled"] is False
    second = strict(api.run_json(be, json.dumps({"shots_per_probe": 64})))   # no new_run in between
    assert second["status"] == "failed" and "one-job guard" in second["error"]
    assert be.jobs == 1 and second["jobs_submitted"] == 1
    assert "counts" not in second and "metrics" not in second
    assert second["settings"]["shots_per_probe"] == 64 and "source" in second
    third_profile = strict(api.profile_json(be, True))                        # a new page load
    assert third_profile["jobs_submitted"] == 0
    third = strict(api.run_json(be, json.dumps({"shots_per_probe": 64})))
    assert third["status"] == "completed" and be.jobs == 2


def test_run_json_backend_run_raises_gives_failed_with_evidence():
    be = FailingBackend(_seeded())
    r = strict(api.run_json(be, json.dumps({"world_coupling": 0.5, "shots_per_probe": 100})))
    assert r["status"] == "failed" and "provider down" in r["error"] and be.jobs == 1
    assert r["jobs_submitted"] == 1 and r["settings"]["shots_per_probe"] == 100
    src = r["source"]
    assert src["job_returned"] is False and src["job_id"] is None
    assert src["submitted_as"] == "circuit" and src["n_circuits"] == 1 and src["shots_requested"] == 100
    assert src["provider_family"] == "basic" and src["mode"] == "tile"
    assert "counts" not in r and "metrics" not in r


def test_run_json_result_failure_keeps_job_id_and_never_resubmits():
    be = FailingResultBackend()
    r = strict(api.run_json(be, json.dumps({"shots_per_probe": 100})))
    assert r["status"] == "failed" and "simulation failed" in r["error"]
    assert be.jobs == 1                                                        # retry polls, no resubmit
    assert r["source"]["job_id"] == "job-123" and r["source"]["job_returned"] is True
    assert r["source"]["provider_family"] == "ionq_sim"


def test_run_json_uses_actual_totals_when_the_provider_rounds_counts():
    be = RoundingBackend(_seeded(3))
    r = strict(api.run_json(be, "{}"))
    assert r["status"] == "completed" and be.jobs == 1
    seen = r["metrics"]["shots_seen"]
    assert r["source"]["shots_requested"] == 1024 and r["source"]["shots_seen"] == seen
    assert any(n != 1024 for n in seen.values()), seen                      # rounding changed totals
    assert all(1000 <= n <= 1024 for n in seen.values())
    c = r["counts"]
    for name in obs.PROBES:
        assert sum(c[name].values()) == seen[name]
    m = r["metrics"]
    assert m["p_low"] == pytest.approx((c["intent_low"]["10"] + c["intent_low"]["11"]) / seen["intent_low"])
    assert m["p_self_1"] == pytest.approx((c["display"]["10"] + c["display"]["11"]) / seen["display"])
    assert m["hoeffding_e"] == pytest.approx(obs.hoeffding_e(seen["intent_low"], seen["intent_high"]), abs=1e-12)
    assert m["hoeffding_e"] > obs.hoeffding_e(1024, 1024)
    assert r["source"]["job_id"].startswith("scaled-")


@pytest.mark.parametrize("bad", [
    {"shots_per_probe": 0}, {"shots_per_probe": 5000}, {"persona": "god"}, {"world_coupling": -0.1},
    {"perspective_rad": 3.5}, {"intention_rad": 7}, {"mode": "batch"}, {"shots_per_probe": "lots"},
])
def test_run_json_invalid_settings_fail_without_submitting(bad):
    be = CountingBackend(_seeded())
    r = strict(api.run_json(be, json.dumps(bad)))
    assert r["status"] == "failed" and list(bad)[0] in r["error"] and be.jobs == 0
    assert r["jobs_submitted"] == 0 and "counts" not in r


@pytest.mark.parametrize("text", ["{", "[1]", '{"world_coupling": NaN}', "null?"])
def test_run_json_bad_json_fails_without_submitting(text):
    be = CountingBackend(_seeded())
    r = strict(api.run_json(be, text))
    assert r["status"] == "failed" and be.jobs == 0


def test_run_json_without_backend_fails_without_crashing():
    r = strict(api.run_json(None, "{}"))
    assert r["status"] == "failed" and "no backend" in r["error"] and r["jobs_submitted"] == 0


# ------------------------------------------------------------------ explain_json

def test_explain_json_personas_from_a_completed_run():
    be = CountingBackend(_seeded(5))
    run_text = api.run_json(be, json.dumps({"world_coupling": 0.5}))
    run = strict(run_text)
    for persona in obs.PERSONAS:
        e = strict(api.explain_json(run_text, persona))
        assert e["persona"] == persona and e["factual"] == run["explanation"]["factual"]
        assert e["poetic"] == run["explanation"]["poetic"][persona] and e["resolved"] is True
        assert set(e["poetic_all"]) == set(obs.PERSONAS) and e["model_version"] == obs.MODEL_VERSION
    m = run["metrics"]
    f = strict(api.explain_json(run_text, "demon"))["factual"]
    assert "capacity %.3f" % m["capacity"] in f and "interval %.3f to %.3f" % tuple(m["capacity_ci95"]) in f
    assert NO_RESOLVED not in f
    # default persona, odd case, dict input
    assert strict(api.explain_json(run_text))["persona"] == "self"
    assert strict(api.explain_json(run_text, ""))["persona"] == "self"
    assert strict(api.explain_json(run, " Observer "))["persona"] == "observer"
    # a result that carries only its explanation still works
    only = {"explanation": run["explanation"]}
    assert strict(api.explain_json(json.dumps(only), "demon"))["poetic"] == run["explanation"]["poetic"]["demon"]


def test_explain_json_unresolved_run_states_the_rule():
    be = CountingBackend(_seeded(5))
    run_text = api.run_json(be, json.dumps({"world_coupling": 1.0}))
    for persona in obs.PERSONAS:
        e = strict(api.explain_json(run_text, persona))
        assert e["resolved"] is False and NO_RESOLVED in e["factual"] and NO_RESOLVED in e["poetic"]


@pytest.mark.parametrize("result,persona", [
    ("not json", "self"), ("{}", "self"), ("[1]", "self"),
    (json.dumps({"status": "failed", "error": "x"}), "self"),
    (json.dumps({"settings": {}, "metrics": {}}), "self"),
])
def test_explain_json_bad_inputs_return_error(result, persona):
    e = strict(api.explain_json(result, persona))
    assert "error" in e and "poetic" not in e


def test_explain_json_bad_persona_returns_error():
    be = CountingBackend(_seeded(5))
    run_text = api.run_json(be, json.dumps({"shots_per_probe": 50}))
    e = strict(api.explain_json(run_text, "nobody"))
    assert "error" in e and "persona" in e["error"]


# ------------------------------------------------------------------ curves_json

def _check_curves(d, expect_fallback):
    assert d["model_version"] == obs.MODEL_VERSION and "does not test nature" in d["sim_note"]
    t = d["theory"]
    n = len(t["w"])
    assert n >= 11 and t["w"][0] == 0.0 and t["w"][-1] == 1.0
    for key in ("capacity", "p_low", "p_high", "connection_bits", "openness_bits", "p_self_1"):
        assert len(t[key]) == n, key
    for w, c, lo, hi, info in zip(t["w"], t["capacity"], t["p_low"], t["p_high"], t["connection_bits"]):
        assert c == pytest.approx(math.cos(w * PI / 2), abs=2e-6)
        assert hi - lo == pytest.approx(c, abs=5e-6) and 0.0 <= info <= 1.0 + 1e-9
    assert t["connection_bits"][0] == pytest.approx(0.0, abs=1e-6) and t["connection_bits"][-1] == pytest.approx(1.0, abs=1e-6)
    assert t["capacity_formula"] == "cos(w * pi / 2)"
    nz = d["noise"]
    x = nz["x_name"]
    assert len(nz[x]) == len(nz["capacity"]) >= 5 and nz["capacity"][0] >= nz["capacity"][-1]
    assert nz["note"] and nz["capacity"][0] <= 1.0 + 1e-9
    cov = d["coverage"]
    assert cov["nominal"] == 0.95 and {r["w"] for r in cov["rows"]} >= {0.0, 0.5, 1.0}
    for row in cov["rows"]:
        assert row["coverage_95"] >= 0.95 and row["repeats"] >= 100 and row["shots"] >= 1
        assert row["capacity_exact"] == pytest.approx(math.cos(row["w"] * PI / 2), abs=2e-6)
    prov = d["provenance"]
    assert prov["hoeffding_e_1024"] == pytest.approx(obs.hoeffding_e(1024, 1024))
    for key in ("theory", "noise", "coverage"):
        source = prov["sources"][key]
        if expect_fallback:
            assert source.startswith("computed in this session") and prov[key] is None
        else:
            assert source == "precomputed" or source.startswith("computed in this session")
            if source == "precomputed":
                assert prov[key]["file"] == api.DATA_FILES[key] and prov[key]["git_commit"]
                assert prov[key]["machine"] == "48-thread x86 workstation"


def test_curves_json_live_path():
    d = strict(api.curves_json())
    _check_curves(d, expect_fallback=False)


def test_curves_json_falls_back_to_live_computation_without_data_files(monkeypatch):
    def _missing(key):
        raise FileNotFoundError(api.DATA_FILES[key])
    monkeypatch.setattr(api, "_load", _missing)
    d = strict(api.curves_json())
    _check_curves(d, expect_fallback=True)
    assert len(d["theory"]["w"]) == 101 and d["noise"]["x_name"] == "scale"
    assert d["noise"]["scale"][-1] == 80.0 and d["noise"]["capacity"][-1] < d["noise"]["capacity"][0]
    assert [r["w"] for r in d["coverage"]["rows"]] == [0.0, 0.5, 1.0]
    assert all(r["repeats"] == 200 and r["shots"] == 1024 for r in d["coverage"]["rows"])


def test_data_text_loader_literal_paths():
    with pytest.raises(KeyError):
        api._data_text("nope")
    for key, rel in api.DATA_FILES.items():
        path = os.path.join(PROJECT, rel)
        if os.path.exists(path):
            assert api._load(key)["machine"] == "48-thread x86 workstation"
        else:
            with pytest.raises(OSError):
                api._data_text(key)


# ------------------------------------------------------------------ main.py form

def test_main_py_qollab_form_rules():
    src = _read("qollab_project/main.py")
    assert ATTRIBUTION in src
    sigs = re.findall(r"^def main\((.*)\):[ \t]*$", src, flags=re.M)
    assert len(sigs) == 1 and src.count("def main(") == 1                   # one line, column 0
    tree = ast.parse(src)
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    assert len(mains) == 1
    fn = mains[0]
    args = fn.args
    assert not args.vararg and not args.kwarg and not args.kwonlyargs and not args.posonlyargs
    assert len(args.defaults) == len(args.args) >= 1
    for a, default in zip(args.args, args.defaults):
        assert isinstance(a.annotation, ast.Name) and a.annotation.id in ("int", "float", "str"), a.arg
        assert isinstance(default, ast.Constant), a.arg
        if a.annotation.id in ("int", "float"):
            assert isinstance(default.value, (int, float)) and not isinstance(default.value, bool)
            assert default.value >= 0
            assert isinstance(default.value, int) if a.annotation.id == "int" else True
        else:
            assert isinstance(default.value, str)
    names = [a.arg for a in args.args]
    assert names == ["intention_deg", "world_coupling", "perspective_deg", "shots_per_probe", "persona"]
    # no __main__ guard and no module-level main() call: Qollab appends the call itself
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id != "__name__"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "main"
    assert "__main__" not in src
    # backend is Qollab's injected global: read inside main, never built or assigned here
    for forbidden in ("BasicSimulator(", "AerSimulator(", "IonQProvider(", "get_backend(", "backend ="):
        assert forbidden not in src, forbidden
    uses = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "backend"]
    assert uses and all(isinstance(n.ctx, ast.Load) for n in uses)
    compile(src, "main.py", "exec")


def test_main_runs_under_the_qollab_exec_emulation_with_one_job(capsys):
    be = run_smoke_local.run_qollab_style('main(90.0, 0.5, 0.0, 300, "self")', project="qollab_project")
    out = capsys.readouterr().out
    assert be.jobs == 1
    assert out.count("THE FREE WILL OBSERVATORY") == 1                      # main() ran exactly once
    assert "Traceback" not in out and "RUN FAILED" not in out and "Invalid settings" not in out
    assert "LAPLACE'S DEMON FORECAST" in out and "P(Self=1) = 0.5000" in out
    assert "COUNTS (bit order SelfWorld" in out and "READINGS:" in out
    assert "Capacity   C = |p_high - p_low| = " in out and "(ideal cos(gamma) = 0.7071)" in out
    assert "Openness   O = " in out and "Connection I = " in out
    assert "total 300 (requested 300)" in out and "Bit-order canary: True" in out
    assert "The Self says:" in out and "EXPLANATION:" in out
    assert "BASELINES (theoretical classical references)" in out
    assert "Simulator honesty:" in out and out.rstrip().endswith(ATTRIBUTION)


def test_main_fake_ionq_path_one_job_no_transpile(capsys):
    be = run_smoke_local.run_qollab_style('main(90.0, 1.0, 0.0, 200, "demon")', fake_ionq=True,
                                          project="qollab_project")
    out = capsys.readouterr().out
    assert be.jobs == 1
    assert "ionq_sim" in out and "one job per run" in out and "mode tile" in out
    assert NO_RESOLVED in out                                                  # w = 1: unresolved
    assert "Laplace's Demon says:" in out and "Traceback" not in out


def test_main_invalid_settings_print_and_submit_nothing(capsys):
    be = run_smoke_local.run_qollab_style('main(400.0, 0.0, 0.0, 1024, "self")', project="qollab_project")
    out = capsys.readouterr().out
    assert be.jobs == 0 and "Invalid settings" in out and "intention_rad" in out and "Traceback" not in out
    be2 = run_smoke_local.run_qollab_style('main(90.0, 0.0, 0.0, 100, "god")', project="qollab_project")
    out2 = capsys.readouterr().out
    assert be2.jobs == 1 and "Unknown persona" in out2 and "The Self says:" in out2


# ------------------------------------------------------------------ IonQ serialization (offline)

def test_packed_job_serializes_for_ionq_offline(monkeypatch):
    qiskit_ionq = pytest.importorskip("qiskit_ionq")
    from qiskit_ionq import helpers, ionq_backend
    monkeypatch.setattr(ionq_backend, "get_n_qubits", lambda name, fallback=4: 29)   # no network lookup
    backend = qiskit_ionq.IonQProvider("STUB").get_backend("simulator")
    backend.set_options(noise_model="forte-1")
    assert backend.num_qubits == 29
    blocks = obs.probes({"world_coupling": 0.5, "intention_rad": 1.0, "perspective_rad": 0.3})
    args = dict(backend.options.items(), shots=1024)

    tile = qk_packer.pack(blocks, max_qubits=29, mode="tile", canary=True)
    assert len(tile.circuits) == 1
    body = json.loads(helpers.qiskit_to_ionq(tile.circuits[0], backend, passed_args=args))
    assert body["type"] == "ionq.circuit.v1" and body["shots"] == 1024
    assert body["noise"]["model"] == "forte-1" and body["backend"] == "simulator"
    circ = body["input"]["circuit"]
    assert body["input"]["qubits"] == 17 and body["input"]["gateset"] == "qis"
    assert {g["gate"] for g in circ} <= {"h", "rz", "ry", "x"}
    n_cx = sum(1 for inst in tile.circuits[0].data if inst.operation.name == "cx")
    assert n_cx == 8 and sum(1 for g in circ if g.get("controls")) == n_cx
    assert len(circ) == sum(1 for inst in tile.circuits[0].data if inst.operation.name != "measure")
    header = json.loads(gzip.decompress(base64.b64decode(body["metadata"]["qiskit_header"])))
    assert header["memory_slots"] == 17 and header["n_qubits"] == 17 and header["name"] == "tile0"
    assert header["meas_mapped"][:3] == [2, 0, 1]                           # the orientation canary's order
    assert sorted(header["meas_mapped"]) == list(range(17))

    lst = qk_packer.pack(blocks, max_qubits=29, mode="list", canary=True)
    body2 = json.loads(helpers.qiskit_to_ionq(lst.circuits, backend, passed_args=args))
    assert body2["type"] == "ionq.multi-circuit.v1" and body2["shots"] == 1024
    circs = body2["input"]["circuits"]
    assert [c["name"] for c in circs] == list(qk_packer.CANARY_NAMES) + list(obs.PROBES)
    assert body2["input"]["qubits"] == 3
    assert {g["gate"] for c in circs for g in c["circuit"]} <= {"h", "rz", "ry", "x"}
    assert all(c["circuit"] for c in circs)                                  # cal0's rz(0) keeps it non-empty
    assert backend._client is None                                           # nothing touched the API


# ------------------------------------------------------------------ FakeFez (opt-in, slow)

@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("FWO_SLOW") != "1", reason="set FWO_SLOW=1: FakeFez noisy path takes ~15-30 s")
def test_fakefez_noisy_list_path_slow():
    from qiskit_ibm_runtime.fake_provider.backends import FakeFez
    be = FakeFez()
    p = strict(api.profile_json(be, True))
    assert p["profile"]["family"] == "ibm_noise" and p["mode"] == "list" and p["profile"]["noisy"] is True
    r = strict(api.run_json(be, json.dumps({"world_coupling": 0.5})))
    assert r["status"] == "completed", r.get("error")
    src = r["source"]
    assert src["provider_family"] == "ibm_noise" and src["mode"] == "list" and src["remote"] is False
    assert src["noisy"] is True and src["n_circuits"] == 7 and src["submitted_as"] == "list"
    assert src["transpile"]["transpiled"] is True and r["jobs_submitted"] == 1
    assert src["bit_order_check"]["orientation_ok"] is True
    assert 0.0 <= src["bit_order_check"]["p_flip_0to1_mean"] < 0.1
    m = r["metrics"]
    assert all(n == 1024 for n in m["shots_seen"].values())
    assert 0.45 < m["capacity"] < 0.85 and m["resolved"] is True
    assert 0.05 < m["p_low"] < 0.3 and 0.7 < m["p_high"] < 0.95
    assert 0.1 < m["connection_bits"] < 0.5
