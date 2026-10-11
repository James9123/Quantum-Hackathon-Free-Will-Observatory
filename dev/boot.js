// Stub-mode boot: mimic how Qollab starts a JS project, then start main.js unchanged.
//   - globalThis.backend: a stand-in object (Qollab injects a PyProxy instead)
//   - main.js starts first; index.html is injected with innerHTML a little later,
//     so main.js's whenMounted() polling is exercised
// Query parameters: ?backend=basic|ionq|error|none  &mount=ms  &slow=N  &axe=1  &reduce=1  &nowebgl=1  &theme=a|b|c|d  &clean=1
// (none: no global `backend` at all, to exercise main.js's missing-backend path;
//  reduce=1 makes matchMedia report prefers-reduced-motion: reduce, so the no-animation
//  path can be checked in a browser that cannot emulate the preference;
//  nowebgl=1 makes every canvas refuse a WebGL context, so the text-only fallback runs)

const params = new URLSearchParams(location.search);
const kind = params.get("backend") || "basic";
const mountDelay = Number(params.get("mount") || 300);
const NAMES = {
  basic: "basic_simulator",
  ionq: "ionq_simulator (stand-in: local ideal simulator)",
  error: "basic_simulator (stand-in that fails)",
};
if (kind !== "none") globalThis.backend = { name: NAMES[kind] || NAMES.basic, stubKind: kind };

if (params.get("reduce") === "1") {
  const real = globalThis.matchMedia.bind(globalThis);
  globalThis.matchMedia = (q) => (/prefers-reduced-motion/.test(q)
    ? { matches: true, media: q, addEventListener() {}, removeEventListener() {} }
    : real(q));
}

if (params.get("nowebgl") === "1") {
  const realGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
    return /webgl/i.test(String(type)) ? null : realGetContext.call(this, type, ...rest);
  };
}

for (const a of document.querySelectorAll("[data-scenario]")) {
  if (a.dataset.scenario === kind) a.setAttribute("aria-current", "page");
}

// main.js never settles (it ends with `await new Promise(() => {})`), so do not await it.
import("../qollab_project/main.js").catch((err) => console.error("main.js failed: " + err));

// ?theme=a|b|c|d: one of the four design directions as a dev-only stylesheet (never uploaded),
// loaded BEFORE the page mounts so main.js reads the themed scene colours.
// ?clean=1 hides the stub banner and paints the page in the app's background (for screenshots).
const theme = params.get("theme");
if (theme && /^[abcd]$/.test(theme)) {
  await new Promise((resolve) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "./themes/theme-" + theme + ".css";
    link.onload = resolve;
    link.onerror = resolve;
    document.head.appendChild(link);
  });
}
const html = await (await fetch("../qollab_project/index.html", { cache: "no-store" })).text();
setTimeout(() => {
  document.getElementById("qollab-root").innerHTML = html;
  const app = document.getElementById("fwo-app");
  if (theme && /^[abcd]$/.test(theme)) app.dataset.theme = theme;
  if (params.get("clean") === "1") {
    const bar = document.querySelector(".stub-bar");
    if (bar) bar.hidden = true;
    document.body.style.background = getComputedStyle(app).backgroundColor;
  }
}, mountDelay);

if (params.get("axe") === "1") {
  // Dev only: axe-core from the one CDN Qollab allows. Never loaded by qollab_project/.
  const s = document.createElement("script");
  s.src = "https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js";
  s.onload = () => setTimeout(async () => {
    const res = await globalThis.axe.run(document.getElementById("fwo-app"));
    const lines = res.violations.map((v) => v.id + " (" + v.impact + "): " + v.help + " -- " +
      v.nodes.map((n) => n.target.join(" ")).join(" | "));
    const out = document.getElementById("axe-out");
    out.hidden = false;
    out.textContent = "axe-core " + globalThis.axe.version + ": " + res.violations.length + " violation(s), " +
      res.passes.length + " passing rules, " + res.incomplete.length + " needing review\n" + lines.join("\n");
    console.log(out.textContent);
  }, 3000);
  document.head.appendChild(s);
}

// ---------------------------------------------------------------- dev only: drive a state
// ?auto=<intention_deg>|<coupling>|<perspective_deg>   e.g. ?auto=90|0.5|45
// &persona=self|demon|observer   &how=1 (open the How-this-works drawer)   &norun=1 (sliders only)
// &prev=<intention_deg>|<coupling>|<perspective_deg>  run these settings first, so the scene shows a previous run
// Used for screenshots and demo rehearsal; sets <html data-fwo-auto="done"> when finished.
const auto = params.get("auto");
if (auto) {
  const [ideg, w, pdeg] = auto.split("|").map(Number);
  const persona = params.get("persona");
  const byId = (id) => document.getElementById(id);
  const setRange = (id, v) => {
    const el = byId(id);
    if (!el || !Number.isFinite(v)) return;
    el.value = String(v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const until = (pred, ms) => new Promise((resolve) => {
    const t0 = Date.now();
    const tick = () => (pred() ? resolve(true) : (Date.now() - t0 > ms ? resolve(false) : setTimeout(tick, 100)));
    tick();
  });
  (async () => {
    await until(() => byId("fwo-run") && !byId("fwo-run").disabled, 20000);
    const runAndWait = async () => {
      const before = (byId("fwo-factual") || {}).textContent || "";
      byId("fwo-run").click();
      await until(() => {
        const now = (byId("fwo-factual") || {}).textContent || "";
        return now.trim().length > 0 && now !== before;
      }, 30000);
    };
    const prev = params.get("prev");
    if (prev) {
      const [pi, pw, pp] = prev.split("|").map(Number);
      setRange("fwo-intention", pi);
      setRange("fwo-coupling", pw);
      setRange("fwo-perspective", pp);
      await runAndWait();
      await until(() => byId("fwo-run") && !byId("fwo-run").disabled, 20000);
    }
    setRange("fwo-intention", ideg);
    setRange("fwo-coupling", w);
    setRange("fwo-perspective", pdeg);
    if (persona && byId("fwo-tab-" + persona)) byId("fwo-tab-" + persona).click();
    if (params.get("norun") !== "1") await runAndWait();
    if (params.get("how") === "1" && byId("fwo-how")) byId("fwo-how").open = true;
    await new Promise((r) => setTimeout(r, 1400));   // let the 1 s result transition finish
    document.documentElement.dataset.fwoAuto = "done";
    console.log("auto: done");
  })();
}
