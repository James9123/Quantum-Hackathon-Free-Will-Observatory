// RPG-style dialogue box for the guides: an animated sprite portrait to the side (a
// labelled placeholder when no sprite exists), the speaker's name, a typewriter reveal
// with a soft synthesized blip per few characters, and click, Enter, Space or Escape (or
// the Skip button) to show the whole line at once.
//
// Portrait animation follows the page, never the other way round: the page says which
// action each line plays (design/persona-dialogue.md section 6). Frame timing comes from the
// sheet data (fps, optional per-frame ticks, optional play-once-then-hold). Under
// prefers-reduced-motion the portrait shows one still key frame and never advances.
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

// Sprite actions by guide: the Self idle | happy | angry (a droop that plays once and holds);
// the Demon idle | gesture | anger; the Observer idle | stare (a long still, then a glance) |
// dance. A missing sheet falls back to idle.
const MIN_FRAME_MS = 16;
const CHAR_MS = 25;                 // typewriter pace
const BLIP_S = 0.045;               // blip length
const JITTER = 0.04;                // +-4 % pitch

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
 * @param lib   the ./dom.js helpers
 * @param els   { box, portrait, portraitWho, name, text, skip, live, sound, soundHelp,
 *                sceneSkip, sceneHint (the opening cutscene's Skip intro button and hint) }
 * @param opts  { reducedMotion, setTimeoutFn, clearTimeoutFn, seed, audioContextClass,
 *                sprites: the SPRITES table from ./sprites.js (optional) }
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
  let speaker = null;          // who spoke last (a new speaker slides in)

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

  // ---------------------------------------------------------------- sprite portrait
  const sprites = opts.sprites || null;
  let spriteEl = null;
  let want = "idle";            // the action the page asked for
  const anim = { persona: null, action: null, frame: 0, step: 0, timer: null, size: 128 };

  function sheetFor(persona, action) {
    return (sprites && sprites[persona] && sprites[persona][action]) || null;
  }

  function actionFor(persona) {
    return sheetFor(persona, want) ? want : "idle";
  }

  function pickSize(sheet) {
    const sizes = Object.keys(sheet.src).map(Number).sort((a, b) => b - a);
    const w = els.portrait ? els.portrait.clientWidth || sizes[0] : sizes[0];
    for (const size of sizes) if (w >= size) return size;      // whole-number scales only
    return sizes[sizes.length - 1];
  }

  function frameOrder(sheet) {
    if (Array.isArray(sheet.play) && sheet.play.length) return sheet.play;
    const order = [];
    for (let i = 0; i < sheet.frames; i++) order.push(i);
    return order;
  }

  function drawFrame(sheet, index) {
    const size = anim.size;
    spriteEl.style.backgroundImage = 'url("' + sheet.src[String(size)] + '")';
    spriteEl.style.backgroundSize = (sheet.frames * size) + "px " + size + "px";
    spriteEl.style.backgroundPosition = (-index * size) + "px 0px";
    spriteEl.style.width = size + "px";
    spriteEl.style.height = size + "px";
    anim.frame = index;
  }

  function stopAnim() {
    if (anim.timer !== null) {
      clearTimeoutFn(anim.timer);
      anim.timer = null;
    }
  }

  function scheduleTick(sheet, index) {
    const ticks = Array.isArray(sheet.ticks) ? (sheet.ticks[index] || 1) : 1;
    anim.timer = setTimeoutFn(tickAnim, Math.max(MIN_FRAME_MS, Math.round(1000 * ticks / (sheet.fps || 8))));
  }

  function tickAnim() {
    anim.timer = null;
    const sheet = sheetFor(anim.persona, anim.action);
    if (!sheet || !spriteEl) return;
    const order = frameOrder(sheet);
    anim.step += 1;
    if (anim.step >= order.length) {
      if (!sheet.loop) {
        // play once, then hold (the Self's droop stays on its last frame until the page asks for another action)
        const hold = sheet.hold === null || sheet.hold === undefined ? order[order.length - 1] : sheet.hold;
        drawFrame(sheet, hold);
        return;
      }
      anim.step = 0;
    }
    const index = order[anim.step];
    drawFrame(sheet, index);
    scheduleTick(sheet, index);
  }

  function playAction(persona, action, restart) {
    const sheet = sheetFor(persona, action);
    if (!sheet || !spriteEl) return;
    if (!restart && anim.persona === persona && anim.action === action) return;
    stopAnim();
    anim.persona = persona;
    anim.action = action;
    anim.step = 0;
    anim.size = pickSize(sheet);
    const order = frameOrder(sheet);
    if (reduced) {
      const key = sheet.keyFrame === null || sheet.keyFrame === undefined ? order[0] : sheet.keyFrame;
      drawFrame(sheet, key);          // one still frame, no timers
      return;
    }
    drawFrame(sheet, order[0]);
    scheduleTick(sheet, order[0]);
  }

  function setPortrait(persona, name) {
    if (els.portraitWho) els.portraitWho.textContent = name;
    els.box.classList.remove("fwo-dialogue--self", "fwo-dialogue--demon", "fwo-dialogue--observer");
    els.box.classList.add("fwo-dialogue--" + (VOICES[persona] ? persona : "self"));
    if (!els.portrait) return;
    if (sheetFor(persona, "idle")) {
      if (!spriteEl) {
        spriteEl = lib.h("span", { class: "fwo-sprite" });
        els.portrait.appendChild(spriteEl);
      }
      els.portrait.classList.add("fwo-portrait--sprite");
      playAction(persona, actionFor(persona), false);
    } else {
      // no sheet for this guide: the labelled placeholder stays visible
      els.portrait.classList.remove("fwo-portrait--sprite");
      stopAnim();
      anim.persona = null;
      anim.action = null;
    }
  }

  /** An extra strip (the easter egg) on the shown guide's portrait: hold frame 1 for
   *  o.freezeMs, play to the last frame at the strip's fps, hold it o.endMs, then go back to
   *  the guide's own action. Reduced motion: the last frame as a still, then back. */
  function playOnce(persona, sheet, o) {
    if (!sheet || !spriteEl || anim.persona !== persona) return false;
    const opt = Object.assign({ freezeMs: 600, endMs: 700 }, o || {});
    stopAnim();
    anim.action = "extra";
    anim.size = pickSize(sheet);
    const back = () => {
      anim.timer = null;
      anim.action = null;
      playAction(persona, actionFor(persona), true);
    };
    if (reduced) {
      drawFrame(sheet, sheet.frames - 1);
      anim.timer = setTimeoutFn(back, 1500);
      return true;
    }
    let i = 0;
    drawFrame(sheet, 0);
    const tick = () => {
      i += 1;
      if (i >= sheet.frames) { anim.timer = setTimeoutFn(back, opt.endMs); return; }
      drawFrame(sheet, i);
      anim.timer = setTimeoutFn(tick, Math.max(MIN_FRAME_MS, Math.round(1000 / (sheet.fps || 5))));
    };
    anim.timer = setTimeoutFn(tick, opt.freezeMs);
    return true;
  }

  /** Change the shown guide's animation without retyping its line. */
  function setAction(action) {
    want = action || "idle";
    if (anim.persona && spriteEl) playAction(anim.persona, actionFor(anim.persona), false);
  }

  /** Re-pick the sheet size after a layout change (128 px on wide screens, 64 on phones). */
  function refresh() {
    const sheet = anim.persona ? sheetFor(anim.persona, anim.action) : null;
    if (!sheet || !spriteEl) return;
    const size = pickSize(sheet);
    if (size !== anim.size) {
      anim.size = size;
      drawFrame(sheet, anim.frame);
    }
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
    if (els.skip) els.skip.hidden = !!done || scene !== null;   // in the cutscene a press on the box does it
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

  /** Show `line` as spoken by `persona`, playing opts.action (default idle). Writes the live
   *  region once, unless opts.announce is false (nothing is announced on page load);
   *  opts.animate false shows the whole line at once. A change of speaker (or opts.slide)
   *  slides the new speaker in. */
  function show(persona, name, line, opts) {
    const o = Object.assign({ announce: true, animate: true, action: "idle", slide: false }, opts || {});
    stopTimer();
    pending = null;
    shows += 1;
    const text = String(line || "");
    if (o.announce) els.live.textContent = text ? name + ": " + text : "";
    els.box.hidden = false;
    const changed = speaker !== null && speaker !== persona;
    speaker = persona;
    if ((changed || o.slide) && !reduced) {
      els.box.classList.remove("fwo-dialogue--enter");
      void els.box.offsetWidth;             // restart the slide
      els.box.classList.add("fwo-dialogue--enter");
    }
    want = o.action || "idle";
    setPortrait(persona, name);
    els.name.textContent = name;
    if (reduced || !o.animate || !text.length) {
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

  // ---------------------------------------------------------------- the opening cutscene
  // A scripted exchange (design/persona-cutscene.md), one line per press: click, Enter or
  // Space completes the typing and a second press shows the next line; Escape or "Skip
  // intro" ends the scene. The page hears each line (onLine: it selects the speaker's tab)
  // and the end (onDone(skipped)). The first line is not announced (nothing speaks on page
  // load); every later line follows a press, so it is announced once like any other.
  let scene = null;           // { lines, i, onLine, onDone }

  function sceneLine() {
    const L = scene.lines[scene.i];
    if (scene.onLine) scene.onLine(L, scene.i);
    show(L.persona, L.name, L.line, { action: L.action, announce: scene.i > 0, slide: scene.i === 0 });
  }

  function play(lines, o) {
    if (!lines || !lines.length) return;
    scene = { lines, i: 0, onLine: o && o.onLine, onDone: o && o.onDone };
    els.box.classList.add("fwo-dialogue--scene");
    if (els.sceneSkip) els.sceneSkip.hidden = false;
    if (els.sceneHint) els.sceneHint.hidden = false;
    if (typeof document !== "undefined") document.addEventListener("keydown", onDocKey);
    sceneLine();
  }

  function advance() {
    if (!scene) return;
    if (pending) { finish(); return; }
    scene.i += 1;
    if (scene.i >= scene.lines.length) endScene(false);
    else sceneLine();
  }

  function endScene(skipped) {
    if (!scene) return;
    const done = scene.onDone;
    scene = null;
    stopTimer();
    pending = null;
    els.box.classList.remove("fwo-dialogue--scene");
    if (els.sceneSkip) els.sceneSkip.hidden = true;
    if (els.sceneHint) els.sceneHint.hidden = true;
    if (typeof document !== "undefined") document.removeEventListener("keydown", onDocKey);
    if (done) done(!!skipped);
  }

  // Keys while the scene plays and focus rests on the page itself, not in a control (the box
  // handles its own keys). Escape skips from anywhere.
  function onDocKey(ev) {
    if (!scene || els.box.contains(ev.target)) return;
    if (ev.key === "Escape") { endScene(true); return; }
    const t = ev.target;
    const free = !t || t === document.body || t === document.documentElement;
    if (!free || (ev.key !== "Enter" && ev.key !== " ")) return;
    ev.preventDefault();
    unlock();
    advance();
  }

  function onSkipEvent(ev) {
    if (ev.type === "keydown" && !["Enter", " ", "Escape"].includes(ev.key)) return;
    if (ev.type === "keydown") ev.preventDefault();
    if (scene) {
      if (ev.type === "keydown" && ev.key === "Escape") { endScene(true); return; }
      unlock();                 // a click or a key press is the gesture that allows the blips
      advance();
      return;
    }
    if (pending) finish();
  }
  els.box.addEventListener("click", onSkipEvent);
  els.box.addEventListener("keydown", onSkipEvent);
  if (els.skip) els.skip.addEventListener("click", (ev) => { ev.stopPropagation(); finish(); });
  if (els.sceneSkip) els.sceneSkip.addEventListener("click", (ev) => { ev.stopPropagation(); endScene(true); });

  return {
    unlock, show, clear, finish, setAction, refresh, play, playOnce,
    skipScene() { endScene(true); },
    get inScene() { return scene !== null; },
    get soundEnabled() { return soundOn && unlocked; },
    get typing() { return pending !== null; },
    get shows() { return shows; },
    get animation() { return { persona: anim.persona, action: anim.action, frame: anim.frame, size: anim.size, running: anim.timer !== null }; },
    get action() { return want; },
    setSound(on) { soundOn = !!on; if (els.sound && !els.sound.disabled) els.sound.checked = soundOn; },
  };
}
