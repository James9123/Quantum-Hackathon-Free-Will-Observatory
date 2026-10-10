// Noise dial: preset select + sliders -> noise_dial_json -> S, gauge, plain-language
// reading (aria-live), per-setting table. Debounced; only the newest answer is shown.
//
// Screen readers: each slider announces its own value (aria-valuetext). The reading
// is a polite live region, so it is written only once the dial has been still for
// SETTLE_MS; otherwise every arrow-key step would queue a long sentence. The number,
// the above/below badge and the gauge still update after the short COMPUTE_MS debounce.

const COMPUTE_MS = 120;
const SETTLE_MS = 900;

export function createDial(lib, exp, opts) {
  const { h, byId, replace, fmt, fmtPct, table, debounce } = lib;
  const { callDial, setTimeoutFn, onResult, onPresetChange, onError } = opts;
  const preset = byId("qh-preset");
  const sliders = {
    p2: { input: byId("qh-p2"), out: byId("qh-p2-out"), text: (v) => fmt(v, 3), say: (v) => "p2 = " + fmt(v, 3) },
    ro: { input: byId("qh-ro"), out: byId("qh-ro-out"), text: (v) => fmtPct(v, 1), say: (v) => fmtPct(v, 1) + " per bit" },
    scale: { input: byId("qh-scale"), out: byId("qh-scale-out"), text: (v) => fmt(v, 0) + "\u00d7", say: (v) => fmt(v, 0) + " times the published rates" },
  };
  const sValue = byId("qh-dial-s");
  const side = byId("qh-dial-side");
  const fill = byId("qh-gauge-fill");
  const reading = byId("qh-dial-reading");
  const rates = byId("qh-dial-rates");
  const note = byId("qh-preset-note");
  const tableSlot = byId("qh-dial-table");
  let seq = 0;
  let shown = 0;
  let last = null;
  // Newest text wins: a reading superseded within SETTLE_MS is never written.
  const write = (text) => { if (reading.textContent !== text) reading.textContent = text; };
  const settle = debounce(write, SETTLE_MS, setTimeoutFn);
  // now = true (first load, explicit refresh): write at once, and still supersede
  // any reading that is waiting to settle.
  const announce = (text, now) => { if (now) write(text); settle(text); };

  function values() {
    const out = {};
    for (const [k, s] of Object.entries(sliders)) out[k] = Number(s.input.value);
    return out;
  }

  function syncOutputs() {
    for (const s of Object.values(sliders)) {
      const v = Number(s.input.value);
      s.out.textContent = s.text(v);
      s.input.setAttribute("aria-valuetext", s.say(v));
    }
  }

  function syncFields() {
    const p = exp.presets[preset.value] || exp.presets.custom;
    const all = new Set(Object.values(exp.presets).flatMap((x) => x.fields));
    for (const id of all) byId(id).hidden = !p.fields.includes(id);
  }

  function render(data, now) {
    last = data;
    const above = !!data.exceeds;
    sValue.textContent = fmt(data.S);
    side.textContent = above ? "above the bound of 2" : "at or below the bound of 2";
    side.className = "qh-side " + (above ? "qh-side--above" : "qh-side--below");
    const frac = Math.max(0, Math.min(1, data.S / exp.gaugeMax));
    fill.style.width = (100 * frac).toFixed(2) + "%";
    fill.classList.toggle("qh-gauge-fill--below", !above);
    announce(data.reading || "", now);
    const e = (data.noise && data.noise.effective) || {};
    rates.textContent = "Effective rates: one-qubit depolarizing p1 = " + fmt(e.p1, 5) +
      ", two-qubit p2 = " + fmt(e.p2, 5) + ", readout flips " + fmtPct(e.r01, 2) + " (0\u21921) and " +
      fmtPct(e.r10, 2) + " (1\u21920)." + (data.elapsed_ms !== undefined ? " Computed in " + fmt(data.elapsed_ms, 1) + " ms." : "");
    note.hidden = !data.preset_note;
    note.textContent = data.preset_note || "";
    const cols = exp.outcomeColumns;
    replace(tableSlot, table(
      "Exact values under this noise setting. a = Alice's bit, b = Bob's bit; E = P(same) \u2212 P(different).",
      ["setting", "coef", "E"].concat(cols.map((c) => c.label)),
      (data.terms || []).map((t) => [exp.termName(t, data.settings_degrees), t.coef > 0 ? "+1" : "\u22121", fmt(t.E, 4)]
        .concat(cols.map((c) => fmt((t.dist || {})[c.key], 4))))));
    if (onResult) onResult(data);
  }

  async function compute(now = false) {
    const mine = ++seq;
    const params = exp.dialParams(preset.value, values());
    let data;
    try {
      data = await callDial(params);
    } catch (err) {
      data = { error: String(err && err.message ? err.message : err) };
    }
    if (mine < shown) return; // an answer to a newer request is already on screen
    shown = mine;
    if (!data || typeof data !== "object" || data.error) {
      const msg = data && data.error ? String(data.error) : "no answer";
      announce("The noise dial could not compute this setting: " + msg, now);
      if (onError) onError(msg);
      return;
    }
    render(data, now);
  }

  const schedule = debounce(compute, COMPUTE_MS, setTimeoutFn);

  for (const s of Object.values(sliders)) {
    s.input.addEventListener("input", () => { syncOutputs(); schedule(); });
  }
  preset.addEventListener("change", () => {
    syncFields();
    const p = exp.presets[preset.value];
    if (p && onPresetChange) onPresetChange(p.curve);
    schedule();
  });

  syncOutputs();
  syncFields();
  return {
    refresh: () => compute(true),
    current: () => last,
    preset: () => preset.value,
  };
}
