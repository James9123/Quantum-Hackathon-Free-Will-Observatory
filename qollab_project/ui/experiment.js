// Everything CHSH-specific that the generic UI components need, in one place.
// To swap in another experiment, replace this file (and ui_api.py); the components
// in badge.js, card.js, dial.js and chart.js read only what is described here.
//
// UI modules import nothing: main.js hands them the helpers from dom.js, so they
// behave the same under Qollab's CommonJS loader and as native modules in dev/.

const SQRT8 = 2 * Math.SQRT2;

export function makeExperiment(lib) {
  const { fmt, fmtInt } = lib;

  function termName(term, degrees) {
    const [a, b] = term.vars;
    const deg = (v) => (degrees && v in degrees ? " (" + fmt(degrees[v], 0) + "\u00b0)" : "");
    return a + deg(a) + " \u00b7 " + b + deg(b);
  }

  return {
    id: "chsh",
    symbol: "S",
    witness: "CHSH",
    bound: 2,
    ideal: SQRT8,
    boundLabel: "classical bound S = 2",
    idealLabel: "quantum ideal 2\u221a2 \u2248 2.828",
    gaugeMax: 3, // the gauge in index.html runs from 0 to 3 (ticks at 2 and 2.828)

    termName,

    // Outcome columns for the dial's probability table. Python keys are Qiskit's
    // "<Bob bit><Alice bit>"; the table shows (a, b) = (Alice, Bob).
    outcomeColumns: [
      { key: "00", label: "P(a=0, b=0)" },
      { key: "10", label: "P(a=0, b=1)" },
      { key: "01", label: "P(a=1, b=0)" },
      { key: "11", label: "P(a=1, b=1)" },
    ],

    // Dial presets: which slider fields each one shows (ids from index.html) and
    // which precomputed curve matches it.
    presets: {
      custom: { fields: ["qh-p2-field", "qh-ro-field"], curve: "p2" },
      ionq_forte_like: { fields: ["qh-scale-field"], curve: "ionq" },
      ionq_forte_like_spam: { fields: ["qh-scale-field"], curve: "ionq" },
    },

    // noise_dial_json params from the slider values.
    dialParams(preset, values) {
      if (preset === "custom") {
        return { preset, p1: 0, p2: values.p2, r01: values.ro, r10: values.ro, scale: 1 };
      }
      return { preset, scale: values.scale };
    },

    // Where the dial's current setting sits on a curve (null: not on that chart).
    dialPoint(curveKey, dial) {
      if (!dial || typeof dial.S !== "number") return null;
      const eff = (dial.noise && dial.noise.effective) || {};
      const offCurve = (eff.r01 || 0) > 0 || (eff.r10 || 0) > 0;
      const note = offCurve ? " (includes readout error, so it sits below the curve)" : "";
      if (curveKey === "p2" && dial.preset === "custom") {
        return { x: eff.p2 || 0, y: dial.S, label: "your dial setting" + note };
      }
      if (curveKey === "ionq" && dial.preset !== "custom") {
        return { x: dial.noise.scale, y: dial.S, label: "your dial setting" + note };
      }
      return null;
    },

    // Chart descriptions. `data` is the parsed curve_json() result.
    curves: {
      p2: {
        dataKey: "p2_curve",
        title: "Exact S versus two-qubit depolarizing strength p2",
        xLabel: "two-qubit depolarizing strength p2",
        xDigits: 3,
        marker(data) {
          const x = data.p2_curve.lambda_star;
          return x === null || x === undefined ? null
            : { x, y: 2, label: "\u03bb* = " + fmt(x, 4) + ", where S reaches 2" };
        },
        summary(data) {
          const c = data.p2_curve;
          const n = c.S.length;
          const theory = c.lambda_star_theory;
          return "Exact S falls in a straight line from " + fmt(c.S[0]) + " at p2 = " + fmt(c.x[0], 2) +
            " to " + fmt(c.S[n - 1]) + " at p2 = " + fmt(c.x[n - 1], 2) +
            ". It reaches the classical bound S = 2 at p2 = \u03bb* = " + fmt(c.lambda_star, 4) +
            (theory ? " (theory: 1 \u2212 1/\u221a2 = " + fmt(theory, 4) + ")" : "") +
            ". Below \u03bb* quantum theory predicts a value no local hidden-variable model reaches; above it, it does not.";
        },
        columns: ["p2", "S", "above 2?", "shots per setting for 3 se"],
        row(data, i) {
          const c = data.p2_curve;
          const s3 = c.shots_3sigma ? c.shots_3sigma[i] : null;
          return [fmt(c.x[i], 3), fmt(c.S[i], 4), c.S[i] > 2 ? "yes" : "no",
            s3 === null || s3 === undefined ? "n/a" : fmtInt(s3)];
        },
      },
      ionq: {
        dataKey: "ionq_like",
        title: "Exact S versus the IonQ-like noise scale",
        xLabel: "scale (multiple of IonQ's published Forte-1 simulator rates)",
        xDigits: 0,
        marker(data) {
          const x = data.ionq_like.crossing_scale;
          return x === null || x === undefined ? null
            : { x, y: 2, label: "S reaches 2 at scale \u2248 " + fmt(x, 1) };
        },
        summary(data) {
          const c = data.ionq_like;
          const n = c.S.length;
          const cross = c.crossing_scale;
          return "With IonQ's published Forte-1 simulator rates applied to this project's gates " +
            "(an approximation of IonQ's model), exact S is " + fmt(c.S_at_scale_1) + " at scale 1 and " +
            fmt(c.S[n - 1]) + " at scale " + fmt(c.x[n - 1], 0) + ". " +
            (cross === null || cross === undefined
              ? "S stays above the classical bound over the whole range."
              : "S stays above the classical bound until the rates are about " + fmt(cross, 1) + " times larger.");
        },
        columns: ["scale", "S", "above 2?"],
        row(data, i) {
          const c = data.ionq_like;
          return [fmt(c.x[i], 0) + "\u00d7", fmt(c.S[i], 4), c.S[i] > 2 ? "yes" : "no"];
        },
      },
    },
  };
}
