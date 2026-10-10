"""Experiment registry for lab/sweep.py (off-platform; runs on a workstation).

Each experiment maps one parameter point (a dict) to a JSON-safe result dict. They
import the same modules the browser project uses, from qollab_project/.
"""

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT = os.path.join(ROOT, "qollab_project")
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

import chsh  # noqa: E402
import qk_estimators  # noqa: E402
import qk_noise  # noqa: E402


def noise_from(params):
    return qk_noise.NoiseSpec(
        p1=float(params.get("p1", 0.0)),
        p2=float(params.get("p2", 0.0)),
        readout=(float(params.get("r01", 0.0)), float(params.get("r10", 0.0))),
        scale=float(params.get("scale", 1.0)),
    )


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


EXPERIMENTS = {
    "chsh": chsh_point,
    "chsh_coverage": chsh_coverage,
    "chsh_aer": chsh_aer_point,
}

DERIVED = {
    "chsh": lambda: {"lambda_star_numeric": chsh.crossing(),
                     "lambda_star_theory": chsh.LAMBDA_STAR},
}
