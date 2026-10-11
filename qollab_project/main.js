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
// The page reads top to bottom as three steps (pick a guide, set the dials, run),
// then the results in plain words, then optional detail panels.
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
import { createPlate } from "./ui/plate.js";
import { EGGS } from "./ui/eggs.js";
import { createEggStage } from "./ui/egg.js";
import { createDialogue } from "./ui/dialogue.js";
import { SPRITES } from "./ui/sprites.js";
import { renderBars, renderBarLegend, renderLines, renderLineLegend } from "./ui/chart.js";
import { renderFutures, renderReadings, renderRunError, renderDemonForecast, renderDemonCompare, renderBaselines, renderRecord, renderHow, renderSure, renderHonesty, renderCoverage, personaName } from "./ui/readings.js";

const { byId, replace, fmt, fmtInt, fmtRad, table } = dom;
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

// Theme flags for the 3D view: a transparent canvas (the panel's CSS background shows through)
// and soft halos behind the spheres. Set by a theme as --fwo-scene-transparent: 1 / --fwo-scene-halo: 1.
function sceneFlags(appEl) {
  const out = { transparent: false, halo: false };
  try {
    const cs = getComputedStyle(appEl);
    out.transparent = cs.getPropertyValue("--fwo-scene-transparent").trim() === "1";
    out.halo = cs.getPropertyValue("--fwo-scene-halo").trim() === "1";
  } catch (err) { /* defaults */ }
  return out;
}

