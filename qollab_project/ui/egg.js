// The side panel's easter egg: the Self stands at the foot of the Style panel under a bucket of
// water, still on frame 1 of its angry strip (the pose before the splash; the dialogue box's own
// sheets are not used here). Press the bucket: it tips and pours, and when the water lands the
// Self holds frame 1 for a beat, plays on to frame 8, then rests on frame 1 again. Decoration
// only; it never touches the run, the readings or the dialogue. Timers run only during a pour and
// stop when the panel closes. Under prefers-reduced-motion the press shows the pouring bucket
// and the last angry frame as stills, then resets. No imports: main.js passes in EGGS.

const MIN_MS = 16;

export function createEggStage(els, data, opts) {
  const o = Object.assign({ reducedMotion: false, setTimeoutFn: setTimeout, clearTimeoutFn: clearTimeout,
    freezeMs: 500, landAt: 4, endMs: 700 }, opts || {});
  // called unbound: the browser's timer functions throw when called as a method of another object
  const setT = o.setTimeoutFn, clearT = o.clearTimeoutFn;
  const angry = data.angry, bucket = data.bucket;
  let selfTimer = null, bucketTimer = null, busy = false;

  function cellOf(sheet) {
    return sheet.cell || 128;
  }

  function srcOf(sheet) {
    return typeof sheet.src === "string" ? sheet.src : sheet.src[String(cellOf(sheet))];
  }

  function draw(el, sheet, i) {
    const size = cellOf(sheet);
    el.style.backgroundImage = 'url("' + srcOf(sheet) + '")';
    el.style.backgroundSize = (sheet.frames * size) + "px " + size + "px";
    el.style.backgroundPosition = (-i * size) + "px 0px";
    el.style.width = size + "px";
    el.style.height = size + "px";
  }

  function clearSelf() {
    if (selfTimer !== null) { clearT(selfTimer); selfTimer = null; }
  }

  function clearBucket() {
    if (bucketTimer !== null) { clearT(bucketTimer); bucketTimer = null; }
  }

  function frameMs(sheet, i) {
    const ticks = Array.isArray(sheet.ticks) ? (sheet.ticks[i] || 1) : 1;
    return Math.max(MIN_MS, Math.round((1000 * ticks) / (sheet.fps || 6)));
  }

  // the resting pose: frame 1 of the angry strip, before the splash
  function rest() {
    clearSelf();
    draw(els.self, angry, 0);
  }

  function playAngry() {
    clearSelf();
    draw(els.self, angry, 0);
    if (o.reducedMotion) {
      draw(els.self, angry, angry.frames - 1);
      return;
    }
    let i = 0;
    const tick = () => {
      i += 1;
      if (i >= angry.frames) {
        selfTimer = setT(() => { busy = false; rest(); }, o.endMs);
        return;
      }
      draw(els.self, angry, i);
      selfTimer = setT(tick, frameMs(angry, i));
    };
    selfTimer = setT(tick, o.freezeMs);
  }

  /** Press the bucket: it pours, and the Self reacts when the water lands. */
  function pour() {
    if (busy) return;
    busy = true;
    clearBucket();
    if (o.reducedMotion) {
      draw(els.bucket, bucket, o.landAt);
      playAngry();
      bucketTimer = setT(() => { draw(els.bucket, bucket, 0); rest(); busy = false; }, 1200);
      return;
    }
    let i = 0;
    draw(els.bucket, bucket, 0);
    const tick = () => {
      i += 1;
      if (i >= bucket.frames) { draw(els.bucket, bucket, 0); bucketTimer = null; return; }
      draw(els.bucket, bucket, i);
      if (i === o.landAt) playAngry();
      bucketTimer = setT(tick, frameMs(bucket, i));
    };
    bucketTimer = setT(tick, frameMs(bucket, 0));
  }

  /** The panel opened: the Self waits on its resting pose. */
  function start() {
    if (!busy) rest();
  }

  /** The panel closed: every timer stops, both rest on frame 1. */
  function stop() {
    busy = false;
    clearSelf();
    clearBucket();
    rest();
    draw(els.bucket, bucket, 0);
  }

  rest();
  draw(els.bucket, bucket, 0);
  els.button.addEventListener("click", pour);
  return { start, stop, pour, get busy() { return busy; } };
}
