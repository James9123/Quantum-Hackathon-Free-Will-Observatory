// RPG-style dialogue box for the persona line: a portrait emblem, the speaker's name, a
// typewriter reveal with a soft synthesized blip per few characters, and click, Enter,
// Space or Escape to show the whole line at once.
//
// Contract with the rest of the page:
// - The polite live region (#fwo-poetic) still receives the FULL line, once per show(),
//   exactly as before; the typewriter animates a separate copy that assistive tech ignores.
// - Nothing ever sounds before a user gesture: unlock() must be called from a click or key
//   handler (Run, the persona tabs, the sound checkbox) before any blip can play.
// - Under prefers-reduced-motion the reveal is instant and sound is off unless the visitor
//   ticks it on. The factual sentence is never animated or voiced.
// - No assets: the blips are WebAudio oscillators. Pitch jitter uses a seeded generator,
//   never the built-in random generator, so two visitors hear the same line the same way.

const VOICES = {
  self: { type: "triangle", hz: 440, gain: 0.14, every: 2 },
  demon: { type: "square", hz: 196, gain: 0.07, every: 3 },
  observer: { type: "sine", hz: 660, gain: 0.12, every: 2 },
};
const MASTER_GAIN = 0.125;          // about -18 dB
const CHAR_MS = 25;                 // typewriter pace
const BLIP_S = 0.045;               // blip length
const JITTER = 0.04;                // +-4 % pitch

// Emblems: lantern (the Self carries its own light), eye (the Demon sees the law),
// lens (the Observer chooses what to look through). Strokes use currentColor.
const EMBLEMS = {
  self: [
    ["path", { d: "M18 14h12l2 6v18a3 3 0 0 1-3 3H19a3 3 0 0 1-3-3V20z" }],
    ["path", { d: "M21 14v-4h6v4M16 30h16" }],
    ["path", { d: "M24 24c-2.5 2.2-2.5 5.3 0 7 2.5-1.7 2.5-4.8 0-7z", fill: "currentColor", stroke: "none" }],
  ],
  demon: [
    ["path", { d: "M6 24c5-8 11-12 18-12s13 4 18 12c-5 8-11 12-18 12S11 32 6 24z" }],
    ["circle", { cx: "24", cy: "24", r: "6" }],
    ["path", { d: "M24 18v6l4 2" }],
    ["path", { d: "M12 10l3 3M36 10l-3 3M24 6v4" }],
  ],
  observer: [
    ["circle", { cx: "21", cy: "21", r: "11" }],
    ["path", { d: "M29 29l11 11" }],
    ["path", { d: "M21 14v14M14 21h14" }],
    ["circle", { cx: "21", cy: "21", r: "3", fill: "currentColor", stroke: "none" }],
  ],
};

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * @param lib   the ./dom.js helpers (svg, clear)
 * @param els   { box, portrait, name, text, skip, live, sound, soundHelp }
 * @param opts  { reducedMotion, setTimeoutFn, clearTimeoutFn, seed, audioContextClass }
 */
