"""Engine tests for the Free Will Observatory (qollab_project/observatory.py).

Covers the build guide's verification table (p.13): the no-coupling endpoints, half and
full coupling, the connection probe, the q0-only flip through the full pack -> simulate
-> unpack -> canonical path, and perspective changes; the closed form against the
Statevector on an 810-point grid; the controlled-RY block; the three readings and the
Hoeffding interval; and one job (tile, list and tiles) on a seeded BasicSimulator.

A simulator computes what quantum theory predicts for these circuits; nothing here tests
nature, and Capacity is a reading of a designed model, not a measurement of agency.
"""
import math

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import CRYGate
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Operator, Statevector

import observatory as obs
import qk_noise
import qk_packer
import qk_runtime

PI = math.pi
E1024 = 2.0 * math.sqrt(math.log(80.0) / 2048.0)          # guide p.6: about 0.0925
NO_RESOLVED = "No resolved influence at this shot count"
ATTRIBUTION = "This effort is supported by Qollab & IonQ"
ZERO = {"00": 0, "01": 0, "10": 0, "11": 0}


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


class SmallUnknownBackend(CountingBackend):
    """An unrecognized backend that reports 12 qubits: forces the 'tiles' layout."""
    __module__ = "somewhere.else"
    name = "mystery"
    num_qubits = 12


def _p1(dist):
    total = sum(dist.values())
    return (dist.get("10", 0) + dist.get("11", 0)) / total


def _run(settings, seed=11, backend=None):
    qk_runtime.begin_run()
    return obs.run(backend or _seeded(seed), settings)


def _sd(p, n=1024):
    return math.sqrt(max(p * (1.0 - p), 0.0) / n)


@pytest.fixture(autouse=True)
def fresh_run():
    qk_runtime.begin_run()
    yield
    qk_runtime.begin_run()


# ---------------------------------------------------------------- constants

def test_constants_contract_and_attribution():
    assert obs.BIT_ORDER == "SelfWorld"
    assert obs.PROBES == ("display", "intent_low", "intent_high", "connection")
    assert obs.OUTCOMES == ("00", "01", "10", "11")
    assert obs.PERSONAS == ("self", "demon", "observer")
    assert obs.MODES == ("auto", "tile", "list")
    assert (obs.SHOTS_MIN, obs.SHOTS_MAX) == (1, 4096)
    assert obs.ATTRIBUTION == ATTRIBUTION
    assert obs.NO_RESOLVED.startswith(NO_RESOLVED)
    assert "does not test nature" in obs.SIM_NOTE and "not a measurement of free will" in obs.SIM_NOTE
    assert "cos(gamma) cos(phi - beta)" in obs.FORMULA
    assert obs.MODEL_VERSION and obs.versions()["model_version"] == obs.MODEL_VERSION
    assert obs.versions()["qiskit"]
    for name in obs.__all__:
        assert hasattr(obs, name), name


# ---------------------------------------------------------------- settings

def test_validate_settings_defaults_and_gamma():
    s = obs.validate_settings({})
    assert s["intention_rad"] == PI / 2 and s["world_coupling"] == 0.0 and s["perspective_rad"] == 0.0
    assert s["shots_per_probe"] == 1024 and s["persona"] == "self" and s["mode"] == "auto"
    assert s["canary"] is True and s["gamma_rad"] == 0.0
    assert obs.validate_settings(None) == s
    assert obs.validate_settings({"world_coupling": None, "persona": None}) == s   # JS null = missing
    assert obs.validate_settings({"world_coupling": 0.5})["gamma_rad"] == pytest.approx(PI / 4)
    assert obs.validate_settings({"world_coupling": 1})["gamma_rad"] == pytest.approx(PI / 2)
    assert obs.validate_settings({"unknown_key": 3}) == s                           # ignored


def test_validate_settings_accepts_js_style_values():
    s = obs.validate_settings({"shots_per_probe": 1024.0, "persona": " DEMON ", "mode": "LIST",
                               "canary": "false", "intention_rad": "1.5", "world_coupling": 1})
    assert s["shots_per_probe"] == 1024 and isinstance(s["shots_per_probe"], int)
    assert s["persona"] == "demon" and s["mode"] == "list" and s["canary"] is False
    assert s["intention_rad"] == 1.5 and s["world_coupling"] == 1.0
    assert obs.validate_settings({"canary": 0})["canary"] is False
    assert obs.validate_settings({"canary": "yes"})["canary"] is True
    assert obs.validate_settings({"shots_per_probe": "256"})["shots_per_probe"] == 256
    # JS rounding of 2*pi: a hair over the top of the range is clipped, not refused
    assert obs.validate_settings({"intention_rad": 2 * PI + 1e-12})["intention_rad"] == 2 * PI
    assert obs.validate_settings({"perspective_rad": PI})["perspective_rad"] == PI


@pytest.mark.parametrize("bad", [
    {"intention_rad": -0.1}, {"intention_rad": 7.0}, {"intention_rad": float("nan")},
    {"intention_rad": "abc"}, {"intention_rad": [1.0]}, {"intention_rad": True},
    {"world_coupling": 1.5}, {"world_coupling": -0.01},
    {"perspective_rad": 3.2}, {"perspective_rad": -1e-6},
    {"shots_per_probe": 0}, {"shots_per_probe": 5000}, {"shots_per_probe": 4097},
    {"shots_per_probe": 10.5}, {"shots_per_probe": True}, {"shots_per_probe": "many"},
    {"persona": "god"}, {"persona": 1}, {"mode": "batch"}, {"canary": "maybe"}, {"canary": 2},
])
def test_validate_settings_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        obs.validate_settings(bad)


