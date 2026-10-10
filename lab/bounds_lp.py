"""Linear-programming checks for classical (local / macrorealist) bounds.

Off-platform tool: runs on a workstation, not in the browser. Uses SciPy's HiGHS
(`scipy.optimize.linprog(method="highs")`), falling back to `highspy` if SciPy is absent.

Behaviours are probability tables p(a, b | x, y) flattened in a fixed order
(x, y, a, b) with a, b in range(outputs). The local polytope is the convex hull
of deterministic strategies a = f(x), b = g(y).

    python lab/bounds_lp.py            # prints the CHSH self-checks
"""

import itertools
import math

import numpy as np


def index(x, y, a, b, n_in, n_out):
    return ((x * n_in[1] + y) * n_out + a) * n_out + b


def deterministic_vertices(n_in=(2, 2), n_out=2):
    """All local deterministic behaviours as rows of a 0/1 matrix."""
    size = n_in[0] * n_in[1] * n_out * n_out
    rows = []
    for fa in itertools.product(range(n_out), repeat=n_in[0]):
        for fb in itertools.product(range(n_out), repeat=n_in[1]):
            v = np.zeros(size)
            for x in range(n_in[0]):
                for y in range(n_in[1]):
                    v[index(x, y, fa[x], fb[y], n_in, n_out)] = 1.0
            rows.append(v)
    return np.array(rows)


def behaviour(prob, n_in=(2, 2), n_out=2):
    """Flatten prob(x, y, a, b) -> float into the vector convention above."""
    size = n_in[0] * n_in[1] * n_out * n_out
    v = np.zeros(size)
    for x in range(n_in[0]):
        for y in range(n_in[1]):
            for a in range(n_out):
                for b in range(n_out):
                    v[index(x, y, a, b, n_in, n_out)] = prob(x, y, a, b)
    return v


def white_noise(n_in=(2, 2), n_out=2):
    return behaviour(lambda x, y, a, b: 1.0 / n_out ** 2, n_in, n_out)


def _linprog(c, A_eq, b_eq, bounds):
    """Minimize c.x subject to A_eq x = b_eq and bounds. Returns (status_ok, x, fun)."""
    try:
        from scipy.optimize import linprog
        res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
        return bool(res.success), res.x, res.fun
    except ImportError:
        import highspy
        h = highspy.Highs()
        h.silent()
        n = len(c)
        inf = highspy.kHighsInf
        lo = [(-inf if b[0] is None else b[0]) for b in bounds]
        hi = [(inf if b[1] is None else b[1]) for b in bounds]
        for j in range(n):
            h.addVar(lo[j], hi[j])
            h.changeColCost(j, float(c[j]))
        for i, row in enumerate(np.asarray(A_eq)):
            idx = [j for j in range(n) if row[j] != 0]
            h.addRow(float(b_eq[i]), float(b_eq[i]), len(idx), idx, [float(row[j]) for j in idx])
        h.run()
        ok = h.getModelStatus() == highspy.HighsModelStatus.kOptimal
        sol = np.array(h.getSolution().col_value)
        return ok, sol, float(np.dot(c, sol))


def critical_visibility(p, vertices, noise):
    """Largest v in [0, 1] such that v*p + (1-v)*noise lies in conv(vertices).

    v = 1 means p itself is local. For the Tsirelson CHSH point this is 1/sqrt(2).
    LP variables: weights w (one per vertex) and v. Maximize v.
    """
    V = np.asarray(vertices)
    n_v, dim = V.shape
    # sum_k w_k V_k - v (p - noise) = noise ;  sum_k w_k = 1
    A = np.zeros((dim + 1, n_v + 1))
    A[:dim, :n_v] = V.T
    A[:dim, n_v] = -(np.asarray(p) - np.asarray(noise))
    A[dim, :n_v] = 1.0
    b = np.concatenate([np.asarray(noise), [1.0]])
    c = np.zeros(n_v + 1)
    c[n_v] = -1.0
    ok, x, fun = _linprog(c, A, b, [(0, None)] * n_v + [(0, 1)])
    if not ok:
        raise RuntimeError("LP failed")
    return float(x[n_v])


def is_local(p, vertices):
    """Feasibility LP: is p a convex combination of the vertices?"""
    V = np.asarray(vertices)
    n_v, dim = V.shape
    A = np.vstack([V.T, np.ones((1, n_v))])
    b = np.concatenate([np.asarray(p), [1.0]])
    ok, _, _ = _linprog(np.zeros(n_v), A, b, [(0, None)] * n_v)
    return ok


def max_over_polytope(coeffs, vertices):
    """Max of a linear functional over conv(vertices), solved as an LP (and cross-checked
    against the vertex maximum, which must agree)."""
    V = np.asarray(vertices)
    n_v = V.shape[0]
    vals = V @ np.asarray(coeffs)
    ok, x, fun = _linprog(-vals, np.ones((1, n_v)), np.array([1.0]), [(0, None)] * n_v)
    if not ok:
        raise RuntimeError("LP failed")
    lp = -float(fun)
    if abs(lp - float(vals.max())) > 1e-9:
        raise AssertionError("LP and vertex maximum disagree: %r vs %r" % (lp, vals.max()))
    return lp


def chsh_coefficients(n_out=2):
    """CHSH as a linear functional on p(a,b|x,y): sum_xy s_xy * E_xy, E = P(a=b) - P(a!=b)."""
    n_in = (2, 2)
    sign = {(0, 0): 1, (0, 1): 1, (1, 0): 1, (1, 1): -1}
    return behaviour(lambda x, y, a, b: sign[(x, y)] * (1 if a == b else -1), n_in, n_out)


def tsirelson_behaviour():
    """|Phi+> with A along {0, pi/2}, B along {pi/4, -pi/4} (X-Z plane)."""
    ta = (0.0, math.pi / 2)
    tb = (math.pi / 4, -math.pi / 4)

    def prob(x, y, a, b):
        e = math.cos(ta[x] - tb[y])
        return (1 + (e if a == b else -e)) / 4

    return behaviour(prob)


def pr_box():
    return behaviour(lambda x, y, a, b: 0.5 if (a ^ b) == (x & y) else 0.0)


def self_check():
    V = deterministic_vertices()
    out = {
        "n_vertices": int(V.shape[0]),
        "chsh_local_max": max_over_polytope(chsh_coefficients(), V),
        "tsirelson_S": float(chsh_coefficients() @ tsirelson_behaviour()),
        "tsirelson_critical_visibility": critical_visibility(tsirelson_behaviour(), V, white_noise()),
        "pr_box_critical_visibility": critical_visibility(pr_box(), V, white_noise()),
        "noisy_tsirelson_0.70_is_local": is_local(
            0.70 * tsirelson_behaviour() + 0.30 * white_noise(), V),
    }
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(self_check(), indent=2))
