import json
import math
import time

import numpy as np
import pytest
from qiskit import QuantumCircuit, transpile

import qk_noise as qn

ONE_Q = ("h", "x", "y", "z", "s", "sdg", "rx", "ry", "rz")
TWO_Q = ("cx", "cz", "swap")


def random_circuit(n, n_gates, seed):
    rng = np.random.default_rng(seed)
    qc = QuantumCircuit(n)
    for _ in range(n_gates):
        if rng.random() < 0.35:
            a, b = (int(q) for q in rng.choice(n, size=2, replace=False))
            getattr(qc, TWO_Q[rng.integers(len(TWO_Q))])(a, b)
        else:
            name = ONE_Q[rng.integers(len(ONE_Q))]
            q = int(rng.integers(n))
            if name in ("rx", "ry", "rz"):
                getattr(qc, name)(float(rng.uniform(-math.pi, math.pi)), q)
            else:
                getattr(qc, name)(q)
    return qc


def aer_probs(qc, measure, p1, p2):
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, depolarizing_error
    nm = NoiseModel(basis_gates=list(ONE_Q + TWO_Q))   # keep cz/swap native when p=0
    nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), list(ONE_Q))
    nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), list(TWO_Q))
    sim = AerSimulator(method="density_matrix", noise_model=nm, fusion_enable=False)
    circ = qc.copy()
    circ.save_probabilities_dict(qubits=measure)
    tc = transpile(circ, sim, optimization_level=0)
    assert dict(tc.count_ops()) == dict(circ.count_ops())   # nothing merged or rewritten
    raw = sim.run(tc).result().data(0)["probabilities"]
    m = len(measure)
    return {format(int(k, 16) if isinstance(k, str) else int(k), "0%db" % m): float(v)
            for k, v in raw.items()}


def assert_close(a, b, tol):
    for k in set(a) | set(b):
        assert abs(a.get(k, 0.0) - b.get(k, 0.0)) < tol, (k, a.get(k), b.get(k))


# ---------------------------------------------------------------- vs Aer density matrix

@pytest.mark.parametrize("n,seed", [(2, 1), (2, 2), (3, 3), (3, 4), (4, 5), (4, 6)])
@pytest.mark.parametrize("p1,p2", [(0.0, 0.0), (0.01, 0.05), (0.2, 0.0), (0.3, 0.9)])
def test_matches_aer_density_matrix(n, seed, p1, p2):
    qc = random_circuit(n, 6 * n, seed)
    rng = np.random.default_rng(100 + seed)
    for measure in (list(rng.permutation(n)), [int(q) for q in rng.permutation(n)[: n - 1]]):
        measure = [int(q) for q in measure]
        got = qn.exact_distribution(qc, measure, qn.NoiseSpec(p1=p1, p2=p2))
        assert abs(sum(got.values()) - 1.0) < 1e-12
        assert_close(got, aer_probs(qc, measure, p1, p2), 1e-9)


def test_noiseless_matches_statevector_path():
    for seed in range(4):
        qc = random_circuit(4, 20, seed)
        qc.global_phase = 0.7
        assert_close(qn.exact_distribution(qc, [3, 0, 2]), qn.ideal_distribution(qc, [3, 0, 2]), 1e-12)


def test_bit_order_measure0_rightmost():
    qc = QuantumCircuit(3)
    qc.x(0)
    qc.x(1)
    assert qn.exact_distribution(qc, [2, 0, 1]) == {"110": 1.0}
    assert qn.ideal_distribution(qc, [2, 0, 1]) == {"110": 1.0}
    assert qn.exact_distribution(qc, [2]) == {"0": 1.0}


def test_one_qubit_depolarizing_hand_value():
    # ry(t)|0> then depolarize with l: P(1) = (1 - l) sin^2(t/2) + l/2 (Aer convention).
    for t, lam in ((0.4, 0.3), (2.5, 1.2), (1.0, 4 / 3)):
        qc = QuantumCircuit(2)
        qc.ry(t, 1)
        got = qn.exact_distribution(qc, [1], qn.NoiseSpec(p1=lam))
        assert abs(got.get("1", 0.0) - ((1 - lam) * math.sin(t / 2) ** 2 + lam / 2)) < 1e-14


