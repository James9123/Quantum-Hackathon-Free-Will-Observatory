"""Experiment registry for lab/sweep.py (off-platform; runs on a workstation).

Each experiment maps one parameter point (a dict) to a JSON-safe result dict. They
import the same modules the browser project uses, from qollab_project/, plus the CHSH
reference experiment from reference/chsh/.

Free Will Observatory experiments (settings not given take the app defaults:
phi = pi/2, beta = 0; w must be given for fwo_theory and fwo_coverage):

    fwo_theory    params w [, phi, beta]: exact C, O, I, p_low, p_high, P(Self=1)
    fwo_noise     params p1, p2, r01, r10, scale [, w, phi, beta]: the same readings
                  under qk_noise.NoiseSpec, e.g. --grid scale=0:80:41
                  --fixed p1=<IonQ r1q> --fixed p2=<IonQ r2q> for the IonQ-like degradation
    fwo_coverage  params w [, repeats, shots]: empirical coverage of the Hoeffding 95%
                  interval for C and its mean width, from seeded sampling of the
                  exact distributions
"""

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT = os.path.join(ROOT, "qollab_project")
_REFERENCE = os.path.join(ROOT, "reference", "chsh")
for _path in (_PROJECT, _REFERENCE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import chsh  # noqa: E402
import observatory  # noqa: E402
import qk_estimators  # noqa: E402
import qk_noise  # noqa: E402

import numpy as np  # noqa: E402


def noise_from(params):
    return qk_noise.NoiseSpec(
        p1=float(params.get("p1", 0.0)),
        p2=float(params.get("p2", 0.0)),
        readout=(float(params.get("r01", 0.0)), float(params.get("r10", 0.0))),
        scale=float(params.get("scale", 1.0)),
    )


# ---------------------------------------------------------------- CHSH (reference)

def _sampled_S(noise, fold, shots, seed):
    value, var = 0.0, 0.0
    for i, t in enumerate(chsh.SPEC["terms"]):
        dist = qk_noise.exact_distribution(chsh.circuit_for(t, fold), [0, 1], noise)
        counts = qk_noise.sample(dist, shots, seed * 1000 + i)
        e, se = qk_estimators.parity(counts)
        value += t["coef"] * e
        var += (t["coef"] * se) ** 2
    return value, math.sqrt(var)


def _shots_needed(S, E, k):
    if S <= 2.0:
        return None
    sd = qk_estimators.witness_sd_per_shot(chsh.SPEC, E)
    return int(qk_estimators.shots_for_sigma(S - 2.0, sd, k=k))


def chsh_point(params, shots=0, seed=0):
    """Exact S (density matrix) at one noise point, the shots per setting needed
    to see S > 2 at 3 and 5 sigma, and optionally a sampled estimate."""
    noise = noise_from(params)
    fold = int(params.get("fold", 1))
    ex = chsh.exact(noise, fold=fold)
    out = {
        "S": ex["S"],
        "E": ex["E"],
        "shots_3sigma": _shots_needed(ex["S"], ex["E"], 3),
        "shots_5sigma": _shots_needed(ex["S"], ex["E"], 5),
    }
    if shots:
        s_hat, se = _sampled_S(noise, fold, int(shots), int(seed))
        out.update(S_sampled=s_hat, se_sampled=se)
    return out


def chsh_coverage(params, shots=1000, seed=0):
    """Error-bar calibration: over `repeats` seeded runs, how often does
    S_hat +/- se cover the exact S? (~68.3% expected for honest 1-sigma bars)."""
    noise = noise_from(params)
    repeats = int(params.get("repeats", 200))
    exact_S = chsh.exact(noise)["S"]
    inside1 = inside2 = 0
    for r in range(repeats):
        s_hat, se = _sampled_S(noise, 1, int(shots), int(seed) * 100003 + r)
        inside1 += abs(s_hat - exact_S) <= se
        inside2 += abs(s_hat - exact_S) <= 2 * se
    return {"S_exact": exact_S, "repeats": repeats, "shots": int(shots),
            "coverage_1sigma": inside1 / repeats, "coverage_2sigma": inside2 / repeats}


def chsh_aer_point(params, shots=0, seed=0):
    """Cross-check: the same CHSH circuits through qiskit-aer's density-matrix
    simulator with the equivalent depolarizing noise model (lab only)."""
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, depolarizing_error
    noise = noise_from(params)
    p1, p2, _, _ = noise.effective()
    nm = NoiseModel()
    if p1:
        nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), ["h", "ry", "rz", "x", "sx"])
    if p2:
        nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), ["cx"])
    sim = AerSimulator(method="density_matrix", noise_model=nm, fusion_enable=False)
    E = {}
    for t in chsh.SPEC["terms"]:
        qc = chsh.circuit_for(t, int(params.get("fold", 1))).copy()
        qc.save_probabilities_dict([0, 1])
        probs = sim.run(qc, shots=1).result().data(0)["probabilities"]
        E[t["label"]] = sum(p * (1 if bin(int(k, 0) if isinstance(k, str) else k).count("1") % 2 == 0 else -1)
                            for k, p in probs.items())
    S = sum(t["coef"] * E[t["label"]] for t in chsh.SPEC["terms"])
    return {"S_aer": S, "S_exact": chsh.exact(noise)["S"], "E_aer": E}


# ---------------------------------------------------------------- Free Will Observatory

_READINGS = ("p_self_1", "p_low", "p_high", "delta_signed", "capacity", "openness_bits",
             "connection_bits")


def fwo_settings(params):
    """Observatory settings from sweep params: w (required unless defaulting to 0),
    optional phi (intention_rad) and beta (perspective_rad)."""
    s = {"world_coupling": float(params.get("w", observatory.DEFAULTS["world_coupling"]))}
    if "phi" in params:
        s["intention_rad"] = float(params["phi"])
    if "beta" in params:
        s["perspective_rad"] = float(params["beta"])
    return observatory.validate_settings(s)


