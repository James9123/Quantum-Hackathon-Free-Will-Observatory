// Sentences the page shows or announces. Pure functions of the API replies, so the
// same words appear on screen, in the canvas's aria-label and in the console.
// No imports: main.js passes the dom helpers in.

export const HONESTY = "A simulator computes what quantum theory predicts, and how a noise model degrades it. " +
  "It does not test nature. The readings are a designed, fictional model of agency: capacity is not proof of free will, " +
  "and a responsive classical system can score highly on it too.";

export const PROBES = ["display", "intent_low", "intent_high", "connection"];

export const NO_RESOLVED = "No resolved influence at this shot count.";

export const PROBE_TEXT = {
  display: "display: the user's phi, gamma and beta; full circuit. Drives the visible future distribution.",
  intent_low: "intent_low: phi = beta, same gamma and beta. One end of the accessible probability range.",
  intent_high: "intent_high: phi = beta + pi, same gamma and beta. The opposite end of that range.",
  connection: "connection: the user's phi and gamma, no final RZ(-beta) or H; both qubits measured in Z. Shared information in a fixed reference basis.",
};

function deg(lib, rad) {
  return lib.fmtDeg(rad);
}

function num(m, key) {
  const v = m ? m[key] : null;
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

// The guide's wording for capacity, with the resolved / unresolved sentence.
export function capacitySentence(lib, metrics) {
  const { fmt } = lib;
  const c = num(metrics, "capacity");
  const ci = metrics && Array.isArray(metrics.capacity_ci95) ? metrics.capacity_ci95 : [null, null];
  const head = "Capacity " + fmt(c, 2) + "; conservative 95% interval " + fmt(ci[0], 2) + " to " + fmt(ci[1], 2) + ".";
  if (metrics && metrics.resolved) {
    return head + " The interval excludes zero: in this model, opposite intentions measurably reshaped the odds.";
  }
  return head + " " + NO_RESOLVED;
}

export function bridgeWord(I) {
  if (I === null) return "unknown";
  if (I < 0.05) return "almost none";
  if (I < 0.35) return "faint";
  if (I < 0.75) return "clear";
  return "strong";
}

function totalShots(counts) {
  if (!counts) return null;
  let n = 0;
  for (const v of Object.values(counts)) n += Number(v) || 0;
  return n;
}

// aria-label for the canvas, rewritten after every completed run.
export function sceneLabel(lib, run, prev) {
  const { fmt, fmtPct, fmtInt } = lib;
  if (!run) {
    return "Observatory scene before any run: a brain-shaped graph of decorative nodes (the fictional Self), " +
      "two placeholder future spheres drawn as faint wireframes labelled no run yet, and a faint bridge to the World sphere. " +
      "Press Run experiment to fill it with a measured distribution.";
  }
  const m = run.metrics || {};
  const p1 = num(m, "p_self_1");
  const p0 = p1 === null ? null : 1 - p1;
  const I = num(m, "connection_bits");
  const n = totalShots(run.counts && run.counts.display);
  let s = "Observatory scene after the run: Future 0 (Self = 0, lower right sphere) holds " + fmtPct(p0) +
    " and Future 1 (Self = 1, upper right sphere) holds " + fmtPct(p1) + " of the display probe's " + fmtInt(n) +
    " shots; sphere volume and branch thickness follow those probabilities. The World bridge carries " +
    fmt(I, 2) + " bits of connection (" + bridgeWord(I) + ") from the separate connection probe.";
  if (prev && prev.metrics) {
    const q1 = num(prev.metrics, "p_self_1");
    s += " The previous run (" + fmtPct(q1 === null ? null : 1 - q1) + " / " + fmtPct(q1) +
      ") is drawn as a faint wireframe labelled previous.";
  }
  return s + " The brain nodes and the particle stream are decorative and carry no data beyond these proportions.";
}

export function draftText(lib, d) {
  const { fmt } = lib;
  return "intention " + deg(lib, d.intention_rad) + " (" + fmt(d.intention_rad, 3) + " rad), World coupling " +
    fmt(d.world_coupling, 2) + " (gamma = " + deg(lib, d.world_coupling * Math.PI / 2) + "), perspective " +
    deg(lib, d.perspective_rad) + " (" + fmt(d.perspective_rad, 3) + " rad), " + lib.fmtInt(d.shots_per_probe) +
    " shots per probe";
}

// The Self tab: what the draft is and what the Demon expects of it.
export function selfDraftText(lib, draft, ideal) {
  const { fmt } = lib;
  let s = "Draft: " + draftText(lib, draft) + ".";
  if (ideal) {
    s += " For this draft the Demon forecasts P(Self = 1) = " + fmt(ideal.p_self_1, 3) +
      " and an ideal capacity of " + fmt(ideal.capacity, 3) + ".";
  }
  return s;
}

// The Observer tab: the measured observable changes with beta, capacity does not.
export function observerText(lib, draft, ideal) {
  const { fmt } = lib;
  const diff = draft.intention_rad - draft.perspective_rad;
  let s = "At the draft settings phi \u2212 beta = " + deg(lib, diff) + ", so the display probe asks about the " +
    "equatorial direction at " + deg(lib, draft.perspective_rad) + " and the Demon forecasts P(Self = 1) = " +
    (ideal ? fmt(ideal.p_self_1, 3) : "n/a") + ".";
  s += " Ideal capacity cos(gamma) = " + fmt(Math.cos(draft.world_coupling * Math.PI / 2), 3) +
    " does not depend on the perspective: both capacity probes keep the readout at beta and only move phi.";
  return s;
}

// Fallback factual sentence when the engine returns none.
export function factualFallback(lib, run) {
  const { fmt, fmtPct, fmtInt } = lib;
  const s = run.settings || {};
  const m = run.metrics || {};
  const n = totalShots(run.counts && run.counts.display);
  return "With intention " + deg(lib, s.intention_rad) + ", World coupling " + fmt(s.world_coupling, 2) +
    " and perspective " + deg(lib, s.perspective_rad) + ", the display probe gave P(Self = 1) = " + fmt(m.p_self_1, 3) +
    " over " + fmtInt(n) + " shots; opposite intentions moved it from " + fmt(m.p_low, 3) + " to " + fmt(m.p_high, 3) +
    " (capacity " + fmt(m.capacity, 3) + "), openness " + fmt(m.openness_bits, 3) + " bits, connection " +
    fmt(m.connection_bits, 3) + " bits (" + fmtPct(m.p_self_1) + " of shots went to Future 1).";
}

export function chartSummary(lib, cur, prev, forecastFor) {
  const { fmtPct } = lib;
  if (!cur) {
    return forecastFor
      ? "No run yet. The outlined bars are the Demon's forecast for the draft: Future 0 " + fmtPct(1 - forecastFor.p_self_1) +
        ", Future 1 " + fmtPct(forecastFor.p_self_1) + "."
      : "No run yet.";
  }
  const p1 = num(cur.metrics, "p_self_1");
  const f1 = cur.prediction ? num(cur.prediction, "p_self_1") : null;
  let s = "Current run: Future 0 " + fmtPct(1 - p1) + ", Future 1 " + fmtPct(p1) + " (solid bars).";
  if (f1 !== null) s += " Demon forecast for the same settings: " + fmtPct(1 - f1) + " / " + fmtPct(f1) + " (outlined bars).";
  if (prev && prev.metrics) {
    const q1 = num(prev.metrics, "p_self_1");
    s += " Previous run: " + fmtPct(1 - q1) + " / " + fmtPct(q1) + " (hatched bars).";
  } else {
    s += " No previous run to compare with.";
  }
  return s;
}

export function curveSummary(lib, theory, noise) {
  const { fmt } = lib;
  if (!theory || !theory.w || !theory.w.length) return "The theoretical curves are unavailable.";
  const n = theory.w.length;
  const mid = Math.round((n - 1) / 2);
  let s = "Ideal capacity cos(gamma) falls from " + fmt(theory.capacity[0], 3) + " at w = " + fmt(theory.w[0], 2) +
    " through " + fmt(theory.capacity[mid], 3) + " at w = " + fmt(theory.w[mid], 2) + " to " + fmt(theory.capacity[n - 1], 3) +
    " at w = " + fmt(theory.w[n - 1], 2) + ". The band between P_low and P_high (the range opposite intentions can reach) " +
    "shrinks to nothing while the connection rises to " + fmt(theory.connection_bits ? theory.connection_bits[n - 1] : null, 2) +
    " bits. These are theoretical values from the equation, not experiment results.";
  if (noise && noise.capacity) {
    s += " Under the IonQ-like noise model the capacity is slightly lower; that curve is not drawn here, " +
      "it is tabulated under \"How far to trust the interval and the noise model\".";
  }
  return s;
}

// ---------------------------------------------------------------- plain words
// The friendly layer: what the page says on its first screen. Every number still
// comes from the API replies; only the wording is simpler. Technical sentences above
// stay in the drop-down panels.

// The guides' greetings before any run. PLACEHOLDERS: the team's own lines replace
// these (see the persona-lines guide); keep each under about 160 characters.
export const INTRO = {
  self: "Hi, I'm the Self. Set the dials and press Run, and I'll show you how far my choice can move the odds between my two possible futures.",
  demon: "I am Laplace's Demon. I never touch the dials, but I know the rules: I predict the odds before you run, then we check me against the sample.",
  observer: "I'm the Observer. I don't change the Self; I choose the question we ask it. Turn the point of view and run again to see the answer change.",
};

export function plainDeg(lib, rad) {
  return lib.fmtDeg(rad);
}

export function couplingWord(w) {
  if (w === null || w === undefined || !Number.isFinite(w)) return "unknown";
  if (w < 0.005) return "none";
  if (w < 0.25) return "light";
  if (w < 0.6) return "some";
  if (w < 0.995) return "strong";
  return "fully tied";
}

export function opennessWord(o) {
  if (o === null) return "Not measured.";
  if (o >= 0.9) return "Wide open: as unpredictable as a coin flip.";
  if (o >= 0.5) return "Leaning one way, but still open.";
  if (o >= 0.05) return "Mostly settled: one future is very likely.";
  return "Settled: the outcome is close to certain.";
}

export function connectionWord(i) {
  if (i === null) return "Not measured.";
  if (i < 0.05) return "The World knows almost nothing about which way the Self went.";
  if (i < 0.35) return "The World keeps a faint record of which way the Self went.";
  if (i < 0.75) return "The World keeps a clear record of which way the Self went.";
  return "The World knows almost exactly which way the Self went.";
}

// What each reading means, shown before the first run.
export const MEANING = {
  capacity: "How far opposite choices can push the odds of Future 1. 1 means all the way; 0 means not at all.",
  openness: "How unpredictable the next outcome is. 1 is a 50/50 coin flip; 0 is certain.",
  connection: "How much the World's record reveals about the Self. 1 is everything; 0 is nothing.",
};

export function plainBackend(info) {
  if (!info || info.error || !info.profile) return "this simulator";
  const p = info.profile;
  const family = p.family || "";
  if (family === "basic") return "the built-in simulator";
  if (family === "braket_local") return "the AWS Braket local simulator";
  if (family === "ibm_noise") return "an IBM noise-model simulator (" + (p.name || "IBM") + ")";
  if (family === "ionq_sim") return "IonQ's simulator" + (p.noise_model ? " (" + p.noise_model + " noise model)" : "");
  if (family === "ionq_qpu") return "IonQ hardware (" + (p.name || "QPU") + ")";
  return p.name || "this simulator";
}

export function runPolicy(info, oneJob) {
  const where = plainBackend(info);
  return oneJob
    ? "Runs on " + where + ": one job per visit, so the button locks after one press. Remote jobs take a few seconds."
    : "Runs on " + where + ", right in your browser: press Run as often as you like. Each press is one job of four tiny circuits.";
}

// The Self's tip: what the dials say now, in plain words.
export function selfTip(lib, d, ideal) {
  let s = "Your dials: choice " + plainDeg(lib, d.intention_rad) + ", ties to the world " + couplingWord(d.world_coupling) +
    ", point of view " + plainDeg(lib, d.perspective_rad) + ".";
  if (ideal) s += " Theory says your choice can swing the odds by up to " + lib.fmt(ideal.capacity, 2) + ".";
  return s;
}

// The Demon's line: its forecast for the current dials.
export function demonLine(lib, ideal) {
  if (!ideal) return "Working out the forecast\u2026";
  return "My forecast for your dials: Future 1 " + lib.fmtPct(ideal.p_self_1) + ", Future 0 " + lib.fmtPct(1 - ideal.p_self_1) +
    ". Opposite choices could swing that by up to " + lib.fmt(ideal.capacity, 2) + ".";
}

// The Observer's tip.
export function observerTip(lib, d, ideal) {
  return "Point of view " + plainDeg(lib, d.perspective_rad) + ". Changing it changes the answer (" +
    (ideal ? "Future 1 " + lib.fmtPct(ideal.p_self_1) : "Future 1 n/a") +
    "), but not how much your choice can swing the odds.";
}

// One status line after a run, in plain words, with the exact unresolved sentence.
export function doneSentence(lib, m, secs) {
  const { fmt, fmtPct } = lib;
  const ci = Array.isArray(m.capacity_ci95) ? m.capacity_ci95 : [null, null];
  let s = "Done in " + secs + " s. Future 1 " + fmtPct(m.p_self_1) + ", Future 0 " + fmtPct(1 - m.p_self_1) + ". ";
  if (m.resolved) {
    s += "Your choice can swing the odds by " + fmt(m.capacity, 2) + " (95% sure: " + fmt(ci[0], 2) + " to " + fmt(ci[1], 2) + ").";
  } else {
    s += "The swing is " + fmt(m.capacity, 2) + ", too small to tell apart from zero. " + NO_RESOLVED;
  }
  return s;
}

// Plain scene caption after a run.
export function sceneCaption(lib, run, prev, available) {
  const { fmt, fmtPct, fmtInt } = lib;
  const m = run.metrics || {};
  const n = totalShots(run.counts && run.counts.display);
  let s = (available ? "" : "The 3D view is unavailable here. ") + "Future 1 holds " + fmtPct(m.p_self_1) + " and Future 0 " +
    fmtPct(1 - m.p_self_1) + " of " + fmtInt(n) + " tries; the bigger sphere is the more likely future. The bridge to the World shows what it knows: " +
    fmt(m.connection_bits, 2) + " bits (" + bridgeWord(num(m, "connection_bits")) + ").";
  if (prev && prev.metrics) s += " The faint outline is your previous run.";
  return s + " The brain-like web is decoration, not qubits or neurons.";
}
