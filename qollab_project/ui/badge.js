// Backend badge: name, simulator or hardware, ideal or noisy, local or remote, the
// job policy and the packing mode. Text only, so no signal depends on colour.
// `info` is the parsed profile_json() reply: {profile, mode, one_job, versions, ...}.

export function renderBadge(lib, info, listEl, policyEl, fallbackName) {
  const { h, replace } = lib;
  const failed = !info || info.error || info.status === "failed";
  if (failed) {
    replace(listEl,
      h("li", { class: "fwo-chip fwo-chip--strong" }, fallbackName || "unknown backend"),
      h("li", { class: "fwo-chip" }, "profile unavailable"),
      h("li", { class: "fwo-chip" }, "treated as one job per run"));
    replace(policyEl, "Could not read the backend profile" +
      (info && info.error ? " (" + info.error + ")" : "") +
      ", so Run allows one job per page load to be safe.");
    return;
  }
  const p = info.profile || {};
  const simulator = p.family !== "ionq_qpu";
  const noisy = p.noisy
    ? (p.noise_model ? "noisy (" + p.noise_model + ")" : "noisy (provider noise model)")
    : "ideal (no noise)";
  const oneJob = !!info.one_job || !!p.one_job;
  replace(listEl,
    h("li", { class: "fwo-chip fwo-chip--strong" }, p.name || fallbackName || "backend"),
    h("li", { class: "fwo-chip" }, simulator ? "simulator" : "hardware"),
    h("li", { class: "fwo-chip" }, noisy),
    h("li", { class: "fwo-chip" }, p.remote ? "remote" : "local (in your browser)"),
    h("li", { class: "fwo-chip" }, oneJob ? "one job per run" : "no job limit"),
    h("li", { class: "fwo-chip" }, "up to " + (p.max_qubits || "?") + " qubits"),
    h("li", { class: "fwo-chip" }, "packing: " + (info.mode || "auto")));
  replace(policyEl, oneJob
    ? "This backend accepts one job per run. Run experiment submits that one job (all four probes, plus the canary, in one submission); to submit another, run the project again."
    : "Local simulator: no job limit. Each press of Run experiment submits one job holding all four probes.");
}
