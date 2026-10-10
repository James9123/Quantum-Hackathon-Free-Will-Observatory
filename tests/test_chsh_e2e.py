"""P1 acceptance: the CHSH reference experiment end to end."""
import json
import math

import pytest
from qiskit.providers.basic_provider import BasicSimulator

import chsh
import qk_bounds
import qk_cards
import qk_mitigation
import qk_noise
import qk_runtime

SQRT8 = 2 * math.sqrt(2)


def test_bounds_classical_and_quantum_ideal():
    W = qk_bounds.WITNESSES
    assert qk_bounds.classical_max_enumerate(W["CHSH"]) == pytest.approx(2.0)
    assert qk_bounds.classical_max_enumerate(W["MAGIC_SQUARE"]) == pytest.approx(8 / 9)
    assert qk_bounds.classical_max_enumerate(W["LG_K3"]) == pytest.approx(1.0)
    assert qk_bounds.quantum_ideal(W["CHSH"], chsh.builder) == pytest.approx(SQRT8, abs=1e-9)


def test_noise_dial_lambda_star():
    assert chsh.exact()["S"] == pytest.approx(SQRT8, abs=1e-12)
    for lam in (0.0, 0.1, 0.25, 0.5):
        S = chsh.exact(qk_noise.NoiseSpec(p2=lam))["S"]
        assert S == pytest.approx(SQRT8 * (1 - lam), abs=1e-12)
    assert chsh.crossing() == pytest.approx(1 - 1 / math.sqrt(2), abs=1e-8)
    assert chsh.LAMBDA_STAR == pytest.approx(0.2928932, abs=1e-7)


def test_zne_improves_S_under_folded_depolarizing_noise():
    noise = qk_noise.NoiseSpec(p1=0.01, p2=0.05)
    out = chsh.zne_exact(noise, folds=(1, 3, 5), method="linear")
    s1 = out["S_by_fold"][1]
    assert out["S_by_fold"][5] < out["S_by_fold"][3] < s1 < SQRT8
    assert abs(out["S_zne"] - SQRT8) < abs(s1 - SQRT8)
    rich = chsh.zne_exact(noise, folds=(1, 3, 5), method="richardson")
    assert abs(rich["S_zne"] - SQRT8) < abs(out["S_zne"] - SQRT8)


class SyntheticReadoutBackend:
    """BasicSimulator whose counts get independent per-bit readout flips (seeded),
    to exercise the canary-driven readout inversion."""

    def __init__(self, p01, p10, seed=5):
        import numpy as np
        self._inner = BasicSimulator()
        self._inner.set_options(seed_simulator=seed)
        self._rng = np.random.default_rng(seed)
        self.p01, self.p10 = p01, p10
        self.name = "basic_simulator"

    @property
    def target(self):
        return self._inner.target

    def run(self, circuits, shots=1024, **kw):
        res = self._inner.run(circuits, shots=shots, **kw).result()
        n = len(circuits) if isinstance(circuits, list) else 1
        flipped = []
        for i in range(n):
            out = {}
            for key, c in res.get_counts(i).items():
                for _ in range(c):
                    bits = []
                    for ch in key:
                        r = self._rng.random()
                        if ch == "0":
                            bits.append("1" if r < self.p01 else "0")
                        else:
                            bits.append("0" if r < self.p10 else "1")
                    k = "".join(bits)
                    out[k] = out.get(k, 0) + 1
            flipped.append(out)

        class _Res:
            def get_counts(self_, i=None):
                return flipped if i is None else flipped[i]
            results = []

        class _Job:
            def result(self_):
                return _Res()

            def job_id(self_):
                return "synthetic"

        return _Job()


def test_one_packed_run_gives_claim_card_basic_simulator():
    be = BasicSimulator()
    be.set_options(seed_simulator=17)
    qk_runtime.begin_run()
    card, det = chsh.run(be, shots=4000, mode="tile")
    assert qk_runtime.jobs_submitted() == 1
    assert det["analysis"]["canary"]["orientation_ok"]
    assert card["schema"] == "claim-card/1" and card["witness"] == "CHSH"
    assert abs(card["raw"]["value"] - SQRT8) < 3 * card["raw"]["se"]
    assert card["verdict"].startswith("exceeds")
    assert card["mitigated"] is None          # ideal simulator: no readout error to invert
    json.dumps(card, allow_nan=False)
    text = qk_cards.card_text(card)
    assert "CHSH" in text and "not a test of nature" in text
    assert all(len(line) <= 100 for line in text.splitlines())


@pytest.mark.parametrize("mode", ["tile", "list"])
def test_packed_run_with_readout_errors_mitigates_back_to_ideal(mode):
    be = SyntheticReadoutBackend(p01=0.04, p10=0.07)
    prof = dict(qk_runtime.backend_profile(BasicSimulator()), name="synthetic-readout")
    qk_runtime.begin_run()
    card, det = chsh.run(be, shots=6000, mode=mode, profile=prof)
    an = det["analysis"]
    can = an["canary"]
    assert can["orientation_ok"]
    assert can["p_flip_0to1_mean"] == pytest.approx(0.04, abs=0.01)
    assert can["p_flip_1to0_mean"] == pytest.approx(0.07, abs=0.01)
    raw, mit = card["raw"], card["mitigated"]
    expected_raw = SQRT8 * (1 - 0.04 - 0.07) ** 2   # contrast loss, small offset ignored
    assert raw["value"] < SQRT8 - 3 * raw["se"]
    assert abs(raw["value"] - expected_raw) < 0.1
    assert mit is not None and abs(mit["value"] - SQRT8) < 2 * mit["se"] + 0.02
    assert "readout" in mit["method"]


def test_packed_zne_run_on_local_simulator_one_job():
    be = BasicSimulator()
    be.set_options(seed_simulator=3)
    qk_runtime.begin_run()
    card, det = chsh.run_zne(be, shots=2000, folds=(1, 3, 5))
    assert qk_runtime.jobs_submitted() == 1
    by = det["analysis"]["by_fold"]
    for f in (1, 3, 5):                       # ideal simulator: folding changes nothing
        assert abs(by[f][0] - SQRT8) < 4 * by[f][1]
    assert "ZNE" in card["mitigated"]["method"]
