import ast
import copy
import json
import math
import pathlib

import pytest
from qiskit import QuantumCircuit

import qk_bounds as qb

PI = math.pi
W = qb.WITNESSES


def bell_pair_builder(angles):
    """Correlator builder: |Phi+> on (0, 1), then ry(-theta) per side and measure [0, 1].
    For |Phi+> this predicts E = cos(theta_first - theta_second)."""
    def build(term):
        va, vb = term["vars"]
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc.ry(-angles[va], 0)
        qc.ry(-angles[vb], 1)
        return qc, [0, 1]
    return build


def chsh_game_builder(theta_a, theta_b):
    def build(x, y):
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc.ry(-theta_a[x], 0)
        qc.ry(-theta_b[y], 1)
        return qc, [0, 1], lambda key: (int(key[-1]), int(key[-2]))
    return build


def magic_square_builder(r, c):
    """Two |Phi+> pairs: Alice holds qubits (0, 1), Bob (2, 3); pairs are (0, 2), (1, 3).

    Square of observables (first factor on the first qubit of a party):
        XI   IX   XX
        IZ   ZI   ZZ
       -XZ  -ZX   YY
    Each party rotates its row / column into Z readouts; the third entry follows
    from the other two (row product +1, column product -1).
    """
    qc = QuantumCircuit(4)
    qc.h([0, 1])
    qc.cx(0, 2)
    qc.cx(1, 3)
    if r == 0:
        qc.h([0, 1])
    elif r == 2:            # CZ then H (x) H maps XZ -> ZI and ZX -> IZ
        qc.cz(0, 1)
        qc.h([0, 1])
    if c == 0:
        qc.h(2)
    elif c == 1:
        qc.h(3)
    else:                   # CX then H on the control maps XX -> ZI and ZZ -> IZ
        qc.cx(2, 3)
        qc.h(2)

    def decode(key):
        m = [1 if key[-1 - j] == "0" else -1 for j in range(4)]
        a = [(m[0], m[1]), (m[1], m[0]), (-m[0], -m[1])][r]
        b = [(m[2], m[3]), (m[3], m[2]), (m[2], m[3])][c]
        return (a[0], a[1], a[0] * a[1]), (b[0], b[1], -b[0] * b[1])
    return qc, [0, 1, 2, 3], decode


# --- catalog ---------------------------------------------------------------------

def test_catalog_shapes():
    assert set(W) == {"CHSH", "LG_K3", "CHSH_GAME", "MAGIC_SQUARE"}
    assert [t["label"] for t in W["CHSH"]["terms"]] == ["a0b0", "a0b1", "a1b0", "a1b1"]
    assert [t["coef"] for t in W["CHSH"]["terms"]] == [1.0, 1.0, 1.0, -1.0]
    assert W["CHSH"]["quantum"] == 2.8284271247461903
    assert W["CHSH_GAME"]["quantum"] == pytest.approx(0.8535533905932737, abs=1e-15)
    assert [(t["vars"], t["coef"]) for t in W["LG_K3"]["terms"]] == [
        (["Q1", "Q2"], 1.0), (["Q2", "Q3"], 1.0), (["Q1", "Q3"], -1.0)]
    for name, spec in W.items():
        assert spec["name"] == name and spec["direction"] == "max" and spec["ref"]


# --- classical bounds ------------------------------------------------------------

@pytest.mark.parametrize("name, want", [
    ("CHSH", 2.0), ("LG_K3", 1.0), ("CHSH_GAME", 0.75), ("MAGIC_SQUARE", 8 / 9)])
def test_classical_enumeration(name, want):
    got = qb.classical_max_enumerate(W[name])
    assert type(got) is float
    assert got == pytest.approx(want, abs=1e-12)
    assert got == pytest.approx(W[name]["classical"], abs=1e-12)


def test_classical_enumeration_min_direction():
    spec = copy.deepcopy(W["CHSH"])
    spec["direction"] = "min"
    assert qb.classical_max_enumerate(spec) == -2.0
    spec = copy.deepcopy(W["LG_K3"])
    spec["direction"] = "min"
    assert qb.classical_max_enumerate(spec) == -3.0
    spec["terms"][0]["vars"] = ["Q1", "Q9"]
    with pytest.raises(ValueError, match="Q9"):
        qb.classical_max_enumerate(spec)
    # games: CHSH can be lost at most 3 of 4 times (parity argument); the
    # magic square can be lost always (Bob answers minus Alice's entries).
    game = dict(W["CHSH_GAME"], direction="min")
    assert qb.classical_max_enumerate(game) == pytest.approx(0.25, abs=1e-12)
    game = dict(W["MAGIC_SQUARE"], direction="min")
    assert qb.classical_max_enumerate(game) == pytest.approx(0.0, abs=1e-12)


