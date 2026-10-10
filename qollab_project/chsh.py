"""CHSH: the reference experiment that exercises the toolkit end to end.

Alice (qubit 0) and Bob (qubit 1) share |Phi+>. Alice measures along an angle
theta_A in {0, pi/2}, Bob along theta_B in {pi/4, -pi/4}, both in the X-Z plane.
Quantum theory predicts E(theta_A, theta_B) = cos(theta_A - theta_B), so
S = E00 + E01 + E10 - E11 = 2*sqrt(2); every local deterministic strategy gives
S <= 2 (Clauser, Horne, Shimony & Holt 1969; Tsirelson 1980 for the 2*sqrt(2) maximum).

With one two-qubit depolarizing channel of strength lam after the CX, S = 2*sqrt(2)(1-lam),
which drops to the classical bound at lam* = 1 - 1/sqrt(2).
"""

import math

import qk_bounds
import qk_cards
import qk_estimators
import qk_mitigation
import qk_noise
import qk_packer
import qk_primitives
import qk_runtime

SPEC = qk_bounds.WITNESSES["CHSH"]
ANGLES = {"A0": 0.0, "A1": math.pi / 2, "B0": math.pi / 4, "B1": -math.pi / 4}
LAMBDA_STAR = 1 - 1 / math.sqrt(2)
SQRT8 = 2 * math.sqrt(2)

CLAIM = ("Two qubits prepared in |Phi+> and measured at the CHSH angles give "
         "S above 2, the largest value any local hidden-variable model allows.")
ASSUMPTIONS = [
    "Locality: Alice's outcome does not depend on Bob's setting, and vice versa.",
    "Realism: outcomes are fixed by pre-existing (hidden) variables.",
    "Measurement independence: settings are chosen independently of those variables.",
]
NOT_SHOWN = [
    "Both qubits sit in one device (or one simulator), with no space-like separation "
    "between the measurements, so the locality loophole is wide open.",
    "Settings are fixed by the program, not chosen by independent random sources.",
]
COUNTERARGUMENTS = [
    "Superdeterminism: if settings and hidden variables are correlated, any S is possible.",
    "Nonlocal hidden-variable theories (e.g. Bohmian mechanics) reproduce S = 2*sqrt(2).",
    "Many-worlds readings avoid nonlocality by denying that each run has a single outcome.",
]


def circuit_for(term, fold=1):
    """Unmeasured 2-qubit circuit for one CHSH term (vars like ["A0", "B1"])."""
    from qiskit import QuantumCircuit
    a, b = term["vars"]
    qc = QuantumCircuit(2, name="chsh_%s" % term["label"])
    qk_primitives.bell_pair(qc, 0, 1, "phi+")
    qk_primitives.measure_along(qc, 0, ANGLES[a])
    qk_primitives.measure_along(qc, 1, ANGLES[b])
    return qk_primitives.fold(qc, fold) if fold != 1 else qc


def builder(term):
    """For qk_bounds.quantum_ideal: (circuit, measured qubits in term-var order)."""
    return circuit_for(term), [0, 1]


def blocks(fold=1, suffix=""):
    return [qk_packer.Block(t["label"] + suffix, circuit_for(t, fold), [0, 1],
                            {"term": t["label"], "fold": fold})
            for t in SPEC["terms"]]


def _parity_from_probs(dist):
    return sum(p * (1 if k.count("1") % 2 == 0 else -1) for k, p in dist.items())


def exact(noise=None, fold=1):
    """Exact S and per-term E under a NoiseSpec (density matrix, no sampling)."""
    E = {}
    for t in SPEC["terms"]:
        dist = qk_noise.exact_distribution(circuit_for(t, fold), [0, 1], noise)
        E[t["label"]] = _parity_from_probs(dist)
    S = sum(t["coef"] * E[t["label"]] for t in SPEC["terms"])
    return {"S": S, "E": E}


def crossing(p1=0.0, readout=(0.0, 0.0), tol=1e-10):
    """Smallest 2-qubit depolarizing strength p2 at which exact S falls to 2."""
    def s_of(p2):
        return exact(qk_noise.NoiseSpec(p1=p1, p2=p2, readout=readout))["S"]
    lo, hi = 0.0, 16.0 / 15.0
    if s_of(lo) <= 2.0:
        return 0.0
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if s_of(mid) > 2.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _term_counts(unpacked, suffix=""):
    return {t["label"]: unpacked[t["label"] + suffix] for t in SPEC["terms"]}


def readout_mitigated(term_counts, p01, p10):
    """S from per-term readout inversion with the canary's mean flip rates.

    se is the raw shot-noise se scaled by 1/(1-p01-p10)^2, the parity contrast
    of a 2-bit correlator under this model (an approximation when p01 != p10)."""
    contrast = (1 - p01 - p10) ** 2
    value, var = 0.0, 0.0
    terms = {}
    for t in SPEC["terms"]:
        counts = term_counts[t["label"]]
        e_raw, se_raw = qk_estimators.parity(counts)
        e = _parity_from_probs(qk_mitigation.readout_inverse(counts, p01, p10))
        se = se_raw / contrast
        terms[t["label"]] = {"E": e, "se": se}
        value += t["coef"] * e
        var += (t["coef"] * se) ** 2
    return {"value": value, "se": math.sqrt(var), "terms": terms,
            "method": "readout inversion (tensor model, canary flip rates)"}


