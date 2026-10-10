import math

import numpy as np
import pytest
from qiskit import QuantumCircuit, QuantumRegister, transpile
from qiskit.circuit import Parameter
from qiskit.quantum_info import (DensityMatrix, Operator, Pauli, Statevector,
                                 partial_trace, random_density_matrix, random_statevector)

import qk_primitives as pr

PI = math.pi
ALLOWED = {"h", "x", "y", "z", "s", "sdg", "rx", "ry", "rz", "cx", "cz", "swap", "measure"}
S2 = 1 / math.sqrt(2)


def ops(qc):
    return {inst.operation.name for inst in qc.data}


def ket(n, bits):
    """Basis vector with qubit q set to bits[q] (dict), Qiskit index order."""
    v = np.zeros(2 ** n, dtype=complex)
    v[sum(val << q for q, val in bits.items())] = 1
    return v


def exp_z(state, q, n):
    label = ["I"] * n
    label[n - 1 - q] = "Z"
    return float(np.real(state.expectation_value(Pauli("".join(label)))))


def random_u(n, seed, depth=4):
    rng = np.random.default_rng(seed)
    qc = QuantumCircuit(QuantumRegister(n, "d"), name="u", global_phase=0.37)
    one = ("h", "x", "y", "z", "s", "sdg")
    for _ in range(depth):
        for q in range(n):
            getattr(qc, one[rng.integers(len(one))])(q)
            getattr(qc, ("rx", "ry", "rz")[rng.integers(3)])(float(rng.uniform(-PI, PI)), q)
        for q in range(n - 1):
            getattr(qc, ("cx", "cz", "swap")[rng.integers(3)])(q, q + 1)
    return qc


# ---- Bell / GHZ ----------------------------------------------------------

BELL = {  # (amplitude, value of a, value of b)
    "phi+": [(1, 0, 0), (1, 1, 1)],
    "phi-": [(1, 0, 0), (-1, 1, 1)],
    "psi+": [(1, 0, 1), (1, 1, 0)],
    "psi-": [(1, 0, 1), (-1, 1, 0)],
}


@pytest.mark.parametrize("kind", pr.BELL_KINDS)
@pytest.mark.parametrize("a,b", [(0, 1), (2, 0)])
def test_bell_pair_states(kind, a, b):
    qc = pr.bell_pair(QuantumCircuit(3), a, b, kind)
    exp = sum(amp * S2 * ket(3, {a: va, b: vb}) for amp, va, vb in BELL[kind])
    sv = Statevector(qc)
    assert sv.equiv(Statevector(exp))
    assert np.allclose(sv.data, exp)          # exact, with a as the first ket character
    assert ops(qc) <= ALLOWED


def test_bell_pair_rejects_bad_input():
    with pytest.raises(ValueError):
        pr.bell_pair(QuantumCircuit(2), 0, 1, "phi")
    with pytest.raises(ValueError):
        pr.bell_pair(QuantumCircuit(2), 1, 1)


@pytest.mark.parametrize("qubits", [[0, 1, 2], [3, 0, 4, 1, 2]])
def test_ghz(qubits):
    n = len(qubits)
    qc = pr.ghz(QuantumCircuit(n), qubits)
    exp = S2 * (ket(n, {}) + ket(n, {q: 1 for q in range(n)}))
    assert Statevector(qc).equiv(Statevector(exp))
    assert ops(qc) <= ALLOWED
    assert qc.count_ops() == {"h": 1, "cx": n - 1}
    cx_pairs = [tuple(qc.find_bit(b).index for b in inst.qubits) for inst in qc.data[1:]]
    assert cx_pairs == list(zip(qubits, qubits[1:]))             # a chain, not a star


# ---- measurement-basis changes --------------------------------------------

@pytest.mark.parametrize("ta,tb", [(0, 0), (0, PI / 4), (PI / 2, -PI / 4),
                                   (0.3, 2.1), (-1.7, 4.0), (PI, 0)])