def test_results_json_safe():
    qc = random_circuit(3, 10, 8)
    for d in (qn.exact_distribution(qc, [2, 1], qn.IONQ_FORTE_LIKE), qn.ideal_distribution(qc, [2, 1]),
              qn.sample(qn.ideal_distribution(qc, [2, 1]), 50, 0)):
        assert json.loads(json.dumps(d)) == d
        assert all(type(k) is str and len(k) == 2 for k in d)
        assert all(type(v) in (float, int) for v in d.values())


def test_tiny_entries_dropped():
    qc = QuantumCircuit(2)
    qc.ry(2e-8, 0)                      # P(1) = sin^2(1e-8) = 1e-16 < 1e-15
    qc.ry(2e-7, 1)                      # P(1) = 1e-14, kept
    for f in (qn.exact_distribution, qn.ideal_distribution):
        got = f(qc, [0, 1])
        assert set(got) == {"00", "10"} and got["10"] == pytest.approx(1e-14, rel=1e-6)
        assert abs(sum(got.values()) - 1.0) < 1e-15


def test_barrier_delay_skipped_id_is_noisy():
    qc = QuantumCircuit(1)
    qc.barrier()
    qc.delay(100, 0)
    assert qn.exact_distribution(qc, [0], qn.NoiseSpec(p1=0.5)) == {"0": 1.0}
    qc.id(0)
    got = qn.exact_distribution(qc, [0], qn.NoiseSpec(p1=0.5))
    assert abs(got["1"] - 0.25) < 1e-12


# ---------------------------------------------------------------- readout

def test_readout_confusion_analytic():
    qc = QuantumCircuit(2)
    qc.ry(0.7, 0)
    qc.cx(0, 1)
    qc.ry(1.9, 1)
    r01, r10 = 0.03, 0.08
    ideal = qn.ideal_distribution(qc, [0, 1])
    got = qn.exact_distribution(qc, [0, 1], qn.NoiseSpec(readout=(r01, r10)))
    conf = {("0", "0"): 1 - r01, ("1", "0"): r01, ("0", "1"): r10, ("1", "1"): 1 - r10}
    for read in ("00", "01", "10", "11"):
        want = sum(p * conf[(read[0], true[0])] * conf[(read[1], true[1])]
                   for true, p in ideal.items())
        assert abs(got.get(read, 0.0) - want) < 1e-12


@pytest.mark.parametrize("measure", [[2, 0], [1, 2, 0], [0]])
def test_readout_kron_with_gate_noise(measure):
    qc = random_circuit(3, 12, 21)
    r01, r10 = 0.07, 0.19
    m = len(measure)
    base = qn.exact_distribution(qc, measure, qn.NoiseSpec(p1=0.05, p2=0.1))
    vec = np.zeros(2 ** m)
    for k, p in base.items():
        vec[int(k, 2)] = p
    conf = np.array([[1 - r01, r10], [r01, 1 - r10]])      # [read, true]
    full = conf
    for _ in range(m - 1):
        full = np.kron(full, conf)
    want = {format(i, "0%db" % m): float(v) for i, v in enumerate(full @ vec)}
    got = qn.exact_distribution(qc, measure, qn.NoiseSpec(p1=0.05, p2=0.1, readout=(r01, r10)))
    assert_close(got, want, 1e-12)
    # the dial scales readout too
    half = qn.NoiseSpec(p1=0.025, p2=0.05, readout=(r01 / 2, r10 / 2), scale=2)
    assert_close(qn.exact_distribution(qc, measure, half), want, 1e-12)


def test_readout_full_flip_and_one_sided():
    qc = QuantumCircuit(3)
    qc.x(0)
    assert qn.exact_distribution(qc, [0, 1, 2], qn.NoiseSpec(readout=(1.0, 1.0))) == {"110": 1.0}
    # only true-1 bits can flip under (0, r10): measure[0] is the rightmost character
    got = qn.exact_distribution(qc, [0, 1], qn.NoiseSpec(readout=(0.0, 0.3)))
    assert_close(got, {"01": 0.7, "00": 0.3}, 1e-14)


# ---------------------------------------------------------------- CHSH noise dial

def chsh_s(lam):
    s = 0.0
    for ta, tb, sign in ((0, math.pi / 4, 1), (0, -math.pi / 4, 1),
                         (math.pi / 2, math.pi / 4, 1), (math.pi / 2, -math.pi / 4, -1)):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc.ry(-ta, 0)
        qc.ry(-tb, 1)
        dist = qn.exact_distribution(qc, [0, 1], qn.NoiseSpec(p1=0.0, p2=lam))
        e = sum(p * (1 if k.count("1") % 2 == 0 else -1) for k, p in dist.items())
        s += sign * e
    return s


