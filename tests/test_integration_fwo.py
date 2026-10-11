"""End-to-end integration of The Free Will Observatory: engine, JSON bridge and stub data.

1. The three demo acts of the build guide (p.14) run through the real bridge
   (`observatory_api.run_json`, JSON strings in and out) on a seeded `BasicSimulator`,
   and every reading is checked against the ideal model the way the page would read it:
   the Demon's forecast equals the closed form, the sampled probabilities sit within a
   single-probe Hoeffding half-width of it, the ideal Capacity lies inside the reported
   conservative 95% interval, and the "No resolved influence" sentence appears exactly
   when that interval includes zero.
2. The bit-order rule (a q0-only flip is the app outcome "10") through the sampler.
3. `dev/stub_data.js`, the canned answers the browser stub serves, round-trips as strict
   JSON and is a faithful record of the live engine: re-running the generator's seeds
   reproduces every canned run's counts, readings and forecast.

Simulators compute what quantum theory predicts; they do not test nature. Capacity is a
reading of a designed model, never proof of agency.

This effort is supported by Qollab & IonQ
"""
import json
import math
import os

import pytest
from qiskit.providers.basic_provider import BasicSimulator

import observatory as obs
import observatory_api as api
import qk_runtime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUB_DATA = os.path.join(ROOT, "dev", "stub_data.js")
PI = math.pi
SHOTS = 1024
SEED = 11
NO_RESOLVED = "No resolved influence at this shot count."
# Hoeffding, one probe of N shots: P(|p_hat - p| >= t) <= 2 exp(-2 N t^2); at this t the
# right side is 2/80 = 2.5%. The two-probe interval of the model uses e = 2 t.
HALF = math.sqrt(math.log(80.0) / (2.0 * SHOTS))
E = obs.hoeffding_e(SHOTS, SHOTS)

# Guide p.14, "Demonstrate the idea in three acts": (name, settings, ideal P(Self=1), ideal C)
ACTS = [
    ("act1_possible_futures", {"intention_rad": PI / 2, "world_coupling": 0.0, "perspective_rad": 0.0}, 0.5, 1.0),
    ("act2_intention", {"intention_rad": PI, "world_coupling": 0.0, "perspective_rad": 0.0}, 1.0, 1.0),
    ("act3_constraint", {"intention_rad": PI / 2, "world_coupling": 1.0, "perspective_rad": 0.0}, 0.5, 0.0),
]


def _reject(name):
    raise ValueError("non-strict JSON constant %s" % name)


def _loads(text):
    assert isinstance(text, str), "the bridge must return JSON text, got %s" % type(text).__name__
    return json.loads(text, parse_constant=_reject)


def _backend(seed):
    be = BasicSimulator()
    be.set_options(seed_simulator=seed)
    return be


def _run(settings, seed=SEED, shots=SHOTS):
    qk_runtime.begin_run()
    payload = dict(settings, shots_per_probe=shots, persona="self", mode="auto", canary=True)
    out = _loads(api.run_json(_backend(seed), json.dumps(payload)))
    assert out.get("status") == "completed", out.get("error")
    return out


def _ideal(settings):
    phi, w, beta = settings["intention_rad"], settings["world_coupling"], settings["perspective_rad"]
    gamma = w * PI / 2
    return {
        "p": obs.ideal_p_self_1(phi, gamma, beta),
        "p_low": obs.ideal_p_self_1(beta, gamma, beta),
        "p_high": obs.ideal_p_self_1(beta + PI, gamma, beta),
        "capacity": math.cos(gamma),
    }


# ---------------------------------------------------------------- the three acts