def test_measure_along_bell_correlator(ta, tb):
    qc = pr.bell_pair(QuantumCircuit(2), 0, 1)
    pr.measure_along(qc, 0, ta)
    pr.measure_along(qc, 1, tb)
    zz = float(np.real(Statevector(qc).expectation_value(Pauli("ZZ"))))
    assert zz == pytest.approx(math.cos(ta - tb), abs=1e-12)
    assert ops(qc) <= ALLOWED


@pytest.mark.parametrize("seed", range(5))
def test_measure_along_single_qubit(seed):
    sv = random_statevector(2, seed=seed)
    t = float(np.random.default_rng(seed).uniform(-2 * PI, 2 * PI))
    before = (math.cos(t) * np.real(sv.expectation_value(Pauli("Z")))
              + math.sin(t) * np.real(sv.expectation_value(Pauli("X"))))
    after = exp_z(sv.evolve(pr.measure_along(QuantumCircuit(1), 0, t)), 0, 1)
    assert after == pytest.approx(before, abs=1e-12)


def test_measure_along_accepts_parameter():
    t = Parameter("t")
    qc = pr.bell_pair(QuantumCircuit(2), 0, 1)
    pr.measure_along(qc, 0, t)
    pr.measure_along(qc, 1, 0.4)
    zz = Statevector(qc.assign_parameters({t: 1.1})).expectation_value(Pauli("ZZ"))
    assert float(np.real(zz)) == pytest.approx(math.cos(1.1 - 0.4), abs=1e-12)


@pytest.mark.parametrize("p,rot,unrot", [
    ("X", ["h"], ["h"]), ("Y", ["sdg", "h"], ["h", "s"]), ("Z", [], []), ("I", [], []),
])
def test_basis_change_gate_sequences(p, rot, unrot):
    names = lambda qc: [inst.operation.name for inst in qc.data]   # noqa: E731
    assert names(pr.rotate_for_pauli(QuantumCircuit(1), 0, p)) == rot
    assert names(pr.unrotate_for_pauli(QuantumCircuit(1), 0, p)) == unrot


@pytest.mark.parametrize("p", ["X", "Y", "Z"])
@pytest.mark.parametrize("seed", range(4))
def test_rotate_for_pauli(p, seed):
    sv = random_statevector(2, seed=100 + seed)
    before = float(np.real(sv.expectation_value(Pauli(p))))
    rot = pr.rotate_for_pauli(QuantumCircuit(1), 0, p)
    assert exp_z(sv.evolve(rot), 0, 1) == pytest.approx(before, abs=1e-12)
    assert ops(rot) <= ALLOWED


@pytest.mark.parametrize("p", ["I", "X", "Y", "Z", "y"])
def test_unrotate_inverts_exactly(p):
    qc = pr.rotate_for_pauli(QuantumCircuit(1), 0, p)
    pr.unrotate_for_pauli(qc, 0, p)
    assert Operator(qc) == Operator(QuantumCircuit(1))    # exact, phase included
    assert ops(qc) <= ALLOWED
    if p in "IZ":
        assert qc.size() == 0


def test_bad_pauli_raises():
    for bad in ("W", "XX", ""):
        with pytest.raises(ValueError):
            pr.rotate_for_pauli(QuantumCircuit(1), 0, bad)


# ---- parity to ancilla ------------------------------------------------------