def _sample_counts(dists, shots, rng):
    counts = {}
    for name, dist in dists.items():
        p = np.array([float(dist[k]) for k in observatory.OUTCOMES])
        draw = rng.multinomial(int(shots), p / p.sum())
        counts[name] = {k: int(n) for k, n in zip(observatory.OUTCOMES, draw)}
    return counts


def fwo_theory(params, shots=0, seed=0):
    """Exact readings at one (w, phi, beta) point from the Statevector model, with the
    closed forms beside them; shots > 0 adds one seeded sampled run (with the
    Hoeffding interval for C)."""
    s = fwo_settings(params)
    ex = observatory.exact_metrics(s)
    out = {k: ex[k] for k in _READINGS}
    out.update({
        "gamma_rad": s["gamma_rad"],
        "capacity_closed_form": math.cos(s["gamma_rad"]),
        "p_self_1_closed_form": observatory.ideal_p_self_1(
            s["intention_rad"], s["gamma_rad"], s["perspective_rad"]),
    })
    if shots:
        dists = observatory.exact_probe_distributions(s)
        counts = _sample_counts(dists, int(shots), np.random.default_rng(int(seed)))
        m = observatory.metrics(counts)
        out.update({"sampled": {k: m[k] for k in _READINGS},
                    "capacity_ci95_sampled": m["capacity_ci95"],
                    "resolved_sampled": m["resolved"], "shots": int(shots)})
    return out


def fwo_noise(params, shots=0, seed=0):
    """The same readings under a qk_noise.NoiseSpec (p1, p2, r01, r10, scale): the
    exact density-matrix prediction, no sampling, beside the ideal capacity."""
    s = fwo_settings(params)
    noise = noise_from(params)
    ex = observatory.exact_metrics(s, noise)
    out = {k: ex[k] for k in _READINGS}
    out.update({
        "gamma_rad": s["gamma_rad"],
        "capacity_ideal": math.cos(s["gamma_rad"]),
        "capacity_loss": math.cos(s["gamma_rad"]) - ex["capacity"],
        "noise_effective": noise.to_dict()["effective"],
    })
    if shots:
        dists = observatory.exact_probe_distributions(s, noise)
        counts = _sample_counts(dists, int(shots), np.random.default_rng(int(seed)))
        m = observatory.metrics(counts)
        out.update({"sampled": {k: m[k] for k in _READINGS},
                    "capacity_ci95_sampled": m["capacity_ci95"], "shots": int(shots)})
    return out


def fwo_coverage(params, shots=0, seed=0):
    """Calibration of the conservative 95% interval for C: over `repeats` seeded
    runs of `shots` per probe sampled from the exact distributions, how often the
    interval covers the exact C, its mean width, and how often C reads "resolved".
    A Hoeffding + union-bound interval should cover well above 95%."""
    s = fwo_settings(params)
    repeats = int(params.get("repeats", 200))
    n = int(params.get("shots", 0)) or int(shots) or observatory.DEFAULTS["shots_per_probe"]
    if repeats < 1 or n < 1:
        raise ValueError("repeats and shots must be >= 1")
    dists = observatory.exact_probe_distributions(s)
    exact = observatory.exact_metrics(s)
    exact_c = exact["capacity"]
    rng = np.random.default_rng(int(seed))
    inside = resolved = 0
    width = c_sum = 0.0
    probes = {k: dists[k] for k in ("intent_low", "intent_high")}
    for _ in range(repeats):
        counts = _sample_counts(probes, n, rng)
        d = observatory._p_self_1(counts["intent_high"]) - observatory._p_self_1(counts["intent_low"])
        ci, res = observatory.capacity_interval(d, observatory.hoeffding_e(n, n))
        inside += ci[0] <= exact_c <= ci[1]
        resolved += res
        width += ci[1] - ci[0]
        c_sum += abs(d)
    return {
        "capacity_exact": exact_c,
        "repeats": repeats,
        "shots": n,
        "hoeffding_e": observatory.hoeffding_e(n, n),
        "coverage_95": inside / repeats,
        "mean_width": width / repeats,
        "mean_capacity_hat": c_sum / repeats,
        "resolved_fraction": resolved / repeats,
    }


EXPERIMENTS = {
    "chsh": chsh_point,
    "chsh_coverage": chsh_coverage,
    "chsh_aer": chsh_aer_point,
    "fwo_theory": fwo_theory,
    "fwo_noise": fwo_noise,
    "fwo_coverage": fwo_coverage,
}

DERIVED = {
    "chsh": lambda: {"lambda_star_numeric": chsh.crossing(),
                     "lambda_star_theory": chsh.LAMBDA_STAR},
    "fwo_theory": lambda: {"formula_p_self_1": observatory.FORMULA,
                           "capacity_formula": "cos(gamma), gamma = w * pi / 2",
                           "hoeffding_e_1024": observatory.hoeffding_e(1024, 1024),
                           "model_version": observatory.MODEL_VERSION},
    "fwo_noise": lambda: {"ionq_forte1_r1q": qk_noise.IONQ_FORTE1_R1Q,
                          "ionq_forte1_r2q": qk_noise.IONQ_FORTE1_R2Q,
                          "preset_note": qk_noise.IONQ_PRESET_NOTE,
                          "model_version": observatory.MODEL_VERSION},
    "fwo_coverage": lambda: {"nominal_coverage": 0.95,
                             "interval": "Hoeffding + union bound, d +/- e clipped to [-1, 1], "
                                         "mapped through |.|",
                             "model_version": observatory.MODEL_VERSION},
}
