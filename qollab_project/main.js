// Qollab JS entry for The Free Will Observatory.
//
// Qollab runs this file as the body of an async function with `backend`, `console`
// and `setTimeout` injected; imports become `await require(...)`. index.html is
// injected with innerHTML (its scripts never run), main.css is the only stylesheet,
// and three.js comes from Qollab's import map. The same file runs unchanged in
// dev/index.html, where `observatory_api` is a JS stub and `backend` a stand-in.
//
// Python is called as `api.fn.callPromising(...)` with JSON strings in and out.
// IonQ allows ONE job per run, and IonQ requests only route while this file is
// still running, so it ends by awaiting a promise that never settles.
//
// Simulators compute what quantum theory predicts and how a noise model degrades it;
// they do not test nature. The readings are a designed, fictional model of agency.
//
// This effort is supported by Qollab & IonQ

import * as api from "observatory_api";
import * as THREE from "three";
import * as dom from "./ui/dom.js";
import * as txt from "./ui/text.js";
import { renderBadge } from "./ui/badge.js";
import { createTabs } from "./ui/tabs.js";
import { createScene } from "./ui/scene.js";
import { renderBars, renderBarLegend, renderLines, renderLineLegend } from "./ui/chart.js";
import { renderFutures, renderReadings, renderRunError, renderDemonForecast, renderDemonCompare, renderBaselines, renderDrawer, renderCoverage, personaName } from "./ui/readings.js";

const { byId, h, replace, fmt, fmtInt, fmtPct, fmtRad, fmtDeg, table } = dom;
const PERSONAS = ["self", "demon", "observer"];
const DEG = Math.PI / 180;

function errText(err) {
  return err && err.message ? String(err.message) : String(err);
}

// One call into observatory_api: JSON string back, parsed here. Failures become {error}.
async function callPy(fn, name, ...args) {
  if (!fn || typeof fn.callPromising !== "function") {
    return { error: "observatory_api." + name + " is not available" };
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
    statusEl.classList.toggle("fwo-status--error", !!isError);
  }
  if (isError) console.error("[observatory] " + msg);
  else console.log("[observatory] " + msg);
}

