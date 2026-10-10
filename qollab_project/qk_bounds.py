"""Witness specs and their bounds: classical by enumeration, quantum exactly by statevector.

Works under CPython and Pyodide. Dependencies: qiskit + stdlib.

A witness is a dict of one of two kinds (WITNESSES holds the catalog; treat
it as read-only and copy before editing):

- kind "correlator" (Bell / Leggett-Garg type): "variables" are +-1 valued;
  each term has a "label", its "vars" and a "coef"; the witness is
  sum coef * <product of vars>. Measured data for a term arrives as
  block_counts[label], local bit j holding the outcome of vars[j]
  (bit 0 rightmost); see qk_estimators.witness_value.
- kind "game" (nonlocal game): "inputs" [nx, ny], "answers_a"(x) /
  "answers_b"(y) list the allowed answer tuples, "win"(x, y, a, b) -> bool,
  "input_prob" "uniform". The value is the mean win probability.

"classical" is the bound for local / macrorealist models, "quantum" the
quantum-theory optimum. "direction" "max": the classical bound is an upper
bound (violation = value above it); "min" the reverse. spec_public drops the
callables so a spec can cross to JavaScript.
"""

import itertools
import math

__all__ = ["WITNESSES", "classical_max_enumerate", "quantum_ideal", "spec_public", "catalog"]

CHSH_REF = ("Clauser, Horne, Shimony & Holt, Phys. Rev. Lett. 23, 880 (1969); "
            "quantum maximum: Tsirelson (Cirel'son), Lett. Math. Phys. 4, 93 (1980)")
LG_REF = ("Leggett & Garg, Phys. Rev. Lett. 54, 857 (1985); "
          "review: Emary, Lambert & Nori, Rep. Prog. Phys. 77, 016001 (2014)")
MAGIC_SQUARE_REF = ("Mermin, Phys. Rev. Lett. 65, 3373 (1990); Peres, Phys. Lett. A 151, 107 (1990); "
                    "game form: Aravind, Am. J. Phys. 72, 1303 (2004); "
                    "Brassard, Broadbent & Tapp, Found. Phys. 35, 1877 (2005)")


def _term(a, b, coef):
    return {"label": (a + b).lower(), "vars": [a, b], "coef": float(coef)}


def _bit(v):
    """A one-bit answer given as 0/1 or as a 1-tuple (0,) / (1,)."""
    return int(v[0]) if isinstance(v, (tuple, list)) else int(v)


def _chsh_answers(_x):
    return [(0,), (1,)]


def _chsh_win(x, y, a, b):
    return (_bit(a) ^ _bit(b)) == (int(x) & int(y))


_MS_ROW_ANSWERS = ((1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1))     # product +1
_MS_COL_ANSWERS = ((-1, -1, -1), (-1, 1, 1), (1, -1, 1), (1, 1, -1))     # product -1


def _ms_answers_a(_row):
    return list(_MS_ROW_ANSWERS)


def _ms_answers_b(_col):
    return list(_MS_COL_ANSWERS)


def _ms_win(r, c, a, b):
    """Alice's entry c equals Bob's entry r. Answers breaking the row (+1) or
    column (-1) product rule are not allowed answers, so they never win."""
    a, b = [int(v) for v in a], [int(v) for v in b]
    if math.prod(a) != 1 or math.prod(b) != -1:
        return False
    return a[int(c)] == b[int(r)]


WITNESSES = {
    "CHSH": {
        "name": "CHSH", "kind": "correlator", "variables": ["A0", "A1", "B0", "B1"],
        "terms": [_term("A0", "B0", 1), _term("A0", "B1", 1), _term("A1", "B0", 1), _term("A1", "B1", -1)],
        "classical": 2.0, "quantum": 2.0 * math.sqrt(2.0), "direction": "max", "ref": CHSH_REF,
    },
    # One system read at three times: C_ij = <Q_i Q_j>, K3 = C12 + C23 - C13.
    "LG_K3": {
        "name": "LG_K3", "kind": "correlator", "variables": ["Q1", "Q2", "Q3"],
        "terms": [_term("Q1", "Q2", 1), _term("Q2", "Q3", 1), _term("Q1", "Q3", -1)],
        "classical": 1.0, "quantum": 1.5, "direction": "max", "ref": LG_REF,
    },
    # Win iff a XOR b == x AND y.
    "CHSH_GAME": {
        "name": "CHSH_GAME", "kind": "game", "inputs": [2, 2],
        "answers_a": _chsh_answers, "answers_b": _chsh_answers, "win": _chsh_win,
        "input_prob": "uniform", "classical": 0.75, "quantum": math.cos(math.pi / 8) ** 2,
        "direction": "max", "ref": CHSH_REF,
    },
    # Alice gets row r, Bob column c; each answers three +-1 entries.
    "MAGIC_SQUARE": {
        "name": "MAGIC_SQUARE", "kind": "game", "inputs": [3, 3],
        "answers_a": _ms_answers_a, "answers_b": _ms_answers_b, "win": _ms_win,
        "input_prob": "uniform", "classical": 8.0 / 9.0, "quantum": 1.0,
        "direction": "max", "ref": MAGIC_SQUARE_REF,
    },
}