export function createDialogue(lib, els, opts) {
  const reduced = !!opts.reducedMotion;
  const setTimeoutFn = opts.setTimeoutFn || setTimeout;
  const clearTimeoutFn = opts.clearTimeoutFn || clearTimeout;
  const AudioContextClass = opts.audioContextClass === undefined
    ? (typeof AudioContext === "function" ? AudioContext : null)
    : opts.audioContextClass;
  const rand = mulberry32(opts.seed || 20261011);

  let ctx = null;             // created in unlock(), inside a user gesture
  let master = null;
  let unlocked = false;
  let soundOn = !reduced && !!AudioContextClass;
  let timer = null;
  let pending = null;         // { line, i, persona } while a reveal is running
  let shows = 0;

  // The box takes over the visible rendering; the live region keeps its job for
  // assistive tech only.
  els.live.classList.add("fwo-sr");

  if (els.sound) {
    if (!AudioContextClass) {
      els.sound.checked = false;
      els.sound.disabled = true;
      soundOn = false;
      if (els.soundHelp) els.soundHelp.textContent = "This browser offers no audio synthesis, so the dialogue stays silent.";
    } else {
      els.sound.checked = soundOn;
      if (reduced && els.soundHelp) {
        els.soundHelp.textContent = "Off because your system asks for reduced motion; tick to hear the blips anyway. The numbers never make a sound.";
      }
      els.sound.addEventListener("change", () => {
        soundOn = els.sound.checked;
        if (soundOn) unlock();          // the tick itself is the gesture
      });
    }
  }

  function unlock() {
    if (!AudioContextClass || unlocked) return;
    try {
      ctx = new AudioContextClass();
      master = ctx.createGain();
      master.gain.value = MASTER_GAIN;
      master.connect(ctx.destination);
      if (ctx.state === "suspended" && typeof ctx.resume === "function") ctx.resume();
      unlocked = true;
    } catch (err) {
      ctx = null;
      unlocked = false;
    }
  }

  function blip(persona) {
    if (!soundOn || !unlocked || !ctx) return;
    const v = VOICES[persona] || VOICES.self;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const env = ctx.createGain();
      osc.type = v.type;
      osc.frequency.value = v.hz * (1 + (rand() * 2 - 1) * JITTER);
      env.gain.setValueAtTime(0.0001, now);
      env.gain.exponentialRampToValueAtTime(v.gain, now + 0.005);
      env.gain.exponentialRampToValueAtTime(0.0001, now + BLIP_S);
      osc.connect(env);
      env.connect(master);
      osc.start(now);
      osc.stop(now + BLIP_S + 0.01);
    } catch (err) {
      // audio is decoration; never let it break the page
    }
  }

  function setPortrait(persona) {
    lib.clear(els.portrait);
    const parts = EMBLEMS[persona] || EMBLEMS.self;
    for (const [tag, attrs] of parts) {
      els.portrait.appendChild(lib.svg(tag, Object.assign({
        fill: "none", stroke: "currentColor", "stroke-width": "2.2",
        "stroke-linecap": "round", "stroke-linejoin": "round",
      }, attrs)));
    }
    els.box.classList.remove("fwo-dialogue--self", "fwo-dialogue--demon", "fwo-dialogue--observer");
    els.box.classList.add("fwo-dialogue--" + (EMBLEMS[persona] ? persona : "self"));
  }

  function stopTimer() {
    if (timer !== null) {
      clearTimeoutFn(timer);
      timer = null;
    }
  }

  function setCue(done) {
    els.box.classList.toggle("fwo-dialogue--done", !!done);
    els.box.classList.toggle("fwo-dialogue--typing", !done);
    if (els.skip) els.skip.hidden = !!done;
  }

  function finish() {
    stopTimer();
    if (pending) {
      els.text.textContent = pending.line;
      pending = null;
    }
    setCue(true);
  }

  function step() {
    timer = null;
    if (!pending) return;
    const { line, persona } = pending;
    pending.i += 1;
    els.text.textContent = line.slice(0, pending.i);
    const ch = line[pending.i - 1];
    const v = VOICES[persona] || VOICES.self;
    if (ch && ch !== " " && pending.i % v.every === 0) blip(persona);
    if (pending.i >= line.length) {
      pending = null;
      setCue(true);
      return;
    }
    const pause = /[.!?;:]/.test(ch) ? CHAR_MS * 8 : (ch === "," ? CHAR_MS * 4 : CHAR_MS);
    timer = setTimeoutFn(step, pause);
  }

  /** Show `line` as spoken by `persona`; writes the live region once. */
  function show(persona, name, line) {
    stopTimer();
    pending = null;
    shows += 1;
    const text = String(line || "");
    els.live.textContent = text ? name + ": " + text : "";
    if (!text) {
      els.box.hidden = true;
      els.text.textContent = "";
      return;
    }
    els.box.hidden = false;
    setPortrait(persona);
    els.name.textContent = name;
    if (reduced || !text.length) {
      els.text.textContent = text;
      setCue(true);
      return;
    }
    els.text.textContent = "";
    pending = { line: text, i: 0, persona };
    setCue(false);
    timer = setTimeoutFn(step, CHAR_MS);
  }

  function clear() {
    stopTimer();
    pending = null;
    els.live.textContent = "";
    els.text.textContent = "";
    els.box.hidden = true;
  }

  function onSkipEvent(ev) {
    if (ev.type === "keydown" && !["Enter", " ", "Escape"].includes(ev.key)) return;
    if (ev.type === "keydown") ev.preventDefault();
    if (pending) finish();
  }
  els.box.addEventListener("click", onSkipEvent);
  els.box.addEventListener("keydown", onSkipEvent);
  if (els.skip) els.skip.addEventListener("click", (ev) => { ev.stopPropagation(); finish(); });

  return {
    unlock, show, clear, finish,
    get soundEnabled() { return soundOn && unlocked; },
    get typing() { return pending !== null; },
    get shows() { return shows; },
    setSound(on) { soundOn = !!on; if (els.sound && !els.sound.disabled) els.sound.checked = soundOn; },
  };
}
