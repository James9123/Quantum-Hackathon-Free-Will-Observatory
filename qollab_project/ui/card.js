// Claim-card component. Renders the card dict from qk_cards.claim_card (as returned
// by run_chsh_json) plus the run's diagnostics. Generic: it reads only card fields
// and the `exp` description (term names), never CHSH constants.

const VERDICT_STYLE = {
  "exceeds classical bound": { cls: "qh-verdict--exceeds", mark: "\u25b2" },
  "consistent with classical bound": { cls: "qh-verdict--consistent", mark: "\u25a0" },
};

function boundText(card) {
  const dir = card.direction || "max";
  return dir === "max"
    ? "classical value \u2264 " + card.bound + "; the claim needs a larger value"
    : "classical value \u2265 " + card.bound + "; the claim needs a smaller value";
}

function list(lib, items) {
  const { h } = lib;
  const rows = items && items.length ? items : ["(none recorded)"];
  return h("ul", {}, rows.map((s) => h("li", {}, s)));
}

function measured(lib, card, key) {
  const { fmt, zText } = lib;
  const m = card[key];
  if (!m) return null;
  return fmt(m.value) + " \u00b1 " + fmt(m.se) + "  (z = " + zText(m.value, m.se, card.bound, card.direction) + ")";
}

function diagnostics(lib, exp, run) {
  const { h, fmt, fmtInt, fmtPct, table } = lib;
  const parts = [];
  const terms = run.terms || [];
  if (terms.length) {
    const hasMit = terms.some((t) => t.E_mitigated !== null && t.E_mitigated !== undefined);
    const headers = ["setting", "coef", "E (raw)", "se", "shots"].concat(hasMit ? ["E (mitigated)"] : []);
    parts.push(table("Per-setting correlations E from this job", headers, terms.map((t) =>
      [exp.termName(t), t.coef > 0 ? "+1" : "\u22121", fmt(t.E), fmt(t.se), fmtInt(t.n)]
        .concat(hasMit ? [fmt(t.E_mitigated)] : []))));
  }
  const c = run.canary;
  if (c) {
    parts.push(table("Canary: bit order and readout flips", ["check", "result"], [
      ["bit order", c.orientation_ok ? "OK (expected " + c.orientation_expected + ", majority " + c.orientation_majority + ")"
        : "FAILED (expected " + c.orientation_expected + ", majority " + c.orientation_majority + ")"],
      ["orientation shots matching", fmtPct(c.orientation_fraction)],
      ["mean flip 0 \u2192 1", fmtPct(c.p_flip_0to1_mean, 2)],
      ["mean flip 1 \u2192 0", fmtPct(c.p_flip_1to0_mean, 2)],
    ]));
  }
  const L = run.layout;
  const j = run.job || {};
  if (L) {
    parts.push(table("Layout and job", ["item", "value"], [
      ["packing mode", L.mode + (run.mode_requested && run.mode_requested !== L.mode ? " (requested " + run.mode_requested + ")" : "")],
      ["circuits in the job", String(L.n_circuits)],
      ["qubits per circuit", (L.qubits_per_circuit || []).join(", ")],
      ["blocks (incl. canary)", String(L.n_blocks)],
      ["jobs submitted", run.job_submitted ? "1" : "0"],
      ["job id", j.job_id || "n/a"],
      ["wall time", j.wall_s === undefined || j.wall_s === null ? "n/a" : fmt(j.wall_s, 2) + " s"],
    ]));
  }
  return h("details", { class: "qh-details" },
    h("summary", {}, "Diagnostics: per-setting correlations, canary, layout, job"), parts);
}

// Render a successful run. Returns {setText} to fill the plain-text view later.
export function renderCard(lib, exp, slot, run) {
  const { h, replace, fmt } = lib;
  const card = run.card;
  const style = VERDICT_STYLE[card.verdict] || { cls: "qh-verdict--inconclusive", mark: "\u25cf" };
  const basis = card.verdict_basis || "raw";
  const zBasis = basis === "mitigated" ? card.mitigated : card.raw;
  const canaryOk = !run.canary || run.canary.orientation_ok;
  const pre = h("pre", { tabindex: "0", role: "region", "aria-label": "Claim card as plain text" }, "Loading\u2026");
  const mitText = measured(lib, card, "mitigated");
  const article = h("article", { class: "qh-card", "aria-labelledby": "qh-card-h" },
    h("h3", { id: "qh-card-h" }, "Claim card: " + card.id),
    canaryOk ? null : h("p", { class: "qh-note qh-note--error" },
      "Warning: the bit-order canary failed, so the numbers below are not trustworthy."),
    h("p", { class: "qh-verdict " + style.cls },
      h("span", { "aria-hidden": "true" }, style.mark + " "), "VERDICT: " + card.verdict),
    h("p", { class: "qh-small" }, "Basis: " + basis + " z = " +
      lib.zText(zBasis.value, zBasis.se, card.bound, card.direction) +
      ". Rule: z \u2265 " + card.z_threshold + " exceeds the bound, z \u2264 0 is consistent with it, anything between is inconclusive. " +
      "A z-score covers shot noise only."),
    h("dl", { class: "qh-dl" },
      h("dt", {}, "Claim"), h("dd", {}, card.claim),
      h("dt", {}, "Assumptions"), h("dd", {}, list(lib, card.assumptions)),
      h("dt", {}, "Witness and bound"), h("dd", {}, card.witness + ": " + boundText(card)),
      h("dt", {}, "Quantum ideal"), h("dd", { class: "qh-num" }, fmt(card.quantum_ideal)),
      h("dt", {}, "Raw value"), h("dd", { class: "qh-num" }, measured(lib, card, "raw")),
      h("dt", {}, "Mitigated value"), h("dd", { class: "qh-num" },
        mitText ? mitText + "; " + card.mitigated.method : (run.mitigation_note || "not applied")),
      h("dt", {}, "Backend"), h("dd", {}, card.backend + " (" + (card.simulator ? "simulator" : "hardware") +
        "), " + card.shots + " shots per setting, one job")),
    h("h4", {}, "What this does NOT show"), list(lib, card.not_shown),
    h("h4", {}, "Counterarguments"), list(lib, card.counterarguments),
    diagnostics(lib, exp, run),
    h("details", { class: "qh-details" }, h("summary", {}, "Plain-text card (also printed to the console)"), pre));
  replace(slot, article);
  return {
    setText(text) { replace(pre, text || "(plain-text view unavailable)"); },
  };
}

export function renderRunError(lib, slot, run) {
  const { h, replace } = lib;
  replace(slot, h("div", { class: "qh-note qh-note--error" },
    h("p", {}, h("strong", {}, "The run failed: "), run.error),
    h("p", {}, submissionText(run))));
}

// What is known about the job, without claiming more than the evidence shows:
// a submission attempt whose call raised may or may not have reached the provider.
function submissionText(run) {
  const j = run.job || {};
  if (!run.job_submitted) return "No job reached the backend.";
  if (j.job_returned === false) {
    return "A submission was attempted, but the backend did not return a job, so it is not known " +
      "whether the provider received it.";
  }
  return "A job was submitted" + (j.job_id ? " (job id " + j.job_id + ")" : "") + " before the failure.";
}
