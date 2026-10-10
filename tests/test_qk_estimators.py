import ast
import json
import math
import pathlib

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

import qk_bounds as qb
import qk_estimators as est

CHSH = qb.WITNESSES["CHSH"]


def two_bit(e, n=100):
    """Counts on 2 bits with parity expectation e (even keys '00'/'11', odd '01'/'10')."""
    even = int(round(n * (1 + e) / 2))
    odd = n - even
    return {"00": even - even // 2, "11": even // 2, "01": odd - odd // 2, "10": odd // 2}


# --- marginal / probs / parity -------------------------------------------------

def test_marginal_keeps_bits_with_first_rightmost():
    counts = {"011": 5, "100": 3}
    assert est.marginal(counts, [0]) == {"0": 3, "1": 5}
    assert est.marginal(counts, [2]) == {"0": 5, "1": 3}
    # bits[0] = 2 becomes rightmost: "011" -> bit0 '1', bit2 '0' -> "10"
    assert est.marginal(counts, [2, 0]) == {"01": 3, "10": 5}
    assert est.marginal(counts, [0, 1, 2]) == counts
    assert est.marginal({"10": 4, "00": 2, "11": 0}, [1]) == {"0": 2, "1": 4}


def test_marginal_rejects_bad_bits():
    with pytest.raises(ValueError):
        est.marginal({"01": 1}, [2])
    with pytest.raises(ValueError):
        est.marginal({"01": 1}, [0, 0])


def test_probs_matches_qiskit_convention():
    qc = QuantumCircuit(3)
    qc.ry(0.7, 0)
    qc.ry(1.9, 1)
    qc.cx(1, 2)
    qc.ry(0.4, 2)
    sv = Statevector(qc)
    counts = {k: int(round(p * 1e6)) for k, p in sv.probabilities_dict().items()}
    for bits in ([2, 0], [1], [0, 2, 1]):
        got = est.probs(counts, bits)
        want = sv.probabilities_dict(qargs=bits)
        assert set(got) == {str(k) for k in want}
        for k, p in want.items():
            assert got[str(k)] == pytest.approx(float(p), abs=1e-5)
    full = est.probs({"0": 1, "1": 3})
    assert full == {"0": 0.25, "1": 0.75}
    assert est.probs({}) == {}


def test_parity_values_and_se():
    counts = {"011": 5, "100": 3}
    assert est.parity(counts, [0])[0] == pytest.approx(-0.25)
    assert est.parity(counts, [2])[0] == pytest.approx(0.25)
    # all bits: "011" even -> +5, "100" odd -> -3
    e, se = est.parity(counts)
    assert e == pytest.approx(0.25)
    assert se == pytest.approx(math.sqrt((1 - 0.25 ** 2) / 8))
    # permuted bit list gives the same product
    assert est.parity(counts, [1, 2])[0] == est.parity(counts, [2, 1])[0]
    assert est.parity({"00": 10}) == (1.0, 0.0)
    e, se = est.parity({})
    assert math.isnan(e) and math.isnan(se)
    # a one-shot iterable of bits must apply to every key, not just the first
    assert est.parity({"01": 3, "11": 1}, iter([0]))[0] == -1.0


# --- witness_value -------------------------------------------------------------

def test_witness_value_by_hand():
    es = {"a0b0": 0.6, "a0b1": 0.7, "a1b0": 0.8, "a1b1": -0.5}
    blocks = {lab: two_bit(e, 200) for lab, e in es.items()}
    # an extra (third) local bit beyond the term's vars is ignored
    blocks["a0b0"] = {"1" + k: v for k, v in blocks["a0b0"].items()}
    out = est.witness_value(CHSH, blocks)
    want = 0.6 + 0.7 + 0.8 + 0.5
    want_se = math.sqrt(sum((1 - e * e) / 200 for e in es.values()))
    assert out["value"] == pytest.approx(want)
    assert out["se"] == pytest.approx(want_se)
    assert out["terms"]["a1b1"] == {"E": pytest.approx(-0.5), "se": pytest.approx(math.sqrt(0.75 / 200)),
                                    "n": 200, "coef": -1.0}
    json.dumps(out)


def test_witness_value_missing_label_and_game():
    blocks = {lab: two_bit(0.5) for lab in ("a0b0", "a0b1", "a1b0")}
    with pytest.raises(KeyError, match="a1b1"):
        est.witness_value(CHSH, blocks)
    with pytest.raises(NotImplementedError, match="win_rate"):
        est.witness_value(qb.WITNESSES["MAGIC_SQUARE"], {})


# --- win_rate / z_vs_bound -------------------------------------------------------

def test_win_rate_wilson_textbook():
    r = est.win_rate(8, 10)
    assert r["p"] == pytest.approx(0.8)
    assert r["se"] == pytest.approx(math.sqrt(0.016))
    assert r["wilson_lo"] == pytest.approx(0.4902, abs=1e-4)
    assert r["wilson_hi"] == pytest.approx(0.9433, abs=1e-4)
    assert (r["wins"], r["n"]) == (8, 10)
    edge = est.win_rate(0, 20)
    assert edge["wilson_lo"] == pytest.approx(0.0, abs=1e-12)
    assert edge["wilson_hi"] == pytest.approx(0.1611, abs=1e-4)
    full = est.win_rate(20, 20)
    assert full["wilson_hi"] == pytest.approx(1.0) and full["wilson_hi"] <= 1.0
    assert math.isnan(est.win_rate(0, 0)["p"])
    with pytest.raises(ValueError):
        est.win_rate(11, 10)
    json.dumps(r)


def test_z_vs_bound_both_directions():
    assert est.z_vs_bound(2.4, 0.1, 2.0) == pytest.approx(4.0)
    assert est.z_vs_bound(1.8, 0.1, 2.0) == pytest.approx(-2.0)
    assert est.z_vs_bound(0.5, 0.1, 0.8, direction="min") == pytest.approx(3.0)
    assert est.z_vs_bound(0.9, 0.05, 0.8, direction="min") == pytest.approx(-2.0)
    assert est.z_vs_bound(2.1, 0.0, 2.0) == math.inf
    assert est.z_vs_bound(1.9, 0.0, 2.0) == -math.inf
    assert est.z_vs_bound(2.0, 0.0, 2.0) == 0.0
    assert est.z_vs_bound(2.1, 0.0, 2.0, direction="min") == -math.inf
    with pytest.raises(ValueError):
        est.z_vs_bound(1, 1, 1, direction="up")


# --- shot planning -------------------------------------------------------------------

def test_sd_per_shot_and_shots_for_sigma():
    r = 1 / math.sqrt(2)
    sd = est.witness_sd_per_shot(CHSH, {"a0b0": r, "a0b1": r, "a1b0": r, "a1b1": -r})
    assert sd == pytest.approx(math.sqrt(2))
    gap = 2 * math.sqrt(2) - 2
    n = est.shots_for_sigma(gap, sd, k=5)
    assert n == math.ceil((5 * sd / gap) ** 2) == 73
    assert 5 * sd / math.sqrt(n) <= gap < 5 * sd / math.sqrt(n - 1)
    assert est.shots_for_sigma(1.0, 0.5, k=2) == 1           # exact boundary, no float drift
    assert est.shots_for_sigma(0.1, 1.0, k=3) == 900
    assert est.shots_for_sigma(0.3, 0.0) == 1
    # ceil((1/gap)^2) overshoots to 3 here in floats; the answer is 2
    assert est.shots_for_sigma(1 / math.sqrt(2), 1.0, k=1) == 2
    # N is the smallest count meeting the inequality, whichever way floats round
    for s in range(1, 61, 3):
        for g in range(1, 61, 2):
            for k in (1, 3, 5):
                sd, gp = s / 100, g / 1000
                n = est.shots_for_sigma(gp, sd, k=k)
                assert k * sd / math.sqrt(n) <= gp and (n == 1 or k * sd / math.sqrt(n - 1) > gp)
    # a gap at float resolution (value ~= bound) must return promptly, not spin
    huge = est.shots_for_sigma(4.4e-16, math.sqrt(2), k=5)
    assert huge == pytest.approx((5 * math.sqrt(2) / 4.4e-16) ** 2, rel=1e-9)
    with pytest.raises(ValueError):
        est.shots_for_sigma(0.0, 1.0)
    with pytest.raises(ValueError):
        est.shots_for_sigma(-0.1, 1.0)
    with pytest.raises(KeyError, match="a1b1"):
        est.witness_sd_per_shot(CHSH, {"a0b0": 0.0, "a0b1": 0.0, "a1b0": 0.0})


# --- bootstrap -----------------------------------------------------------------------

def test_bootstrap_matches_analytic_se():
    counts = {"00": 700, "11": 500, "01": 200, "10": 100}      # E = 0.6, N = 1500
    e, se = est.parity(counts)
    mean, sd = est.bootstrap({"t": counts}, lambda bc: est.parity(bc["t"])[0], B=300, seed=0)
    assert e == pytest.approx(0.6)
    assert mean == pytest.approx(e, abs=3 * se)
    assert sd == pytest.approx(se, rel=0.15)
    again = est.bootstrap({"t": counts}, lambda bc: est.parity(bc["t"])[0], B=300, seed=0)
    assert again == (mean, sd)
    assert isinstance(mean, float) and isinstance(sd, float)


def test_bootstrap_witness_se_and_block_independence():
    es = {"a0b0": 0.7, "a0b1": 0.7, "a1b0": 0.7, "a1b1": -0.7}
    blocks = {lab: two_bit(e, 1000) for lab, e in es.items()}
    blocks["empty"] = {}
    seen_totals = set()

    def stat(bc):
        seen_totals.update(sum(c.values()) for lab, c in bc.items() if lab != "empty")
        assert bc["empty"] == {}
        return est.witness_value(CHSH, bc)["value"]

    analytic = est.witness_value(CHSH, blocks)
    _, sd = est.bootstrap(blocks, stat, B=200, seed=3)
    assert seen_totals == {1000}
    assert sd == pytest.approx(analytic["se"], rel=0.15)
    with pytest.raises(ValueError):
        est.bootstrap(blocks, stat, B=1)


def test_returns_plain_python_numbers():
    counts = {np.str_("01"): np.int64(3), np.str_("10"): np.int64(1)}
    e, se = est.parity(counts)
    assert type(e) is float and type(se) is float
    assert all(type(v) is int for v in est.marginal(counts, [0]).values())
    json.dumps(est.probs(counts))


def test_pyodide_safe_imports():
    tree = ast.parse(pathlib.Path(est.__file__).read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"math", "numpy"}
