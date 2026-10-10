import math

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Statevector

import qk_packer as pk
import qk_runtime as rt

PI = math.pi


def chsh_blocks():
    out = []
    for name, ta, tb in (("a0b0", 0, PI / 4), ("a0b1", 0, -PI / 4),
                         ("a1b0", PI / 2, PI / 4), ("a1b1", PI / 2, -PI / 4)):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc.ry(-ta, 0)
        qc.ry(-tb, 1)
        out.append(pk.Block(name, qc, [0, 1], {"ta": ta, "tb": tb}))
    return out


def random_block(name, n, seed, measure):
    rng = np.random.default_rng(seed)
    qc = QuantumCircuit(n)
    for _ in range(3):
        for q in range(n):
            qc.ry(float(rng.uniform(0, PI)), q)
            qc.rz(float(rng.uniform(0, 2 * PI)), q)
        for q in range(n - 1):
            qc.cx(q, q + 1)
    return pk.Block(name, qc, list(measure), {})


def exact_marginal(block):
    """Exact distribution over block.measure, key convention: measure[0] rightmost."""
    return Statevector(block.circuit).probabilities_dict(qargs=block.measure)


def run_packed(packed, shots, seed):
    be = BasicSimulator()
    be.set_options(seed_simulator=seed)
    prof = rt.backend_profile(be)
    rt.begin_run()
    circs = rt.prepare(packed.circuits, be, prof)
    return rt.run_once(be, circs, shots, prof)


def run_separately(block, shots, seed):
    qc = QuantumCircuit(block.num_qubits, len(block.measure))
    qc.compose(block.circuit, inplace=True)
    qc.measure(block.measure, list(range(len(block.measure))))
    be = BasicSimulator()
    be.set_options(seed_simulator=seed)
    return be.run(qc, shots=shots).result().get_counts()


def parity(counts):
    n = sum(counts.values())
    e = sum((1 if k.count("1") % 2 == 0 else -1) * c for k, c in counts.items()) / n
    return e, math.sqrt(max(1 - e * e, 1e-12) / n)


def assert_dist_close(counts, exact, shots, k=3.0, label=""):
    keys = set(counts) | {key for key, p in exact.items() if p > 1e-12}
    for key in keys:
        p = exact.get(key, 0.0)
        phat = counts.get(key, 0) / shots
        sigma = math.sqrt(max(p * (1 - p), 1.0 / shots) / shots)
        assert abs(phat - p) <= k * sigma + 1e-12, (label, key, phat, p, sigma)


# ---------------------------------------------------------------- layout

def test_tile_layout_17_qubits_canary_first():
    packed = pk.pack(chsh_blocks(), max_qubits=29, mode="tile")
    assert len(packed.circuits) == 1
    qc = packed.circuits[0]
    assert qc.num_qubits == 17 and qc.num_clbits == 17 and len(qc.cregs) == 1
    names = [s.name for s in packed.slots]
    assert names[:3] == list(pk.CANARY_NAMES)
    assert packed.slot("a0b0").qubits == [9, 10] and packed.slot("a1b1").clbits == [15, 16]
    assert packed.slot(pk.CANARY_ORIENT).measure == [2, 0, 1]
    summ = packed.summary()
    assert summ["n_circuits"] == 1 and summ["qubits_per_circuit"] == [17]


def test_list_and_tiles_modes():
    blocks = chsh_blocks()
    lst = pk.pack(blocks, max_qubits=29, mode="list")
    assert len(lst.circuits) == 7 and [c.num_qubits for c in lst.circuits] == [3, 3, 3, 2, 2, 2, 2]
    tiles = pk.pack(blocks, max_qubits=6, mode="tiles")
    sizes = [c.num_qubits for c in tiles.circuits]
    assert max(sizes) <= 6 and sum(sizes) == 17
    assert sizes == [6, 5, 6]


def test_pack_rejects_bad_input():
    blocks = chsh_blocks()
    with pytest.raises(ValueError, match="use mode"):
        pk.pack(blocks, max_qubits=16, mode="tile")
    with pytest.raises(ValueError, match="duplicate"):
        pk.pack(blocks + [blocks[0]], max_qubits=40, mode="tile")
    measured = QuantumCircuit(2, 2)
    measured.measure([0, 1], [0, 1])
    with pytest.raises(ValueError, match="unmeasured"):
        pk.pack([pk.Block("m", measured, [0, 1])], max_qubits=10)
    with pytest.raises(ValueError, match="bad measure"):
        pk.pack([pk.Block("b", QuantumCircuit(2), [0, 2])], max_qubits=10)
    with pytest.raises(ValueError, match="reserved"):
        pk.pack([pk.Block(pk.CANARY_CAL0, QuantumCircuit(1), [0])], max_qubits=10)
    with pytest.raises(ValueError, match="mode"):
        pk.pack(blocks, max_qubits=40, mode="zigzag")
    with pytest.raises(ValueError, match="needs 3 qubits"):
        pk.pack(blocks, max_qubits=2, mode="list")


def test_capacity():
    blocks = chsh_blocks()
    assert pk.capacity(blocks, 17) == 4
    assert pk.capacity(blocks, 16) == 3
    assert pk.capacity(blocks, 8, canary=False) == 4
    assert pk.capacity(blocks, 10) == 0


# ---------------------------------------------------------------- deterministic bit bookkeeping