def test_validate_settings_rejects_non_objects():
    for bad in ([1, 2], "{}", 3):
        with pytest.raises(ValueError):
            obs.validate_settings(bad)


# ---------------------------------------------------------------- circuits

def test_make_circuit_is_the_guide_circuit_with_standard_gates():
    qc = obs.make_circuit(0.3, 0.4, 0.5)
    assert qc.num_qubits == 2 and qc.num_clbits == 0
    assert [inst.operation.name for inst in qc.data] == ["h", "rz", "ry", "cx", "ry", "cx", "rz", "h"]
    qubits = [[qc.find_bit(q).index for q in inst.qubits] for inst in qc.data]
    assert qubits == [[0], [0], [1], [0, 1], [1], [0, 1], [0], [0]]       # Self = q0, World = q1
    params = [list(inst.operation.params) for inst in qc.data]
    assert params[1] == [0.3] and params[2] == [0.4] and params[4] == [-0.4] and params[6] == [-0.5]
    ref = obs.make_circuit(0.3, 0.4, 0.5, reference=True)
    assert [inst.operation.name for inst in ref.data] == ["h", "rz", "ry", "cx", "ry", "cx"]


@pytest.mark.parametrize("gamma", [0.0, 0.3, PI / 4, 1.1, PI / 2])
def test_cry_block_equals_cry_gate_with_control_q0(gamma):
    block = QuantumCircuit(2)
    block.ry(gamma, 1)
    block.cx(0, 1)
    block.ry(-gamma, 1)
    block.cx(0, 1)
    ref = QuantumCircuit(2)
    ref.append(CRYGate(2 * gamma), [0, 1])                   # control q0 (Self), target q1 (World)
    assert Operator(block).equiv(Operator(ref))
    assert np.allclose(Operator(block).data, Operator(ref).data, atol=1e-12)   # equal, no phase
    if gamma:
        wrong = QuantumCircuit(2)
        wrong.append(CRYGate(2 * gamma), [1, 0])              # control q1 would be a bug
        assert not Operator(block).equiv(Operator(wrong))


@pytest.mark.parametrize("phi,gamma,beta", [(0.3, 0.4, 0.5), (PI / 2, PI / 4, 0.0), (4.0, 1.2, 2.5)])
def test_full_circuit_equals_cry_version_and_guide_state(phi, gamma, beta):
    ref = QuantumCircuit(2)
    ref.h(0)
    ref.rz(phi, 0)
    ref.cry(2 * gamma, 0, 1)
    ref.rz(-beta, 0)
    ref.h(0)
    assert Operator(obs.make_circuit(phi, gamma, beta)).equiv(Operator(ref))
    # guide p.4: before readout the state is [|00> + e^{i phi}(cos g |10> + sin g |11>)]/sqrt2,
    # ket order Self, World; Qiskit's index is World*2 + Self.
    expected = np.array([1.0, np.exp(1j * phi) * math.cos(gamma), 0.0,
                         np.exp(1j * phi) * math.sin(gamma)]) / math.sqrt(2)
    assert Statevector(obs.make_circuit(phi, gamma, reference=True)).equiv(Statevector(expected))


def test_probe_angles_follow_the_guide_table():
    s = obs.validate_settings({"intention_rad": 1.0, "world_coupling": 0.5, "perspective_rad": 0.4})
    angles = obs._probe_angles(s)
    g = PI / 4
    assert angles["display"] == (1.0, g, 0.4, False)
    assert angles["intent_low"] == (0.4, g, 0.4, False)
    assert angles["intent_high"] == (0.4 + PI, g, 0.4, False)
    assert angles["connection"] == (1.0, g, 0.0, True)
    blocks = obs.probes(s)
    assert [b.name for b in blocks] == list(obs.PROBES)
    assert all(b.measure == [0, 1] and b.num_qubits == 2 for b in blocks)
    assert blocks[3].meta["reference"] is True and blocks[3].meta["beta"] is None


# ---------------------------------------------------------------- closed form

def test_closed_form_matches_statevector_on_810_point_grid():
    worst, n = 0.0, 0
    for phi in np.linspace(0.0, 2 * PI, 10):
        for gamma in np.linspace(0.0, PI / 2, 9):
            for beta in np.linspace(0.0, PI, 9):
                p_sv = Statevector(obs.make_circuit(phi, gamma, beta)).probabilities([0])[1]
                worst = max(worst, abs(p_sv - obs.ideal_p_self_1(phi, gamma, beta)))
                n += 1
    assert n == 810
    assert worst < 1e-12, worst


@pytest.mark.parametrize("phi,w,beta", [(0.0, 0.0, 0.0), (1.0, 0.3, 0.2), (PI / 2, 0.5, 0.0),
                                        (2.5, 0.8, 1.0), (5.0, 1.0, 3.0), (2 * PI, 0.25, PI)])
