import itertools
import json
import math

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

import qk_mitigation as mt
import qk_runtime as rt

PI = math.pi
TSIRELSON = 2 * math.sqrt(2)


# ---------------------------------------------------------------- reference models (test-side)

def _per_bit(p, n):
    return [float(p)] * n if np.ndim(p) == 0 else [float(x) for x in p]


def forward(probs, p01, p10):
    """Read distribution under independent per-bit flips, written key by key:
    P(read r) = sum_t P(t) prod_i P(read bit i | true bit i), bit i = character -1-i."""
    n = len(next(iter(probs)))
    a, b = _per_bit(p01, n), _per_bit(p10, n)
    out = {"".join(r): 0.0 for r in itertools.product("01", repeat=n)}
    for t, pt in probs.items():
        for r in out:
            w = pt
            for i in range(n):
                tb, rb = t[-1 - i], r[-1 - i]
                if tb == "0":
                    w *= a[i] if rb == "1" else 1 - a[i]
                else:
                    w *= b[i] if rb == "0" else 1 - b[i]
            out[r] += w
    return out


def parity(probs, bits=None):
    """<prod of (+1 for bit 0, -1 for bit 1)> over the chosen local bits (default: all)."""
    total = sum(probs.values())
    acc = 0.0
    for k, p in probs.items():
        sel = range(len(k)) if bits is None else bits
        acc += p * (-1) ** sum(k[-1 - i] == "1" for i in sel)
    return acc / total


def random_dist(n, seed):
    rng = np.random.default_rng(seed)
    w = rng.dirichlet(np.ones(2 ** n))
    return {format(i, "0%db" % n): float(x) for i, x in enumerate(w)}


def close(d1, d2, tol):
    keys = set(d1) | set(d2)
    return max(abs(d1.get(k, 0.0) - d2.get(k, 0.0)) for k in keys) <= tol


# ---------------------------------------------------------------- readout_inverse

def test_readout_inverse_exact_per_bit_lists():
    true = random_dist(3, seed=11)
    p01, p10 = [0.02, 0.07, 0.11], [0.05, 0.01, 0.09]
    got = mt.readout_inverse(forward(true, p01, p10), p01, p10)
    assert close(got, true, 1e-12)
    assert all(len(k) == 3 for k in got)


def test_readout_inverse_exact_scalars():
    true = random_dist(3, seed=12)
    got = mt.readout_inverse(forward(true, 0.03, 0.05), 0.03, 0.05)
    assert close(got, true, 1e-12)


def test_readout_inverse_bit_position_convention():
    # only local bit 0 (the rightmost character) misreads
    true = {"000": 0.5, "101": 0.5}
    read = forward(true, [0.2, 0.0, 0.0], [0.1, 0.0, 0.0])
    assert read["001"] == pytest.approx(0.1) and read["100"] == pytest.approx(0.05)
    assert close(mt.readout_inverse(read, [0.2, 0.0, 0.0], [0.1, 0.0, 0.0]), true, 1e-12)
    wrong = mt.readout_inverse(read, [0.0, 0.0, 0.2], [0.0, 0.0, 0.1])
    assert not close(wrong, true, 1e-3)


def test_readout_inverse_counts_width_and_dropped_zeros():
    got = mt.readout_inverse({"0011": 30, "0000": 70}, 0.0, 0.0)
    assert got == {"0000": 0.7, "0011": 0.3}
    assert all(type(v) is float for v in got.values())
    json.dumps(got)
    assert mt.readout_inverse({"1": 1, "10": 3}, 0.0, 0.0) == {"01": 0.25, "10": 0.75}