def _parity_case(n, paulis, anc_pos, seed):
    """Random mixed data state on n qubits, ancilla |0> placed at anc_pos,
    data handed to parity_to_ancilla in a shuffled order."""
    rng = np.random.default_rng(seed)
    rho = random_density_matrix(2 ** n, seed=seed)
    full = DensityMatrix.from_label("0").tensor(rho)        # ancilla on qubit n
    move = QuantumCircuit(n + 1)
    for q in range(n, anc_pos, -1):
        move.swap(q, q - 1)                                 # ancilla -> anc_pos
    full = full.evolve(move)
    phys = [d if d < anc_pos else d + 1 for d in range(n)]
    order = [int(i) for i in rng.permutation(n)]
    label = ["I"] * n
    for d, p in zip(order, paulis):
        label[n - 1 - d] = p.upper()
    qc = QuantumCircuit(n + 1)
    pr.parity_to_ancilla(qc, [phys[d] for d in order], paulis, anc_pos)
    return rho, Pauli("".join(label)), full.evolve(qc), qc


@pytest.mark.parametrize("n,paulis,anc_pos,seed", [
    (3, "XYZ", 3, 1), (3, "YIY", 0, 2), (4, "IYXZ", 2, 3), (4, "ZZZZ", 4, 4),
    (4, "YYYY", 1, 5), (3, "III", 2, 6), (3, ["x", "Z", "I"], 1, 7),
])
def test_parity_to_ancilla(n, paulis, anc_pos, seed):
    rho, P, after, qc = _parity_case(n, paulis, anc_pos, seed)
    before = float(np.real(rho.expectation_value(P)))
    assert exp_z(after, anc_pos, n + 1) == pytest.approx(before, abs=1e-10)
    Pm = P.to_matrix()
    dephased = (rho.data + Pm @ rho.data @ Pm) / 2
    assert np.allclose(partial_trace(after, [anc_pos]).data, dephased, atol=1e-10)
    # Per outcome: anc=0 leaves Pi+ rho Pi+, anc=1 leaves Pi- rho Pi- (Pi+- = (1 +- P)/2).
    za = ["I"] * (n + 1)
    za[n - anc_pos] = "Z"
    za = Pauli("".join(za)).to_matrix()
    eye_a, eye_d = np.eye(2 ** (n + 1)), np.eye(2 ** n)
    for sign, bit in ((1, 0), (-1, 1)):
        proj_a = (eye_a + (1 - 2 * bit) * za) / 2
        branch = DensityMatrix(proj_a @ after.data @ proj_a, dims=after.dims())
        proj_d = (eye_d + sign * Pm) / 2
        assert np.allclose(partial_trace(branch, [anc_pos]).data,
                           proj_d @ rho.data @ proj_d, atol=1e-10)
    assert ops(qc) <= ALLOWED


def test_parity_to_ancilla_random_strings():
    rng = np.random.default_rng(11)
    for trial in range(6):
        n = int(rng.integers(3, 5))
        paulis = "".join(rng.choice(list("IXYZ"), size=n))
        test_parity_to_ancilla(n, paulis, int(rng.integers(0, n + 1)), 50 + trial)


@pytest.mark.parametrize("kind,key", [("phi+", "00"), ("phi-", "01"), ("psi+", "10"), ("psi-", "11")])
def test_bell_measurement_by_two_parities(kind, key):
    """XX into q2 and ZZ into q3 read every Bell state deterministically and
    leave it intact. Key is q3 q2 (bit 0 rightmost): phi- has XX = -1 -> q2 = 1."""
    bell = Statevector(pr.bell_pair(QuantumCircuit(2), 0, 1, kind))
    qc = pr.bell_pair(QuantumCircuit(4), 0, 1, kind)
    pr.parity_to_ancilla(qc, [0, 1], "XX", 2)
    pr.parity_to_ancilla(qc, [0, 1], "ZZ", 3)
    sv = Statevector(qc)
    assert sv.probabilities_dict(qargs=[2, 3])[key] == pytest.approx(1, abs=1e-12)
    assert sv.equiv(Statevector.from_label(key).tensor(bell))


