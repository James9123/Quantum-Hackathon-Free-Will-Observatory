"""The Observatory experiments in lab/experiments.py (fwo_theory, fwo_noise, fwo_coverage):
documented keys, closed forms, noise degradation and the calibration of the conservative
95% interval. These run off-platform; nothing here touches a backend."""
import math

import pytest

import experiments as lab
import observatory as obs
import qk_noise

PI = math.pi
READINGS = {"p_self_1", "p_low", "p_high", "delta_signed", "capacity", "openness_bits", "connection_bits"}
E1024 = obs.hoeffding_e(1024, 1024)


def test_registry_and_derived():
    for name in ("fwo_theory", "fwo_noise", "fwo_coverage"):
        assert callable(lab.EXPERIMENTS[name]) and callable(lab.DERIVED[name])
        derived = lab.DERIVED[name]()
        assert derived["model_version"] == obs.MODEL_VERSION
    d = lab.DERIVED["fwo_theory"]()
    assert d["formula_p_self_1"] == obs.FORMULA and d["hoeffding_e_1024"] == pytest.approx(E1024)
    assert "cos(gamma)" in d["capacity_formula"]
    assert lab.DERIVED["fwo_noise"]()["ionq_forte1_r2q"] == qk_noise.IONQ_FORTE1_R2Q
    assert lab.DERIVED["fwo_coverage"]()["nominal_coverage"] == 0.95


def test_fwo_settings_defaults_and_overrides():
    s = lab.fwo_settings({})
    assert s["world_coupling"] == 0.0 and s["intention_rad"] == PI / 2 and s["perspective_rad"] == 0.0
    s = lab.fwo_settings({"w": 0.5, "phi": 1.0, "beta": 0.2})
    assert s["gamma_rad"] == pytest.approx(PI / 4) and s["intention_rad"] == 1.0 and s["perspective_rad"] == 0.2
    assert lab.fwo_settings({"w": "0.25"})["world_coupling"] == 0.25
    with pytest.raises(ValueError):
        lab.fwo_settings({"w": 1.5})


@pytest.mark.parametrize("w", [0.0, 0.25, 0.5, 0.9, 1.0])
def test_fwo_theory_keys_and_closed_forms(w):
    out = lab.fwo_theory({"w": w})
    assert READINGS | {"gamma_rad", "capacity_closed_form", "p_self_1_closed_form"} <= set(out)
    assert "sampled" not in out
    gamma = w * PI / 2
    assert out["gamma_rad"] == pytest.approx(gamma, abs=1e-15)
    assert out["capacity"] == pytest.approx(math.cos(gamma), abs=1e-12)          # C = cos(gamma) exactly
    assert out["capacity_closed_form"] == pytest.approx(math.cos(gamma), abs=1e-15)
    assert out["p_self_1"] == pytest.approx(out["p_self_1_closed_form"], abs=1e-12)
    assert out["p_self_1"] == pytest.approx(0.5, abs=1e-12)                    # phi = pi/2 default
    assert out["p_low"] == pytest.approx((1 - math.cos(gamma)) / 2, abs=1e-12)
    assert out["p_high"] == pytest.approx((1 + math.cos(gamma)) / 2, abs=1e-12)
    assert out["openness_bits"] == pytest.approx(1.0, abs=1e-12)
    assert 0.0 <= out["connection_bits"] <= 1.0 + 1e-12


def test_fwo_theory_table_row_and_phi_beta():
    half = lab.fwo_theory({"w": 0.5})
    assert half["p_low"] == pytest.approx(0.1464, abs=5e-5) and half["p_high"] == pytest.approx(0.8536, abs=5e-5)
    assert half["connection_bits"] == pytest.approx(obs.binary_entropy(0.25) - 0.5, abs=1e-12)
    assert lab.fwo_theory({"w": 0.0})["connection_bits"] == pytest.approx(0.0, abs=1e-12)
    assert lab.fwo_theory({"w": 1.0})["connection_bits"] == pytest.approx(1.0, abs=1e-12)
    out = lab.fwo_theory({"w": 0.3, "phi": 2.0, "beta": 0.6})
    assert out["p_self_1"] == pytest.approx(obs.ideal_p_self_1(2.0, 0.3 * PI / 2, 0.6), abs=1e-12)
    assert out["capacity"] == pytest.approx(math.cos(0.3 * PI / 2), abs=1e-12)


def test_fwo_theory_sampled_run_is_seeded_and_consistent():
    a = lab.fwo_theory({"w": 0.5}, shots=1024, seed=3)
    b = lab.fwo_theory({"w": 0.5}, shots=1024, seed=3)
    c = lab.fwo_theory({"w": 0.5}, shots=1024, seed=4)
    assert a["sampled"] == b["sampled"] and a["sampled"] != c["sampled"]
    assert set(a["sampled"]) == READINGS and a["shots"] == 1024
    lo, hi = a["capacity_ci95_sampled"]
    assert 0.0 <= lo <= a["sampled"]["capacity"] <= hi <= 1.0
    assert lo <= math.cos(PI / 4) <= hi and a["resolved_sampled"] is True
    assert hi - lo == pytest.approx(2 * E1024, abs=1e-12)
    assert abs(a["sampled"]["p_low"] - a["p_low"]) < 5 * math.sqrt(a["p_low"] * (1 - a["p_low"]) / 1024)
    z = lab.fwo_theory({"w": 1.0}, shots=1024, seed=5)
    assert z["capacity_ci95_sampled"][0] == 0.0 and z["resolved_sampled"] is False