def test_readout_inverse_clips_negatives_and_renormalizes():
    # every shot read 0, but a 10% 0->1 rate predicts some 1s: exact inverse is negative there
    assert mt.readout_inverse({"0": 1.0}, 0.1, 0.05) == {"0": 1.0}
    got = mt.readout_inverse({"00": 0.9, "01": 0.1}, 0.1, 0.0)
    assert sum(got.values()) == pytest.approx(1.0) and min(got.values()) > 0
    # exact inverse: 00 -> 1/0.9, 10 -> -0.1/0.9 (clipped), 01 and 11 -> 0; renormalized
    assert close(got, {"00": 1.0}, 1e-12)
    # a partial clip keeps the surviving entries' ratios
    raw = {"00": 0.50, "01": 0.20, "10": 0.30}
    got = mt.readout_inverse(raw, 0.1, 0.0)
    t = forward_inverse_unclipped(raw, 0.1, 0.0)
    assert t["11"] < 0
    pos = {k: v for k, v in t.items() if v > 0}
    assert close(got, {k: v / sum(pos.values()) for k, v in pos.items()}, 1e-12)


def forward_inverse_unclipped(probs, p01, p10):
    """Exact inverse via an explicit 2^n x 2^n Kronecker matrix (test-side reference only)."""
    n = len(next(iter(probs)))
    a, b = _per_bit(p01, n), _per_bit(p10, n)
    M = np.ones((1, 1))
    for i in reversed(range(n)):            # leftmost key character = highest local bit
        M = np.kron(M, np.array([[1 - a[i], b[i]], [a[i], 1 - b[i]]]))
    v = np.zeros(2 ** n)
    for k, p in probs.items():
        v[int(k, 2)] = p
    v /= v.sum()
    t = np.linalg.solve(M, v)
    return {format(i, "0%db" % n): float(x) for i, x in enumerate(t)}


def test_readout_inverse_matches_dense_kron_inverse_on_noisy_input():
    # a noisy (not exactly forward-generated) 4-bit histogram, rates per bit, no clipping
    rng = np.random.default_rng(5)
    p01, p10 = [0.01, 0.04, 0.02, 0.06], [0.03, 0.02, 0.08, 0.05]
    true = random_dist(4, seed=6)
    read = forward(true, p01, p10)
    counts = dict(zip(read, rng.multinomial(200000, list(read.values())).tolist()))
    ref = forward_inverse_unclipped(counts, p01, p10)
    assert min(ref.values()) > 0
    assert close(mt.readout_inverse(counts, p01, p10), ref, 1e-12)


@pytest.mark.parametrize("probs,p01,p10", [
    ({"01": 1}, 0.5, 0.5),                 # 1 - a - b == 0
    ({"01": 1}, [0.1, 0.6], [0.1, 0.5]),   # bit 1 not invertible
    ({"01": 1}, [0.1, 0.1, 0.1], 0.1),     # list length != width
    ({"01": 1}, 1.2, 0.0),                 # rate out of range
    ({"0a": 1}, 0.1, 0.1),                 # not a bitstring
    ({}, 0.1, 0.1),
    ({"01": -1, "00": 2}, 0.1, 0.1),
    ({"01": 0}, 0.1, 0.1),
])
def test_readout_inverse_rejects(probs, p01, p10):
    with pytest.raises(ValueError):
        mt.readout_inverse(probs, p01, p10)


# ---------------------------------------------------------------- P1 acceptance: CHSH under readout flips

CHSH = (("a0b0", 0.0, PI / 4, +1), ("a0b1", 0.0, -PI / 4, +1),
        ("a1b0", PI / 2, PI / 4, +1), ("a1b1", PI / 2, -PI / 4, -1))


def chsh_exact(ta, tb):
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.ry(-ta, 0)
    qc.ry(-tb, 1)
    return {k: float(v) for k, v in Statevector(qc).probabilities_dict().items()}