@pytest.mark.parametrize("name,settings,p_ideal,c_ideal", ACTS)
def test_demo_act_through_the_bridge(name, settings, p_ideal, c_ideal):
    run = _run(settings)
    m, pred, counts = run["metrics"], run["prediction"], run["counts"]
    ideal = _ideal(settings)
    assert ideal["p"] == pytest.approx(p_ideal, abs=1e-12)
    assert ideal["capacity"] == pytest.approx(c_ideal, abs=1e-12)

    # The Demon's forecast is the closed form, to rounding.
    assert pred["p_self_1"] == pytest.approx(p_ideal, abs=1e-12)
    assert pred["capacity"] == pytest.approx(c_ideal, abs=1e-12)
    assert pred["p_low"] == pytest.approx(ideal["p_low"], abs=1e-12)
    assert pred["p_high"] == pytest.approx(ideal["p_high"], abs=1e-12)
    assert pred["capacity_closed_form"] == pytest.approx(c_ideal, abs=1e-12)

    # Every probe returned the requested shots, in the app's bit order.
    assert run["bit_order"] == "SelfWorld"
    assert set(counts) == set(obs.PROBES)
    for probe in obs.PROBES:
        assert set(counts[probe]) == set(obs.OUTCOMES)
        assert sum(counts[probe].values()) == SHOTS
    assert m["shots_seen"] == {probe: SHOTS for probe in obs.PROBES}
    assert run["source"]["bit_order_check"]["orientation_ok"] is True

    # Sampled probabilities within a single-probe Hoeffding half-width of the ideal.
    assert abs(m["p_self_1"] - p_ideal) <= HALF
    assert abs(m["p_low"] - ideal["p_low"]) <= HALF
    assert abs(m["p_high"] - ideal["p_high"]) <= HALF

    # Capacity: the ideal lies inside the conservative 95% interval, whose half-width is e.
    lo, hi = m["capacity_ci95"]
    assert m["hoeffding_e"] == pytest.approx(E) and E == pytest.approx(0.0925, abs=5e-4)
    assert lo <= c_ideal <= hi
    assert 0.0 <= lo <= m["capacity"] <= hi <= 1.0
    assert m["capacity"] == pytest.approx(abs(m["p_high"] - m["p_low"]))
    assert m["resolved"] is (lo > 0.0)
    assert m["resolved"] is (c_ideal > 0.0)        # true for these three acts at 1,024 shots

    # Openness and Connection against the ideal model.
    assert m["openness_bits"] == pytest.approx(obs.binary_entropy(m["p_self_1"]))
    if settings["world_coupling"] == 0.0:
        # The World is never written to: counts with World = 1 are impossible, so I = 0 exactly.
        assert counts["connection"]["01"] == 0 and counts["connection"]["11"] == 0
        assert m["connection_bits"] == 0.0 and pred["connection_bits"] == pytest.approx(0.0, abs=1e-12)
    else:
        # Full coupling: only matching pairs, I = h(p00) close to 1 bit.
        assert counts["connection"]["01"] == 0 and counts["connection"]["10"] == 0
        assert pred["connection_bits"] == pytest.approx(1.0, abs=1e-12)
        assert m["connection_bits"] >= 0.98

    # The honest sentence: present exactly when the interval includes zero.
    factual = run["explanation"]["factual"]
    assert (NO_RESOLVED in factual) is (not m["resolved"])
    assert ("%.3f" % m["capacity"]) in factual and ("%.3f" % lo) in factual and ("%.3f" % hi) in factual
    for persona in obs.PERSONAS:
        line = run["explanation"]["poetic"][persona]
        assert line and (NO_RESOLVED in line) is (not m["resolved"])
        # explain_json agrees with the lines embedded in the run.
        again = _loads(api.explain_json(json.dumps(run), persona))
        assert "error" not in again
        assert again["factual"] == factual and again["poetic"] == line and again["resolved"] is m["resolved"]


def test_act2_is_certain_and_act1_act3_are_open():
    """Act 2 (phi = pi at w = 0) sends every display shot to Self = 1; Acts 1 and 3 are
    about half/half, yet only Act 1 resolves a capacity: the central contrast."""
    a1, a2, a3 = (_run(s) for _, s, _, _ in ACTS)
    assert a2["counts"]["display"] == {"00": 0, "01": 0, "10": SHOTS, "11": 0}
    assert a2["metrics"]["p_self_1"] == 1.0 and a2["metrics"]["openness_bits"] == 0.0
    for run in (a1, a3):
        assert run["metrics"]["openness_bits"] >= 0.99
    assert a1["metrics"]["capacity"] == 1.0 and a1["metrics"]["capacity_ci95"] == pytest.approx([1.0 - E, 1.0])
    assert a3["metrics"]["resolved"] is False and a3["metrics"]["capacity_ci95"][0] == 0.0
    assert a3["metrics"]["capacity_ci95"][1] == pytest.approx(abs(a3["metrics"]["delta_signed"]) + E)
    assert a3["metrics"]["capacity"] <= E                # otherwise the sample would have resolved


@pytest.mark.parametrize("seed", [1, 2, 3, 11])
def test_act3_never_forces_the_estimate_to_zero(seed):
    run = _run(ACTS[2][1], seed=seed)
    m = run["metrics"]
    assert m["capacity"] == abs(m["p_high"] - m["p_low"])
    assert m["capacity_ci95"] == [0.0, pytest.approx(m["capacity"] + E)]
    assert m["resolved"] is False
    assert NO_RESOLVED in run["explanation"]["factual"]


# ---------------------------------------------------------------- bit order