def test_exact_metrics_match_closed_forms(phi, w, beta):
    s = {"intention_rad": phi, "world_coupling": w, "perspective_rad": beta}
    gamma = w * PI / 2
    m = obs.exact_metrics(s)
    assert m["p_self_1"] == pytest.approx(obs.ideal_p_self_1(phi, gamma, beta), abs=1e-12)
    assert m["p_low"] == pytest.approx((1 - math.cos(gamma)) / 2, abs=1e-12)
    assert m["p_high"] == pytest.approx((1 + math.cos(gamma)) / 2, abs=1e-12)
    assert m["capacity"] == pytest.approx(math.cos(gamma), abs=1e-12)
    assert m["delta_signed"] == pytest.approx(math.cos(gamma), abs=1e-12)
    assert m["openness_bits"] == pytest.approx(obs.binary_entropy(m["p_self_1"]), abs=1e-12)
    # connection probe in the fixed Z basis: P(00)=1/2, P(10)=cos^2/2, P(11)=sin^2/2
    d = obs.exact_probe_distributions(s)["connection"]
    assert d["00"] == pytest.approx(0.5, abs=1e-12) and d["01"] == pytest.approx(0.0, abs=1e-12)
    assert d["10"] == pytest.approx(math.cos(gamma) ** 2 / 2, abs=1e-12)
    assert d["11"] == pytest.approx(math.sin(gamma) ** 2 / 2, abs=1e-12)
    pred = obs.prediction(s)
    assert pred["p_self_1_closed_form"] == pytest.approx(pred["p_self_1"], abs=1e-12)
    assert pred["capacity_closed_form"] == pytest.approx(pred["capacity"], abs=1e-12)
    for name in obs.PROBES:
        dist = pred["probe_distributions"][name]
        assert set(dist) == set(obs.OUTCOMES) and sum(dist.values()) == pytest.approx(1.0, abs=1e-12)


# ---------------------------------------------------------------- guide p.13 table

@pytest.mark.parametrize("beta", [0.0, 0.4, PI / 2, 2.0, PI])
def test_no_coupling_endpoints_exact(beta):
    s = {"world_coupling": 0.0, "intention_rad": 1.0, "perspective_rad": beta}
    d = obs.exact_probe_distributions(s)
    assert _p1(d["intent_low"]) == pytest.approx(0.0, abs=1e-12)        # phi = beta: Self always 0
    assert _p1(d["intent_high"]) == pytest.approx(1.0, abs=1e-12)       # phi = beta + pi: always 1
    assert d["intent_high"]["10"] == pytest.approx(1.0, abs=1e-12)      # and the World stays 0
    m = obs.exact_metrics(s)
    assert m["capacity"] == pytest.approx(1.0, abs=1e-12) and m["connection_bits"] == pytest.approx(0.0, abs=1e-12)
    assert obs.ideal_p_self_1(beta, 0.0, beta) == pytest.approx(0.0, abs=1e-15)
    assert obs.ideal_p_self_1(beta + PI, 0.0, beta) == pytest.approx(1.0, abs=1e-15)


def test_no_coupling_endpoints_sampled_totals_and_probe_direction():
    r = _run({"world_coupling": 0.0, "intention_rad": PI, "perspective_rad": 0.0, "shots_per_probe": 512})
    c = r["counts"]
    assert c["intent_low"] == dict(ZERO, **{"00": 512})                  # Self 0, World 0
    assert c["intent_high"] == dict(ZERO, **{"10": 512})                 # Self 1 -> "10", never "01"
    assert c["display"] == dict(ZERO, **{"10": 512})                     # phi = pi (Act 2): Self = 1
    assert c["connection"] == dict(ZERO, **{"00": c["connection"]["00"], "10": c["connection"]["10"]})
    m = r["metrics"]
    assert m["p_low"] == 0.0 and m["p_high"] == 1.0 and m["capacity"] == 1.0 and m["delta_signed"] == 1.0
    assert m["resolved"] is True
    assert m["capacity_ci95"] == pytest.approx([1.0 - obs.hoeffding_e(512, 512), 1.0])
    assert m["openness_bits"] == 0.0 and m["connection_bits"] == 0.0
    assert m["shots_seen"] == {name: 512 for name in obs.PROBES}


def test_half_coupling_beta_zero_matches_the_table():
    m = obs.exact_metrics({"world_coupling": 0.5})
    assert m["p_low"] == pytest.approx(0.1464, abs=5e-5)
    assert m["p_high"] == pytest.approx(0.8536, abs=5e-5)
    assert m["capacity"] == pytest.approx(0.7071, abs=5e-5)
    assert m["p_low"] == pytest.approx((1 - math.cos(PI / 4)) / 2, abs=1e-12)
    assert m["capacity"] == pytest.approx(math.cos(PI / 4), abs=1e-12)
    # I = H(W) - H(W|S) = H(1/4) - 1/2 * H(1/2) = 0.311278 bits
    assert m["connection_bits"] == pytest.approx(obs.binary_entropy(0.25) - 0.5, abs=1e-12)
    r = _run({"world_coupling": 0.5})
    s = r["metrics"]
    assert abs(s["p_low"] - m["p_low"]) < 5 * _sd(m["p_low"])
    assert abs(s["p_high"] - m["p_high"]) < 5 * _sd(m["p_high"])
    assert s["capacity_ci95"][0] <= math.cos(PI / 4) <= s["capacity_ci95"][1] and s["resolved"] is True


@pytest.mark.parametrize("phi", [0.0, 0.7, PI / 2, PI, 4.0, 2 * PI])
def test_full_coupling_self_is_half_for_every_phi(phi):
    m = obs.exact_metrics({"world_coupling": 1.0, "intention_rad": phi})
    assert m["p_self_1"] == pytest.approx(0.5, abs=1e-12)
    assert m["capacity"] == pytest.approx(0.0, abs=1e-12)
    assert m["openness_bits"] == pytest.approx(1.0, abs=1e-12)
    assert m["connection_bits"] == pytest.approx(1.0, abs=1e-12)