def test_unpack_deterministic_permuted_and_partial_measure():
    # q0=1, q1=0, q2=1, q3=1 ; measure [3, 1, 0] -> bit0=q3=1, bit1=q1=0, bit2=q0=1 -> "101"
    qc = QuantumCircuit(4)
    qc.x([0, 2, 3])
    b1 = pk.Block("perm", qc, [3, 1, 0])
    qc2 = QuantumCircuit(2)
    qc2.x(1)
    b2 = pk.Block("swap", qc2, [1, 0])         # bit0=q1=1, bit1=q0=0 -> "01"
    for mode, maxq in (("tile", 16), ("list", 16), ("tiles", 6)):
        packed = pk.pack([b1, b2], max_qubits=maxq, mode=mode)
        un = pk.unpack(packed, run_packed(packed, 50, 1))
        assert un["perm"] == {"101": 50}, mode
        assert un["swap"] == {"01": 50}, mode
        rep = pk.canary_report(un)
        assert rep["orientation_ok"] and rep["p_flip_0to1"] == [0, 0, 0] and rep["p_flip_1to0"] == [0, 0, 0]


def test_expected_orientation_key_is_not_a_palindrome():
    k = pk.expected_orientation_key()
    assert k == "110" and k != k[::-1]


# ---------------------------------------------------------------- round trips (statistical)

@pytest.mark.parametrize("mode", ["tile", "list", "tiles"])
def test_chsh_round_trip_packed_vs_separate_within_3_sigma(mode):
    shots = 4000
    blocks = chsh_blocks()
    packed = pk.pack(blocks, max_qubits=12 if mode == "tiles" else 24, mode=mode)
    un = pk.unpack(packed, run_packed(packed, shots, seed=7))
    s = 0.0
    for i, b in enumerate(blocks):
        sep = run_separately(b, shots, seed=100 + i)
        (e1, se1), (e2, se2) = parity(un[b.name]), parity(sep)
        assert abs(e1 - e2) <= 3 * math.hypot(se1, se2), (b.name, e1, e2)
        ideal = math.cos(b.meta["ta"] - b.meta["tb"])
        assert abs(e1 - ideal) <= 3 * se1 + 1e-9
        s += (-1 if b.name == "a1b1" else 1) * e1
    assert abs(s - 2 * math.sqrt(2)) < 0.15


def test_random_blocks_match_exact_marginals():
    shots = 6000
    blocks = [
        random_block("r3", 3, 1, [0, 1, 2]),
        random_block("r3perm", 3, 2, [2, 0]),          # partial + permuted
        random_block("r2", 2, 3, [1, 0]),
        random_block("r4", 4, 4, [3, 1]),
    ]
    for mode in ("tile", "list"):
        packed = pk.pack(blocks, max_qubits=24, mode=mode)
        un = pk.unpack(packed, run_packed(packed, shots, seed=21))
        for b in blocks:
            assert_dist_close(un[b.name], exact_marginal(b), shots, label=(mode, b.name))


# ---------------------------------------------------------------- canary diagnostics

def test_canary_detects_reversed_keys():
    packed = pk.pack(chsh_blocks(), max_qubits=24, mode="tile")
    counts = run_packed(packed, 500, 5)
    rev = [{k[::-1]: v for k, v in c.items()} for c in counts]
    assert pk.canary_report(pk.unpack(packed, rev))["orientation_ok"] is False
    diag = pk.diagnose_orientation(packed, rev)
    assert diag["reversed"] == 1.0 and diag["clbit"] < 0.5
    assert pk.diagnose_orientation(packed, counts)["clbit"] == 1.0


def test_canary_detects_reversal_in_list_mode():
    packed = pk.pack(chsh_blocks(), max_qubits=24, mode="list")
    counts = run_packed(packed, 300, 6)
    rev = [{k[::-1]: v for k, v in c.items()} for c in counts]
    assert pk.canary_report(pk.unpack(packed, rev))["orientation_ok"] is False
    assert pk.diagnose_orientation(packed, rev)["reversed"] == 1.0


def test_canary_detects_qubit_keyed_provider():
    # A provider that reports bit j = value of qubit j (ignoring the clbit map).
    packed = pk.pack(chsh_blocks(), max_qubits=24, mode="tile")
    n = packed.circuits[0].num_qubits
    s = packed.slot(pk.CANARY_ORIENT)
    qubit_vals = {s.qubits[i]: v for i, v in enumerate(pk.ORIENT_PREP)}
    key = ["0"] * n
    for q, v in qubit_vals.items():
        key[n - 1 - q] = str(v)
    fake = [{"".join(key): 100}]
    diag = pk.diagnose_orientation(packed, fake)
    assert diag["qubit"] == 1.0 and diag["clbit"] == 0.0


def test_canary_flip_rates_from_synthetic_counts():
    packed = pk.pack([], max_qubits=9, mode="list")
    orient = {"110": 98, "111": 2}
    cal0 = {"000": 90, "001": 6, "100": 4}         # bit0 flips 6%, bit2 flips 4%
    cal1 = {"111": 80, "110": 10, "011": 10}       # bit0 drops 10%, bit2 drops 10%
    rep = pk.canary_report(pk.unpack(packed, [orient, cal0, cal1]))
    assert rep["orientation_ok"]
    assert rep["p_flip_0to1"] == pytest.approx([0.06, 0.0, 0.04])
    assert rep["p_flip_1to0"] == pytest.approx([0.10, 0.0, 0.10])
    assert rep["p_flip_0to1_mean"] == pytest.approx(0.1 / 3)


def test_unpack_accepts_single_dict_and_checks_length():
    packed = pk.pack(chsh_blocks(), max_qubits=24, mode="tile")
    counts = run_packed(packed, 20, 2)
    assert pk.unpack(packed, counts[0]) == pk.unpack(packed, counts)
    with pytest.raises(ValueError):
        pk.unpack(packed, counts * 2)
