// Qollab JS entry for the CHSH reference experiment.
//
// Qollab runs this file as the body of an async function with `backend`, `console`
// and `setTimeout` injected; imports become `await require(...)`. index.html is
// injected with innerHTML (its scripts never run), main.css is the only stylesheet.
// The same file runs unchanged in dev/index.html, where `ui_api` is a stub module.
//
// Python is called as `api.fn.callPromising(...)` with JSON strings in and out.
// IonQ allows ONE job per run, and IonQ requests only route while this file is
// still running, so it ends by awaiting a promise that never settles.
//
// This effort is supported by Qollab & IonQ

import * as api from "ui_api";
import * as dom from "./ui/dom.js";
import { makeExperiment } from "./ui/experiment.js";
import { renderBadge } from "./ui/badge.js";
import { renderCard, renderRunError } from "./ui/card.js";
import { createDial } from "./ui/dial.js";
import { renderChart, renderLegend } from "./ui/chart.js";

const exp = makeExperiment(dom);
const { byId, h, replace, fmt, fmtInt, fmtPct, table } = dom;

function errText(err) {
  return err && err.message ? String(err.message) : String(err);
}

// One call into ui_api: JSON string back, parsed here. Failures become {error}.
async function callPy(fn, name, ...args) {
  if (!fn || typeof fn.callPromising !== "function") {
    return { error: "ui_api." + name + " is not available" };
  }
  try {
    const ret = await fn.callPromising(...args);
    const obj = JSON.parse(String(ret));
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      return { error: name + " returned " + String(ret).slice(0, 80) + ", not a JSON object" };
    }
    return obj;
  } catch (err) {
    return { error: name + ": " + errText(err) };
  }
}

// Qollab passes `backend` in as a parameter; stub mode sets a global. Either way a
// missing one must not throw a ReferenceError before the page can say so.
const BACKEND = typeof backend === "undefined" || backend === null ? null : backend;

function backendName(b) {
  try {
    const n = b ? (b.name ?? b.backend_name) : null;
    return typeof n === "string" ? n : null;
  } catch (err) {
    return null;
  }
}

let statusEl = null;
function status(msg, isError = false) {
  if (statusEl) {
    statusEl.textContent = msg;
    statusEl.classList.toggle("qh-status--error", !!isError);
  }
  if (isError) console.error("[ui] " + msg);
  else console.log("[ui] " + msg);
}