def test_full_coupling_sampled_interval_contains_zero_and_keeps_the_estimate():
    r = _run({"world_coupling": 1.0})
    m = r["metrics"]
    assert m["capacity"] < 0.1 and m["resolved"] is False
    assert m["capacity_ci95"][0] == 0.0
    assert m["capacity_ci95"][1] == pytest.approx(abs(m["delta_signed"]) + m["hoeffding_e"], abs=1e-12)
    assert m["capacity"] == abs(m["p_high"] - m["p_low"])             # reported, not forced to zero
    assert NO_RESOLVED in r["explanation"]["factual"]
    assert abs(m["p_self_1"] - 0.5) < 5 * _sd(0.5)


def test_connection_zero_at_w0_and_one_bit_at_w1():
    d0 = obs.exact_probe_distributions({"world_coupling": 0.0})["connection"]
    assert d0["01"] == 0.0 and d0["11"] == 0.0                          # World fixed at 0
    d1 = obs.exact_probe_distributions({"world_coupling": 1.0})["connection"]
    assert d1["01"] == 0.0 and d1["10"] == 0.0                          # matching pairs only
    assert obs.exact_metrics({"world_coupling": 0.0})["connection_bits"] == pytest.approx(0.0, abs=1e-12)
    assert obs.exact_metrics({"world_coupling": 1.0})["connection_bits"] == pytest.approx(1.0, abs=1e-12)
    r0 = _run({"world_coupling": 0.0}, seed=3)
    assert r0["counts"]["connection"]["01"] == 0 and r0["counts"]["connection"]["11"] == 0
    assert r0["metrics"]["connection_bits"] == 0.0
    r1 = _run({"world_coupling": 1.0}, seed=4)
    assert r1["counts"]["connection"]["01"] == 0 and r1["counts"]["connection"]["10"] == 0
    assert r1["metrics"]["connection_bits"] == pytest.approx(1.0, abs=0.02)
    # monotone in between
    ws = [0.0, 0.25, 0.5, 0.75, 1.0]
    info = [obs.exact_metrics({"world_coupling": w})["connection_bits"] for w in ws]
    assert all(a < b for a, b in zip(info, info[1:]))


def test_canonical_counts_reverses_once_and_fills_zeros():
    assert obs.canonical_counts({"01": 5}) == dict(ZERO, **{"10": 5})      # Qiskit "01" = World 0, Self 1
    assert obs.canonical_counts({"10": 3}) == dict(ZERO, **{"01": 3})
    assert obs.canonical_counts({"1": 2, "0 1": 4, "11": 1}) == dict(ZERO, **{"10": 6, "11": 1})
    assert obs.canonical_counts({}) == ZERO
    assert obs.canonical_counts({"00": 7.0}) == dict(ZERO, **{"00": 7})
    once = obs.canonical_counts({"01": 5})
    assert obs.canonical_counts(once) != once                             # reversing is not idempotent
    for bad in ({"101": 1}, {"0x": 1}, {"01": -1}, {"2": 1}):
        with pytest.raises(ValueError):
            obs.canonical_counts(bad)


@pytest.mark.parametrize("mode", ["tile", "list"])
@pytest.mark.parametrize("which,local_key,app_key", [(0, "01", "10"), (1, "10", "01")])
def test_flip_one_qubit_through_pack_simulate_unpack_canonical(mode, which, local_key, app_key):
    """Guide p.13 'Flip q0 only -> 10': the whole adapter path, canary blocks included."""
    qc = QuantumCircuit(2)
    qc.x(which)
    block = qk_packer.Block("flip", qc, [0, 1], {})
    be = _seeded(1)
    prof = qk_runtime.backend_profile(be)
    packed = qk_packer.pack([block], max_qubits=prof["max_qubits"], mode=mode, canary=True)
    circs = qk_runtime.prepare(packed.circuits, be, prof)
    counts_list = qk_runtime.run_once(be, circs, 64, prof)
    assert qk_runtime.jobs_submitted() == 1
    unpacked = qk_packer.unpack(packed, counts_list)
    assert qk_packer.canary_report(unpacked)["orientation_ok"] is True
    assert unpacked["flip"] == {local_key: 64}                            # Qiskit order: World then Self
    assert obs.canonical_counts(unpacked["flip"]) == dict(ZERO, **{app_key: 64})


def test_perspective_change_moves_p_but_not_capacity():
    a = obs.exact_metrics({"world_coupling": 0.5, "intention_rad": 1.0, "perspective_rad": 0.0})
    b = obs.exact_metrics({"world_coupling": 0.5, "intention_rad": 1.0, "perspective_rad": 0.7})
    c = obs.exact_metrics({"world_coupling": 0.5, "intention_rad": 0.3, "perspective_rad": 0.0})
    assert a["capacity"] == pytest.approx(math.cos(PI / 4), abs=1e-12)
    assert b["capacity"] == pytest.approx(a["capacity"], abs=1e-12)
    assert abs(a["p_self_1"] - b["p_self_1"]) > 0.05
    assert b["p_self_1"] == pytest.approx(c["p_self_1"], abs=1e-12)     # depends on phi - beta only
    assert a["connection_bits"] == pytest.approx(b["connection_bits"], abs=1e-12)   # fixed basis
    ra = _run({"world_coupling": 0.5, "intention_rad": 1.0, "perspective_rad": 0.0}, seed=8)
    rb = _run({"world_coupling": 0.5, "intention_rad": 1.0, "perspective_rad": 0.7}, seed=9)
    for r in (ra, rb):
        m = r["metrics"]
        assert m["capacity_ci95"][0] <= math.cos(PI / 4) <= m["capacity_ci95"][1] and m["resolved"]
    assert abs(ra["metrics"]["p_self_1"] - a["p_self_1"]) < 5 * _sd(a["p_self_1"])
    assert abs(rb["metrics"]["p_self_1"] - b["p_self_1"]) < 5 * _sd(b["p_self_1"])