// Scene colours come from CSS variables, so a theme in main.css recolours the 3D view too.
function sceneColors(appEl) {
  const keys = { bg: "bg", self: "self", selfLight: "self-light", selfDeep: "self-deep", world: "world",
    worldLight: "world-light", worldDeep: "world-deep", ghost: "ghost", link: "link" };
  const out = {};
  try {
    const cs = getComputedStyle(appEl);
    for (const [k, v] of Object.entries(keys)) {
      const val = cs.getPropertyValue("--fwo-scene-" + v).trim();
      if (/^#[0-9a-fA-F]{6}$/.test(val)) out[k] = val;
    }
  } catch (err) { /* defaults in ui/scene.js */ }
  return out;
}

// A theme can ask for one of the flat drawn scenes (ui/plate.js) instead of the 3D view:
// --fwo-scene-plate: a | b | c | d (the four design directions). Unset: the 3D view.
function scenePlate(appEl) {
  try {
    const v = getComputedStyle(appEl).getPropertyValue("--fwo-scene-plate").trim();
    return /^[abcd]$/.test(v) ? v : "";
  } catch (err) {
    return "";
  }
}

async function start() {
  // Generous: the imports (Pyodide loading observatory_api, three.js) may already have taken a while.
  await dom.whenMounted("fwo-app", setTimeout, 60000);
  statusEl = byId("fwo-status");
  status("Loading the simulator profile\u2026");

  // ---------------------------------------------------------------- elements
  const el = {
    app: byId("fwo-app"),
    intention: byId("fwo-intention"), intentionOut: byId("fwo-intention-out"),
    coupling: byId("fwo-coupling"), couplingOut: byId("fwo-coupling-out"),
    perspective: byId("fwo-perspective"), perspectiveOut: byId("fwo-perspective-out"),
    shots: byId("fwo-shots"), shotsHelp: byId("fwo-shots-help"), mode: byId("fwo-mode"), canary: byId("fwo-canary"),
    draft: byId("fwo-draft"), run: byId("fwo-run"), runPolicy: byId("fwo-run-policy"), progress: byId("fwo-progress"),
    lock: byId("fwo-run-lock"), runError: byId("fwo-run-error"),
    sceneHost: byId("fwo-scene-host"), sceneCaption: byId("fwo-scene-caption"), motion: byId("fwo-motion"), motionHelp: byId("fwo-motion-help"),
    future0: byId("fwo-future-0"), future1: byId("fwo-future-1"), readings: byId("fwo-readings"),
    chart: byId("fwo-chart"), chartSummary: byId("fwo-chart-summary"), chartLegend: byId("fwo-chart-legend"), chartTable: byId("fwo-chart-table"),
    factual: byId("fwo-factual"), record: byId("fwo-record"), poetic: byId("fwo-poetic"), personaNote: byId("fwo-persona-note"),
    baselines: byId("fwo-baselines"),
    dialogue: byId("fwo-dialogue"), dialoguePortrait: byId("fwo-dialogue-portrait"), portraitWho: byId("fwo-portrait-who"),
    dialogueName: byId("fwo-dialogue-name"), dialogueText: byId("fwo-dialogue-text"), dialogueSkip: byId("fwo-dialogue-skip"),
    sceneSkip: byId("fwo-scene-skip"), sceneHint: byId("fwo-scene-hint"),
    styleButton: byId("fwo-style-btn"), stylePanel: byId("fwo-style-panel"), styleClose: byId("fwo-style-close"), egg: byId("fwo-egg"), eggBucket: byId("fwo-egg-bucket"), eggSelf: byId("fwo-egg-self"),
    sound: byId("fwo-sound"), soundHelp: byId("fwo-sound-help"),
    howBody: byId("fwo-how-body"), sureBody: byId("fwo-sure-body"), honesty: byId("fwo-honesty"),
    curve: byId("fwo-curve"), curveSummary: byId("fwo-curve-summary"), curveLegend: byId("fwo-curve-legend"),
    curveTable: byId("fwo-curve-table"), coverage: byId("fwo-coverage"), curveProv: byId("fwo-curve-prov"),
    selfText: byId("fwo-persona-self"), demonLine: byId("fwo-demon-line"), observerText: byId("fwo-observer-text"),
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
  let dialogue = null;       // the RPG-style box; created once the reduced-motion preference is known
  // What each guide currently says, and the animation it plays saying it: its greeting, then
  // its reaction to the last dial it can see, its reading of the last run, or the failure.
  // A tab switch re-shows the selected guide's current line (design/persona-dialogue.md).
  const say = {};
  for (const k of PERSONAS) say[k] = { line: txt.INTRO[k], action: "idle" };
  let sceneExitTo = null;    // a tab clicked during the opening cutscene: where the scene ends

  // ---------------------------------------------------------------- guides (persona tabs)
  // The one dialogue box moves into the selected guide's panel, so each tab really
  // controls the panel holding what that guide says.
  function moveDialogue(key) {
    const panel = byId("fwo-panel-" + key);
    if (panel && el.dialogue.parentNode !== panel) panel.insertBefore(el.dialogue, panel.firstChild);
  }
  const tabs = createTabs(dom, PERSONAS.map((key) => ({ key, tab: byId("fwo-tab-" + key), panel: byId("fwo-panel-" + key) })),
    (key) => {
      if (dialogue) {
        dialogue.unlock();
        if (dialogue.inScene) { sceneExitTo = key; dialogue.skipScene(); sceneExitTo = null; return; }
      }
      persona = key; moveDialogue(key); schedulePoetic();
    });

  // What the selected guide says: its greeting before any run, its reading of the
  // result after one. The polite live region is written once per line (debounced on
  // tab changes, so arrowing through the tabs announces one line, not three).
  function writePoetic(opts) {
    const now = say[persona] || { line: "", action: "idle" };
    if (dialogue) {
      if (dialogue.inScene) return;     // the opening cutscene holds the box until it ends
      dialogue.show(persona, personaName(persona), now.line || "", Object.assign({ action: now.action }, opts || {}));   // writes the live region once
      return;
    }
    el.poetic.textContent = now.line ? personaName(persona) + ": " + now.line : "";
  }
  const schedulePoetic = dom.debounce(writePoetic, 250, setTimeout);

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
    el.intentionOut.textContent = txt.plainDeg(dom, phi);
    el.intention.setAttribute("aria-valuetext", txt.plainDeg(dom, phi) + " (phi = " + fmtRad(phi) + ")");
    el.couplingOut.textContent = fmt(w, 2) + " \u00b7 " + txt.couplingWord(w);
    el.coupling.setAttribute("aria-valuetext", fmt(w, 2) + ", " + txt.couplingWord(w) + " (w = " + fmt(w, 2) + ", gamma = " + fmtRad(w * Math.PI / 2) + ")");
    el.perspectiveOut.textContent = txt.plainDeg(dom, beta);
    el.perspective.setAttribute("aria-valuetext", txt.plainDeg(dom, beta) + " (beta = " + fmtRad(beta) + ")");
    el.draft.textContent = "Technical draft: " + txt.draftText(dom, readDraft()) + ".";
  }

  function describePersonas() {
    const d = readDraft();
    const ideal = forecast && forecast.ideal ? forecast.ideal : null;
    el.selfText.textContent = txt.selfTip(dom, d, ideal);
    el.demonLine.textContent = txt.demonLine(dom, ideal);
    el.observerText.textContent = txt.observerTip(dom, d, ideal);
  }

  async function refreshForecast() {
    const mine = ++forecastSeq;
    const d = readDraft();
    const f = await callPy(api.predict_json, "predict_json", JSON.stringify(d));
    if (mine !== forecastSeq) return;        // a newer draft is already on its way
    forecast = f.error ? null : f;
    renderDemonForecast(dom, el.demonForecast, f, txt.draftText(dom, d));
    describePersonas();
    if (!current) {
      drawChart(); describeChart();
      renderFutures(dom, { f0: el.future0, f1: el.future1 }, null, null, forecast ? forecast.ideal : null);
    }
    drawCurve();
    if (!forecast) status("The Demon's forecast failed: " + f.error, true);
  }
  const scheduleForecast = dom.debounce(refreshForecast, 150, setTimeout);

  for (const input of [el.intention, el.coupling, el.perspective]) {
    input.addEventListener("input", () => {
      syncOutputs();
      scheduleForecast();
    });
  }
  // A released dial (design/persona-dialogue.md section 3): each guide that can see that dial
  // reacts, with the Demon's law for the new draft; the others keep their line. The shown
  // guide speaks its new line if it reacted.
  const released = new Set();
  const flushReactions = dom.debounce(() => {
    const d = readDraft();
    const f = txt.idealFor(d);
    const before = say[persona];
    for (const input of ["intention", "coupling", "perspective"]) {
      if (released.has(input)) Object.assign(say, txt.inputReactions(dom, input, d, f));
    }
    released.clear();
    if (!running && say[persona] !== before) writePoetic();
  }, 600, setTimeout);
  for (const [key, input] of [["intention", el.intention], ["coupling", el.coupling], ["perspective", el.perspective]]) {
    input.addEventListener("change", () => { released.add(key); flushReactions(); });
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

  // ---------------------------------------------------------------- dialogue + scene
  const reduced = prefersReducedMotion();
  if (el.dialogue && el.dialogueName && el.dialogueText) {
    try {
      dialogue = createDialogue(dom, {
        box: el.dialogue, portrait: el.dialoguePortrait, portraitWho: el.portraitWho, name: el.dialogueName,
        text: el.dialogueText, skip: el.dialogueSkip, live: el.poetic, sound: el.sound, soundHelp: el.soundHelp,
        sceneSkip: el.sceneSkip, sceneHint: el.sceneHint,
      }, { reducedMotion: reduced, setTimeoutFn: setTimeout, seed: 20261011, sprites: SPRITES });
      // The opening cutscene (design/persona-cutscene.md): the guides argue over the Demon's
      // sealed forecast for the starting dials. The selected tab follows the speaker; at the
      // end (or on a skip) the box slides back to the Self, or to the tab that was clicked.
      const law = txt.idealFor(readDraft());
      const lines = txt.openingScene(dom, Number.isFinite(law.p) && Number.isFinite(law.C) ? law : null)
        .map((L) => Object.assign({ name: personaName(L.persona) }, L));
      const follow = (key) => { tabs.select(key, false, true); persona = key; moveDialogue(key); };
      dialogue.play(lines, {
        onLine: (L) => follow(L.persona),
        onDone: () => { follow(sceneExitTo || "self"); writePoetic({ slide: true }); },
      });
    } catch (err) {
      dialogue = null;   // the plain live-region line still works
      console.warn("[observatory] dialogue box unavailable: " + err);
    }
  }
  // The scene follows the page style: each style draws its own plate (ui/plate.js); with no
  // style set, the 3D view.
  function makeScene() {
    const plateStyle = scenePlate(el.app);
    return plateStyle
      ? createPlate(dom, el.sceneHost, { style: plateStyle, reducedMotion: reduced, setTimeoutFn: setTimeout })
      : createScene(THREE, dom, el.sceneHost, Object.assign({ reducedMotion: reduced, setTimeoutFn: setTimeout, colors: sceneColors(el.app) }, sceneFlags(el.app)));
  }
  let scene = makeScene();
  el.motion.checked = !reduced;
  if (reduced) el.motionHelp.textContent = "Your system asks for reduced motion, so animation is off; tick to allow it anyway.";
  el.motion.addEventListener("change", () => { if (scene.available) scene.setMotion(el.motion.checked); });
  if (scene.available) {
    scene.setMotion(!reduced);
    scene.setLabel(txt.sceneLabel(dom, null, null));
  } else {
    // No WebGL: the text, readings and tables carry everything; nothing to animate.
    el.motion.checked = false;
    el.motion.disabled = true;
    el.motionHelp.textContent = "The 3D picture is unavailable in this browser; every value it would show is in the text.";
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
          ? "Your system asks for reduced motion, so animation is off; tick to allow it anyway."
          : "Decoration only; the numbers never move with it.";
      });
    }
  } catch (err) { /* older browsers: the initial preference still applies */ }

  // ---------------------------------------------------------------- page style (A to D)
  // The four design directions ship in main.css, scoped by data-theme on #fwo-app (D by
  // default in index.html). The Style panel changes the attribute and redraws the scene in
  // the new style with the current result; nothing else is recomputed.
  function setStyle(key) {
    if (!/^[abcd]$/.test(key) || el.app.dataset.theme === key) return;
    el.app.dataset.theme = key;
    if (scene && scene.dispose) scene.dispose();
    scene = makeScene();
    if (scene.available) {
      scene.setMotion(el.motion.checked);
      scene.setLabel(txt.sceneLabel(dom, current, previous));
      if (current) scene.setResult(current, previous, futureLabels(current, previous));
    }
    if (dialogue) dialogue.refresh();
  }
  // The Style button opens a side panel with the four style buttons; the pressed one is the
  // page's style. Escape, the close button or the Style button again closes it, and focus
  // returns to the Style button.
  // The easter egg at the foot of the panel: the Self idles under a bucket of water; press the
  // bucket and it pours on him (ui/egg.js). It runs only while the panel is open.
  const egg = createEggStage({ button: el.egg, bucket: el.eggBucket, self: el.eggSelf },
    { idle: SPRITES.self.idle, angry: EGGS.angry, bucket: EGGS.bucket },
    { reducedMotion: reduced, setTimeoutFn: setTimeout, clearTimeoutFn: clearTimeout });
  const styleOptions = Array.from(el.stylePanel.querySelectorAll("[data-style]"));
  function markStyle() {
    for (const b of styleOptions) b.setAttribute("aria-pressed", b.dataset.style === el.app.dataset.theme ? "true" : "false");
  }
  function showStyles(open) {
    el.stylePanel.hidden = !open;
    el.styleButton.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) egg.start(); else egg.stop();
    if (open) (styleOptions.find((b) => b.getAttribute("aria-pressed") === "true") || el.styleClose).focus();
    else el.styleButton.focus();
  }
  el.styleButton.addEventListener("click", () => showStyles(el.stylePanel.hidden));
  el.styleClose.addEventListener("click", () => showStyles(false));
  el.stylePanel.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    ev.stopPropagation();          // the opening cutscene's Escape is not this one
    showStyles(false);
  });
  for (const b of styleOptions) b.addEventListener("click", () => { setStyle(b.dataset.style); markStyle(); });
  markStyle();


  function futureLabels(run, prev) {
    const p1 = run.metrics.p_self_1;
    const out = { f1: "Future 1 \u00b7 " + dom.fmtPct(p1), f0: "Future 0 \u00b7 " + dom.fmtPct(1 - p1), prev1: "", prev0: "" };
    if (prev && prev.metrics) {
      out.prev1 = "previous " + dom.fmtPct(prev.metrics.p_self_1);
      out.prev0 = "previous " + dom.fmtPct(1 - prev.metrics.p_self_1);
    }
    return out;
  }

  // ---------------------------------------------------------------- charts (in the detail panels)
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
      title: "Before and after: the chance of Future 0 and Future 1 for the previous run, this run and the Demon's forecast",
      desc: txt.chartSummary(dom, current, previous, forecastFor),
      groups: [0, 1].map((i) => ({ label: "Future " + i, bars: barsFor(i) })),
    });
    const items = [];
    if (previous) items.push({ kind: "previous", label: "previous run (hatched)" });
    if (current) items.push({ kind: "current", label: "this run (solid)" });
    items.push({ kind: "forecast", label: (current ? "Demon forecast for this run" : "Demon forecast for your dials") + " (outlined, dashed)" });
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
        current ? pick(current.prediction.p_self_1) : (forecastFor ? pick(forecastFor.p_self_1) + " (your dials)" : "n/a")]);
    }
    replace(el.chartTable, table("Chances shown in the chart", ["future", "previous run", "this run", "Demon forecast"], rows));
  }

  function drawCurve() {
    if (!curves || curves.error || !curves.theory || !curves.theory.w) return;
    const t = curves.theory;
    const d = readDraft();
    const cfg = {
      id: "fwo-theory",
      title: "Theory: the most a choice can swing the odds, the two opposite-choice chances, and what the World knows, against the ties to the world w",
      desc: txt.curveSummary(dom, t, curves.noise),
      xLabel: "ties to the world w (gamma = w pi / 2)", yLabel: "value (0 to 1)",
      xs: t.w,
      series: [
        { label: "most a choice can swing the odds, cos(gamma) (solid)", ys: t.capacity, dash: "solid", cls: "fwo-c-line--capacity" },
        { label: "chance of Future 1 with choice = point of view (dashed)", ys: t.p_low, dash: "dashed", cls: "fwo-c-line--band" },
        { label: "chance of Future 1 with the opposite choice (dashed)", ys: t.p_high, dash: "dashed", cls: "fwo-c-line--band" },
        { label: "what the World knows, in bits (dash-dot)", ys: t.connection_bits, dash: "dashdot", cls: "fwo-c-line--connection" },
      ],
      point: { x: d.world_coupling, y: Math.cos(d.world_coupling * Math.PI / 2), label: "your dials on the swing curve (filled diamond)" },
    };
    renderLines(dom, el.curve, cfg);
    renderLineLegend(dom, el.curveLegend, cfg);
  }

  function describeCurve() {
    const t = curves.theory;
    el.curveSummary.textContent = txt.curveSummary(dom, t, curves.noise);
    const rows = t.w.map((w, i) => [fmt(w, 2), fmt(t.capacity[i], 4), fmt(t.p_low[i], 4), fmt(t.p_high[i], 4),
      fmt((t.openness_bits || [])[i], 4), fmt((t.connection_bits || [])[i], 4)]);
    replace(el.curveTable, table("Theory curves (" + rows.length + " points; choice and point of view at their defaults)",
      ["w", "capacity", "P_low", "P_high", "openness (bits)", "connection (bits)"], rows, { tall: true }));
    const p = t.provenance;
    el.curveProv.textContent = p
      ? "Precomputed by " + p.generator + " at commit " + p.git_commit + " on a " + p.machine + " (" + p.created_utc + "): exact values, no sampling."
      : "Source: " + (t.source || "unknown") + ".";
  }

  // ---------------------------------------------------------------- the simulator
  // `true`: this page load is a new Qollab run, so Python starts a fresh one-job
  // budget even if the interpreter was reused. Nothing else ever passes `true`.
  profile = BACKEND === null
    ? { error: "no backend was injected into main.js" }
    : await callPy(api.profile_json, "profile_json", BACKEND, true);
  const name = profile.error ? backendName(BACKEND) || "this backend" : (profile.profile && profile.profile.name) || "backend";
  renderBadge(dom, profile, byId("fwo-badge-list"), byId("fwo-badge-policy"), backendName(BACKEND));
  oneJob = !!profile.error || !!profile.one_job;
  if (!profile.error && profile.mode) el.mode.options[0].textContent = "automatic (" + profile.mode + " on this simulator)";
  el.runPolicy.textContent = txt.runPolicy(profile, oneJob);

  // ---------------------------------------------------------------- run
  function lockRun() {
    el.run.disabled = true;
    el.lock.hidden = false;
    el.lock.textContent = (profile.error
      ? "The button is now locked: the simulator profile could not be read, so this page allows one press per visit"
      : "The button is now locked: this simulator accepts one job per visit and this page has used it") +
      ". To run again, start the project again.";
    el.lock.setAttribute("tabindex", "-1");
    el.lock.focus();
  }

  let ticking = false;
  function startTicker(t0) {
    ticking = true;
    el.progress.hidden = false;
    const tick = () => {
      if (!ticking) return;
      el.progress.textContent = "Running on the simulator\u2026 " + ((Date.now() - t0) / 1000).toFixed(1) + " s";
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
    // each guide's reading of the run, and its animation (observatory.explanation)
    const acts = expl.animation || {};
    for (const k of PERSONAS) {
      if (expl.poetic && expl.poetic[k]) say[k] = { line: expl.poetic[k], action: acts[k] || "idle" };
    }
    renderFutures(dom, { f0: el.future0, f1: el.future1 }, current, previous, null);
    renderReadings(dom, txt, el.readings, current);
    drawChart();
    describeChart();
    el.factual.textContent = expl.factual || txt.factualFallback(dom, run);
    writePoetic();
    renderDemonCompare(dom, el.demonCompare, current);
    renderBaselines(dom, el.baselines, run.baselines);
    renderRecord(dom, txt, el.record, current, profile);
    renderHow(dom, txt, el.howBody, current);
    if (scene.available) {
      scene.setResult(current, previous, futureLabels(current, previous));
      scene.setLabel(txt.sceneLabel(dom, current, previous));
    }
    el.sceneCaption.textContent = txt.sceneCaption(dom, current, previous, scene.available);
    const check = (run.source || {}).bit_order_check || {};
    const warn = check.orientation_ok === false ? " WARNING: the self-check failed; the counts are not trustworthy." : "";
    status(txt.doneSentence(dom, m, secs) + warn, !!warn);
  }

  el.run.addEventListener("click", async () => {
    if (dialogue) dialogue.unlock();   // the gesture that allows audio later
    if (running || el.run.disabled || (oneJob && jobsUsed >= 1)) return;
    const shots = readShots();
    if (shots === null) {
      el.shots.setAttribute("aria-invalid", "true");
      el.shotsHelp.textContent = "Enter a whole number of shots from 1 to 4,096.";
      status("Not run: the shots per circuit (under Advanced run settings) must be a whole number from 1 to 4,096.", true);
      el.shots.focus();
      return;
    }
    running = true;
    jobsUsed += 1;
    if (oneJob) lockRun();
    else el.run.setAttribute("aria-disabled", "true");
    // a run in flight: every guide keeps its line, at rest (the cutscene ends here if it still plays)
    if (dialogue && dialogue.inScene) dialogue.skipScene();
    for (const k of PERSONAS) say[k] = { line: say[k].line, action: "idle" };
    if (dialogue) dialogue.setAction("idle");
    replace(el.runError);
    const draft = readDraft();
    status("Running one job on " + name + ": four tiny circuits" + (draft.canary ? " plus the self-check" : "") + ", " +
      fmtInt(shots) + " shots each\u2026");
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
      el.lock.textContent += run.status === "completed" || src.job_returned ? " (A job was submitted, so this visit's one job is used.)"
        : run.error && /one-job guard|no backend/.test(run.error) ? " (No job reached the simulator.)" : " (A submission was attempted.)";
    }
    try {
      if (run.status !== "completed") {
        const r = run.error ? run : Object.assign({ error: "the engine returned no status" }, run);
        renderRunError(dom, el.runError, r, current && current.source ? current.source.job_id : null);
        Object.assign(say, txt.FAILURE);
        writePoetic();
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
  renderRecord(dom, txt, el.record, null, profile);
  renderHow(dom, txt, el.howBody, null);
  renderSure(dom, el.sureBody);
  renderHonesty(dom, txt, el.honesty);

  // Redraw the scene and the SVG charts at their new pixel width. A throttle with a
  // trailing run (not a pure debounce) so a burst of size changes can never starve
  // it; the charts are only rebuilt when their container width really changed (they
  // sit in closed detail panels at first, so opening one triggers a redraw).
  let drawnChartW = 0, drawnCurveW = 0, redrawPending = false;
  function redraw() {
    if (scene.available) scene.resize();
    if (dialogue) dialogue.refresh();
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
  for (const d of el.app.querySelectorAll("details")) d.addEventListener("toggle", scheduleRedraw);
  try { addEventListener("resize", scheduleRedraw); } catch (err) { /* no window: the observer alone */ }

  // A failure in the forecast or the curves must not leave Run disabled.
  let problem = "";
  try {
    status("Working out the Demon's forecast\u2026");
    await refreshForecast();
    status("Loading the theory curves\u2026");
    curves = await callPy(api.curves_json, "curves_json");
    if (curves.error) {
      el.curveSummary.textContent = "The theory curves are unavailable: " + curves.error;
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
    status("The simulator profile is unavailable (" + profile.error + "). The forecast works; Run allows one job on this page." + problem, true);
  } else {
    status("Ready on " + name + ". Pick a guide, set the dials, then press Run." + problem, !!problem);
  }
}

try {
  await start();
} catch (err) {
  status("The page could not start: " + errText(err), true);
}

// Keep main.js running: IonQ requests only route while it is alive.
await new Promise(() => {});