def test_parity_to_ancilla_rejects_bad_input():
    qc = QuantumCircuit(4)
    with pytest.raises(ValueError):
        pr.parity_to_ancilla(qc, [0, 1], "XYZ", 3)
    with pytest.raises(ValueError):
        pr.parity_to_ancilla(qc, [0, 1], "XY", 1)
    with pytest.raises(ValueError):
        pr.parity_to_ancilla(qc, [0, 0], "XY", 3)
    with pytest.raises(ValueError):
        pr.parity_to_ancilla(qc, [0, 1], "XQ", 3)


# ---- CNOT copy ---------------------------------------------------------------

def test_copy_to_ancilla():
    once = pr.copy_to_ancilla(QuantumCircuit(2), 0, 1)
    assert Statevector.from_label("01").evolve(once).equiv(Statevector.from_label("11"))
    twice = pr.copy_to_ancilla(pr.copy_to_ancilla(QuantumCircuit(2), 0, 1), 0, 1)
    assert Operator(twice) == Operator(QuantumCircuit(2))
    assert ops(twice) <= ALLOWED


# ---- folding -----------------------------------------------------------------

@pytest.mark.parametrize("seed", range(3))
def test_fold_preserves_unitary_and_scales_size(seed):
    u = random_u(3, seed)
    ref, size0 = Operator(u), u.size()
    for factor in (1, 3, 5, np.int64(7)):
        f = pr.fold(u, factor)
        assert f is not u
        assert Operator(f) == ref                           # exact, global phase included
        assert f.size() == int(factor) * u.size()
        assert f.qregs == u.qregs and f.num_clbits == 0
        assert f.metadata["fold_factor"] == int(factor)
        assert ops(f) <= ALLOWED
    assert u.size() == size0 and u.global_phase == 0.37    # input untouched
    seq = list(u.data) + list(u.inverse().data) + list(u.data)   # U (U^dagger U), in order
    assert list(pr.fold(u, 3).data) == seq


def test_fold_of_fold_multiplies_factor_and_keeps_metadata():
    u = random_u(2, 4)
    u.metadata = {"tag": "x"}
    ff = pr.fold(pr.fold(u, 3), 5)
    assert ff.metadata == {"tag": "x", "fold_factor": 15}
    assert ff.size() == 15 * u.size()
    assert Operator(ff) == Operator(u)
    assert u.metadata == {"tag": "x"}


def test_fold_barriers():
    u = random_u(2, 9)
    f = pr.fold(u, 5, barrier=True)
    assert f.count_ops()["barrier"] == 4
    assert Operator(f) == Operator(u)
    assert f.size() == 5 * u.size()                         # size() skips barriers
    assert ops(f) <= ALLOWED | {"barrier"}
    assert "barrier" not in pr.fold(u, 5).count_ops()


def test_fold_barriers_block_cross_segment_cancellation():
    """With barriers each segment is optimized on its own, so the CX count of a
    transpiled fold is the sum over segments; without them level 1 may collapse it."""
    u = random_u(3, 2)
    t = lambda c: transpile(c, basis_gates=["rz", "sx", "x", "cx"],    # noqa: E731
                            optimization_level=1, seed_transpiler=1)
    cx = lambda c: t(c).count_ops().get("cx", 0)                        # noqa: E731
    folded = t(pr.fold(u, 3, barrier=True))
    assert folded.count_ops().get("cx", 0) == 2 * cx(u) + cx(u.inverse()) > 0
    assert Operator(folded).equiv(Operator(u))


@pytest.mark.parametrize("factor", [0, 2, 4, -1, -3, 3.0, "3", True, None])
def test_fold_rejects_bad_factor(factor):
    with pytest.raises(ValueError):
        pr.fold(random_u(2, 0), factor)


def test_fold_rejects_measured_circuits():
    u = random_u(2, 1)
    measured = u.copy()
    measured.measure_all()
    with pytest.raises(ValueError):
        pr.fold(measured, 3)
    with pytest.raises(ValueError):
        pr.fold(QuantumCircuit(2, 1), 3)


def test_standard_gate_constant():
    assert pr.STANDARD_GATES == ALLOWED
