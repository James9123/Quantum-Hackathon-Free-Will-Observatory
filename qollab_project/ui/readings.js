// Text and table views of a run: the two futures, the three readings, the Demon's
// forecast and comparison, the baselines and the "How this works" drawer. Everything
// the canvas shows is also here as text, so the page works without the 3D view.
// No imports: main.js passes the dom helpers (lib) and the text helpers (txt).

const OUTCOMES = ["00", "01", "10", "11"];
const PROBE_ORDER = ["display", "intent_low", "intent_high", "connection"];
const PERSONA_NAME = { self: "The Self", demon: "Laplace's Demon", observer: "The Observer" };

function num(o, key) {
  const v = o ? o[key] : null;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function total(counts) {
  let n = 0;
  for (const k of OUTCOMES) n += Number((counts || {})[k]) || 0;
  return n;
}

export function personaName(key) {
  return PERSONA_NAME[key] || key;
}

// ---------------------------------------------------------------- futures

function futureCard(lib, which, p, count, n, prevP, forecastP) {
  const { h, fmtPct, fmtInt, fmt } = lib;
  const parts = [
    h("p", { class: "fwo-future-p" }, p === null ? "no run yet" : fmtPct(p)),
    h("p", { class: "fwo-small" }, "Self = " + which + (p === null ? "" : ": " + fmtInt(count) + " of " + fmtInt(n) + " display shots")),
  ];
  if (p !== null) {
    parts.push(h("div", { class: "fwo-meter", "aria-hidden": "true" },
      h("div", { class: "fwo-meter-fill", style: null })));
    parts[parts.length - 1].firstChild.style.width = (100 * p).toFixed(1) + "%";
  }
  const extra = [];
  if (prevP !== null) extra.push("previous " + fmtPct(prevP));
  if (forecastP !== null) extra.push("Demon forecast " + fmt(forecastP, 3));
  if (extra.length) parts.push(h("p", { class: "fwo-small" }, extra.join("; ")));
  return parts;
}

export function renderFutures(lib, slots, run, prev, forecast) {
  const { replace } = lib;
  const m = run ? run.metrics : null;
  const p1 = num(m, "p_self_1");
  const c = run && run.counts ? run.counts.display : null;
  const n = c ? total(c) : 0;
  const q1 = prev && prev.metrics ? num(prev.metrics, "p_self_1") : null;
  const f1 = forecast ? num(forecast, "p_self_1") : null;
  replace(slots.f0, futureCard(lib, 0, p1 === null ? null : 1 - p1, c ? (Number(c["00"]) || 0) + (Number(c["01"]) || 0) : 0, n,
    q1 === null ? null : 1 - q1, f1 === null ? null : 1 - f1));
  replace(slots.f1, futureCard(lib, 1, p1, c ? (Number(c["10"]) || 0) + (Number(c["11"]) || 0) : 0, n, q1, f1));
}

// ---------------------------------------------------------------- readings

const DEFINITIONS = {
  capacity: "C = |p_high \u2212 p_low|: how far the two opposite intentions (phi = beta and phi = beta + pi, same coupling and readout) move P(Self = 1). 0 to 1; ideal cos(gamma). The primary fictional agency measure.",
  openness: "Binary entropy of the display P(Self = 1): how uncertain the current Self outcome is. 0 to 1 bit. Uncertainty, not capacity.",
  connection: "Mutual information between Self and World in the separate connection probe, read in a fixed Z basis. 0 to 1 bit. Classical information in that basis, not an entanglement certification.",
};

function card(lib, id, title, value, unit, lines, definition, cls) {
  const { h } = lib;
  return h("article", { class: "fwo-reading " + (cls || ""), "aria-labelledby": id + "-h" },
    h("h3", { id: id + "-h", class: "fwo-reading-h" }, title),
    h("p", { class: "fwo-reading-value" }, h("span", { class: "fwo-reading-num" }, value), unit ? h("span", { class: "fwo-reading-unit" }, " " + unit) : null),
    lines.map((s) => h("p", { class: "fwo-reading-line" }, s)),
    h("p", { class: "fwo-small fwo-definition" }, definition));
}

export function renderReadings(lib, txt, slot, run) {
  const { h, replace, fmt } = lib;
  if (!run || run.status !== "completed") {
    replace(slot,
      card(lib, "fwo-r-cap", "Capacity (in this model)", "\u2013", "", ["No run yet."], DEFINITIONS.capacity),
      card(lib, "fwo-r-open", "Openness", "\u2013", "bits", ["No run yet."], DEFINITIONS.openness),
      card(lib, "fwo-r-conn", "Connection", "\u2013", "bits", ["No run yet."], DEFINITIONS.connection));
    return;
  }
  const m = run.metrics || {};
  const pred = run.prediction || {};
  const ci = Array.isArray(m.capacity_ci95) ? m.capacity_ci95 : [null, null];
  const resolved = !!m.resolved;
  replace(slot,
    card(lib, "fwo-r-cap", "Capacity (in this model)", fmt(m.capacity, 3), "",
      ["Conservative 95% interval " + fmt(ci[0], 3) + " to " + fmt(ci[1], 3) + " (Hoeffding e = " + fmt(m.hoeffding_e, 4) + ").",
        resolved ? "Resolved: the interval excludes zero, so in this model opposite intentions measurably reshaped the odds."
          : txt.NO_RESOLVED + " The interval includes zero.",
        "p_low = " + fmt(m.p_low, 3) + ", p_high = " + fmt(m.p_high, 3) + "; ideal cos(gamma) = " + fmt(pred.capacity, 3) + "."],
      DEFINITIONS.capacity, resolved ? "fwo-reading--resolved" : "fwo-reading--unresolved"),
    card(lib, "fwo-r-open", "Openness", fmt(m.openness_bits, 3), "bits",
      ["From the display probe's P(Self = 1) = " + fmt(m.p_self_1, 3) + "; ideal " + fmt(pred.openness_bits, 3) + " bits."],
      DEFINITIONS.openness),
    card(lib, "fwo-r-conn", "Connection", fmt(m.connection_bits, 3), "bits",
      ["From the connection probe only; ideal " + fmt(pred.connection_bits, 3) + " bits. Bridge: " + txt.bridgeWord(num(m, "connection_bits")) + "."],
      DEFINITIONS.connection));
}

export function renderRunError(lib, slot, run, previousJobId) {
  const { h, replace } = lib;
  const src = (run && run.source) || {};
  const stale = previousJobId !== null && previousJobId !== undefined && src.job_id === previousJobId;
  let evidence;
  if (src.job_returned && !stale) evidence = "A job was submitted" + (src.job_id ? " (job id " + src.job_id + ")" : "") + " before the failure.";
  else if (stale) evidence = "No new job is recorded (the job evidence still names the previous run's job), so this attempt failed before submission.";
  else if (src.n_circuits || src.submitted_as) evidence = "A submission was attempted, but no job object came back, so it is not known whether the provider received it.";
  else evidence = "No job reached the backend.";
  replace(slot, h("div", { class: "fwo-note fwo-note--error", role: "group", "aria-label": "Run failure" },
    h("p", {}, h("strong", {}, "The run failed: "), String((run && run.error) || "unknown error")),
    h("p", {}, evidence + " Nothing was substituted: the previous readings, if any, stay labelled as previous.")));
}

// ---------------------------------------------------------------- the Demon

export function renderDemonForecast(lib, slot, forecast, draftText) {
  const { h, replace, fmt, table } = lib;
  if (!forecast || forecast.error || forecast.status === "failed") {
    replace(slot, h("p", { class: "fwo-small" }, "Forecast unavailable" + (forecast && forecast.error ? ": " + forecast.error : ".")));
    return;
  }
  const i = forecast.ideal || {};
  const n = forecast.noisy_ionq_like;
  const rows = [
    ["P(Self = 1), display probe", fmt(i.p_self_1, 4), n ? fmt(n.p_self_1, 4) : "n/a"],
    ["p_low (phi = beta)", fmt(i.p_low, 4), n ? fmt(n.p_low, 4) : "n/a"],
    ["p_high (phi = beta + pi)", fmt(i.p_high, 4), n ? fmt(n.p_high, 4) : "n/a"],
    ["Capacity C", fmt(i.capacity, 4), n ? fmt(n.capacity, 4) : "n/a"],
    ["Openness (bits)", fmt(i.openness_bits, 4), n ? fmt(n.openness_bits, 4) : "n/a"],
    ["Connection (bits)", fmt(i.connection_bits, 4), n ? fmt(n.connection_bits, 4) : "n/a"],
  ];
  replace(slot,
    h("p", {}, "Forecast for the draft (" + draftText + "), computed exactly from the model before any job: " +
      "the Demon knows the probability law, not the controls."),
    h("p", { class: "fwo-formula" }, i.formula_p_self_1 || ""),
    table("Demon forecast: exact readings for the draft settings", ["reading", "ideal", "IonQ-like noise model"], rows),
    n && n.note ? h("p", { class: "fwo-small" }, n.note) : null);
}

export function renderDemonCompare(lib, slot, run) {
  const { h, replace, fmt, fmtInt, table } = lib;
  if (!run || run.status !== "completed") {
    replace(slot, h("p", { class: "fwo-small" }, "After a run, this compares the forecast with the sampled result."));
    return;
  }
  const m = run.metrics || {}, p = run.prediction || {};
  const n = (m.shots_seen || {}).display || 0;
  const pf = num(p, "p_self_1"), pm = num(m, "p_self_1");
  const sigma = pf === null ? null : Math.sqrt(Math.max(pf * (1 - pf), 1e-12) / Math.max(n, 1));
  const rows = [
    ["P(Self = 1)", fmt(pf, 4), fmt(pm, 4), sigma === null ? "n/a" : fmt(pm - pf, 4) + " (shot noise about " + fmt(sigma, 4) + ")"],
    ["Capacity C", fmt(p.capacity, 4), fmt(m.capacity, 4), "interval " + fmt((m.capacity_ci95 || [])[0], 3) + " to " + fmt((m.capacity_ci95 || [])[1], 3)],
    ["Openness (bits)", fmt(p.openness_bits, 4), fmt(m.openness_bits, 4), ""],
    ["Connection (bits)", fmt(p.connection_bits, 4), fmt(m.connection_bits, 4), ""],
  ];
  replace(slot,
    h("p", {}, "Forecast versus the completed run (" + fmtInt(n) + " display shots). The forecast was written before the job; the sample is the record."),
    table("Demon forecast compared with the completed run", ["reading", "forecast", "sampled", "difference / note"], rows));
}

// ---------------------------------------------------------------- baselines

export function renderBaselines(lib, slot, baselines) {
  const { h, replace, fmt } = lib;
  const b = baselines || {};
  const one = (key, fallbackLabel) => {
    const x = b[key] || {};
    return h("article", { class: "fwo-baseline" },
      h("h3", { class: "fwo-reading-h" }, x.label || fallbackLabel),
      h("p", {}, "Capacity " + fmt(x.capacity === undefined ? null : x.capacity, 1) + ", openness " +
        fmt(x.openness_bits === undefined ? null : x.openness_bits, 1) + " bits"),
      x.description ? h("p", { class: "fwo-small" }, x.description) : null);
  };
  replace(slot, one("fixed_output", "fixed output"), one("fair_coin", "intention-independent fair coin"),
    h("p", { class: "fwo-small fwo-baseline-note" }, b.note || "Theoretical classical references: their contrast explains the metric; it is not a proof that classical systems cannot have capacity."));
}

// ---------------------------------------------------------------- the drawer

export function circuitText(lib, s) {
  const { fmt } = lib;
  const phi = s ? s.intention_rad : null, gamma = s ? s.gamma_rad : null, beta = s ? s.perspective_rad : null;
  return [
    "Self  q0 |0> -- H -- RZ(phi) ------- o ------------- o -- RZ(-beta) -- H -- measure",
    "World q1 |0> ------------- RY(gamma) -- X -- RY(-gamma) -- X -------------------- measure",
    "",
    "o--X : controlled-NOT (control = Self). RY(gamma), CX, RY(-gamma), CX equals a",
    "controlled RY(2 gamma) from the Self onto the World.",
    "display probe:    phi = " + fmt(phi, 4) + " rad, gamma = " + fmt(gamma, 4) + " rad, beta = " + fmt(beta, 4) + " rad",
    "intent_low:       phi = beta;      intent_high: phi = beta + pi   (same gamma, beta)",
    "connection probe: phi, gamma as above; no final RZ(-beta) / H; both qubits read in Z",
    "bit order shown everywhere: SelfWorld ('10' = Self 1, World 0); Qiskit's c1c0 is reversed once.",
  ].join("\n");
}

function countsTable(lib, name, counts, requested) {
  const { table, fmt, fmtInt } = lib;
  const n = total(counts);
  const rows = OUTCOMES.map((k) => [k, fmtInt((counts || {})[k] || 0), n ? fmt(((counts || {})[k] || 0) / n, 4) : "n/a"]);
  rows.push(["total", fmtInt(n), requested ? "requested " + fmtInt(requested) : ""]);
  return table("Counts: " + name + " probe (SelfWorld)", ["outcome", "count", "fraction"], rows);
}

export function renderDrawer(lib, txt, slot, run, profile) {
  const { h, replace, fmt, fmtInt, fmtPct, table } = lib;
  const parts = [];
  parts.push(h("h3", {}, "The circuit"));
  parts.push(h("pre", { class: "fwo-pre", tabindex: "0", role: "region", "aria-label": "Circuit as a text diagram" },
    circuitText(lib, run && run.settings ? run.settings : null)));
  parts.push(h("h3", {}, "The four probes of one job"));
  parts.push(h("ul", {}, PROBE_ORDER.map((p) => h("li", {}, txt.PROBE_TEXT[p]))));
  if (run && run.status === "completed") {
    const s = run.source || {}, m = run.metrics || {};
    parts.push(h("h3", {}, "Counts (bit order " + (run.bit_order || "SelfWorld") + ")"));
    const requested = (run.settings || {}).shots_per_probe;
    parts.push(h("div", { class: "fwo-count-grid" }, PROBE_ORDER.map((p) => countsTable(lib, p, (run.counts || {})[p], requested))));
    parts.push(h("p", { class: "fwo-small" }, "P(Self = 1) per probe: display " + fmt(m.p_self_1, 4) + ", intent_low " + fmt(m.p_low, 4) +
      ", intent_high " + fmt(m.p_high, 4) + ". Capacity uses the actual totals of the two intent probes."));
    parts.push(h("h3", {}, "Job and backend"));
    const check = s.bit_order_check || {};
    const canaryText = check.orientation_ok === true ? "passed (bit order confirmed in the same job)"
      : check.orientation_ok === false ? "FAILED: the counts above are not trustworthy"
        : "not checked (canary disabled)";
    parts.push(table("Job record", ["item", "value"], [
      ["backend", String(s.backend_name || "n/a") + " (" + (s.provider_family || "?") + ")"],
      ["kind", (s.simulator === false ? "hardware" : "simulator") + ", " + (s.noisy ? "noisy" : "ideal") + ", " + (s.remote ? "remote" : "local")],
      ["packing mode", String(s.mode || "n/a") + (s.layout && s.layout.n_circuits ? " (" + s.layout.n_circuits + " circuit(s), " + (s.layout.qubits_per_circuit || []).join("/") + " qubits)" : "")],
      ["submitted as", String(s.submitted_as || "n/a")],
      ["job id", String(s.job_id || "n/a")],
      ["wall time", s.wall_s === null || s.wall_s === undefined ? "n/a" : fmt(s.wall_s, 2) + " s"],
      ["shots requested per probe", fmtInt(s.shots_requested)],
      ["shots seen", PROBE_ORDER.map((p) => p + " " + fmtInt((s.shots_seen || {})[p])).join(", ")],
      ["bit-order / readout canary", canaryText + "; flip rates P(1|0) = " + fmtPct(check.p_flip_0to1_mean, 2) + ", P(0|1) = " + fmtPct(check.p_flip_1to0_mean, 2)],
      ["versions", Object.entries(s.versions || {}).map(([k, v]) => k + " " + v).join(", ")],
      ["model version", String(run.model_version || "n/a")],
    ]));
  } else {
    parts.push(h("p", { class: "fwo-small" }, "After a run this drawer shows the four count tables, the packing mode, the job id, the backend details, the shots seen and the canary result."));
    if (profile && profile.profile) {
      const p = profile.profile;
      parts.push(h("p", { class: "fwo-small" }, "Backend profile: " + p.name + " (" + p.family + "), " + (p.noisy ? "noisy" : "ideal") + ", " +
        (p.remote ? "remote" : "local") + ", up to " + p.max_qubits + " qubits, packing mode " + profile.mode + (profile.one_job ? ", one job per run." : ".")));
    }
  }
  parts.push(h("h3", {}, "Honesty"));
  parts.push(h("p", {}, txt.HONESTY));
  parts.push(h("p", { class: "fwo-small" }, "The correspondence between the controls and the words intention, World and perspective is designed, not discovered: " +
    "the phase is called intention because varying it changes interference; the coupling is called World coupling because it wires the Self to a second qubit that records which alternative it took " +
    "(the World never pushes the Self toward a future; its record only reduces the interference the Self can use); " +
    "the readout angle is called perspective because it changes the measured observable. A responsive classical system can also score highly on capacity."));
  parts.push(h("p", { class: "fwo-small" }, "World coupling (w) is a controlled rotation by 2 gamma with gamma = w pi/2: coherent and reversible in principle, not noise. " +
    "In the ideal state Capacity = cos(gamma) is the Self's interference visibility and the World's which-alternative distinguishability is sin(gamma); " +
    "they satisfy C^2 + D^2 = 1, the wave-particle duality relation, so the slider trades one for the other. Joint control of Self and World could undo the coupling."));
  replace(slot, parts);
}

export function renderCoverage(lib, slot, curves) {
  const { h, replace, fmt, fmtInt, table } = lib;
  const parts = [];
  const cov = curves && curves.coverage;
  if (cov && cov.rows && cov.rows.length) {
    parts.push(h("p", { class: "fwo-small" }, "Interval check: for each coupling, repeated seeded samples of the two intent probes were drawn from the exact " +
      "distributions and the conservative 95% interval was checked against the exact capacity. Source: " + (cov.source || "unknown") + "."));
    parts.push(table("Hoeffding interval coverage", ["w", "exact C", "shots / probe", "repeats", "coverage", "mean width"],
      cov.rows.map((r) => [fmt(r.w, 2), fmt(r.capacity_exact, 3), fmtInt(r.shots), fmtInt(r.repeats), fmt(r.coverage_95, 3), fmt(r.mean_width, 3)])));
  }
  const noise = curves && curves.noise;
  if (noise && noise.capacity && noise.capacity.length) {
    const xs = noise[noise.x_name || "scale"] || [];
    const pick = [];
    for (let i = 0; i < xs.length; i++) if (i === 0 || i === xs.length - 1 || i % Math.max(1, Math.floor(xs.length / 6)) === 0) pick.push(i);
    parts.push(table("Capacity under the IonQ-like noise model (" + (noise.x_name || "scale") + " = multiple of the published rates; w = " + fmt((noise.fixed || {}).w, 2) + ")",
      [noise.x_name || "scale", "capacity", "P(Self = 1)", "connection (bits)"],
      pick.map((i) => [fmt(xs[i], 1), fmt(noise.capacity[i], 4), fmt((noise.p_self_1 || [])[i], 4), fmt((noise.connection_bits || [])[i], 4)])));
    if (noise.note) parts.push(h("p", { class: "fwo-small" }, noise.note + " Source: " + (noise.source || "unknown") + "."));
  }
  if (!parts.length) parts.push(h("p", { class: "fwo-small" }, "Validation data unavailable."));
  replace(slot, parts);
}
