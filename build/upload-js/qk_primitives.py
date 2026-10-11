"""Circuit building blocks: Bell/GHZ preparation, measurement-basis changes,
non-destructive parity checks, CNOT copies and global unitary folding (ZNE).

Works under CPython and under Pyodide. Dependencies: qiskit + stdlib.

Every function except `fold` appends gates to `qc` in place and returns `qc`.
Only standard gates are emitted (STANDARD_GATES); `fold` reuses the input's own
gates and their inverses, so an allowed-gate input stays allowed.

Conventions:
- Ket order in docstrings is |a b ...> with the FIRST character for the first
  qubit argument (Qiskit prints keys the other way round: bit 0 rightmost).
- A Z measurement reading bit 0 means eigenvalue +1, bit 1 means -1.
- Pauli strings pair up position by position with the qubit list: paulis[i]
  acts on qubits[i]. This is NOT Qiskit's Pauli-label order.
"""

import numbers

__all__ = [
    "STANDARD_GATES", "BELL_KINDS", "bell_pair", "ghz", "measure_along",
    "rotate_for_pauli", "unrotate_for_pauli", "parity_to_ancilla",
    "copy_to_ancilla", "fold",
]

STANDARD_GATES = frozenset((
    "h", "x", "y", "z", "s", "sdg", "rx", "ry", "rz", "cx", "cz", "swap", "measure",
))
BELL_KINDS = ("phi+", "phi-", "psi+", "psi-")
_PAULIS = "IXYZ"


def _pauli(p):
    s = str(p).upper()
    if len(s) != 1 or s not in _PAULIS:
        raise ValueError("Pauli must be one of I, X, Y, Z; got %r" % (p,))
    return s


def bell_pair(qc, a, b, kind="phi+"):
    """Prepare a Bell pair on |0>_a |0>_b. Kets as |a b>, each normalized:
    phi+ = |00>+|11>, phi- = |00>-|11>, psi+ = |01>+|10>, psi- = |01>-|10>."""
    if kind not in BELL_KINDS:
        raise ValueError("kind must be one of %r; got %r" % (BELL_KINDS, kind))
    if a == b:
        raise ValueError("bell_pair needs two different qubits")
    qc.h(a)
    if kind.endswith("-"):
        qc.z(a)              # |+> -> |->: the relative sign
    if kind.startswith("psi"):
        qc.x(b)              # target starts in |1>: odd parity
    qc.cx(a, b)
    return qc


def ghz(qc, qubits):
    """(|0...0> + |1...1>)/sqrt(2) on `qubits`: h on the first, then a CX chain."""
    qubits = list(qubits)
    if not qubits:
        raise ValueError("ghz needs at least one qubit")
    qc.h(qubits[0])
    for c, t in zip(qubits, qubits[1:]):
        qc.cx(c, t)
    return qc


def measure_along(qc, q, theta):
    """Rotate so a later Z measurement on q measures cos(theta) Z + sin(theta) X.

    ry(-theta) maps that axis of the x-z plane onto +z. On |Phi+>, measuring A
    along ta and B along tb gives <ZZ> = cos(ta - tb). theta may be a qiskit
    Parameter (bind it before running).
    """
    try:
        theta = float(theta)
    except TypeError:        # symbolic Parameter / ParameterExpression stays symbolic
        pass
    qc.ry(-theta, q)
    return qc


def rotate_for_pauli(qc, q, p):
    """Basis change so a later Z measurement on q measures Pauli p.
    X: h. Y: sdg then h. Z and I: nothing."""
    p = _pauli(p)
    if p == "X":
        qc.h(q)
    elif p == "Y":
        qc.sdg(q)
        qc.h(q)
    return qc


def unrotate_for_pauli(qc, q, p):
    """Exact inverse of rotate_for_pauli (Y: h then s)."""
    p = _pauli(p)
    if p == "X":
        qc.h(q)
    elif p == "Y":
        qc.h(q)
        qc.s(q)
    return qc


def parity_to_ancilla(qc, qubits, paulis, anc):
    """Non-destructive (stabilizer-style) measurement of the product of
    paulis[i] on qubits[i], written into `anc`.

    With anc starting in |0>, a later Z measurement of anc reads 0 for
    eigenvalue +1 and 1 for -1. The data qubits are left projected onto that
    eigenspace (dephased in the eigenbasis of the product) but not measured.
    "I" entries are skipped.
    """
    qubits = list(qubits)
    paulis = [_pauli(p) for p in paulis]
    if len(paulis) != len(qubits):
        raise ValueError("%d paulis for %d qubits" % (len(paulis), len(qubits)))
    if len(set(qubits)) != len(qubits):
        raise ValueError("duplicate data qubits %r" % (qubits,))
    if anc in qubits:
        raise ValueError("ancilla %r is also a data qubit" % (anc,))
    active = [(q, p) for q, p in zip(qubits, paulis) if p != "I"]
    for q, p in active:
        rotate_for_pauli(qc, q, p)
    for q, _ in active:
        qc.cx(q, anc)
    for q, p in active:
        unrotate_for_pauli(qc, q, p)
    return qc


def copy_to_ancilla(qc, src, anc):
    """CNOT 'measurement' of src into anc (deferred measurement). With anc in |0>
    it copies the Z-basis value; applying it a second time uncopies."""
    qc.cx(src, anc)
    return qc


def _check_factor(factor):
    if (isinstance(factor, bool) or not isinstance(factor, numbers.Integral)
            or factor < 1 or factor % 2 == 0):
        raise ValueError("fold factor must be an odd positive int; got %r" % (factor,))
    return int(factor)


def fold(circuit, factor, barrier=False):
    """Global unitary folding for zero-noise extrapolation. Returns a NEW circuit
    U (U^dagger U)^k with k = (factor - 1) / 2: the same unitary, factor times
    the gates.

    `circuit` must be unmeasured: no clbits, no measure or reset. The register
    layout, name stem, global phase and metadata carry over; metadata
    "fold_factor" is the total scale (folding a folded circuit multiplies).
    barrier=True puts a barrier between segments. Either way, transpile folded
    circuits with optimization_level=0 so the U^dagger U pairs are not cancelled.
    """
    factor = _check_factor(factor)
    if circuit.num_clbits or any(
            inst.operation.name in ("measure", "reset") for inst in circuit.data):
        raise ValueError("fold needs an unmeasured circuit with no clbits")
    inv = circuit.inverse()
    out = circuit.copy_empty_like(name="%s_fold%d" % (circuit.name, factor))
    out.global_phase = 0          # each compose adds its own circuit's phase
    meta = dict(circuit.metadata or {})
    meta["fold_factor"] = factor * int(meta.get("fold_factor", 1))
    out.metadata = meta
    out.compose(circuit, inplace=True)
    for _ in range((factor - 1) // 2):
        for seg in (inv, circuit):
            if barrier:
                out.barrier()
            out.compose(seg, inplace=True)
    return out
