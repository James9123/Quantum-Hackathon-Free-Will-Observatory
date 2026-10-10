"""Classical error mitigation: readout-confusion inversion and zero-noise extrapolation.

Works under CPython on a laptop and under Pyodide on Qollab. Dependencies: numpy + stdlib
(plus qk_runtime for the IonQ debias kwargs).

Readout model (tensor product, independent bits). For local bit i (bit 0 is the
RIGHTMOST key character) with a = P(read 1 | true 0) and b = P(read 0 | true 1):

    M_i = [[1 - a, b],        column = true value 0/1, row = read value 0/1
           [a,     1 - b]]

The read distribution is (M_{n-1} x ... x M_0) applied to the true one. Inverting it
needs det M_i = 1 - a - b > 0 for every bit. The inverse is applied axis by axis on a
(2,)*n tensor, so the cost is O(n 2^n), never a 2^n x 2^n matrix.

These corrections assume the calibration rates describe the readout of the bits being
corrected. They remove the readout bias the model predicts; they cannot remove shot
noise, and the corrected estimate's shot noise is larger than the raw one's.

Every public function returns JSON-safe values (str keys, plain floats).
"""

import math

import numpy as np

from qk_runtime import ionq_run_kwargs

__all__ = [
    "readout_inverse", "readout_inverse_parity", "zne", "ionq_run_kwargs", "ZNE_METHODS",
]

ZNE_METHODS = ("linear", "richardson", "exp")
MAX_DENSE_BITS = 20          # 2^20 float64 = 8 MiB of tensor; plenty for block-local keys
_SYMMETRIC_TOL = 1e-12


def _flip_rates(p, n, name):
    """Scalar or per-bit list (index 0 = rightmost bit) -> float array of length n."""
    try:
        arr = np.asarray(p, dtype=float)
    except (TypeError, ValueError):
        raise ValueError("%s: not a number or list of numbers: %r" % (name, p)) from None
    if arr.ndim == 0:
        arr = np.full(n, float(arr))
    elif arr.shape != (n,):
        raise ValueError("%s: need a scalar or %d per-bit values, got shape %r"
                         % (name, n, arr.shape))
    if not np.all(np.isfinite(arr)) or np.any(arr < 0) or np.any(arr > 1):
        raise ValueError("%s: flip rates must lie in [0, 1], got %r" % (name, arr.tolist()))
    return arr


def _contrast(a, b):
    """Per-bit 1 - a - b; raises when a bit's confusion matrix is not invertible."""
    det = 1.0 - a - b
    bad = [i for i, d in enumerate(det) if d <= 0]
    if bad:
        raise ValueError("readout not invertible: 1 - p01 - p10 <= 0 for local bit(s) %r" % bad)
    return det


def _dense(probs):
    """{bitstring: prob or count} -> (n, normalized probability vector of length 2^n).

    Shorter keys are zero-padded on the left to the widest key, as normalize_counts does.
    """
    items = list(dict(probs).items())
    if not items:
        raise ValueError("readout_inverse: empty distribution")
    for k, _ in items:
        if not isinstance(k, str) or not k or set(k) - {"0", "1"}:
            raise ValueError("readout_inverse: key %r is not a bitstring" % (k,))
    n = max(len(k) for k, _ in items)
    if n > MAX_DENSE_BITS:
        raise ValueError("readout_inverse: %d bits > MAX_DENSE_BITS %d; marginalize first"
                         % (n, MAX_DENSE_BITS))
    vec = np.zeros(2 ** n)
    for k, v in items:
        v = float(v)
        if not math.isfinite(v) or v < 0:
            raise ValueError("readout_inverse: bad weight %r for key %r" % (v, k))
        vec[int(k, 2)] += v
    total = vec.sum()
    if total <= 0:
        raise ValueError("readout_inverse: distribution has zero total weight")
    return n, vec / total


def readout_inverse(probs, p_flip_0to1, p_flip_1to0):
    """Undo tensor-product readout confusion on a distribution.

    probs: {bitstring: prob or count} (normalized here). p_flip_0to1 / p_flip_1to0:
    scalars (same for every bit) or lists indexed by LOCAL bit position (index 0 =
    rightmost character), e.g. canary_report's per-bit rates for the same qubits.
    Returns {bitstring: float} with the input's key width, outcomes with zero
    corrected probability dropped. The exact inverse can go slightly negative under
    shot noise; negatives are clipped to 0 and the result renormalized (this clipping
    is the only nonlinear step, and it is absent whenever no entry goes negative).
    """
    n, vec = _dense(probs)
    a = _flip_rates(p_flip_0to1, n, "p_flip_0to1")
    b = _flip_rates(p_flip_1to0, n, "p_flip_1to0")
    det = _contrast(a, b)
    t = vec.reshape((2,) * n)
    for i in range(n):
        axis = n - 1 - i                  # key character n-1-i holds local bit i
        inv = np.array([[1.0 - b[i], -b[i]], [-a[i], 1.0 - a[i]]]) / det[i]
        t = np.moveaxis(np.tensordot(inv, t, axes=([1], [axis])), 0, axis)
    p = np.clip(t.reshape(-1), 0.0, None)
    p = p / p.sum()                       # the inverse keeps the total at 1; clipping only raises it
    return {format(int(idx), "0%db" % n): float(p[idx]) for idx in np.flatnonzero(p)}