def test_fwo_noise_keys_degradation_and_hand_checks():
    ideal = lab.fwo_noise({"w": 0.5})
    assert READINGS | {"gamma_rad", "capacity_ideal", "capacity_loss", "noise_effective"} <= set(ideal)
    assert ideal["capacity"] == pytest.approx(math.cos(PI / 4), abs=1e-12) and ideal["capacity_loss"] == pytest.approx(0.0, abs=1e-12)
    assert set(ideal["noise_effective"]) == {"p1", "p2", "r01", "r10"}
    noisy = lab.fwo_noise({"w": 0.5, "p1": 0.01, "p2": 0.05})
    assert noisy["capacity_ideal"] == pytest.approx(math.cos(PI / 4), abs=1e-15)
    assert 0.0 < noisy["capacity"] < noisy["capacity_ideal"]
    assert noisy["capacity_loss"] == pytest.approx(noisy["capacity_ideal"] - noisy["capacity"], abs=1e-15)
    assert noisy["noise_effective"]["p2"] == pytest.approx(0.05)
    # w = 0, two-qubit depolarizing only: each CX multiplies the Self coherence by (1 - p2)
    two = lab.fwo_noise({"w": 0.0, "p2": 0.1})
    assert two["capacity"] == pytest.approx(0.81, abs=1e-9)
    # symmetric readout flips r at w = 0: p_low = r, p_high = 1 - r, C = 1 - 2r
    ro = lab.fwo_noise({"w": 0.0, "r01": 0.1, "r10": 0.1})
    assert ro["capacity"] == pytest.approx(0.8, abs=1e-12) and ro["p_low"] == pytest.approx(0.1, abs=1e-12)
    assert ro["connection_bits"] == pytest.approx(0.0, abs=1e-12)
    # the scale dial: 0 restores the ideal, larger hurts more
    base = lab.fwo_noise({"w": 0.5, "p1": qk_noise.IONQ_FORTE1_R1Q, "p2": qk_noise.IONQ_FORTE1_R2Q, "scale": 1})
    off = lab.fwo_noise({"w": 0.5, "p1": qk_noise.IONQ_FORTE1_R1Q, "p2": qk_noise.IONQ_FORTE1_R2Q, "scale": 0})
    far = lab.fwo_noise({"w": 0.5, "p1": qk_noise.IONQ_FORTE1_R1Q, "p2": qk_noise.IONQ_FORTE1_R2Q, "scale": 40})
    assert off["capacity"] == pytest.approx(math.cos(PI / 4), abs=1e-12)
    assert far["capacity"] < base["capacity"] < off["capacity"]
    assert base["noise_effective"]["p2"] == pytest.approx(qk_noise.IONQ_FORTE1_R2Q)
    sampled = lab.fwo_noise({"w": 0.5, "p2": 0.05}, shots=512, seed=1)
    assert set(sampled["sampled"]) == READINGS and sampled["shots"] == 512
    assert len(sampled["capacity_ci95_sampled"]) == 2


@pytest.mark.parametrize("w", [0.0, 0.5, 1.0])
def test_fwo_coverage_is_at_least_nominal_at_200_repeats(w):
    out = lab.fwo_coverage({"w": w, "repeats": 200}, seed=0)
    assert set(out) == {"capacity_exact", "repeats", "shots", "hoeffding_e", "coverage_95",
                        "mean_width", "mean_capacity_hat", "resolved_fraction"}
    assert out["repeats"] == 200 and out["shots"] == 1024
    assert out["hoeffding_e"] == pytest.approx(E1024, abs=1e-12)
    assert out["capacity_exact"] == pytest.approx(math.cos(w * PI / 2), abs=1e-12)
    assert out["coverage_95"] >= 0.95
    assert 0.0 < out["mean_width"] <= 2 * E1024 + 1e-12
    assert abs(out["mean_capacity_hat"] - out["capacity_exact"]) < 0.05
    assert 0.0 <= out["resolved_fraction"] <= 1.0
    if w == 0.0:
        assert out["coverage_95"] == 1.0 and out["resolved_fraction"] == 1.0
        assert out["mean_capacity_hat"] == 1.0 and out["mean_width"] == pytest.approx(E1024, abs=1e-12)
    if w == 1.0:
        assert out["resolved_fraction"] == 0.0                                  # |d| never beats e


def test_fwo_coverage_params_and_validation():
    small = lab.fwo_coverage({"w": 0.5, "repeats": 20, "shots": 64}, seed=2)
    assert small["shots"] == 64 and small["repeats"] == 20
    assert small["hoeffding_e"] == pytest.approx(obs.hoeffding_e(64, 64))
    via_arg = lab.fwo_coverage({"w": 0.5, "repeats": 5}, shots=256)
    assert via_arg["shots"] == 256
    same = lab.fwo_coverage({"w": 0.5, "repeats": 30}, seed=7)
    assert same == lab.fwo_coverage({"w": 0.5, "repeats": 30}, seed=7)
    for bad in ({"w": 0.5, "repeats": 0}, {"w": 0.5, "shots": -3, "repeats": 3}):
        with pytest.raises(ValueError):
            lab.fwo_coverage(bad)
