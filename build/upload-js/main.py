"""The Free Will Observatory: console entry for Qollab (Python project form).

A fictional instrument: a two-qubit "Self" (qubit 0) and "World" (qubit 1). Three
controls (an intention phase, a World coupling, a readout perspective), four probes in
ONE live job (display, intent_low, intent_high, connection) and three readings:
Capacity (how far opposite intentions move P(Self=1)), Openness (binary entropy of the
Self outcome) and Connection (mutual information with the World in a fixed reference
basis). Laplace's Demon forecasts the exact probabilities before the job runs.

Honesty: a simulator computes what quantum theory predicts for these circuits (and how
a noise model would degrade it); it does not test nature. The readings are a designed
model of agency, not a measurement of free will. When the capacity interval includes
zero the reading is "No resolved influence at this shot count."

This effort is supported by Qollab & IonQ
"""

import json
import math

import observatory
import observatory_api
import qk_runtime

ATTRIBUTION = "This effort is supported by Qollab & IonQ"
PROBE_PURPOSE = {
    "display": "the visible future distribution (user phi, gamma, beta)",
    "intent_low": "one end of the accessible range (phi = beta)",
    "intent_high": "the opposite end (phi = beta + pi)",
    "connection": "shared information in a fixed Z basis (no final RZ/H)",
}


def _count_table(name, counts, shots_seen):
    total = sum(counts.values())
    lines = ["  %-12s %s" % (name, PROBE_PURPOSE[name])]
    lines.append("    outcome(SelfWorld)   count   fraction")
    for key in ("00", "01", "10", "11"):
        n = counts.get(key, 0)
        lines.append("    %-20s %6d   %.4f" % (key, n, (n / total) if total else 0.0))
    lines.append("    total %d (requested %d)" % (total, shots_seen))
    return "\n".join(lines)


def _readings_text(m, pred):
    lo, hi = m["capacity_ci95"]
    lines = [
        "  Capacity   C = |p_high - p_low| = %.4f   conservative 95%% interval %.4f to %.4f"
        "   (ideal cos(gamma) = %.4f)" % (m["capacity"], lo, hi, pred["capacity"]),
        "             p_low = %.4f, p_high = %.4f, signed difference %.4f, Hoeffding e = %.4f"
        % (m["p_low"], m["p_high"], m["delta_signed"], m["hoeffding_e"]),
    ]
    if not m["resolved"]:
        lines.append("             %s" % observatory.NO_RESOLVED)
    lines += [
        "  Openness   O = binary entropy of P(Self=1) = %.4f bits   (ideal %.4f)"
        % (m["openness_bits"], pred["openness_bits"]),
        "  Connection I = mutual information, connection probe = %.4f bits   (ideal %.4f)"
        % (m["connection_bits"], pred["connection_bits"]),
    ]
    return "\n".join(lines)