def test_q0_only_flip_reads_as_app_outcome_10():
    """Guide p.13: flip q0 (the Self) only; the app outcome must be '10' with certainty."""
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(2, 2)
    qc.x(0)
    qc.measure([0, 1], [0, 1])
    raw = _backend(SEED).run(qc, shots=256).result().get_counts()
    assert raw == {"01": 256}                       # Qiskit: c1 c0 = World Self
    assert obs.canonical_counts(raw) == {"00": 0, "01": 0, "10": 256, "11": 0}


# ---------------------------------------------------------------- stub data

def _stub():
    if not os.path.exists(STUB_DATA):
        pytest.skip("dev/stub_data.js not generated (run tools/make_ui_stubs.py)")
    with open(STUB_DATA, encoding="utf-8") as fh:
        text = fh.read()
    assert text.startswith("// GENERATED by tools/make_ui_stubs.py")
    body = text.split("export const STUB = ", 1)[1].rstrip()
    assert body.endswith(";")
    return json.loads(body[:-1], parse_constant=_reject)


def test_stub_data_round_trips_as_strict_json():
    data = _stub()
    text = json.dumps(data, allow_nan=False, separators=(",", ":"), sort_keys=True)
    assert json.loads(text, parse_constant=_reject) == data
    for token in ("NaN", "Infinity"):
        assert token not in text
    assert data["model_version"] == obs.MODEL_VERSION
    assert data["shots"] == SHOTS


def test_stub_runs_reproduce_the_live_engine():
    """Each canned run was produced by the real engine with a recorded seed; running the
    same seed again must give the same counts, readings and forecast (job ids and wall
    times differ, nothing else)."""
    import make_ui_stubs
    data = _stub()
    assert [s["key"] for s in data["settings"]] == [make_ui_stubs.settings_key(*s) for s in make_ui_stubs.SETTINGS]
    for i, spec in enumerate(make_ui_stubs.SETTINGS):
        key = make_ui_stubs.settings_key(*spec)
        canned = data["runs"]["basic"][key]
        settings = make_ui_stubs.settings_obj(*spec)
        qk_runtime.begin_run()
        fresh = _loads(api.run_json(make_ui_stubs._seeded_basic(make_ui_stubs.SEED + i), json.dumps(settings)))
        assert fresh["status"] == "completed", fresh.get("error")
        assert canned["status"] == "completed" and canned["bit_order"] == "SelfWorld"
        assert canned["settings"] == fresh["settings"]
        assert canned["counts"] == fresh["counts"], key
        assert canned["metrics"] == fresh["metrics"], key
        assert canned["prediction"] == fresh["prediction"], key
        assert canned["baselines"] == fresh["baselines"]
        assert canned["source"]["shots_seen"] == fresh["source"]["shots_seen"]
        assert canned["source"]["bit_order_check"]["orientation_ok"] is True
        # The canned forecast is the live predict_json for the same settings.
        predict = _loads(api.predict_json(json.dumps(settings)))
        assert data["predicts"][key]["ideal"] == predict["ideal"]
        assert data["predicts"][key]["ideal"] == fresh["prediction"]        # the same exact model
        assert data["predicts"][key]["baselines"] == fresh["baselines"]


def test_stub_demo_settings_match_the_guide_table():
    """The canned runs cover the three acts and the half-coupling row of guide p.5."""
    data = _stub()
    runs = data["runs"]["basic"]
    act1, act2, act3, half = (runs[k] for k in ("90|0|0|1024", "180|0|0|1024", "90|1|0|1024", "90|0.5|0|1024"))
    assert act1["metrics"]["capacity"] == 1.0 and act1["metrics"]["resolved"] is True
    assert act2["metrics"]["p_self_1"] == 1.0 and act2["metrics"]["openness_bits"] == 0.0
    assert act3["metrics"]["resolved"] is False and NO_RESOLVED in act3["explanation"]["factual"]
    assert act3["prediction"]["capacity"] == pytest.approx(0.0, abs=1e-12)
    assert half["prediction"]["p_low"] == pytest.approx(0.1464, abs=5e-5)
    assert half["prediction"]["p_high"] == pytest.approx(0.8536, abs=5e-5)
    assert half["prediction"]["capacity"] == pytest.approx(0.7071, abs=5e-5)
    lo, hi = half["metrics"]["capacity_ci95"]
    assert lo <= math.cos(PI / 4) <= hi and half["metrics"]["resolved"] is True
    # The IonQ-shaped stand-in's second call was refused before anything was submitted.
    refused = data["runs"]["ionq:refused"]
    assert refused["status"] == "failed" and "one-job guard" in refused["error"]
    assert refused["jobs_submitted"] == 1
