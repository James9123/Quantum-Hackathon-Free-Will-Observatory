// Backend badge: name, ideal/noisy, local/remote, job policy. Text only, so no
// signal depends on color. `profile` is the parsed profile_json() result.

export function renderBadge(lib, profile, listEl, policyEl, fallbackName) {
  const { h, replace } = lib;
  if (!profile || profile.error) {
    replace(listEl,
      h("li", { class: "qh-chip qh-chip--strong" }, fallbackName || "unknown backend"),
      h("li", { class: "qh-chip" }, "profile unavailable"),
      h("li", { class: "qh-chip" }, "treated as one job per run"));
    replace(policyEl, "Could not read the backend profile" +
      (profile && profile.error ? " (" + profile.error + ")" : "") +
      ", so the Run button allows one job per page load to be safe.");
    return;
  }
  const noisy = profile.noisy
    ? (profile.noise_model ? "noisy (" + profile.noise_model + ")" : "noisy (provider noise model)")
    : "ideal (no noise)";
  replace(listEl,
    h("li", { class: "qh-chip qh-chip--strong" }, profile.name),
    h("li", { class: "qh-chip" }, profile.simulator === false ? "hardware" : "simulator"),
    h("li", { class: "qh-chip" }, noisy),
    h("li", { class: "qh-chip" }, profile.remote ? "remote" : "local (in your browser)"),
    h("li", { class: "qh-chip" }, profile.one_job ? "one job per run" : "no job limit"),
    h("li", { class: "qh-chip" }, "up to " + profile.max_qubits + " qubits"));
  replace(policyEl, profile.job_policy || "");
}