def test_p1_readout_mitigation_restores_chsh():
    p01, p10, shots = 0.03, 0.05, 20000
    d = 1 - p01 - p10
    rng = np.random.default_rng(20261009)
    keys = ["00", "01", "10", "11"]
    z = np.array([parity({k: 1.0}) for k in keys])
    # E_mit = sum_k f_k g_k is linear in the raw frequencies f (no clipping here):
    # per bit, (M^-1)^T applied to (+1, -1) is ((+1, -1) + (a - b)) / (1 - a - b).
    g = np.array([np.prod([((1 if k[-1 - i] == "0" else -1) + p01 - p10) / d for i in range(2)])
                  for k in keys])
    s_raw = s_mit = var_raw = var_mit = s_pred = 0.0
    for _, ta, tb, sign in CHSH:
        exact = chsh_exact(ta, tb)
        assert parity(exact) == pytest.approx(sign * math.sqrt(0.5), abs=1e-12)
        read = forward(exact, p01, p10)
        f = rng.multinomial(shots, [read[k] for k in keys]) / shots
        raw = dict(zip(keys, f.tolist()))
        mit = mt.readout_inverse(raw, p01, p10)
        assert set(mit) == set(keys) and min(mit.values()) > 0.05   # linear regime, nothing clipped
        e_raw, e_mit = parity(raw), parity(mit)
        assert e_mit == pytest.approx(float(f @ g), abs=1e-12)
        s_raw += sign * e_raw
        s_mit += sign * e_mit
        s_pred += sign * parity(read)
        var_raw += (1 - e_raw ** 2) / shots
        var_mit += (float(f @ g ** 2) - float(f @ g) ** 2) / shots
    sig_raw, sig_mit = math.sqrt(var_raw), math.sqrt(var_mit)
    # mitigated noise is the raw noise inflated by about 1/(1 - a - b)^2
    assert sig_mit == pytest.approx(sig_raw / d ** 2, rel=0.05)
    assert abs(s_mit - TSIRELSON) < 2 * sig_mit
    assert abs(s_raw - s_pred) < 3 * sig_raw              # raw S is where the flip model puts it
    assert TSIRELSON - s_raw > 10 * sig_raw               # ... measurably below 2 sqrt 2
    assert s_pred == pytest.approx(d ** 2 * TSIRELSON + 2 * (p10 - p01) ** 2, abs=1e-12)


# ---------------------------------------------------------------- readout_inverse_parity

@pytest.mark.parametrize("n,p", [(1, 0.08), (2, 0.04), (3, 0.04), (3, [0.01, 0.03, 0.06])])
def test_parity_closed_form_matches_full_inversion(n, p):
    true = random_dist(n, seed=30 + n)
    read = forward(true, p, p)
    e_read = parity(read)
    got = mt.readout_inverse_parity(e_read, p, p, n)
    assert type(got) is float
    assert got == pytest.approx(parity(true), abs=1e-12)
    assert got == pytest.approx(parity(mt.readout_inverse(read, p, p)), abs=1e-12)
    if np.ndim(p) == 0:
        assert got == pytest.approx(e_read / (1 - 2 * p) ** n, abs=1e-15)


def test_parity_closed_form_is_not_clipped():
    assert mt.readout_inverse_parity(0.95, 0.05, 0.05, 1) == pytest.approx(0.95 / 0.9)


def test_parity_closed_form_json_shaped_inputs():
    got = mt.readout_inverse_parity(np.float64(0.5), np.float64(0.05), 0.05, 2.0)
    assert type(got) is float and got == pytest.approx(0.5 / 0.81)
    assert mt.readout_inverse_parity(0.5, [0.05, 0.05], [0.05, 0.05], np.int64(2)) == got


@pytest.mark.parametrize("p01,p10,n", [
    (0.03, 0.05, 2),               # asymmetric: no closed form in E alone
    ([0.02, 0.02], [0.02, 0.03], 2),
    (0.5, 0.5, 2),                 # not invertible
    ([0.02, 0.02], [0.02, 0.02], 3),
    (0.02, 0.02, 0),
    (0.02, 0.02, 2.5),
    (0.02, 0.02, True),
    (0.02, 0.02, "2"),
    (0.02, 0.02, float("nan")),
])
def test_parity_closed_form_rejects(p01, p10, n):
    with pytest.raises(ValueError):
        mt.readout_inverse_parity(0.5, p01, p10, n)