def readout_inverse_parity(E, p_flip_0to1, p_flip_1to0, n_bits):
    """Closed-form readout correction of an n-bit parity <Z...Z>, SYMMETRIC flips only.

    For one bit, <z_read> = (1 - a - b) <z_true> + (b - a). With a != b the offset
    terms make the read parity depend on every lower-order correlator of the true
    distribution, so no formula in E alone exists: use readout_inverse on the full
    distribution instead (this function raises ValueError). With a == b on every bit
    each read bit is the true bit XOR an independent flip, so

        E_true = E_read / prod_i (1 - 2 a_i)      ( = E_read / (1 - 2a)^n for scalars ).

    Rates may be scalars or per-bit lists of length n_bits (an integral float such as
    2.0 is accepted). The result is the unbiased linear estimate and is NOT clipped:
    under shot noise it can leave [-1, 1].
    """
    try:
        ok = (not isinstance(n_bits, (bool, str)) and float(n_bits).is_integer()
              and n_bits >= 1)
    except (TypeError, ValueError, OverflowError):
        ok = False
    if not ok:
        raise ValueError("n_bits must be a positive integer, got %r" % (n_bits,))
    n = int(n_bits)
    a = _flip_rates(p_flip_0to1, n, "p_flip_0to1")
    b = _flip_rates(p_flip_1to0, n, "p_flip_1to0")
    if np.any(np.abs(a - b) > _SYMMETRIC_TOL):
        raise ValueError("readout_inverse_parity needs p_flip_0to1 == p_flip_1to0 per bit; "
                         "for asymmetric flips use readout_inverse on the distribution")
    return float(E) / float(np.prod(_contrast(a, b)))


def _zne_points(values):
    """{scale: (estimate, se)} -> sorted float arrays (c, y, se). JSON string keys are fine."""
    if not isinstance(values, dict):
        raise ValueError("zne: values must be a dict {scale_factor: (estimate, se)}")
    pts = []
    for c, v in values.items():
        try:
            est, se = v
            row = (float(c), float(est), float(se))
        except (TypeError, ValueError):
            raise ValueError("zne: entry %r: %r is not scale -> (estimate, se)" % (c, v)) from None
        if not all(math.isfinite(x) for x in row) or row[2] < 0:
            raise ValueError("zne: entry %r: need finite values and se >= 0, got %r" % (c, v))
        pts.append(row)
    if len(pts) < 2:
        raise ValueError("zne: need at least 2 scale factors, got %d" % len(pts))
    pts.sort()
    c, y, se = (np.array(col) for col in zip(*pts))
    if len(set(c.tolist())) != len(c):
        raise ValueError("zne: duplicate scale factors %r" % c.tolist())
    return c, y, se


def _line_weights(c, se):
    """L with intercept = L @ y for a straight-line fit y = a + b c.

    Weighted least squares with weights 1/se^2; ordinary least squares if any se is 0.
    The intercept's standard error is then sqrt(sum L_i^2 se_i^2): for WLS that equals
    sqrt of [(X^T W X)^-1]_00, the textbook parameter covariance (not rescaled by the
    residuals); for OLS it is the same propagation of the given se's.
    """
    X = np.column_stack([np.ones_like(c), c])
    w = np.ones_like(c) if np.any(se == 0) else 1.0 / se ** 2
    XtW = X.T * w
    return np.linalg.solve(XtW @ X, XtW)[0]


def _lagrange_weights_at_zero(c):
    """w_i with P(0) = sum w_i y_i for the unique degree len(c)-1 polynomial through (c, y)."""
    w = np.ones_like(c)
    for i in range(len(c)):
        for j in range(len(c)):
            if j != i:
                w[i] *= c[j] / (c[j] - c[i])
    return w


def zne(values, method="linear"):
    """Zero-noise extrapolation to scale factor 0. Returns (value, se) as plain floats.

    values: {scale_factor: (estimate, se)}, e.g. {1: (0.61, 0.01), 3: (0.42, 0.01)}.
    Every method is a linear combination sum L_i y_i of the estimates (in log space for
    "exp"), and se = sqrt(sum L_i^2 se_i^2) treats the points as independent.

    - "linear":     least-squares line a + b c (weights 1/se^2; unweighted if any se
                    is 0); returns (a, se_a).
    - "richardson": the polynomial of degree len(values)-1 through every point,
                    evaluated at 0 (Lagrange weights). Exact for such polynomials but
                    amplifies noise: its se grows quickly with the number of points.
    - "exp":        y = y0 exp(-k c) with asymptote 0, the decay global depolarizing
                    noise predicts for a traceless observable: a line through
                    (c, log|y|) with se_log = se/|y|, value = y0, se by the delta
                    method. All estimates must be nonzero and share one sign.
    """
    if method not in ZNE_METHODS:
        raise ValueError("zne: method must be one of %r, got %r" % (ZNE_METHODS, method))
    c, y, se = _zne_points(values)
    if method == "richardson":
        L = _lagrange_weights_at_zero(c)
        return float(L @ y), float(np.sqrt(np.sum(L ** 2 * se ** 2)))
    if method == "linear":
        L = _line_weights(c, se)
        return float(L @ y), float(np.sqrt(np.sum(L ** 2 * se ** 2)))
    if np.any(y == 0) or len(set(np.sign(y).tolist())) != 1:
        raise ValueError("zne: method 'exp' needs nonzero estimates of one sign, got %r"
                         % y.tolist())
    sign = float(np.sign(y[0]))
    se_log = se / np.abs(y)
    L = _line_weights(c, se_log)
    value = sign * math.exp(float(L @ np.log(np.abs(y))))
    return value, abs(value) * float(np.sqrt(np.sum(L ** 2 * se_log ** 2)))