# ---------------------------------------------------------------- readings

def test_binary_entropy_endpoints_and_symmetry():
    assert obs.binary_entropy(0.0) == 0.0 and obs.binary_entropy(1.0) == 0.0
    assert obs.binary_entropy(0.5) == pytest.approx(1.0, abs=1e-15)
    assert obs.binary_entropy(0.25) == pytest.approx(0.8112781244591328, abs=1e-12)
    assert obs.binary_entropy(0.1) == pytest.approx(obs.binary_entropy(0.9), abs=1e-15)
    assert obs.binary_entropy(-0.2) == 0.0 and obs.binary_entropy(1.3) == 0.0      # clipped, no NaN
    assert 0.0 <= obs.binary_entropy(0.37) <= 1.0


def test_mutual_information_on_hand_made_counts():
    assert obs.mutual_information({"00": 50, "11": 50}) == pytest.approx(1.0, abs=1e-15)
    assert obs.mutual_information({"01": 50, "10": 50}) == pytest.approx(1.0, abs=1e-15)
    assert obs.mutual_information({"00": 25, "01": 25, "10": 25, "11": 25}) == pytest.approx(0.0, abs=1e-15)
    assert obs.mutual_information({"00": 50, "10": 50}) == pytest.approx(0.0, abs=1e-15)   # World fixed
    assert obs.mutual_information({"00": 30, "01": 10, "10": 45, "11": 15}) == pytest.approx(0.0, abs=1e-12)
    assert obs.mutual_information({"00": 50, "10": 25, "11": 25}) == pytest.approx(
        obs.binary_entropy(0.25) - 0.5, abs=1e-12)
    assert obs.mutual_information({"00": 0.5, "11": 0.5}) == pytest.approx(1.0, abs=1e-15)  # probabilities too
    assert obs.mutual_information({"00": 999, "11": 1}) > 0.0
    for bad in ({}, {"00": 0, "11": 0}):
        with pytest.raises(ValueError):
            obs.mutual_information(bad)


def test_hoeffding_e_formula_and_limits():
    e = obs.hoeffding_e(1024, 1024)
    assert e == pytest.approx(E1024, abs=1e-12)
    assert e == pytest.approx(0.092513, abs=1e-6)
    assert e == pytest.approx(0.0925, abs=1e-4)                            # guide p.6
    assert obs.hoeffding_e(256, 256) == pytest.approx(2 * e, abs=1e-12)
    assert obs.hoeffding_e(1020, 1021) == pytest.approx(
        math.sqrt(math.log(80) / 2040) + math.sqrt(math.log(80) / 2042), abs=1e-12)
    assert obs.hoeffding_e(0, 1024) == math.inf and obs.hoeffding_e(1024, 0) == math.inf
    assert obs.hoeffding_e(1, 1) > 1.0


@pytest.mark.parametrize("delta,e,lo,hi,resolved", [
    (0.70, 0.09, 0.61, 0.79, True),
    (-0.70, 0.09, 0.61, 0.79, True),          # sign of d is irrelevant for C = |d|
    (0.05, 0.09, 0.00, 0.14, False),          # spans zero: lower 0, upper = max magnitude
    (-0.05, 0.09, 0.00, 0.14, False),
    (0.09, 0.09, 0.00, 0.18, False),          # touching zero counts as including it
    (0.00, 0.00, 0.00, 0.00, False),
    (0.98, 0.09, 0.89, 1.00, True),           # clipped to [-1, 1]
    (-0.98, 0.09, 0.89, 1.00, True),
    (1.00, 0.0925, 0.9075, 1.00, True),       # guide p.13: w=0 example interval
])
def test_capacity_interval_cases(delta, e, lo, hi, resolved):
    ci, res = obs.capacity_interval(delta, e)
    assert ci == pytest.approx([lo, hi], abs=1e-12) and res is resolved
    assert ci[0] >= 0.0 and ci[1] <= 1.0


def test_capacity_interval_with_infinite_e_is_uninformative():
    assert obs.capacity_interval(0.3, math.inf) == ([0.0, 1.0], False)