def analyze(unpacked, canary=None, mitigate=True):
    raw = qk_estimators.witness_value(SPEC, _term_counts(unpacked))
    out = {"raw": raw, "mitigated": None, "canary": canary}
    if mitigate and canary:
        p01, p10 = canary["p_flip_0to1_mean"], canary["p_flip_1to0_mean"]
        if (p01 > 0 or p10 > 0) and 1 - p01 - p10 > 0.2:
            out["mitigated"] = readout_mitigated(_term_counts(unpacked), p01, p10)
    return out


def card(analysis, *, backend_name, shots, simulator=True, noise=None, provenance=None):
    raw = analysis["raw"]
    mit = analysis.get("mitigated")
    return qk_cards.claim_card(
        id="chsh",
        claim=CLAIM,
        assumptions=list(ASSUMPTIONS),
        witness="CHSH",
        bound=SPEC["classical"],
        direction=SPEC["direction"],
        quantum_ideal=SPEC["quantum"],
        raw={"value": raw["value"], "se": raw["se"]},
        mitigated=None if mit is None else {"value": mit["value"], "se": mit["se"],
                                            "method": mit["method"]},
        backend=backend_name,
        shots=int(shots),
        noise=noise,
        provenance=provenance or {},
        not_shown=list(NOT_SHOWN),
        counterarguments=list(COUNTERARGUMENTS),
        simulator=simulator,
    )


def run(backend, shots=1000, mode="auto", mitigate=True, profile=None, run_kwargs=None):
    """ONE job: canary + the 4 CHSH settings. Returns (card, details)."""
    profile = profile or qk_runtime.backend_profile(backend)
    mode = qk_runtime.preferred_mode(profile, mode)
    packed = qk_packer.pack(blocks(), max_qubits=profile["max_qubits"], mode=mode, canary=True)
    circs = qk_runtime.prepare(packed.circuits, backend, profile)
    counts = qk_runtime.run_once(backend, circs, shots, profile, **(run_kwargs or {}))
    unpacked = qk_packer.unpack(packed, counts)
    canary = qk_packer.canary_report(unpacked)
    analysis = analyze(unpacked, canary, mitigate)
    summ = packed.summary()
    prov = {"layout": "%s: %d circuit(s), qubits %s" % (summ["mode"], summ["n_circuits"],
                                                         summ["qubits_per_circuit"]),
            "orientation_ok": canary["orientation_ok"],
            "p_flip_0to1_mean": canary["p_flip_0to1_mean"],
            "p_flip_1to0_mean": canary["p_flip_1to0_mean"],
            "job": {k: qk_runtime.LAST_RUN.get(k) for k in ("n_circuits", "wall_s", "job_id")}}
    c = card(analysis, backend_name=profile["name"], shots=shots,
             simulator=profile["family"] != "ionq_qpu", provenance=prov)
    return c, {"analysis": analysis, "unpacked": unpacked, "profile": profile, "layout": summ}


def zne_exact(noise, folds=(1, 3, 5), method="linear"):
    """Exact S at each fold factor under `noise`, and the zero-noise extrapolation."""
    pts = {f: exact(noise, fold=f)["S"] for f in folds}
    est, _ = qk_mitigation.zne({f: (v, 1e-6) for f, v in pts.items()}, method=method)
    return {"S_by_fold": pts, "S_zne": est}


def run_zne(backend, shots=1000, folds=(1, 3, 5), mode="auto", method="linear", profile=None,
            run_kwargs=None):
    """ONE job with every fold factor packed in. Only meaningful on simulators that
    execute the folded gates as written (local ones); IonQ's compiler likely undoes folding.
    mode "auto": first-fit tiles on one-job backends, one circuit per block elsewhere."""
    profile = profile or qk_runtime.backend_profile(backend)
    if mode == "auto":
        mode = "tiles" if profile.get("one_job") else "list"
    blks = []
    for f in folds:
        blks += blocks(fold=f, suffix="_f%d" % f)
    packed = qk_packer.pack(blks, max_qubits=profile["max_qubits"], mode=mode, canary=True)
    circs = qk_runtime.prepare(packed.circuits, backend, profile, optimization_level=0)
    counts = qk_runtime.run_once(backend, circs, shots, profile, **(run_kwargs or {}))
    unpacked = qk_packer.unpack(packed, counts)
    by_fold = {}
    for f in folds:
        w = qk_estimators.witness_value(SPEC, _term_counts(unpacked, "_f%d" % f))
        by_fold[f] = (w["value"], w["se"])
    value, se = qk_mitigation.zne(by_fold, method=method)
    analysis = {"raw": {"value": by_fold[folds[0]][0], "se": by_fold[folds[0]][1]},
                "mitigated": {"value": value, "se": se,
                              "method": "ZNE (%s, folds %s)" % (method, list(folds))},
                "by_fold": by_fold}
    c = card(analysis, backend_name=profile["name"], shots=shots,
             simulator=profile["family"] != "ionq_qpu",
             provenance={"layout": "%s: %d circuit(s)" % (packed.mode, len(packed.circuits))})
    return c, {"analysis": analysis, "unpacked": unpacked}