function prefersReducedMotion() {
  try {
    return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (err) {
    return false;
  }
}

async function start() {
  // Generous: the imports (Pyodide loading observatory_api, three.js) may already have taken a while.
  await dom.whenMounted("fwo-app", setTimeout, 60000);
  statusEl = byId("fwo-status");
  status("Loading the backend profile\u2026");

  // ---------------------------------------------------------------- elements
  const el = {
    intention: byId("fwo-intention"), intentionOut: byId("fwo-intention-out"),
    coupling: byId("fwo-coupling"), couplingOut: byId("fwo-coupling-out"),
    perspective: byId("fwo-perspective"), perspectiveOut: byId("fwo-perspective-out"),
    shots: byId("fwo-shots"), shotsHelp: byId("fwo-shots-help"), mode: byId("fwo-mode"), canary: byId("fwo-canary"),
    draft: byId("fwo-draft"), run: byId("fwo-run"), runPolicy: byId("fwo-run-policy"), progress: byId("fwo-progress"),
    lock: byId("fwo-run-lock"), runError: byId("fwo-run-error"),
    sceneHost: byId("fwo-scene-host"), sceneCaption: byId("fwo-scene-caption"), motion: byId("fwo-motion"), motionHelp: byId("fwo-motion-help"),
    future0: byId("fwo-future-0"), future1: byId("fwo-future-1"), readings: byId("fwo-readings"),
    chart: byId("fwo-chart"), chartSummary: byId("fwo-chart-summary"), chartLegend: byId("fwo-chart-legend"), chartTable: byId("fwo-chart-table"),
    factual: byId("fwo-factual"), poetic: byId("fwo-poetic"), personaNote: byId("fwo-persona-note"), baselines: byId("fwo-baselines"),
    howBody: byId("fwo-how-body"), curve: byId("fwo-curve"), curveSummary: byId("fwo-curve-summary"), curveLegend: byId("fwo-curve-legend"),
    curveTable: byId("fwo-curve-table"), coverage: byId("fwo-coverage"), curveProv: byId("fwo-curve-prov"),
    selfText: byId("fwo-persona-self"), observerText: byId("fwo-observer-text"),
    demonForecast: byId("fwo-demon-forecast"), demonCompare: byId("fwo-demon-compare"),
  };
  const shotsHelpText = el.shotsHelp.textContent;

  // ---------------------------------------------------------------- state
  let profile = null;
  let oneJob = true;
  let jobsUsed = 0;
  let running = false;
  let current = null;        // last completed run
  let previous = null;       // the one before it (the ghost)
  let forecast = null;       // predict_json for the draft
  let forecastSeq = 0;
  let curves = null;
  let persona = "self";

  // ---------------------------------------------------------------- persona tabs
  const tabs = createTabs(dom, PERSONAS.map((key) => ({ key, tab: byId("fwo-tab-" + key), panel: byId("fwo-panel-" + key) })),
    (key) => { persona = key; schedulePoetic(); });

  // The persona line is a polite live region: written once per completed run, and
  // (debounced) when the persona changes, so arrowing through the tabs announces
  // one line, not three. The data never changes with the persona.
  function writePoetic() {
    if (!current || !current.explanation || !current.explanation.poetic) {
      el.poetic.textContent = "";
      return;
    }
    const line = current.explanation.poetic[persona];
    el.poetic.textContent = line ? personaName(persona) + ": " + line : "";
  }
  const schedulePoetic = dom.debounce(writePoetic, 600, setTimeout);

  // ---------------------------------------------------------------- the draft
  function readShots() {
    const raw = String(el.shots.value).trim();
    const n = Number(raw);
    if (!/^[0-9]+$/.test(raw) || !Number.isInteger(n) || n < 1 || n > 4096) return null;
    return n;
  }

  function readDraft() {
    return {
      intention_rad: Number(el.intention.value) * DEG,
      world_coupling: Number(el.coupling.value),
      perspective_rad: Number(el.perspective.value) * DEG,
      shots_per_probe: readShots() ?? 1024,
      persona,
      mode: el.mode.value,
      canary: !!el.canary.checked,
    };
  }

  function syncOutputs() {
    const phi = Number(el.intention.value) * DEG;
    const w = Number(el.coupling.value);
    const beta = Number(el.perspective.value) * DEG;
    el.intentionOut.textContent = fmtRad(phi);
    el.intention.setAttribute("aria-valuetext", "phi = " + fmtRad(phi));
    el.couplingOut.textContent = fmt(w, 2) + " (gamma " + fmtDeg(w * Math.PI / 2) + ")";
    el.coupling.setAttribute("aria-valuetext", "w = " + fmt(w, 2) + ", gamma = " + fmtRad(w * Math.PI / 2));
    el.perspectiveOut.textContent = fmtRad(beta);
    el.perspective.setAttribute("aria-valuetext", "beta = " + fmtRad(beta));
    el.draft.textContent = "Draft: " + txt.draftText(dom, readDraft()) + ".";
  }

  function describePersonas() {
    const d = readDraft();
    const ideal = forecast && forecast.ideal ? forecast.ideal : null;
    el.selfText.textContent = txt.selfDraftText(dom, d, ideal);
    el.observerText.textContent = txt.observerText(dom, d, ideal);
  }

  async function refreshForecast() {
    const mine = ++forecastSeq;
    const d = readDraft();
    const f = await callPy(api.predict_json, "predict_json", JSON.stringify(d));
    if (mine !== forecastSeq) return;        // a newer draft is already on its way
    forecast = f.error ? null : f;
    renderDemonForecast(dom, el.demonForecast, f, txt.draftText(dom, d));
    describePersonas();
    if (!current) { drawChart(); describeChart(); }
    drawCurve();
    if (!forecast) status("The Demon's forecast failed: " + f.error, true);
  }
  const scheduleForecast = dom.debounce(refreshForecast, 150, setTimeout);

  for (const input of [el.intention, el.coupling, el.perspective]) {
    input.addEventListener("input", () => { syncOutputs(); scheduleForecast(); });
  }
  el.shots.addEventListener("input", () => {
    el.shots.removeAttribute("aria-invalid");
    el.shotsHelp.textContent = shotsHelpText;
    syncOutputs();
    scheduleForecast();
  });
  el.mode.addEventListener("change", syncOutputs);
  el.canary.addEventListener("change", syncOutputs);
  syncOutputs();

  // ---------------------------------------------------------------- the scene
  const reduced = prefersReducedMotion();
  const scene = createScene(THREE, dom, el.sceneHost, { reducedMotion: reduced, setTimeoutFn: setTimeout });
  el.motion.checked = !reduced;
  if (reduced) el.motionHelp.textContent = "Your system asks for reduced motion, so animation is off; tick to allow the particle flow anyway.";
  el.motion.addEventListener("change", () => { if (scene.available) scene.setMotion(el.motion.checked); });
  if (scene.available) {
    scene.setMotion(!reduced);
    scene.setLabel(txt.sceneLabel(dom, null, null));
  } else {
    // No WebGL: the text, readings and tables carry everything; nothing to animate.
    el.motion.checked = false;
    el.motion.disabled = true;
    el.motionHelp.textContent = "The 3D view is unavailable in this browser, so there is nothing to animate; every value it would show is in the text below.";
    console.warn("[observatory] 3D view unavailable; text view only");
  }
  try {
    if (typeof matchMedia === "function") {
      matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", (ev) => {
        if (!scene.available) return;
        scene.setReducedMotion(ev.matches);
        scene.setMotion(!ev.matches);
        el.motion.checked = !ev.matches;
        el.motionHelp.textContent = ev.matches
          ? "Your system asks for reduced motion, so animation is off; tick to allow the particle flow anyway."
          : "Decoration only; the numbers never move with it.";
      });
    }
  } catch (err) { /* older browsers: the initial preference still applies */ }

  function futureLabels(run, prev) {
    const p1 = run.metrics.p_self_1;
    const out = { f1: "Future 1 \u00b7 " + fmtPct(p1), f0: "Future 0 \u00b7 " + fmtPct(1 - p1), prev1: "", prev0: "" };
    if (prev && prev.metrics) {
      out.prev1 = "previous " + fmtPct(prev.metrics.p_self_1);
      out.prev0 = "previous " + fmtPct(1 - prev.metrics.p_self_1);
    }
    return out;
  }

  // ---------------------------------------------------------------- charts
  function barsFor(i) {
    const bars = [];
    const pick = (p1) => (p1 === null || p1 === undefined ? null : (i === 1 ? p1 : 1 - p1));
    if (previous && previous.metrics) bars.push({ kind: "previous", value: pick(previous.metrics.p_self_1) });
    if (current && current.metrics) bars.push({ kind: "current", value: pick(current.metrics.p_self_1) });
    const f = current && current.prediction ? current.prediction.p_self_1 : (forecast && forecast.ideal ? forecast.ideal.p_self_1 : null);
    if (f !== null && f !== undefined) bars.push({ kind: "forecast", value: pick(f) });
    return bars;
  }

  function drawChart() {
    const forecastFor = !current && forecast ? forecast.ideal : null;
    renderBars(dom, el.chart, {
      id: "fwo-bars",
      title: "Before and after: P(Future 0) and P(Future 1) for the previous run, the current run and the Demon's forecast",
      desc: txt.chartSummary(dom, current, previous, forecastFor),
      groups: [0, 1].map((i) => ({ label: "Future " + i + " (Self = " + i + ")", bars: barsFor(i) })),
    });
    const items = [];
    if (previous) items.push({ kind: "previous", label: "previous run (hatched)" });
    if (current) items.push({ kind: "current", label: "current run (solid)" });
    items.push({ kind: "forecast", label: (current ? "Demon forecast for the run's settings" : "Demon forecast for the draft") + " (outlined, dashed)" });
    renderBarLegend(dom, el.chartLegend, items);
  }

  function describeChart() {
    const forecastFor = !current && forecast ? forecast.ideal : null;
    el.chartSummary.textContent = txt.chartSummary(dom, current, previous, forecastFor);
    const rows = [];
    for (const i of [0, 1]) {
      const pick = (p1) => (p1 === null || p1 === undefined ? "n/a" : fmt(i === 1 ? p1 : 1 - p1, 4));
      const counts = current && current.counts ? current.counts.display : null;
      const n = counts ? (i === 1 ? (counts["10"] || 0) + (counts["11"] || 0) : (counts["00"] || 0) + (counts["01"] || 0)) : null;
      rows.push(["Future " + i,
        previous ? pick(previous.metrics.p_self_1) : "n/a",
        current ? pick(current.metrics.p_self_1) + " (" + fmtInt(n) + " shots)" : "n/a",
        current ? pick(current.prediction.p_self_1) : (forecastFor ? pick(forecastFor.p_self_1) + " (draft)" : "n/a")]);
    }
    replace(el.chartTable, table("Probabilities shown in the chart", ["future", "previous run", "current run", "Demon forecast"], rows));
  }

  function drawCurve() {
    if (!curves || curves.error || !curves.theory || !curves.theory.w) return;
    const t = curves.theory;
    const d = readDraft();
    const cfg = {
      id: "fwo-theory",
      title: "Theory: ideal capacity, the low and high intention probabilities, and connection against the World coupling w",
      desc: txt.curveSummary(dom, t, curves.noise),
      xLabel: "World coupling w (gamma = w pi / 2)", yLabel: "value (0 to 1)",
      xs: t.w,
      series: [
        { label: "ideal capacity cos(gamma) (solid)", ys: t.capacity, dash: "solid", cls: "fwo-c-line--capacity" },
        { label: "P_low, intention phi = beta (dashed)", ys: t.p_low, dash: "dashed", cls: "fwo-c-line--band" },
        { label: "P_high, intention phi = beta + pi (dashed)", ys: t.p_high, dash: "dashed", cls: "fwo-c-line--band" },
        { label: "connection in bits (dash-dot)", ys: t.connection_bits, dash: "dashdot", cls: "fwo-c-line--connection" },
      ],
      point: { x: d.world_coupling, y: Math.cos(d.world_coupling * Math.PI / 2), label: "your draft's coupling on the capacity curve (filled diamond)" },
    };
    renderLines(dom, el.curve, cfg);
    renderLineLegend(dom, el.curveLegend, cfg);
  }

  function describeCurve() {
    const t = curves.theory;
    el.curveSummary.textContent = txt.curveSummary(dom, t, curves.noise);
    const rows = t.w.map((w, i) => [fmt(w, 2), fmt(t.capacity[i], 4), fmt(t.p_low[i], 4), fmt(t.p_high[i], 4),
      fmt((t.openness_bits || [])[i], 4), fmt((t.connection_bits || [])[i], 4)]);
    replace(el.curveTable, table("Theory curves (" + rows.length + " points; intention and perspective at their defaults)",
      ["w", "capacity", "P_low", "P_high", "openness (bits)", "connection (bits)"], rows, { tall: true }));
    const p = t.provenance;
    el.curveProv.textContent = p
      ? "Precomputed by " + p.generator + " at commit " + p.git_commit + " on a " + p.machine + " (" + p.created_utc + "): exact values, no sampling."
      : "Source: " + (t.source || "unknown") + ".";
  }

  // ---------------------------------------------------------------- backend badge
  // `true`: this page load is a new Qollab run, so Python starts a fresh one-job
  // budget even if the interpreter was reused. Nothing else ever passes `true`.
  profile = BACKEND === null
    ? { error: "no backend was injected into main.js" }
    : await callPy(api.profile_json, "profile_json", BACKEND, true);
  const name = profile.error ? backendName(BACKEND) || "this backend" : (profile.profile && profile.profile.name) || "backend";
  renderBadge(dom, profile, byId("fwo-badge-list"), byId("fwo-badge-policy"), backendName(BACKEND));
  oneJob = !!profile.error || !!profile.one_job;
  if (!profile.error && profile.mode) el.mode.options[0].textContent = "auto (" + profile.mode + " on this backend)";
  el.runPolicy.textContent = oneJob
    ? "One job per run on this backend: the button locks after one press."
    : "No job limit on this local simulator: each press submits one job of four probes.";

  // ---------------------------------------------------------------- run
  function lockRun() {
    el.run.disabled = true;
    el.lock.hidden = false;
    el.lock.textContent = (profile.error
      ? "Run is now disabled: the backend profile could not be read, so this page allows one press per run"
      : "Run is now disabled: this backend accepts one job per run and this page has used its one press") +
      ". To submit another job, run the project again.";
    el.lock.setAttribute("tabindex", "-1");
    el.lock.focus();
  }

  let ticking = false;
  function startTicker(t0) {
    ticking = true;
    el.progress.hidden = false;
    const tick = () => {
      if (!ticking) return;
      el.progress.textContent = "Live simulator: waiting for the job\u2026 " + ((Date.now() - t0) / 1000).toFixed(1) + " s";
      setTimeout(tick, 250);
    };
    tick();
  }
  function stopTicker() {
    ticking = false;
    el.progress.hidden = true;
  }

  function showResult(run, secs) {
    previous = current;
    current = run;
    const m = run.metrics || {};
    const expl = run.explanation || {};
    renderFutures(dom, { f0: el.future0, f1: el.future1 }, current, previous, null);
    renderReadings(dom, txt, el.readings, current);
    drawChart();
    describeChart();
    el.factual.textContent = expl.factual || txt.factualFallback(dom, run);
    writePoetic();
    if (expl.note) el.personaNote.textContent = expl.note + " Switching persona changes the interpretation only, never the data.";
    renderDemonCompare(dom, el.demonCompare, current);
    renderBaselines(dom, el.baselines, run.baselines);
    renderDrawer(dom, txt, el.howBody, current, profile);
    if (scene.available) {
      scene.setResult(current, previous, futureLabels(current, previous));
      scene.setLabel(txt.sceneLabel(dom, current, previous));
    }
    el.sceneCaption.textContent = (scene.available ? "Scene: " : "The 3D view is unavailable here; it would show ") +
      "Future 0 " + fmtPct(1 - m.p_self_1) + ", Future 1 " + fmtPct(m.p_self_1) +
      " from the display probe; World bridge " + fmt(m.connection_bits, 2) + " bits (" + txt.bridgeWord(m.connection_bits) + ") from the connection probe" +
      (previous ? "; the previous run (" + fmtPct(1 - previous.metrics.p_self_1) + " / " + fmtPct(previous.metrics.p_self_1) + ") is the faint wireframe labelled previous." : ".") +
      " Decorative nodes suggest a brain; they are not qubits or neurons.";
    const check = (run.source || {}).bit_order_check || {};
    const warn = check.orientation_ok === false ? " WARNING: the bit-order canary failed; the counts are not trustworthy." : "";
    status("Done in " + secs + " s: " + txt.capacitySentence(dom, m) + " Openness " + fmt(m.openness_bits, 3) + " bits, connection " +
      fmt(m.connection_bits, 3) + " bits." + warn, !!warn);
  }

  el.run.addEventListener("click", async () => {
    if (running || el.run.disabled || (oneJob && jobsUsed >= 1)) return;
    const shots = readShots();
    if (shots === null) {
      el.shots.setAttribute("aria-invalid", "true");
      el.shotsHelp.textContent = "Enter a whole number of shots from 1 to 4,096.";
      status("Not submitted: shots per probe must be a whole number from 1 to 4,096.", true);
      el.shots.focus();
      return;
    }
    running = true;
    jobsUsed += 1;
    if (oneJob) lockRun();
    else el.run.setAttribute("aria-disabled", "true");
    replace(el.runError);
    const draft = readDraft();
    status("Submitting one job to " + name + ": four probes" + (draft.canary ? " plus the canary" : "") + ", " + fmtInt(shots) +
      " shots per probe (" + txt.draftText(dom, draft) + ")\u2026");
    const t0 = Date.now();
    startTicker(t0);
    const run = BACKEND === null
      ? { status: "failed", error: "no backend was injected into main.js", source: {} }
      : await callPy(api.run_json, "run_json", BACKEND, JSON.stringify(draft));
    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    stopTicker();
    running = false;
    if (!oneJob) el.run.removeAttribute("aria-disabled");
    if (oneJob) {
      const src = run.source || {};
      el.lock.textContent += run.status === "completed" || src.job_returned ? " (A job was submitted, so this run's one job is used.)"
        : run.error && /one-job guard|no backend/.test(run.error) ? " (No job reached the backend.)" : " (A submission was attempted.)";
    }
    try {
      if (run.status !== "completed") {
        const r = run.error ? run : Object.assign({ error: "the engine returned no status" }, run);
        renderRunError(dom, el.runError, r, current && current.source ? current.source.job_id : null);
        status("The run failed after " + secs + " s: " + r.error, true);
        return;
      }
      showResult(run, secs);
    } catch (err) {
      status("The job finished, but its result could not be shown: " + errText(err), true);
    }
  });

  // ---------------------------------------------------------------- initial views
  renderFutures(dom, { f0: el.future0, f1: el.future1 }, null, null, null);
  renderReadings(dom, txt, el.readings, null);
  renderDemonCompare(dom, el.demonCompare, null);
  renderDrawer(dom, txt, el.howBody, null, profile);

  // Redraw the scene and the SVG charts at their new pixel width. A throttle with a
  // trailing run (not a pure debounce) so a burst of size changes can never starve
  // it; the charts are only rebuilt when their container width really changed.
  let drawnChartW = 0, drawnCurveW = 0, redrawPending = false;
  function redraw() {
    if (scene.available) scene.resize();
    if (el.chart.clientWidth !== drawnChartW) { drawnChartW = el.chart.clientWidth; drawChart(); }
    if (el.curve.clientWidth !== drawnCurveW) { drawnCurveW = el.curve.clientWidth; drawCurve(); }
  }
  function scheduleRedraw() {
    if (redrawPending) return;
    redrawPending = true;
    setTimeout(() => { redrawPending = false; redraw(); }, 150);
  }
  drawnChartW = el.chart.clientWidth;
  drawnCurveW = el.curve.clientWidth;
  if (typeof ResizeObserver !== "undefined") {
    const ro = new ResizeObserver(() => scheduleRedraw());
    ro.observe(el.sceneHost);
    ro.observe(el.chart);
    ro.observe(el.curve);
  }
  try { addEventListener("resize", scheduleRedraw); } catch (err) { /* no window: the observer alone */ }

  // A failure in the forecast or the curves must not leave Run disabled.
  let problem = "";
  try {
    status("Computing the Demon's forecast\u2026");
    await refreshForecast();
    status("Loading the theoretical curves\u2026");
    curves = await callPy(api.curves_json, "curves_json");
    if (curves.error) {
      el.curveSummary.textContent = "The theoretical curves are unavailable: " + curves.error;
    } else {
      describeCurve();
      drawCurve();
      renderCoverage(dom, el.coverage, curves);
    }
    const base = forecast && forecast.baselines ? forecast.baselines : null;
    renderBaselines(dom, el.baselines, base);
  } catch (err) {
    problem = " Part of the page could not load: " + errText(err) + ".";
  }

  el.run.disabled = false;
  if (profile.error) {
    status("The backend profile is unavailable (" + profile.error + "). The forecast and curves work; Run allows at most one job on this page." + problem, true);
  } else {
    status("Ready. Backend: " + name + (oneJob ? " (one job per run)." : " (no job limit).") +
      " Set an intention, a World coupling and a perspective, then press Run experiment." + problem, !!problem);
  }
}

try {
  await start();
} catch (err) {
  status("The page could not start: " + errText(err), true);
}

// Keep main.js running: IonQ requests only route while it is alive.
await new Promise(() => {});