def _direction(spec):
    d = spec.get("direction", "max")
    if d not in ("max", "min"):
        raise ValueError("direction must be 'max' or 'min' (got %r)" % (d,))
    return max if d == "max" else min


def _uniform_inputs(spec):
    if spec.get("input_prob", "uniform") != "uniform":
        raise ValueError("only input_prob 'uniform' is supported (got %r)" % (spec.get("input_prob"),))
    nx, ny = (int(n) for n in spec["inputs"])
    return nx, ny


def _term_indices(spec):
    idx = {v: i for i, v in enumerate(spec["variables"])}
    out = []
    for t in spec["terms"]:
        missing = [v for v in t["vars"] if v not in idx]
        if missing:
            raise ValueError("term %r uses unknown variables %r" % (t["label"], missing))
        out.append((float(t["coef"]), [idx[v] for v in t["vars"]]))
    return out


def classical_max_enumerate(spec):
    """Classical bound by brute force (min instead of max when direction is "min").

    correlator: every +-1 assignment to the variables.
    game: every pair of deterministic strategies (input -> allowed answer, per
    party). Shared randomness only mixes these, so it cannot do better.
    """
    pick = _direction(spec)
    kind = spec.get("kind")
    if kind == "correlator":
        terms = _term_indices(spec)
        return float(pick(
            sum(c * math.prod(signs[i] for i in ix) for c, ix in terms)
            for signs in itertools.product((1, -1), repeat=len(spec["variables"]))))
    if kind != "game":
        raise ValueError("unknown witness kind %r" % (kind,))
    nx, ny = _uniform_inputs(spec)
    ans_a = [list(spec["answers_a"](x)) for x in range(nx)]
    ans_b = [list(spec["answers_b"](y)) for y in range(ny)]
    win = spec["win"]
    table = [[[[bool(win(x, y, a, b)) for b in ans_b[y]] for y in range(ny)] for a in ans_a[x]]
             for x in range(nx)]       # table[x][ia][y][ib]
    best = None
    for choice in itertools.product(*(range(len(a)) for a in ans_a)):    # Alice's strategy
        # Bob's best response is chosen per input y independently.
        total = sum(pick(sum(table[x][choice[x]][y][ib] for x in range(nx)) for ib in range(len(ans_b[y])))
                    for y in range(ny))
        best = total if best is None else pick(best, total)
    return float(best / (nx * ny))


def _parity_expectation(p):
    """sum_i p[i] * (-1)^popcount(i): the +-1 product over all measured bits."""
    return sum(float(pi) * (-1.0 if bin(i).count("1") & 1 else 1.0) for i, pi in enumerate(p))


def quantum_ideal(spec, builder):
    """What quantum theory predicts for the witness under `builder`, exactly (no sampling).

    correlator: builder(term) -> (unmeasured circuit, measure qubits, one per
    term var in order); returns sum coef * <product of +-1 outcomes>.
    game: builder(x, y) -> (unmeasured circuit, measure qubits, decode), where
    decode(local_key) -> (a, b) and local_key has measure[0] rightmost (the
    block-local convention); returns the mean exact win probability over
    uniform inputs.
    """
    from qiskit.quantum_info import Statevector
    kind = spec.get("kind")
    if kind == "correlator":
        total = 0.0
        for t in spec["terms"]:
            qc, measure = builder(t)
            measure = [int(q) for q in measure]
            if len(measure) != len(t["vars"]):
                raise ValueError("term %r: builder measured %d qubits for %d variables"
                                 % (t["label"], len(measure), len(t["vars"])))
            total += float(t["coef"]) * _parity_expectation(Statevector(qc).probabilities(qargs=measure))
        return float(total)
    if kind != "game":
        raise ValueError("unknown witness kind %r" % (kind,))
    nx, ny = _uniform_inputs(spec)
    win = spec["win"]
    acc = 0.0
    for x in range(nx):
        for y in range(ny):
            qc, measure, decode = builder(x, y)
            dist = Statevector(qc).probabilities_dict(qargs=[int(q) for q in measure])
            acc += sum(float(p) for key, p in dist.items() if win(x, y, *decode(str(key))))
    return float(acc / (nx * ny))


def _json_safe(v):
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items() if not callable(x)}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if hasattr(v, "tolist"):            # numpy scalar or array
        return v.tolist()
    return str(v)


def spec_public(spec):
    """JSON-safe copy of a witness spec with the callables dropped."""
    return _json_safe(spec)


def catalog():
    """{name: spec_public(spec)} for every entry of WITNESSES."""
    return {name: spec_public(spec) for name, spec in WITNESSES.items()}
