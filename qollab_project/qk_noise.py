"""Exact in-browser noise dial: density-matrix evolution with depolarizing + readout noise.

Works under CPython on a laptop and under Pyodide on Qollab. Dependencies: numpy + qiskit.

What this computes, and what it does not:
- `exact_distribution` evolves the full density matrix from |0...0> and returns the
  outcome probabilities that quantum theory predicts for the circuit under the
  stated noise model. It is a calculation, not a measurement of anything.
- Noise model: after EVERY 1-qubit gate a 1-qubit depolarizing channel with
  parameter p1 acts on that qubit; after EVERY 2-qubit gate a 2-qubit depolarizing
  channel with parameter p2 acts on those two qubits. Readout flips are applied
  classically, independently per measured bit. No idle, crosstalk or leakage noise.
- Depolarizing PARAMETER convention (Aer's `depolarizing_error`):
      rho -> (1 - l) rho + l * I/d (x) Tr_S(rho)      on the d = 2^n qubits S.
  l ranges over [0, 4^n / (4^n - 1)]: l = 1 replaces the qubits by I/d, and the
  top value applies a uniformly random NON-identity Pauli every time.
  Use `error_prob_to_depolarizing` to convert from a Pauli error probability.

Bit conventions (Qiskit's): result keys are bitstrings and the bit for
`measure[j]` is character `-1 - j` (measure[0] rightmost).

Budget: the state is a (2,)*2n complex tensor, 16 * 4^n bytes. n <= 6 is the
interactive budget (milliseconds per gate); n = 10 is a hard cap (16 MiB, slow).
"""

import math
from dataclasses import dataclass

import numpy as np

__all__ = [
    "NoiseSpec", "error_prob_to_depolarizing", "depolarizing_to_error_prob",
    "IONQ_FORTE_LIKE", "IONQ_PRESET_NOTE", "ionq_forte_like", "MAX_QUBITS", "INTERACTIVE_QUBITS",
    "exact_distribution", "ideal_distribution", "sample",
]

MAX_QUBITS = 10              # hard cap for exact_distribution / ideal_distribution
INTERACTIVE_QUBITS = 6       # what stays snappy in the browser
DROP_BELOW = 1e-15           # probabilities below this are dropped from results
_SKIP = ("barrier", "delay")
_FORBIDDEN = ("measure", "reset", "initialize")     # initialize contains a reset
_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _num(x, what):
    x = float(x)
    if not math.isfinite(x):
        raise ValueError("%s must be finite, got %r" % (what, x))
    return x


def _clip(x, hi):
    return min(max(x, 0.0), hi)


@dataclass
class NoiseSpec:
    p1: float = 0.0                 # 1-qubit depolarizing parameter (Aer convention)
    p2: float = 0.0                 # 2-qubit depolarizing parameter (Aer convention)
    readout: tuple = (0.0, 0.0)     # (P(read 1 | true 0), P(read 0 | true 1))
    scale: float = 1.0              # the dial: multiplies every rate above

    def effective(self):
        """(p1, p2, r01, r10) after scaling, clipped to each channel's valid range:
        p1 to [0, 4/3], p2 to [0, 16/15], readout to [0, 1]."""
        s = _num(self.scale, "scale")
        r01, r10 = (_num(r, "readout") for r in self.readout)
        return (
            _clip(s * _num(self.p1, "p1"), 4.0 / 3.0),
            _clip(s * _num(self.p2, "p2"), 16.0 / 15.0),
            _clip(s * r01, 1.0),
            _clip(s * r10, 1.0),
        )

    def is_noiseless(self):
        return not any(self.effective())

    def to_dict(self):
        """JSON-safe: the raw fields plus the effective (scaled, clipped) rates."""
        p1, p2, r01, r10 = self.effective()
        return {
            "p1": float(self.p1),
            "p2": float(self.p2),
            "readout": [float(r) for r in self.readout],
            "scale": float(self.scale),
            "effective": {"p1": p1, "p2": p2, "r01": r01, "r10": r10},
        }

    @classmethod
    def from_dict(cls, d):
        """Inverse of to_dict (ignores "effective"). Missing fields take defaults."""
        d = dict(d or {})
        return cls(
            p1=float(d.get("p1", 0.0)),
            p2=float(d.get("p2", 0.0)),
            readout=tuple(float(r) for r in d.get("readout", (0.0, 0.0))),
            scale=float(d.get("scale", 1.0)),
        )