async function start() {
  // Generous: imports (Pyodide loading ui_api) may already have taken a while.
  await dom.whenMounted("qh-app", setTimeout, 60000);
  statusEl = byId("qh-status");
  status("Loading the backend profile\u2026");

  // ---------------------------------------------------------------- backend badge
  // `true`: this page load is a new Qollab run, so Python starts a fresh one-job
  // budget even if the interpreter was reused. Nothing else ever passes `true`.
  const profile = BACKEND === null
    ? { error: "no backend was injected into main.js" }
    : await callPy(api.profile_json, "profile_json", BACKEND, true);
  const name = profile.error ? backendName(BACKEND) || "this backend" : profile.name;
  renderBadge(dom, profile, byId("qh-badge-list"), byId("qh-badge-policy"), backendName(BACKEND));
  const oneJob = !!profile.error || !!profile.one_job;
  if (!profile.error && profile.simulator === false) {
    byId("qh-honesty").textContent = "This backend is quantum hardware. The card's \u201cwhat this does NOT show\u201d list still applies.";
  } else if (profile.sim_note) {
    byId("qh-honesty").textContent = "Simulator honesty: " + profile.sim_note;
  }

  // ---------------------------------------------------------------- run panel
  const runBtn = byId("qh-run");
  const shotsIn = byId("qh-shots");
  const shotsHelp = byId("qh-shots-help");
  const shotsHelpText = shotsHelp.textContent;
  const modeIn = byId("qh-mode");
  const mitIn = byId("qh-mitigate");
  const lockNote = byId("qh-run-lock");
  const cardSlot = byId("qh-card");
  byId("qh-run-policy").textContent = oneJob
    ? "One job per run on this backend: the button locks after one press."
    : "No job limit on this local simulator: each press submits one job.";
  if (!profile.error && profile.preferred_mode) {
    modeIn.options[0].textContent = "auto (" + profile.preferred_mode + " on this backend)";
  }
  let jobsUsed = 0;
  let running = false;

  function readShots() {
    const raw = String(shotsIn.value).trim();
    const n = Number(raw);
    if (!/^[0-9]+$/.test(raw) || !Number.isInteger(n) || n < 1 || n > 100000) return null;
    return n;
  }
  shotsIn.addEventListener("input", () => {
    shotsIn.removeAttribute("aria-invalid");
    shotsHelp.textContent = shotsHelpText;
  });

  // One-job backends: the button is disabled for good. Focus moves to the visible
  // explanation, so keyboard and screen-reader users are not dropped on <body>.
  function lockRun() {
    runBtn.disabled = true;
    lockNote.hidden = false;
    lockNote.textContent = (profile.error
      ? "Run is now disabled: the backend profile could not be read, so this page allows one press per run"
      : "Run is now disabled: this backend accepts one job per run and this page has used its one press") +
      ". To submit another job, run the project again.";
    lockNote.setAttribute("tabindex", "-1");
    lockNote.focus();
  }

  runBtn.addEventListener("click", async () => {
    if (running || runBtn.disabled || (oneJob && jobsUsed >= 1)) return;
    const shots = readShots();
    if (shots === null) {
      shotsIn.setAttribute("aria-invalid", "true");
      shotsHelp.textContent = "Enter a whole number of shots from 1 to 100,000.";
      status("Not submitted: shots must be a whole number from 1 to 100,000.", true);
      shotsIn.focus();
      return;
    }
    running = true;
    jobsUsed += 1;
    // Local backends: aria-disabled (not disabled) while the job runs, so focus stays put.
    if (oneJob) lockRun();
    else runBtn.setAttribute("aria-disabled", "true");
    const mode = modeIn.value;
    const mitigate = !!mitIn.checked;
    status("Submitting one job to " + name + ": " + fmtInt(shots) + " shots per setting, mode " + mode + "\u2026");
    const t0 = Date.now();
    const run = BACKEND === null
      ? { error: "no backend was injected into main.js", job_submitted: false }
      : await callPy(api.run_chsh_json, "run_chsh_json", BACKEND, shots, mode, mitigate);
    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    running = false;
    if (!oneJob) runBtn.removeAttribute("aria-disabled");
    if (oneJob) {
      lockNote.textContent += run.job_submitted === false
        ? " (No job reached the backend.)"
        : run.job_submitted === true ? " (A submission was made, so this run's one job is used.)" : "";
    }
    try {
      if (run.error) {
        renderRunError(dom, cardSlot, run);
        status("The run failed after " + secs + " s: " + run.error, true);
        return;
      }
      const view = renderCard(dom, exp, cardSlot, run);
      const c = run.card;
      const shown = c.verdict_basis === "mitigated" && c.mitigated ? c.mitigated : c.raw;
      status("Done in " + secs + " s: S = " + fmt(shown.value) + " \u00b1 " + fmt(shown.se) + " (" +
        c.verdict_basis + "). Verdict: " + c.verdict + ". The claim card is under Result.");
      const txt = await callPy(api.card_text_json, "card_text_json", JSON.stringify(c));
      view.setText(txt.error ? "(plain-text view unavailable: " + txt.error + ")" : txt.text);
      if (!txt.error) console.log(txt.text);
    } catch (err) {
      status("The job finished, but its result could not be shown: " + errText(err), true);
    }
  });

  // ---------------------------------------------------------------- noise dial + chart
  let curveData = null;
  let curveKey = "p2";
  const chartEl = byId("qh-chart");
  const radios = { p2: byId("qh-curve-p2"), ionq: byId("qh-curve-ionq") };

  function drawChart() {
    if (!curveData || curveData.error) return;
    const def = exp.curves[curveKey];
    const c = curveData[def.dataKey];
    const marker = def.marker(curveData);
    const cfg = {
      id: "qh-svg",
      title: def.title,
      desc: def.summary(curveData),
      xLabel: def.xLabel,
      yLabel: "S",
      xs: c.x,
      ys: c.S,
      seriesLabel: "exact S (solid line)",
      hLines: [
        { y: curveData.classical_bound, kind: "bound", short: "S = 2", label: exp.boundLabel + " (dashed line)" },
        { y: curveData.quantum_ideal, kind: "ideal", short: "2\u221a2", label: exp.idealLabel + " (dotted line)" },
      ],
      marker: marker ? Object.assign({ short: curveKey === "p2" ? "\u03bb*" : "" }, marker,
        { label: marker.label + " (open circle, dash-dot line)" }) : null,
      point: null,
    };
    const pt = exp.dialPoint(curveKey, dial.current());
    if (pt) cfg.point = Object.assign({}, pt, { label: pt.label + " (filled diamond): S = " + fmt(pt.y) });
    renderChart(dom, chartEl, cfg);
    renderLegend(dom, byId("qh-chart-legend"), cfg);
  }

  function describeCurve() {
    if (!curveData || curveData.error) return;
    const def = exp.curves[curveKey];
    const c = curveData[def.dataKey];
    byId("qh-chart-summary").textContent = def.summary(curveData);
    const rows = c.x.map((_, i) => def.row(curveData, i));
    replace(byId("qh-chart-table"), table(def.title + " (" + rows.length + " points)", def.columns, rows,
      { tall: true, label: "Data table: " + def.title }));
    const p = c.provenance;
    byId("qh-chart-prov").textContent = p
      ? "Precomputed by " + p.generator + " at commit " + p.git_commit + " on a " + p.machine + " (" +
        p.created_utc + "): exact density-matrix values, no sampling."
      : "Source: " + (c.source || "unknown") + ".";
  }

  function showCurve(key, announce) {
    if (!exp.curves[key] || key === curveKey) return;
    curveKey = key;
    radios[key].checked = true;
    describeCurve();
    drawChart();
    if (announce && !running) status("The chart now shows the curve that matches the noise model: " + exp.curves[key].title + ".");
  }

  const dial = createDial(dom, exp, {
    callDial: (params) => callPy(api.noise_dial_json, "noise_dial_json", JSON.stringify(params)),
    setTimeoutFn: setTimeout,
    onResult: () => drawChart(),
    onPresetChange: (key) => showCurve(key, true),
    onError: (msg) => status("Noise dial error: " + msg, true),
  });

  for (const [key, radio] of Object.entries(radios)) {
    radio.addEventListener("change", () => { if (radio.checked) showCurve(key, false); });
  }

  if (typeof ResizeObserver !== "undefined") {
    let lastWidth = 0;
    const redraw = dom.debounce(drawChart, 120, setTimeout);
    new ResizeObserver(() => {
      const w = Math.round(chartEl.clientWidth);
      if (w && Math.abs(w - lastWidth) > 4) { lastWidth = w; redraw(); }
    }).observe(chartEl);
  }

  // A failure in the dial or the chart must not leave Run disabled.
  let problem = "";
  try {
    status("Computing the noise dial\u2026");
    await dial.refresh();
    status("Loading the precomputed curves\u2026");
    curveData = await callPy(api.curve_json, "curve_json");
    if (curveData.error) {
      byId("qh-chart-summary").textContent = "The precomputed curve is unavailable: " + curveData.error;
    } else {
      describeCurve();
      drawChart();
      renderValidation(curveData);
    }
  } catch (err) {
    problem = " Part of the page could not load: " + errText(err) + ".";
  }

  runBtn.disabled = false;
  if (profile.error) {
    status("The backend profile is unavailable (" + profile.error + "). The noise dial and chart work; " +
      "Run allows at most one job on this page." + problem, true);
  } else {
    status("Ready. Backend: " + name + (oneJob ? " (one job per run)." : " (no job limit).") + problem, !!problem);
  }
}