# ---------------------------------------------------------------- zne

def test_zne_linear_exact_and_wls_se():
    s = 0.01
    vals = {c: (0.9 - 0.1 * c, s) for c in (1, 3, 5)}
    v, se = mt.zne(vals)
    assert v == pytest.approx(0.9, abs=1e-12)
    # equal weights: cov = s^2 (X^T X)^-1, X^T X = [[3, 9], [9, 35]] -> [.]_00 = 35/24
    assert se == pytest.approx(s * math.sqrt(35 / 24), rel=1e-12)
    assert type(v) is float and type(se) is float


def test_zne_linear_weighted_matches_textbook_covariance():
    c = np.array([1.0, 2.0, 3.0, 5.0])
    y = np.array([0.81, 0.69, 0.62, 0.41])
    sd = np.array([0.01, 0.02, 0.015, 0.03])
    X = np.column_stack([np.ones(4), c])
    W = np.diag(1 / sd ** 2)
    cov = np.linalg.inv(X.T @ W @ X)
    beta = cov @ X.T @ W @ y
    v, se = mt.zne({float(ci): (float(yi), float(si)) for ci, yi, si in zip(c, y, sd)})
    assert v == pytest.approx(beta[0], rel=1e-12)
    assert se == pytest.approx(math.sqrt(cov[0, 0]), rel=1e-12)


def test_zne_linear_zero_se_falls_back_to_unweighted():
    vals = {1: (0.80, 0.0), 2: (0.71, 0.02), 3: (0.58, 0.02)}
    v, se = mt.zne(vals)
    X = np.column_stack([np.ones(3), [1.0, 2.0, 3.0]])
    ols = np.linalg.lstsq(X, np.array([0.80, 0.71, 0.58]), rcond=None)[0]
    assert v == pytest.approx(ols[0], rel=1e-12) and se > 0
    assert mt.zne({1: (0.8, 0.0), 3: (0.6, 0.0)}) == pytest.approx((0.9, 0.0))


def test_zne_richardson_exact_for_quadratic():
    vals = {c: (1.0 - 0.2 * c + 0.03 * c * c, 0.01) for c in (1, 3, 5)}
    v, se = mt.zne(vals, method="richardson")
    assert v == pytest.approx(1.0, abs=1e-12)
    # Lagrange weights at 0 for nodes 1, 3, 5: 15/8, -5/4, 3/8
    assert se == pytest.approx(0.01 * math.sqrt((15 / 8) ** 2 + (5 / 4) ** 2 + (3 / 8) ** 2))
    assert mt.zne(vals, method="linear")[0] != pytest.approx(1.0, abs=1e-3)


def test_zne_two_points_linear_equals_richardson():
    vals = {1: (0.7, 0.01), 3: (0.5, 0.03)}
    assert mt.zne(vals, "linear") == pytest.approx(mt.zne(vals, "richardson"), rel=1e-12)


def test_zne_se_sanity():
    two = {1: (0.8, 0.01), 3: (0.6, 0.01)}
    three = {**two, 5: (0.4, 0.01)}
    assert mt.zne(three)[1] < mt.zne(two)[1]                    # more points
    tight = {c: (y, se / 2) for c, (y, se) in three.items()}
    assert mt.zne(tight)[1] == pytest.approx(mt.zne(three)[1] / 2)   # smaller se
    assert mt.zne(three)[1] < mt.zne(three, "richardson")[1]    # richardson amplifies noise


def test_zne_accepts_json_shaped_input():
    v, se = mt.zne(json.loads('{"1": [0.8, 0.01], "3": [0.6, 0.01]}'))
    assert v == pytest.approx(0.9) and se > 0
    json.dumps([v, se])