def test_metrics_uses_actual_totals_not_requested_shots():
    counts = {
        "display": {"00": 300, "01": 0, "10": 700, "11": 0},
        "intent_low": {"00": 900, "01": 0, "10": 120, "11": 0},          # 1020 shots
        "intent_high": {"00": 100, "01": 0, "10": 921, "11": 0},         # 1021 shots
        "connection": {"00": 500, "01": 0, "10": 250, "11": 250},
    }
    m = obs.metrics(counts)
    assert m["p_self_1"] == 0.7 and m["p_low"] == pytest.approx(120 / 1020) and m["p_high"] == pytest.approx(921 / 1021)
    assert m["delta_signed"] == pytest.approx(921 / 1021 - 120 / 1020) and m["capacity"] == abs(m["delta_signed"])
    assert m["shots_seen"] == {"display": 1000, "intent_low": 1020, "intent_high": 1021, "connection": 1000}
    assert m["hoeffding_e"] == pytest.approx(obs.hoeffding_e(1020, 1021), abs=1e-12)
    assert m["capacity_ci95"] == pytest.approx([m["capacity"] - m["hoeffding_e"], m["capacity"] + m["hoeffding_e"]])
    assert m["resolved"] is True
    assert m["openness_bits"] == pytest.approx(obs.binary_entropy(0.7)) and m["connection_bits"] == pytest.approx(
        obs.binary_entropy(0.25) - 0.5, abs=1e-12)
    for missing in obs.PROBES:
        with pytest.raises(ValueError):
            obs.metrics({k: v for k, v in counts.items() if k != missing})
    with pytest.raises(ValueError):
        obs.metrics(dict(counts, display={"00": 0, "01": 0, "10": 0, "11": 0}))


def test_metrics_negative_delta_maps_through_abs():
    counts = {
        "display": {"00": 500, "01": 0, "10": 500, "11": 0},
        "intent_low": {"00": 100, "01": 0, "10": 900, "11": 0},
        "intent_high": {"00": 900, "01": 0, "10": 100, "11": 0},
        "connection": {"00": 500, "01": 0, "10": 500, "11": 0},
    }
    m = obs.metrics(counts)
    assert m["delta_signed"] == pytest.approx(-0.8) and m["capacity"] == pytest.approx(0.8)
    assert m["capacity_ci95"][0] == pytest.approx(0.8 - obs.hoeffding_e(1000, 1000)) and m["resolved"]


# ---------------------------------------------------------------- forecast, noise, baselines

def test_prediction_keys_and_bit_order():
    pred = obs.prediction({"world_coupling": 0.5})
    for key in ("p_self_1", "p_low", "p_high", "delta_signed", "capacity", "openness_bits",
                "connection_bits", "formula_p_self_1", "p_self_1_closed_form", "capacity_closed_form",
                "probe_distributions", "bit_order"):
        assert key in pred, key
    assert pred["bit_order"] == "SelfWorld" and pred["formula_p_self_1"] == obs.FORMULA
    assert set(pred["probe_distributions"]) == set(obs.PROBES)
    assert "capacity_ci95" not in pred                                     # no sampling, no interval


def test_baselines_are_the_guide_references():
    b = obs.baselines()
    assert b["fixed_output"]["capacity"] == 0.0 and b["fixed_output"]["openness_bits"] == 0.0
    assert b["fair_coin"]["capacity"] == 0.0 and b["fair_coin"]["openness_bits"] == 1.0
    assert b["kind"] == "theoretical classical references"
    assert "not a proof" in b["note"]


def test_noisy_prediction_degrades_monotonically_and_reports_its_model():
    ideal = obs.exact_metrics({"world_coupling": 0.0})
    n0 = obs.noisy_prediction({"world_coupling": 0.0}, qk_noise.ionq_forte_like(scale=0.0))
    n1 = obs.noisy_prediction({"world_coupling": 0.0})
    n2 = obs.noisy_prediction({"world_coupling": 0.0}, qk_noise.ionq_forte_like(scale=20.0))
    assert n0["capacity"] == pytest.approx(ideal["capacity"], abs=1e-12)
    assert 0.9 < n1["capacity"] < n0["capacity"]
    assert n2["capacity"] < n1["capacity"]
    assert n1["noise"]["effective"]["p2"] == pytest.approx(qk_noise.IONQ_FORTE1_R2Q)
    assert "approximation" in n1["note"] and "not a fresh measurement" in n1["note"]
    assert "capacity_ci95" not in n1
    # the same spec as a dict works too
    n1d = obs.noisy_prediction({"world_coupling": 0.0}, qk_noise.ionq_forte_like().to_dict())
    assert n1d["capacity"] == pytest.approx(n1["capacity"], abs=1e-12)


def test_two_qubit_depolarizing_shrinks_capacity_by_one_minus_p2_squared():
    # w = 0: the two CX gates each multiply the Self coherence by (1 - p2); nothing else acts.
    for p2 in (0.02, 0.1):
        m = obs.exact_metrics({"world_coupling": 0.0}, qk_noise.NoiseSpec(p2=p2))
        assert m["capacity"] == pytest.approx((1 - p2) ** 2, abs=1e-9)
    # symmetric readout flips r: p_low = r, p_high = 1 - r, so C = 1 - 2r
    m = obs.exact_metrics({"world_coupling": 0.0}, qk_noise.NoiseSpec(readout=(0.1, 0.1)))
    assert m["capacity"] == pytest.approx(0.8, abs=1e-12) and m["p_low"] == pytest.approx(0.1, abs=1e-12)


# ---------------------------------------------------------------- explanation

def _hand_counts(n=8):
    half = n // 2
    return {
        "display": {"00": half, "01": 0, "10": half, "11": 0},
        "intent_low": {"00": n - 1, "01": 0, "10": 1, "11": 0},
        "intent_high": {"00": 1, "01": 0, "10": n - 1, "11": 0},
        "connection": {"00": half, "01": 0, "10": half, "11": 0},
    }


