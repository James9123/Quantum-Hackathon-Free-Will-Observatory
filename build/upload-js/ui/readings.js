// Text and table views of a run: the two futures and the three readings in plain words
// (first screen), then the detail panels: the Demon's forecast and comparison, the run
// record, how it works, how sure we are, the baselines and the honesty notes. Everything
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

function meter(lib, value, band) {
  // A 0..1 bar; `band` = [lo, hi] draws the 95% range over it. Decorative: the
  // same numbers are always printed next to it.
  const { h } = lib;
  const bar = h("div", { class: "fwo-meter", "aria-hidden": "true" });
  // custom properties so a theme can draw the same value as an arc, a scale or an orb
  const clamp = (x) => Math.max(0, Math.min(1, Number(x)));
  bar.style.setProperty("--fwo-v", value === null ? "0" : clamp(value).toFixed(4));
  if (band && band[0] !== null && band[1] !== null) {
    bar.style.setProperty("--fwo-lo", clamp(band[0]).toFixed(4));
    bar.style.setProperty("--fwo-hi", clamp(band[1]).toFixed(4));
    bar.classList.add("fwo-meter--band");
  }
  if (value === null) bar.classList.add("fwo-meter--empty");
  if (band && band[0] !== null && band[1] !== null) {
    const r = h("div", { class: "fwo-meter-band" });
    r.style.left = (100 * Math.max(0, Math.min(1, band[0]))).toFixed(1) + "%";
    r.style.width = (100 * Math.max(0, Math.min(1, band[1]) - Math.max(0, Math.min(1, band[0])))).toFixed(1) + "%";
    bar.appendChild(r);
  }
  if (value !== null) {
    const f = h("div", { class: "fwo-meter-fill" });
    f.style.width = (100 * Math.max(0, Math.min(1, value))).toFixed(1) + "%";
    bar.appendChild(f);
  }
  return bar;
}

function futureCard(lib, which, p, count, n, prevP, forecastP) {
  const { h, fmtPct, fmtInt } = lib;
  if (p === null) {
    return [h("p", { class: "fwo-future-p fwo-future-p--empty" }, "?"),
      h("p", { class: "fwo-small" }, forecastP === null ? "Run the experiment to see." :
        "The Demon expects " + fmtPct(forecastP) + ". Run the experiment to see.")];
  }
  const parts = [
    h("p", { class: "fwo-future-p" }, fmtPct(p)),
    meter(lib, p, null),
    h("p", { class: "fwo-small" }, fmtInt(count) + " of " + fmtInt(n) + " tries ended in Future " + which + "."),
  ];
  const extra = [];
  if (forecastP !== null) extra.push("Demon predicted " + fmtPct(forecastP));
  if (prevP !== null) extra.push("last run " + fmtPct(prevP));
  if (extra.length) parts.push(h("p", { class: "fwo-small" }, extra.join(" \u00b7 ")));
  return parts;
}

export function renderFutures(lib, slots, run, prev, forecast) {
  const { replace } = lib;
  const m = run ? run.metrics : null;
  const p1 = num(m, "p_self_1");
  const c = run && run.counts ? run.counts.display : null;
  const n = c ? total(c) : 0;
  const q1 = prev && prev.metrics ? num(prev.metrics, "p_self_1") : null;
  const f1 = run && run.prediction ? num(run.prediction, "p_self_1") : (forecast ? num(forecast, "p_self_1") : null);
  replace(slots.f0, futureCard(lib, 0, p1 === null ? null : 1 - p1, c ? (Number(c["00"]) || 0) + (Number(c["01"]) || 0) : 0, n,
    q1 === null ? null : 1 - q1, f1 === null ? null : 1 - f1));
  replace(slots.f1, futureCard(lib, 1, p1, c ? (Number(c["10"]) || 0) + (Number(c["11"]) || 0) : 0, n, q1, f1));
}

// ---------------------------------------------------------------- readings

const TECH = {
  capacity: "Capacity C = |p_high \u2212 p_low|: the gap between two extra circuits run with opposite choices (phi = beta and phi = beta + pi), same ties and point of view.",
  openness: "Openness: the binary entropy of Future 1's share, in bits (0 settled, 1 a 50/50 coin flip). Uncertainty, not freedom.",
  connection: "Connection: the mutual information between Self and World in a separate check circuit read in a fixed basis, in bits. Not an entanglement test.",
};

function card(lib, id, title, value, band, lines, tech, cls) {
  const { h } = lib;
  return h("article", { class: "fwo-reading " + (cls || ""), "aria-labelledby": id + "-h" },
    h("h3", { id: id + "-h", class: "fwo-reading-h" }, title),
    h("p", { class: "fwo-reading-value" }, h("span", { class: "fwo-reading-num" }, value === null ? "\u2013" : lib.fmt(value, 2)),
      h("span", { class: "fwo-reading-unit" }, " out of 1")),
    meter(lib, value, band),
    lines.map((x) => h("p", { class: "fwo-reading-line" }, x)),
    h("p", { class: "fwo-tech-line" }, tech));
}