def main(intention_deg: float = 90.0, world_coupling: float = 0.0, perspective_deg: float = 0.0, shots_per_probe: int = 1024, persona: str = "self"):
    qk_runtime.begin_run()
    persona = str(persona).strip().lower()
    if persona not in observatory.PERSONAS:
        print("Unknown persona %r; using 'self' (choices: %s)."
              % (persona, ", ".join(observatory.PERSONAS)))
        persona = "self"
    settings = {
        "intention_rad": math.radians(float(intention_deg)),
        "world_coupling": float(world_coupling),
        "perspective_rad": math.radians(float(perspective_deg)),
        "shots_per_probe": int(shots_per_probe),
        "persona": persona,
        "mode": "auto",
        "canary": True,
    }
    print("THE FREE WILL OBSERVATORY (model %s)" % observatory.MODEL_VERSION)
    print()
    prof = json.loads(observatory_api.profile_json(backend))
    if "error" in prof:
        print("Backend: unavailable (%s)" % prof["error"])
    else:
        p = prof["profile"]
        print("Backend: %s (%s, %s, %s, up to %d qubits, packing mode %s%s)" % (
            p["name"], p["family"], "noisy" if p["noisy"] else "ideal",
            "remote" if p["remote"] else "local", p["max_qubits"], prof["mode"],
            ", one job per run" if prof["one_job"] else ""))
    print("Settings: intention phi = %.4f rad (%.1f deg), World coupling w = %.3f "
          "(gamma = %.4f rad), perspective beta = %.4f rad (%.1f deg), %d shots per probe"
          % (settings["intention_rad"], float(intention_deg), settings["world_coupling"],
             settings["world_coupling"] * math.pi / 2, settings["perspective_rad"],
             float(perspective_deg), settings["shots_per_probe"]))
    print()

    forecast = json.loads(observatory_api.predict_json(json.dumps(settings)))
    if forecast.get("status") == "failed" or "error" in forecast:
        print("Invalid settings: %s" % forecast.get("error"))
        return
    ideal = forecast["ideal"]
    print("LAPLACE'S DEMON FORECAST (exact model, before the job):")
    print("  %s" % ideal["formula_p_self_1"])
    print("  P(Self=1) = %.4f; p_low = %.4f, p_high = %.4f; capacity %.4f; openness %.4f "
          "bits; connection %.4f bits" % (ideal["p_self_1"], ideal["p_low"], ideal["p_high"],
                                          ideal["capacity"], ideal["openness_bits"],
                                          ideal["connection_bits"]))
    noisy = forecast.get("noisy_ionq_like")
    if noisy:
        print("  Under an IonQ-like noise model (approximation): P(Self=1) = %.4f, capacity "
              "%.4f, connection %.4f bits" % (noisy["p_self_1"], noisy["capacity"],
                                              noisy["connection_bits"]))
    print()

    print("Submitting ONE job with four probes plus canary blocks...")
    result = json.loads(observatory_api.run_json(backend, json.dumps(settings)))
    if result.get("status") != "completed":
        src = result.get("source") or {}
        print("RUN FAILED: %s" % result.get("error"))
        print("  job id: %s; a job object came back: %s; jobs submitted this run: %s"
              % (src.get("job_id"), src.get("job_returned"), result.get("jobs_submitted")))
        print()
        print(ATTRIBUTION)
        return
    src = result["source"]
    print("Completed: %s job on %s (%s), mode %s, %s circuit(s), %.2f s, job id %s"
          % ("remote" if src["remote"] else "local", src["backend_name"],
             "noisy simulator" if src["noisy"] else "ideal simulator", src["mode"],
             src.get("n_circuits"), src.get("wall_s") or 0.0, src.get("job_id")))
    check = src["bit_order_check"]
    if check["orientation_ok"] is False:
        print("WARNING: the bit-order canary failed; the counts below are not trustworthy.")
    else:
        print("Bit-order canary: %s; readout flip rates P(1|0) = %s, P(0|1) = %s"
              % (check["orientation_ok"], check["p_flip_0to1_mean"], check["p_flip_1to0_mean"]))
    print()
    print("COUNTS (bit order %s: '10' means Self = 1, World = 0):" % result["bit_order"])
    for name in observatory.PROBES:
        print(_count_table(name, result["counts"][name], settings["shots_per_probe"]))
    print()
    print("READINGS:")
    print(_readings_text(result["metrics"], result["prediction"]))
    print()
    expl = result["explanation"]
    print("EXPLANATION:")
    print("  %s" % expl["factual"])
    print("  %s says: %s" % ({"self": "The Self", "demon": "Laplace's Demon",
                              "observer": "The Observer"}[persona], expl["poetic"][persona]))
    print("  (%s)" % expl["note"])
    print()
    base = result["baselines"]
    print("BASELINES (%s):" % base["kind"])
    for key in ("fixed_output", "fair_coin"):
        b = base[key]
        print("  %-34s capacity %.1f, openness %.1f bits: %s"
              % (b["label"], b["capacity"], b["openness_bits"], b["description"]))
    print("  %s" % base["note"])
    print()
    print("Simulator honesty: %s" % observatory.SIM_NOTE)
    print()
    print(ATTRIBUTION)
