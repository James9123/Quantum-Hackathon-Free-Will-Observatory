import math

import numpy as np
import pytest

import bounds_lp as lp


def test_vertex_count_and_normalization():
    V = lp.deterministic_vertices()
    assert V.shape == (16, 16)
    # every vertex is a valid behaviour: each (x, y) block sums to 1
    assert np.allclose(V.reshape(16, 4, 4).sum(axis=2), 1.0)


def test_chsh_local_max_is_2():
    assert lp.max_over_polytope(lp.chsh_coefficients(), lp.deterministic_vertices()) == pytest.approx(2.0)


def test_tsirelson_point():
    p = lp.tsirelson_behaviour()
    assert float(lp.chsh_coefficients() @ p) == pytest.approx(2 * math.sqrt(2))
    v = lp.critical_visibility(p, lp.deterministic_vertices(), lp.white_noise())
    assert v == pytest.approx(1 / math.sqrt(2), abs=1e-7)


def test_pr_box_visibility_is_half():
    v = lp.critical_visibility(lp.pr_box(), lp.deterministic_vertices(), lp.white_noise())
    assert v == pytest.approx(0.5, abs=1e-7)


def test_membership():
    V = lp.deterministic_vertices()
    t, w = lp.tsirelson_behaviour(), lp.white_noise()
    assert lp.is_local(0.70 * t + 0.30 * w, V)
    assert not lp.is_local(0.72 * t + 0.28 * w, V)
    assert lp.is_local(V[3], V)