def test_chsh_noise_dial_crossing():
    for lam in (0.0, 0.1, 0.25, 0.5, 1.0):
        assert abs(chsh_s(lam) - 2 * math.sqrt(2) * (1 - lam)) < 1e-12
    lo, hi = 0.0, 1.0
    while hi - lo > 1e-8:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if chsh_s(mid) > 2 else (lo, mid)
    assert abs(0.5 * (lo + hi) - (1 - 1 / math.sqrt(2))) < 1e-6


# ---------------------------------------------------------------- NoiseSpec

def test_scale_dial_and_clipping():
    assert qn.NoiseSpec(p2=0.1, scale=2).effective() == pytest.approx(qn.NoiseSpec(p2=0.2).effective())
    qc = random_circuit(3, 12, 9)
    assert_close(qn.exact_distribution(qc, [0, 1, 2], qn.NoiseSpec(p1=0.02, p2=0.1, scale=2)),
                 qn.exact_distribution(qc, [0, 1, 2], qn.NoiseSpec(p1=0.04, p2=0.2)), 1e-12)
    eff = qn.NoiseSpec(p1=1.0, p2=1.0, readout=(0.6, 2.0), scale=2).effective()
    assert eff == (4 / 3, 16 / 15, 1.0, 1.0)
    assert qn.NoiseSpec(p1=-0.1, p2=-1, readout=(-0.2, 0.1)).effective() == (0.0, 0.0, 0.0, 0.1)
    assert qn.NoiseSpec(p1=0.1, scale=0).is_noiseless()
    with pytest.raises(ValueError):
        qn.NoiseSpec(p1=float("nan")).effective()


def test_to_dict_json_safe_and_round_trip():
    spec = qn.NoiseSpec(p1=np.float64(0.01), p2=0.02, readout=(0.01, 0.03), scale=1.5)
    d = spec.to_dict()
    assert json.loads(json.dumps(d)) == d
    assert d["effective"]["p2"] == pytest.approx(0.03)
    back = qn.NoiseSpec.from_dict(d)
    assert back.effective() == pytest.approx(spec.effective())
    qc = random_circuit(2, 8, 4)
    assert qn.exact_distribution(qc, [0, 1], d) == qn.exact_distribution(qc, [0, 1], spec)


def test_conversions_round_trip():
    for n in (1, 2, 3):
        for p in (0.0, 1e-4, 0.01, 0.3):
            lam = qn.error_prob_to_depolarizing(p, n)
            assert qn.depolarizing_to_error_prob(lam, n) == pytest.approx(p, abs=1e-15)
    assert qn.error_prob_to_depolarizing(0.75, 1) == pytest.approx(1.0)
    assert qn.error_prob_to_depolarizing(1.0, 2) == pytest.approx(16 / 15)
    with pytest.raises(ValueError):
        qn.error_prob_to_depolarizing(0.1, 0)


@pytest.mark.parametrize("n", [1, 2])
def test_conversion_convention_matches_qiskit_fidelities(n):
    # The docstring's claims: p = 1 - F_process, r = 1 - F_avg = p d / (d + 1), and p is
    # the non-identity Pauli weight of Aer's depolarizing_error(l, n).
    from qiskit.quantum_info import average_gate_fidelity, process_fidelity
    from qiskit_aer.noise import depolarizing_error
    d = 2 ** n
    for p in (0.003, 0.2):
        lam = qn.error_prob_to_depolarizing(p, n)
        err = depolarizing_error(lam, n)
        chan = err.to_quantumchannel()
        assert 1 - process_fidelity(chan) == pytest.approx(p, abs=1e-12)
        assert 1 - average_gate_fidelity(chan) == pytest.approx(p * d / (d + 1), abs=1e-12)
        assert max(err.probabilities) == pytest.approx(1 - p, abs=1e-12)   # the identity term