def test_explanation_resolved_contains_the_numbers():
    r = _run({"world_coupling": 0.5}, seed=11)
    m, pred, ex = r["metrics"], r["prediction"], r["explanation"]
    f = ex["factual"]
    assert "P(Self=1) = %.3f" % m["p_self_1"] in f
    assert "Demon forecast %.3f" % pred["p_self_1"] in f
    assert "capacity %.3f" % m["capacity"] in f
    assert "interval %.3f to %.3f" % tuple(m["capacity_ci95"]) in f
    assert "ideal %.3f" % pred["capacity"] in f
    assert "openness %.3f bits" % m["openness_bits"] in f and "connection %.3f bits" % m["connection_bits"] in f
    assert "World coupling 0.50" in f and NO_RESOLVED not in f
    assert set(ex["poetic"]) == {"self", "demon", "observer"} and all(ex["poetic"].values())
    assert "%.2f" % m["capacity"] in ex["poetic"]["self"]
    assert "%.3f" % pred["p_self_1"] in ex["poetic"]["demon"] and "%.3f" % m["p_self_1"] in ex["poetic"]["demon"]
    assert "beta = %.2f" % r["settings"]["perspective_rad"] in ex["poetic"]["observer"]
    assert ex["resolved"] is True and "artistic interpretation" in ex["note"]
    for line in ex["poetic"].values():
        assert NO_RESOLVED not in line
        assert "proof" not in line.lower() and "proves" not in line.lower()


def test_explanation_unresolved_states_the_rule_in_every_voice():
    r = _run({"world_coupling": 1.0}, seed=11)
    ex = r["explanation"]
    assert ex["resolved"] is False and ex["factual"].endswith(obs.NO_RESOLVED)
    for line in ex["poetic"].values():
        assert NO_RESOLVED in line
    assert "uncertainty alone is not freedom" in ex["poetic"]["self"]       # Act 3 line
    assert "World" in ex["poetic"]["self"]                                     # I = 1 bit: strong World


def test_unresolved_text_does_not_claim_the_law_says_nothing_when_ideal_capacity_is_large():
    """At w = 0.5 the law says C = 0.71; eight shots per probe cannot resolve it (e > 1).
    The voices must say 'not resolved', never 'the dial moves nothing'."""
    s = obs.validate_settings({"world_coupling": 0.5, "shots_per_probe": 8})
    m = obs.metrics(_hand_counts(8))
    assert m["resolved"] is False and m["hoeffding_e"] > 1.0
    pred = obs.prediction(s)
    ex = obs.explanation(s, m, pred)
    assert NO_RESOLVED in ex["factual"]
    for line in ex["poetic"].values():
        assert NO_RESOLVED in line
    assert "moves nothing" not in ex["poetic"]["demon"]
    assert "no longer reshape" not in ex["poetic"]["self"]
    assert "%.2f" % pred["capacity"] in ex["poetic"]["demon"]              # the law's value is quoted
    # at full coupling the law does say zero, and the Demon may say so
    s1 = obs.validate_settings({"world_coupling": 1.0, "shots_per_probe": 8})
    ex1 = obs.explanation(s1, m, obs.prediction(s1))
    assert "moves nothing" in ex1["poetic"]["demon"] and NO_RESOLVED in ex1["poetic"]["demon"]
    assert "no longer reshape" in ex1["poetic"]["self"]


def test_explanation_demon_fit_wording_and_future_label():
    s = obs.validate_settings({"world_coupling": 0.0, "intention_rad": PI})
    m = obs.metrics({
        "display": {"00": 0, "01": 0, "10": 1024, "11": 0},
        "intent_low": {"00": 1024, "01": 0, "10": 0, "11": 0},
        "intent_high": {"00": 0, "01": 0, "10": 1024, "11": 0},
        "connection": {"00": 512, "01": 0, "10": 512, "11": 0},
    })
    ex = obs.explanation(s, m, obs.prediction(s))
    assert "within the shot noise" in ex["poetic"]["demon"] and "1024 shots" in ex["poetic"]["demon"]
    assert "nearly settled" in ex["poetic"]["self"]                           # openness 0, resolved
    assert "Predictability and capacity can coexist" in ex["poetic"]["self"]  # Act 2 line
    assert "1.00" in ex["poetic"]["self"]


# ---------------------------------------------------------------- one job

@pytest.mark.parametrize("mode,submitted_as,n_circuits", [("tile", "circuit", 1), ("list", "list", 7)])
def test_run_is_one_job_with_full_provenance(mode, submitted_as, n_circuits):
    be = CountingBackend(_seeded(7))
    r = _run({"world_coupling": 0.5, "mode": mode, "shots_per_probe": 300}, backend=be)
    assert be.jobs == 1 and qk_runtime.jobs_submitted() == 1
    assert r["status"] == "completed" and r["bit_order"] == "SelfWorld"
    assert r["model_version"] == obs.MODEL_VERSION
    assert r["settings"]["mode"] == mode and r["settings"]["gamma_rad"] == pytest.approx(PI / 4)
    src = r["source"]
    assert src["provider_family"] == "basic" and src["simulator"] is True and src["remote"] is False
    assert src["noisy"] is False and src["mode"] == mode and src["submitted_as"] == submitted_as
    assert src["n_circuits"] == n_circuits and src["job_returned"] is True
    assert src["shots_requested"] == 300 and src["shots_seen"] == {n: 300 for n in obs.PROBES}
    assert src["bit_order_check"]["orientation_ok"] is True
    assert src["bit_order_check"]["p_flip_0to1_mean"] == 0.0 and src["bit_order_check"]["p_flip_1to0_mean"] == 0.0
    assert src["versions"]["qiskit"] and src["sim_note"] == obs.SIM_NOTE
    assert src["layout"]["mode"] == mode and src["layout"]["n_circuits"] == n_circuits and src["layout"]["canary"]
    assert src["transpile"]["transpiled"] is True
    assert isinstance(src["wall_s"], float) and src["wall_s"] >= 0.0
    for name in obs.PROBES:
        c = r["counts"][name]
        assert set(c) == set(obs.OUTCOMES) and all(isinstance(v, int) for v in c.values())
        assert sum(c.values()) == 300
    m = r["metrics"]
    assert m == obs.metrics(r["counts"])                                    # metrics come from the counts
    assert r["prediction"]["capacity"] == pytest.approx(math.cos(PI / 4), abs=1e-12)
    assert r["baselines"]["fair_coin"]["openness_bits"] == 1.0
    assert set(r["explanation"]["poetic"]) == {"self", "demon", "observer"}