def _as_spec(noise):
    if noise is None:
        return NoiseSpec()
    if isinstance(noise, NoiseSpec):
        return noise
    if isinstance(noise, dict):
        return NoiseSpec.from_dict(noise)
    raise TypeError("noise must be a NoiseSpec, a dict or None, got %s" % type(noise).__name__)


def error_prob_to_depolarizing(p, n_qubits):
    """Pauli error probability p -> depolarizing parameter l = p * 4^n / (4^n - 1).

    Convention converted: p is the probability that a NON-IDENTITY Pauli error
    occurs when the n-qubit depolarizing channel is written as a Pauli channel
    (each of the 4^n - 1 non-identity Paulis with probability p / (4^n - 1)).
    This p equals the process (entanglement) infidelity 1 - F_pro.
    It is NOT the average gate infidelity r = 1 - F_avg; for d = 2^n,
    r = p * d / (d + 1). A randomized-benchmarking "depolarizing parameter"
    alpha is 1 - l, not l.
    """
    d2 = _d2(n_qubits)
    return float(p) * d2 / (d2 - 1)


def depolarizing_to_error_prob(l, n_qubits):
    """Inverse of error_prob_to_depolarizing: p = l * (4^n - 1) / 4^n."""
    d2 = _d2(n_qubits)
    return float(l) * (d2 - 1) / d2


def _d2(n_qubits):
    if int(n_qubits) < 1:
        raise ValueError("n_qubits must be >= 1, got %r" % (n_qubits,))
    return 4 ** int(n_qubits)


# IonQ's noise-model guide gives its (pre-September-2025) Forte-1 simulator noise as a
# depolarizing channel after every native gate, rho -> (1-r) rho + r I/d: the same
# PARAMETER convention as NoiseSpec, so these numbers are used as they are.
IONQ_FORTE1_R1Q = 0.0002666666666666667
IONQ_FORTE1_R2Q = 0.004949333333333333
IONQ_FORTE_SPAM = 0.005      # Forte hardware spec sheet: average SPAM error ~0.5%


def ionq_forte_like(spam=False, scale=1.0):
    """A fresh NoiseSpec with IonQ's published Forte-1 simulator rates.

    spam=True adds the hardware sheet's ~0.5% SPAM error as symmetric readout error
    (IonQ's simulator model itself has no readout term). Returns a new object each
    call, so callers may change `.scale` freely."""
    r = IONQ_FORTE_SPAM if spam else 0.0
    return NoiseSpec(p1=IONQ_FORTE1_R1Q, p2=IONQ_FORTE1_R2Q, readout=(r, r), scale=scale)


IONQ_FORTE_LIKE = ionq_forte_like()      # read-only by convention: use ionq_forte_like() to vary it
IONQ_PRESET_NOTE = (
    "IonQ-like preset: IonQ's published depolarizing rates for its Forte-1 noise-model "
    "simulator (r1q = 2.67e-4, r2q = 4.95e-3; same convention as qiskit-aer's "
    "depolarizing_error), as documented for jobs before September 2025. IonQ applies them "
    "after its own compiled native gates; here they act on our standard-gate circuit, so "
    "this approximates the model rather than reproducing it. IonQ's current Forte models "
    "are more complex and not published. Readout error is 0 unless spam=True (0.5%, from "
    "the hardware spec sheet)."
)


# ---------------------------------------------------------------- validation