def test_game_win_predicates():
    win = W["CHSH_GAME"]["win"]
    assert win(1, 1, 0, 1) and win(1, 1, (1,), (0,)) and not win(1, 1, (0,), (0,))
    assert win(0, 1, 1, 1) and not win(1, 0, 1, 0)
    ms = W["MAGIC_SQUARE"]["win"]
    assert ms(0, 2, (1, -1, -1), (-1, 1, 1))           # a[2] = -1 == b[0] = -1
    assert not ms(0, 2, (1, 1, 1), (-1, 1, 1))
    assert not ms(0, 0, (1, 1, -1), (1, 1, -1))         # Alice's row product is -1: not allowed
    assert all(math.prod(a) == 1 for a in W["MAGIC_SQUARE"]["answers_a"](0))
    assert all(math.prod(b) == -1 for b in W["MAGIC_SQUARE"]["answers_b"](2))


# --- quantum values (exact statevector) ------------------------------------------

def test_quantum_ideal_chsh_tsirelson():
    angles = {"A0": 0.0, "A1": PI / 2, "B0": PI / 4, "B1": -PI / 4}
    got = qb.quantum_ideal(W["CHSH"], bell_pair_builder(angles))
    assert abs(got - 2 * math.sqrt(2)) < 1e-9
    assert abs(got - W["CHSH"]["quantum"]) < 1e-9


def test_quantum_ideal_lg_k3_correlators():
    # Correlators cos(theta_i - theta_j) with steps of pi/3 reach the quantum K3 maximum.
    angles = {"Q1": 0.0, "Q2": PI / 3, "Q3": 2 * PI / 3}
    got = qb.quantum_ideal(W["LG_K3"], bell_pair_builder(angles))
    assert abs(got - W["LG_K3"]["quantum"]) < 1e-9


def test_quantum_ideal_chsh_game():
    got = qb.quantum_ideal(W["CHSH_GAME"], chsh_game_builder([0.0, PI / 2], [PI / 4, -PI / 4]))
    assert abs(got - math.cos(PI / 8) ** 2) < 1e-9
    # Everyone measuring Z (a == b always) only loses on x = y = 1: the classical 3/4.
    same = qb.quantum_ideal(W["CHSH_GAME"], chsh_game_builder([0.0, 0.0], [0.0, 0.0]))
    assert abs(same - 0.75) < 1e-9


def test_quantum_ideal_magic_square_wins_always():
    got = qb.quantum_ideal(W["MAGIC_SQUARE"], magic_square_builder)
    assert abs(got - 1.0) < 1e-9


def test_quantum_ideal_respects_measure_list_and_key_order():
    # correlator: only the listed qubits enter the product (qubit 2 is flipped but unmeasured)
    spec = {"name": "T", "kind": "correlator", "variables": ["P", "Q"],
            "terms": [{"label": "pq", "vars": ["P", "Q"], "coef": 2.0}]}

    def flipped(measure):
        def build(term):
            qc = QuantumCircuit(3)
            qc.x([0, 2])
            return qc, measure
        return build
    assert qb.quantum_ideal(spec, flipped([0, 1])) == pytest.approx(-2.0, abs=1e-12)
    assert qb.quantum_ideal(spec, flipped([0, 2])) == pytest.approx(2.0, abs=1e-12)
    # game: decode sees measure[0] as the rightmost character (asymmetric win rule)
    game = {"name": "G", "kind": "game", "inputs": [1, 1], "input_prob": "uniform",
            "answers_a": lambda x: [(0,), (1,)], "answers_b": lambda y: [(0,), (1,)],
            "win": lambda x, y, a, b: (a, b) == (1, 0)}

    def one_on_q0(measure):
        def build(x, y):
            qc = QuantumCircuit(2)
            qc.x(0)
            return qc, measure, lambda key: (int(key[-1]), int(key[-2]))
        return build
    assert qb.quantum_ideal(game, one_on_q0([0, 1])) == pytest.approx(1.0, abs=1e-12)
    assert qb.quantum_ideal(game, one_on_q0([1, 0])) == pytest.approx(0.0, abs=1e-12)


def test_quantum_ideal_checks_measure_length():
    def bad(term):
        qc = QuantumCircuit(2)
        return qc, [0]
    with pytest.raises(ValueError, match="a0b0"):
        qb.quantum_ideal(W["CHSH"], bad)


# --- JSON view ----------------------------------------------------------------------

def test_spec_public_is_json_safe():
    for name, spec in W.items():
        pub = qb.spec_public(spec)
        assert json.loads(json.dumps(pub)) == pub
        assert not any(callable(v) for v in pub.values())
    game = qb.spec_public(W["MAGIC_SQUARE"])
    assert "win" not in game and "answers_a" not in game and game["inputs"] == [3, 3]
    assert qb.spec_public(W["CHSH"]) == W["CHSH"]
    assert set(qb.catalog()) == set(W)


def test_pyodide_safe_imports():
    tree = ast.parse(pathlib.Path(qb.__file__).read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"itertools", "math", "qiskit"}