def test_tile_and_list_agree_with_the_exact_model():
    ex = obs.exact_metrics({"world_coupling": 0.5})
    runs = {mode: _run({"world_coupling": 0.5, "mode": mode}, seed=21 + i)
            for i, mode in enumerate(("tile", "list"))}
    for r in runs.values():
        m = r["metrics"]
        assert all(n == 1024 for n in m["shots_seen"].values())
        for key in ("p_self_1", "p_low", "p_high"):
            assert abs(m[key] - ex[key]) < 5 * _sd(ex[key]), key
        assert m["capacity_ci95"][0] <= ex["capacity"] <= m["capacity_ci95"][1]
        assert abs(m["connection_bits"] - ex["connection_bits"]) < 0.08
    assert abs(runs["tile"]["metrics"]["capacity"] - runs["list"]["metrics"]["capacity"]) < 0.1


def test_tiles_layout_on_a_small_one_job_backend_is_still_one_submission():
    be = SmallUnknownBackend(_seeded(5))
    r = _run({"world_coupling": 0.5, "shots_per_probe": 200}, backend=be)
    assert be.jobs == 1
    src = r["source"]
    assert src["provider_family"] == "unknown" and src["mode"] == "tiles" and src["submitted_as"] == "list"
    assert src["n_circuits"] == 2 and src["layout"]["max_qubits"] == 12
    assert max(src["layout"]["qubits_per_circuit"]) <= 12
    assert src["bit_order_check"]["orientation_ok"] is True
    assert all(n == 200 for n in r["metrics"]["shots_seen"].values())
    assert r["metrics"]["capacity_ci95"][0] <= math.cos(PI / 4) <= r["metrics"]["capacity_ci95"][1]


def test_run_without_canary_reports_the_gap():
    be = CountingBackend(_seeded(2))
    r = _run({"canary": False, "shots_per_probe": 100}, backend=be)
    assert be.jobs == 1 and r["source"]["layout"]["canary"] is False
    check = r["source"]["bit_order_check"]
    assert check["orientation_ok"] is None and check["p_flip_0to1_mean"] is None
    assert "not checked" in check["note"]
    assert r["source"]["layout"]["qubits_per_circuit"] == [8]


def test_run_refuses_a_second_job_on_a_one_job_backend_before_submitting():
    class OneJob(CountingBackend):
        __module__ = "qiskit_ionq.ionq_backend"
        name = "ionq_simulator"
        num_qubits = 29

    be = OneJob(_seeded(6))
    r = _run({"shots_per_probe": 100}, backend=be)
    assert be.jobs == 1 and r["source"]["transpile"]["transpiled"] is False     # IonQ: as written
    assert r["source"]["mode"] == "tile" and r["source"]["provider_family"] == "ionq_sim"
    with pytest.raises(RuntimeError, match="one-job guard"):
        obs.run(be, {"shots_per_probe": 100})
    assert be.jobs == 1


DEMO = [
    ("act1_open_future", {"world_coupling": 0.0, "intention_rad": PI / 2, "perspective_rad": 0.0}, 0.5, 1.0),
    ("act2_intention", {"world_coupling": 0.0, "intention_rad": PI, "perspective_rad": 0.0}, 1.0, 1.0),
    ("act3_constraint", {"world_coupling": 1.0, "intention_rad": PI / 2, "perspective_rad": 0.0}, 0.5, 0.0),
]


@pytest.mark.parametrize("name,settings,p_ideal,c_ideal", DEMO)
def test_guide_demo_acts_on_the_seeded_simulator(name, settings, p_ideal, c_ideal):
    r = _run(settings, seed=11)
    m, pred = r["metrics"], r["prediction"]
    assert pred["p_self_1"] == pytest.approx(p_ideal, abs=1e-12)
    assert pred["capacity"] == pytest.approx(c_ideal, abs=1e-12)
    assert abs(m["p_self_1"] - p_ideal) <= 5 * _sd(p_ideal) + 1e-12
    assert m["capacity_ci95"][0] <= c_ideal <= m["capacity_ci95"][1]
    assert m["resolved"] is (c_ideal > 0)
    assert all(n == 1024 for n in m["shots_seen"].values())
    if c_ideal == 0.0:
        assert NO_RESOLVED in r["explanation"]["factual"]
    else:
        assert m["capacity"] == 1.0 and m["capacity_ci95"] == pytest.approx([1.0 - E1024, 1.0])