def _measure_list(circuit, measure):
    n = int(circuit.num_qubits)
    if measure is None:
        measure = range(n)
    out = []
    for q in measure:
        if isinstance(q, (int, np.integer)) or (isinstance(q, float) and q.is_integer()):
            out.append(int(q))          # JSON / JS numbers may arrive as 1.0
            continue
        try:
            out.append(circuit.find_bit(q).index)
        except Exception:
            raise ValueError("measure entry %r is neither a qubit index nor a Qubit" % (q,))
    if not out:
        raise ValueError("measure list is empty")
    if len(set(out)) != len(out) or any(not 0 <= q < n for q in out):
        raise ValueError("bad measure list %r for %d qubits" % (out, n))
    return out


def _validate(circuit):
    n = int(circuit.num_qubits)
    if n > MAX_QUBITS:
        raise ValueError("circuit has %d qubits > hard cap %d (%d is the interactive budget)"
                         % (n, MAX_QUBITS, INTERACTIVE_QUBITS))
    if circuit.num_clbits:
        raise ValueError("circuit must have no clbits; pass the qubits to read as `measure`")
    for inst in circuit.data:
        name = inst.operation.name
        if name in _FORBIDDEN:
            raise ValueError("%r is not allowed; leave the circuit unmeasured" % name)
        if name not in _SKIP and len(inst.qubits) > 2:
            raise ValueError("%r acts on %d qubits; decompose to 1- and 2-qubit gates first"
                             % (name, len(inst.qubits)))


# ---------------------------------------------------------------- density-matrix kernels
# rho is a (2,)*2n tensor: row axes 0..n-1 then column axes n..2n-1, each big-endian,
# so qubit q is row axis n-1-q and column axis 2n-1-q.

def _axes(qs, n):
    rows = [n - 1 - q for q in reversed(qs)]
    return rows, [n + r for r in rows]


def _apply_unitary(rho, u, qs, n):
    """rho -> U rho U^dagger with U (Qiskit little-endian over qs) on qubits qs."""
    k = len(qs)
    ut = np.asarray(u, dtype=complex).reshape([2] * (2 * k))
    rows, cols = _axes(qs, n)
    rho = np.tensordot(ut, rho, axes=(list(range(k, 2 * k)), rows))
    rho = np.moveaxis(rho, list(range(k)), rows)
    rho = np.tensordot(rho, ut.conj(), axes=(cols, list(range(k, 2 * k))))
    return np.moveaxis(rho, list(range(2 * n - k, 2 * n)), cols)


def _depolarize(rho, lam, qs, n):
    """(1 - lam) rho + lam * (I/d on qs) (x) Tr_qs(rho), in closed form."""
    if lam == 0:
        return rho
    k = len(qs)
    rows, cols = _axes(qs, n)
    full = list(_LETTERS[: 2 * n])
    traced = list(full)
    for r, c in zip(rows, cols):
        traced[c] = traced[r]
    rest = [a for a in range(2 * n) if a not in rows and a not in cols]
    reduced = np.einsum("".join(traced) + "->" + "".join(full[a] for a in rest), rho)
    eye = np.eye(2 ** k).reshape([2] * (2 * k)) / 2 ** k
    spec = ("".join(full[a] for a in rows + cols) + "," + "".join(full[a] for a in rest)
            + "->" + "".join(full))
    return (1 - lam) * rho + lam * np.einsum(spec, eye, reduced)


def _gate_matrix(op):
    try:
        return op.to_matrix()
    except Exception:
        pass
    try:
        from qiskit.quantum_info import Operator
        return Operator(op).data
    except Exception as exc:
        raise ValueError("%r is not a unitary gate (%s)" % (op.name, type(exc).__name__))