def test_ionq_preset():
    # IonQ publishes depolarizing PARAMETERS (Aer convention): used without conversion.
    p1, p2, r01, r10 = qn.IONQ_FORTE_LIKE.effective()
    assert p1 == pytest.approx(4 / 3 * 0.0002)
    assert p2 == pytest.approx(16 / 15 * 0.00464)
    assert (r01, r10) == (0.0, 0.0)
    assert "depolarizing" in qn.IONQ_PRESET_NOTE and "approximates" in qn.IONQ_PRESET_NOTE
    json.dumps(qn.IONQ_FORTE_LIKE.to_dict())
    spam = qn.ionq_forte_like(spam=True, scale=2.0)
    assert spam.effective()[2:] == pytest.approx((0.01, 0.01))
    assert spam is not qn.ionq_forte_like(spam=True)
    assert qn.IONQ_FORTE_LIKE.scale == 1.0


# ---------------------------------------------------------------- guards

def test_guards():
    with pytest.raises(ValueError):
        qn.exact_distribution(QuantumCircuit(qn.MAX_QUBITS + 1), [0])
    qc = QuantumCircuit(3)
    qc.ccx(0, 1, 2)
    with pytest.raises(ValueError):
        qn.exact_distribution(qc, [0, 1, 2])
    with pytest.raises(ValueError):
        qn.exact_distribution(QuantumCircuit(2, 2), [0])
    qc = QuantumCircuit(2)
    qc.reset(0)
    with pytest.raises(ValueError):
        qn.exact_distribution(qc, [0])
    for bad in ([], [0, 0], [2], ["q0"]):
        with pytest.raises(ValueError):
            qn.exact_distribution(QuantumCircuit(2), bad)
    with pytest.raises(ValueError):
        qn.exact_distribution(QuantumCircuit(0), None)          # nothing to read out


def test_both_paths_reject_the_same_circuits():
    from qiskit.circuit import Parameter
    init = QuantumCircuit(1)
    init.initialize([0, 1], 0)
    unbound = QuantumCircuit(1)
    unbound.rx(Parameter("t"), 0)
    for qc in (init, unbound, QuantumCircuit(0)):
        for f in (qn.exact_distribution, qn.ideal_distribution):
            with pytest.raises(ValueError):
                f(qc, None)


def test_measure_accepts_qubits_and_integral_floats():
    qc = QuantumCircuit(3)
    qc.x(2)
    assert qn.exact_distribution(qc, [qc.qubits[2], qc.qubits[0]]) == {"01": 1.0}
    assert qn.ideal_distribution(qc, [2.0, 0.0]) == {"01": 1.0}
    assert qn.exact_distribution(qc, None) == {"100": 1.0}


def test_ten_qubits_allowed():
    qc = QuantumCircuit(qn.MAX_QUBITS)
    qc.h(0)
    qc.cx(0, 9)
    got = qn.exact_distribution(qc, [0, 9], qn.NoiseSpec(p1=0.0, p2=0.0))
    assert_close(got, {"00": 0.5, "11": 0.5}, 1e-12)


# ---------------------------------------------------------------- sample

def test_sample_reproducible_and_totals():
    dist = {"00": 0.4, "11": 0.35, "01": 0.25, "10": 0.0}
    a = qn.sample(dist, 1000, seed=7)
    assert a == qn.sample(dist, 1000, seed=7)
    assert sum(a.values()) == 1000
    assert list(a) == sorted(a) and "10" not in a and all(type(v) is int for v in a.values())
    assert qn.sample(dist, 0, seed=1) == {}
    assert sum(qn.sample(qn.exact_distribution(random_circuit(3, 10, 2), [0, 1, 2]), 777, 3).values()) == 777
    assert qn.sample(dist, 1000, seed=8) != a


def test_sample_frequencies_match_dist():
    # Keys must stay paired with their own probabilities (dist order != sorted order).
    dist = {"11": 0.5, "00": 0.1, "10": 0.3, "01": 0.1}
    shots = 200000
    counts = qn.sample(dist, shots, seed=5)
    for k, p in dist.items():
        sigma = math.sqrt(shots * p * (1 - p))
        assert abs(counts[k] - shots * p) < 5 * sigma, (k, counts[k])


# ---------------------------------------------------------------- timing

def test_six_qubit_noisy_circuit_is_fast():
    qc = random_circuit(6, 20, 11)
    t0 = time.perf_counter()
    got = qn.exact_distribution(qc, list(range(6)), qn.IONQ_FORTE_LIKE)
    assert time.perf_counter() - t0 < 1.0
    assert abs(sum(got.values()) - 1.0) < 1e-12