def test_zne_exp_recovers_exponential_decay():
    for y0 in (0.7, -0.7):
        vals = {c: (y0 * 0.9 ** c, 0.01) for c in (1, 3, 5)}
        v, se = mt.zne(vals, method="exp")
        assert v == pytest.approx(y0, abs=1e-12) and se > 0
    with pytest.raises(ValueError):
        mt.zne({1: (0.5, 0.01), 3: (-0.1, 0.01)}, method="exp")


def test_zne_exp_matches_weighted_log_fit():
    # noisy points: intercept of a WLS line through (c, log|y|) with sigma_log = se/|y|
    c = np.array([1.0, 2.0, 3.0, 5.0])
    y = -np.array([0.62, 0.55, 0.47, 0.33])
    sd = np.array([0.01, 0.02, 0.01, 0.03])
    slope, icpt = np.polyfit(c, np.log(np.abs(y)), 1, w=np.abs(y) / sd)
    v, _ = mt.zne({float(ci): (float(yi), float(si)) for ci, yi, si in zip(c, y, sd)}, "exp")
    assert v == pytest.approx(-math.exp(icpt), rel=1e-10)


def _delta_se(values, method, h=1e-7):
    """sqrt(sum (d value / d y_i)^2 se_i^2) by central differences: the first-order
    propagation of independent point errors, computed without the module's L weights."""
    var = 0.0
    for c, (y, se) in values.items():
        up = {**values, c: (y + h, se)}
        dn = {**values, c: (y - h, se)}
        var += ((mt.zne(up, method)[0] - mt.zne(dn, method)[0]) / (2 * h)) ** 2 * se ** 2
    return math.sqrt(var)


@pytest.mark.parametrize("values,method", [
    ({1: (0.81, 0.01), 2: (0.69, 0.02), 3: (0.62, 0.015), 5: (0.41, 0.03)}, "linear"),
    ({1: (0.80, 0.0), 2: (0.71, 0.02), 3: (0.58, 0.03)}, "linear"),      # OLS fallback
    ({1: (0.81, 0.01), 2: (0.69, 0.02), 3: (0.62, 0.015)}, "richardson"),
    # exp weights 1/(se/|y|)^2 move with y; on exact decay data (zero residuals) that
    # movement drops out at first order, so fixed-weight propagation must match
    ({1: (0.7 * 0.9, 0.01), 2: (0.7 * 0.81, 0.02), 3: (0.7 * 0.729, 0.01),
      5: (0.7 * 0.9 ** 5, 0.03)}, "exp"),
])
def test_zne_se_is_first_order_error_propagation(values, method):
    _, se = mt.zne(values, method)
    assert se == pytest.approx(_delta_se(values, method), rel=1e-5)


@pytest.mark.parametrize("values,method", [
    ({1: (0.8, 0.01)}, "linear"),                   # fewer than 2 points
    ({}, "richardson"),
    ({1: (0.8, 0.01), 3: (0.6, 0.01)}, "cubic"),    # unknown method
    ({1: (0.8, -0.01), 3: (0.6, 0.01)}, "linear"),  # negative se
    ({1: (0.8, 0.01), "1.0": (0.6, 0.01)}, "linear"),   # duplicate scale after float()
    ({1: 0.8, 3: (0.6, 0.01)}, "linear"),           # not a pair
    ({1: (float("nan"), 0.01), 3: (0.6, 0.01)}, "linear"),
    ([(1, 0.8, 0.01), (3, 0.6, 0.01)], "linear"),   # not a dict
])
def test_zne_rejects(values, method):
    with pytest.raises(ValueError):
        mt.zne(values, method=method)


# ---------------------------------------------------------------- re-export / constraints

def test_ionq_run_kwargs_reexport():
    assert mt.ionq_run_kwargs is rt.ionq_run_kwargs
    assert mt.ionq_run_kwargs(True) == {}


def test_module_stays_pyodide_safe():
    src = open(mt.__file__, encoding="utf-8").read()
    assert "qiskit_aer" not in src and "import scipy" not in src