def _evolve(circuit, lam1, lam2):
    n = int(circuit.num_qubits)
    rho = np.zeros([2] * (2 * n), dtype=complex)
    rho[(0,) * (2 * n)] = 1.0
    for inst in circuit.data:
        op = inst.operation
        if op.name in _SKIP or not inst.qubits:      # global phase is irrelevant for rho
            continue
        qs = [circuit.find_bit(q).index for q in inst.qubits]
        rho = _apply_unitary(rho, _gate_matrix(op), qs, n)
        rho = _depolarize(rho, lam1 if len(qs) == 1 else lam2, qs, n)
    return rho


# ---------------------------------------------------------------- distributions

def _marginal(diag, n, measure):
    """Diagonal of rho (length 2^n) -> (2,)*m tensor; axis i is measure[m-1-i]."""
    probs = np.asarray(diag, dtype=float).reshape([2] * n)
    keep = [n - 1 - q for q in reversed(measure)]
    other = [a for a in range(n) if a not in keep]
    m = len(measure)
    return probs.transpose(keep + other).reshape(2 ** m, -1).sum(axis=1).reshape([2] * m)


def _confuse(probs, r01, r10):
    """Apply the per-bit readout confusion C[read, true] to every axis."""
    if not (r01 or r10):
        return probs
    conf = np.array([[1.0 - r01, r10], [r01, 1.0 - r10]])
    for ax in range(probs.ndim):
        probs = np.moveaxis(np.tensordot(conf, probs, axes=([1], [ax])), 0, ax)
    return probs


def _to_dict(flat, m):
    flat = np.asarray(flat, dtype=float).reshape(-1)
    keep = {i: float(v) for i, v in enumerate(flat) if v >= DROP_BELOW}
    total = sum(keep.values())
    fmt = "0%db" % m
    return {format(i, fmt): v / total for i, v in keep.items()}


def exact_distribution(circuit, measure, noise=None):
    """{key: probability} for `circuit` (unmeasured, no clbits) read out on `measure`.

    `noise` is a NoiseSpec, a dict for NoiseSpec.from_dict, or None (noiseless).
    Barriers and delays are skipped; "id" counts as a 1-qubit gate and gets noise.
    Raises ValueError for measure/reset/initialize, clbits, gates on 3+ qubits,
    non-unitary or unbound instructions, an empty or bad `measure`, or more than
    MAX_QUBITS qubits. `measure=None` reads every qubit in order 0..n-1. Entries below 1e-15 are dropped;
    values are floats summing to 1.
    """
    _validate(circuit)
    measure = _measure_list(circuit, measure)
    p1, p2, r01, r10 = _as_spec(noise).effective()
    n = int(circuit.num_qubits)
    rho = _evolve(circuit, p1, p2)
    diag = rho.reshape(2 ** n, 2 ** n).diagonal().real
    probs = _confuse(_marginal(diag, n, measure), r01, r10)
    return _to_dict(probs, len(measure))


def ideal_distribution(circuit, measure):
    """Noiseless fast path via Statevector; same contract as exact_distribution."""
    from qiskit.quantum_info import Statevector
    _validate(circuit)
    measure = _measure_list(circuit, measure)
    try:
        sv = Statevector(circuit)
    except Exception as exc:        # e.g. unbound parameters: same error type as the exact path
        raise ValueError("cannot simulate the circuit (%s: %s)" % (type(exc).__name__, exc))
    probs = sv.probabilities(qargs=measure)     # index bit j <-> measure[j]
    return _to_dict(probs, len(measure))


def sample(dist, shots, seed):
    """Multinomial draw of `shots` outcomes from `dist` -> {key: int}, sorted, no zeros."""
    shots = int(shots)
    if shots < 0:
        raise ValueError("shots must be >= 0")
    keys = sorted(dist)
    if not keys or shots == 0:
        return {}
    p = np.array([float(dist[k]) for k in keys])
    if np.any(p < 0) or not p.sum() > 0:
        raise ValueError("dist must have non-negative values with a positive total")
    draws = np.random.default_rng(seed).multinomial(shots, p / p.sum())
    return {k: int(c) for k, c in zip(keys, draws) if c}