export function renderReadings(lib, txt, slot, run) {
  const { replace, fmt, fmtPct } = lib;
  if (!run || run.status !== "completed") {
    replace(slot,
      card(lib, "fwo-r-cap", "How much your choice can change the odds", null, null, [txt.MEANING.capacity, "Run the experiment to see."], TECH.capacity),
      card(lib, "fwo-r-open", "How open the future is", null, null, [txt.MEANING.openness, "Run the experiment to see."], TECH.openness),
      card(lib, "fwo-r-conn", "How much the World knows", null, null, [txt.MEANING.connection, "Run the experiment to see."], TECH.connection));
    return;
  }
  const m = run.metrics || {};
  const pred = run.prediction || {};
  const ci = Array.isArray(m.capacity_ci95) ? m.capacity_ci95 : [null, null];
  const resolved = !!m.resolved;
  const capLines = [
    "With opposite choices, Future 1 came out at " + fmtPct(m.p_low) + " and " + fmtPct(m.p_high) + ".",
    resolved
      ? "We are 95% sure the true swing is between " + fmt(ci[0], 2) + " and " + fmt(ci[1], 2) + ", so in this model the choice really mattered."
      : "Too small to tell apart from zero: the true swing is somewhere between " + fmt(ci[0], 2) + " and " + fmt(ci[1], 2) + ". " + txt.NO_RESOLVED,
  ];
  replace(slot,
    card(lib, "fwo-r-cap", "How much your choice can change the odds", num(m, "capacity"), ci, capLines,
      TECH.capacity + " Theory for these dials: " + fmt(pred.capacity, 2) + ".", resolved ? "fwo-reading--resolved" : "fwo-reading--unresolved"),
    card(lib, "fwo-r-open", "How open the future is", num(m, "openness_bits"), null,
      [txt.opennessWord(num(m, "openness_bits")), "Open is not the same as free: a coin flip is open too."],
      TECH.openness + " Theory: " + fmt(pred.openness_bits, 2) + "."),
    card(lib, "fwo-r-conn", "How much the World knows", num(m, "connection_bits"), null,
      [txt.connectionWord(num(m, "connection_bits")), "That record is what shrinks the choice's power."],
      TECH.connection + " Theory: " + fmt(pred.connection_bits, 2) + "."));
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

export function renderRecord(lib, txt, slot, run, profile) {
  const { h, replace, fmt, fmtInt, fmtPct, table } = lib;
  const parts = [];
  if (run && run.status === "completed") {
    const s = run.source || {}, m = run.metrics || {};
    parts.push(h("h3", {}, "Counts from the four circuits (bit order " + (run.bit_order || "SelfWorld") + ": '10' means Self 1, World 0)"));
    const requested = (run.settings || {}).shots_per_probe;
    parts.push(h("div", { class: "fwo-count-grid" }, PROBE_ORDER.map((p) => countsTable(lib, p, (run.counts || {})[p], requested))));
    parts.push(h("p", { class: "fwo-small" }, "Share of Future 1 per circuit: display " + fmt(m.p_self_1, 4) + ", intent_low " + fmt(m.p_low, 4) +
      ", intent_high " + fmt(m.p_high, 4) + ". The swing uses the actual totals of the two intent circuits."));
    parts.push(h("h3", {}, "The job"));
    const check = s.bit_order_check || {};
    const canaryText = check.orientation_ok === true ? "passed (bit order confirmed in the same job)"
      : check.orientation_ok === false ? "FAILED: the counts above are not trustworthy"
        : "not checked (self-check circuits switched off)";
    parts.push(table("Job record", ["item", "value"], [
      ["backend", String(s.backend_name || "n/a") + " (" + (s.provider_family || "?") + ")"],
      ["kind", (s.simulator === false ? "hardware" : "simulator") + ", " + (s.noisy ? "noisy" : "ideal") + ", " + (s.remote ? "remote" : "local")],
      ["packing", String(s.mode || "n/a") + (s.layout && s.layout.n_circuits ? " (" + s.layout.n_circuits + " circuit(s), " + (s.layout.qubits_per_circuit || []).join("/") + " qubits)" : "")],
      ["submitted as", String(s.submitted_as || "n/a")],
      ["job id", String(s.job_id || "n/a")],
      ["wall time", s.wall_s === null || s.wall_s === undefined ? "n/a" : fmt(s.wall_s, 2) + " s"],
      ["shots requested per circuit", fmtInt(s.shots_requested)],
      ["shots seen", PROBE_ORDER.map((p) => p + " " + fmtInt((s.shots_seen || {})[p])).join(", ")],
      ["self-check (bit order, readout)", canaryText + "; flip rates P(1|0) = " + fmtPct(check.p_flip_0to1_mean, 2) + ", P(0|1) = " + fmtPct(check.p_flip_1to0_mean, 2)],
      ["versions", Object.entries(s.versions || {}).map(([k, v]) => k + " " + v).join(", ")],
      ["model version", String(run.model_version || "n/a")],
    ]));
  } else {
    parts.push(h("p", { class: "fwo-small" }, "After a run this shows the four count tables, the packing, the job id, the backend and the self-check result."));
    if (profile && profile.profile) {
      const p = profile.profile;
      parts.push(h("p", { class: "fwo-small" }, "Backend: " + p.name + " (" + p.family + "), " + (p.noisy ? "noisy" : "ideal") + ", " +
        (p.remote ? "remote" : "local") + ", up to " + p.max_qubits + " qubits, packing " + profile.mode + (profile.one_job ? ", one job per run." : ".")));
    }
  }
  replace(slot, parts);
}

const STEPS = [
  "The Self is one qubit. A first gate splits it into two possibilities at once: Future 0 and Future 1.",
  "Your choice turns a phase on the Self. A phase decides how the two possibilities add up later, like waves that reinforce or cancel.",
  "Ties to the world connect the Self to a second qubit, the World, which keeps a record of which possibility happened. The more it records, the less the two possibilities can interfere.",
  "Point of view picks the question we ask when we measure the Self.",
  "We measure many times (shots) and count how often the Self lands in Future 0 or Future 1.",
  "Two more circuits try opposite choices with the same ties and point of view: the gap between them is how much a choice can change the odds. A fourth circuit reads the World directly to see what it knows. All four run as one job.",
];

export function renderHow(lib, txt, slot, run) {
  const { h, replace } = lib;
  replace(slot,
    h("ol", { class: "fwo-steps-list" }, STEPS.map((x) => h("li", {}, x))),
    h("h3", {}, "The circuit, drawn as text"),
    h("pre", { class: "fwo-pre", tabindex: "0", role: "region", "aria-label": "Circuit as a text diagram" },
      circuitText(lib, run && run.settings ? run.settings : null)),
    h("h3", {}, "The four circuits in one job"),
    h("ul", {}, PROBE_ORDER.map((p) => h("li", {}, txt.PROBE_TEXT[p]))),
    h("h3", {}, "The math in one paragraph"),
    h("p", {}, "The chance of Future 1 is P(Self = 1) = [1 \u2212 cos(gamma) cos(phi \u2212 beta)] / 2, where phi is your choice, " +
      "beta the point of view and gamma = w \u00b7 pi/2 the ties to the world. Opposite choices therefore differ by cos(gamma): " +
      "that is the most a choice can swing the odds. The World's ability to tell the two possibilities apart is sin(gamma), and " +
      "cos\u00b2 + sin\u00b2 = 1: what the World learns is exactly what the choice loses (the wave-particle duality relation)."));
}

export function renderSure(lib, slot) {
  const { h, replace } = lib;
  replace(slot,
    h("p", {}, "Every reading comes from counting shots, so it wobbles a little from run to run. For the swing your choice can make, " +
      "the page shows a range it is 95% sure contains the true value. The range is deliberately cautious (a Hoeffding bound): " +
      "with 1,024 shots per circuit it reaches about 0.09 either side."),
    h("p", {}, "If that range includes zero, the page says \u201cNo resolved influence at this shot count\u201d: the experiment cannot tell the swing apart " +
      "from nothing. That is not the same as proving it is zero; more shots narrow the range."),
    h("p", { class: "fwo-small" }, "The range was checked against the exact answer in many simulated repeats; the table below shows how often it was right."));
}

export function renderHonesty(lib, txt, slot) {
  const { h, replace } = lib;
  replace(slot,
    h("p", {}, txt.HONESTY),
    h("p", {}, "The words are designed, not discovered: the phase is called a choice (intention) because varying it changes interference; " +
      "the coupling is called ties to the world because it wires the Self to a second qubit that records which possibility it took " +
      "(the World never pushes the Self toward a future; its record only reduces the interference the Self can use); " +
      "the readout angle is called a point of view because it changes the question asked."),
    h("p", {}, "The ties are coherent and reversible in principle, not noise: someone controlling the Self and the World together could undo them " +
      "and restore the full swing. The World here is one qubit whose record can be read completely; a real environment has countless parts."),
    h("p", {}, "This is not a model of brains, and not evidence that quantum systems can be agents. A simple classical switch can also " +
      "score a high swing; the classical comparison panel shows two such references."));
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