function renderValidation(data) {
  const parts = [];
  const cov = data.coverage || {};
  if (cov.rows && cov.rows.length) {
    parts.push(h("p", {}, "Error bars: for each noise level, 2,000 seeded runs were simulated and checked " +
      "against the exact S. About " + fmtPct(cov.expected_1sigma) + " should land within 1 standard error and " +
      fmtPct(cov.expected_2sigma) + " within 2."));
    parts.push(table("Error-bar coverage (precomputed)", ["p2", "exact S", "shots", "within 1 se", "within 2 se"],
      cov.rows.map((r) => [fmt(r.p2, 2), fmt(r.S_exact), fmtInt(r.shots), fmtPct(r.coverage_1sigma), fmtPct(r.coverage_2sigma)])));
  }
  const aer = data.aer_check || {};
  if (aer.n_settings && typeof aer.max_abs_diff === "number") {
    parts.push(h("p", {}, "Cross-check: the noise dial agrees with qiskit-aer's density-matrix simulator to within " +
      aer.max_abs_diff.toExponential(1) + " in S over " + aer.n_settings + " noise settings."));
  }
  if (!parts.length) parts.push(h("p", {}, "Validation data unavailable."));
  replace(byId("qh-validation"), parts);
}

try {
  await start();
} catch (err) {
  status("The page could not start: " + errText(err), true);
}

// Keep main.js running: IonQ requests only route while it is alive.
await new Promise(() => {});
